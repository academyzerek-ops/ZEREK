"""Integration tests for QuickCheckCalculator — full pipeline."""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from calculators.quick_check import QuickCheckCalculator  # noqa: E402
from engine import ZerekDB  # noqa: E402
from main import QCReq  # noqa: E402

DATA_DIR = os.path.join(_ROOT, "data", "kz")

# Грузим БД один раз — eager load всех 33 ниш × 14 листов (медленно).
_db = ZerekDB(data_dir=DATA_DIR)


def _make_req(**overrides):
    """QCReq с дефолтами Quick Check / валидным start_month."""
    defaults = {
        "city_id": "astana",
        "niche_id": "MANICURE",
        "format_id": "MANICURE_HOME",
        "cls": "Стандарт",
        "area_m2": 0,
        "loc_type": "home",
        "capital": 500_000,
        "qty": 1,
        "founder_works": False,
        "rent_override": None,
        "start_month": 5,
        "capex_level": "стандарт",
        "has_license": None,
        "staff_mode": None,
        "staff_count": None,
        "specific_answers": {"experience": "none", "entrepreneur_role": "owner_plus_master"},
    }
    defaults.update(overrides)
    return QCReq(**defaults)


def test_manicure_home_none_pipeline_runs():
    """Базовый прогон MANICURE_HOME / Астана / experience=none."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    # Финальная структура отчёта
    assert "block1" in report
    assert "block5" in report
    assert "block_season" in report
    assert "user_inputs" in report  # adaptive поля попали


def test_block1_color_for_manicure_home_none():
    """MANICURE_HOME / экспериенс none / капитал 500К → зелёный (по baseline 17/23)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    assert report["block1"]["color"] == "green"
    assert report["block1"]["score"] == 17


def test_block5_first_year_chart_present():
    """Block 5 содержит first_year_chart с 12 месяцами."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    chart = report["block5"]["first_year_chart"]
    assert len(chart["months"]) == 12
    assert chart["start_month"] == 5
    assert chart["start_month_label"] == "Май"


def test_block8_stress_traffic_for_manicure_home():
    """Стресс-тест трафик -20% MANICURE_HOME = -963 900 ₸/год (бит-в-бит спека)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    sens = report["block8"]["sensitivities"]
    traffic = next(s for s in sens if s["param"] == "Загрузка / трафик")
    assert traffic["impact_annual"] == -963_900


def test_home_solo_normalization_forces_owner_plus_master():
    """HOME-формат → calculator принудительно ставит entrepreneur_role=owner_plus_master."""
    req = _make_req(specific_answers={"experience": "none"})  # без entrepreneur_role
    calc = QuickCheckCalculator(_db)
    report = calc.run(req)
    # После normalize req.specific_answers должен иметь owner_plus_master
    assert req.specific_answers.get("entrepreneur_role") == "owner_plus_master"
    # И user_inputs в отчёте тоже отражает это
    assert report["user_inputs"]["specific_answers"]["entrepreneur_role"] == "owner_plus_master"


def test_invalid_start_month_raises_400():
    """start_month=None → HTTPException 400."""
    from fastapi import HTTPException
    req = _make_req()
    req.start_month = None
    calc = QuickCheckCalculator(_db)
    with pytest.raises(HTTPException) as exc:
        calc.run(req)
    assert exc.value.status_code == 400
    assert "start_month" in exc.value.detail


def test_pnl_aggregates_present_in_result_via_calculator():
    """R-1 закрыт: pnl_aggregates есть после calculator (не зависит от main.py)."""
    # Запускаем calculator напрямую и проверяем что блоки содержат данные
    # которые требуют pnl_aggregates.mature (block5, block8).
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    # Block 5 payback из compute_unified_payback_months использует mature
    assert report["block5"]["payback_months"] is not None
    # Block 8 sensitivities из mature — числа реалистичные (не нули)
    assert report["block8"]["sensitivities"][0]["impact_annual"] != 0


def test_barber_standard_aktobe_yellow():
    """BARBER_STANDARD / Актобе / 10М капитал → жёлтый по baseline."""
    req = _make_req(
        city_id="aktobe", niche_id="BARBER", format_id="BARBER_STANDARD",
        area_m2=60, loc_type="street", capital=10_000_000, start_month=4,
        specific_answers={"experience": "some", "entrepreneur_role": "owner_only"},
    )
    calc = QuickCheckCalculator(_db)
    report = calc.run(req)
    assert report["block1"]["color"] == "yellow"


# ═══════════════════════════════════════════════════════════════════════
# Этап 7 — YAML overlay для MANICURE_SOLO/STANDARD/PREMIUM
# Эти форматы раньше возвращали HTTP 400 (NaN в xlsx). Теперь работают.
# ═══════════════════════════════════════════════════════════════════════


def test_manicure_solo_works_after_yaml_overlay():
    """MANICURE_SOLO теперь работает (YAML заполняет NaN xlsx)."""
    req = _make_req(
        format_id="MANICURE_SOLO",
        area_m2=12, loc_type="tc", capital=2_000_000,
        specific_answers={"experience": "pro", "entrepreneur_role": "owner_plus_master"},
    )
    calc = QuickCheckCalculator(_db)
    report = calc.run(req)
    assert "block1" in report
    assert report["block1"]["color"] in ("green", "yellow", "red")
    # YAML дал check_med=7000 — выше чем HOME (5000)
    assert report["block5"]["scenarios"]["base"]["revenue"] > 0


def test_manicure_standard_works_after_yaml_overlay():
    """MANICURE_STANDARD теперь работает (YAML CAPEX 4.5M, marketing 175K)."""
    req = _make_req(
        format_id="MANICURE_STANDARD",
        area_m2=35, loc_type="tc", capital=5_000_000,
        specific_answers={"experience": "experienced", "entrepreneur_role": "owner_only"},
    )
    calc = QuickCheckCalculator(_db)
    report = calc.run(req)
    assert "block1" in report
    # CAPEX из YAML = 4.5M (vs xlsx 600K)
    assert report["block6"]["capex_needed"] >= 4_000_000


def test_manicure_premium_works_after_yaml_overlay():
    """MANICURE_PREMIUM теперь работает (YAML CAPEX 9.5M)."""
    req = _make_req(
        format_id="MANICURE_PREMIUM",
        area_m2=60, loc_type="tc", capital=10_000_000,
        specific_answers={"experience": "experienced", "entrepreneur_role": "owner_only"},
    )
    calc = QuickCheckCalculator(_db)
    report = calc.run(req)
    assert "block1" in report
    # PREMIUM формат → ОУР ТОО налоговый режим
    assert report["block5"] is not None


def test_manicure_home_unchanged_after_yaml_overlay():
    """MANICURE_HOME baseline остаётся бит-в-бит (YAML НЕ применяется)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())  # default = MANICURE_HOME experience=none
    # Те же значения что в baseline (Этап 0):
    assert report["block1"]["color"] == "green"
    assert report["block1"]["score"] == 17
    # Stress traffic -20% = -963 900 ₸/год (бит-в-бит спека)
    sens = report["block8"]["sensitivities"]
    traffic = next(s for s in sens if s["param"] == "Загрузка / трафик")
    assert traffic["impact_annual"] == -963_900


def test_manicure_home_response_has_growth_scenarios():
    """Блок «А что дальше?» подмешивается для MANICURE (из growth_scenarios YAML)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    gs = report.get("growth_scenarios")
    assert gs is not None, "growth_scenarios должен быть в ответе для MANICURE"
    assert gs["stagnation"]["label"]
    assert gs["development"]["outcome_year3"]
    assert len(gs["growth_factors"]) >= 3
    assert gs["finmodel_cta"]["price"] == 9000


def test_manicure_home_has_marketing_plan():
    """Блок marketing_plan подмешивается для MANICURE (архетип A1)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    mp = report.get("marketing_plan")
    assert mp is not None
    assert mp["archetype_id"] == "A1"
    assert mp["archetype_name"] == "Beauty & Personal Care"
    assert mp["city_cac"] > 0
    assert len(mp["monthly_plan"]) == 12
    assert "summary" in mp
    assert mp["summary"]["total_year_budget"] > 0


def test_marketing_plan_respects_content_self_produced():
    """content_self_produced=False → content_cost > 0 в каждом месяце."""
    calc = QuickCheckCalculator(_db)
    req_self = _make_req(specific_answers={
        "experience": "none", "entrepreneur_role": "owner_plus_master",
        "content_self_produced": True,
    })
    req_hire = _make_req(specific_answers={
        "experience": "none", "entrepreneur_role": "owner_plus_master",
        "content_self_produced": False,
    })
    total_self = calc.run(req_self)["marketing_plan"]["summary"]["total_year_budget"]
    total_hire = calc.run(req_hire)["marketing_plan"]["summary"]["total_year_budget"]
    # При наёмном контенте общий бюджет выше (15 000 × 12 = 180 000 для A1).
    assert total_hire > total_self
    assert total_hire - total_self == 15_000 * 12


def test_manicure_home_has_danger_zone():
    """MANICURE_HOME всегда получает поле danger_zone (даже если has_risk=False)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    dz = report.get("danger_zone")
    assert dz is not None
    # Обязательные поля
    assert "worst_month" in dz
    assert "max_drawdown" in dz
    assert "break_even_month" in dz
    assert "loss_months" in dz
    assert "has_cashflow_risk" in dz
    # Для MANICURE_HOME маржа высокая → убытков нет
    assert dz["has_cashflow_risk"] is False
    assert dz["loss_months"] == []


def test_manicure_home_danger_zone_feeds_into_capital_seasonal_buffer():
    """worst_month.profit из danger_zone попадает в capital_adequacy.seasonal_buffer."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    dz = report["danger_zone"]
    ca = report["capital_adequacy"]
    worst_profit = int(dz["worst_month"]["profit"])
    expected_buffer = abs(worst_profit) * 2 if worst_profit < 0 else 0
    assert ca["seasonal_buffer"] == expected_buffer
    # safe = comfortable + seasonal_buffer
    assert ca["safe"] == ca["comfortable"] + ca["seasonal_buffer"]


def test_manicure_home_500k_capital_returns_risky():
    """Капитал 500К на MANICURE_HOME — level=risky (хватает на CAPEX 480К, но не на разгон)."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())  # default capital=500_000
    ca = report.get("capital_adequacy")
    assert ca is not None
    assert ca["verdict_level"] == "risky"
    assert ca["verdict_color"] == "yellow"
    assert ca["gap_to_level"] == "comfortable"
    assert ca["minimum"] == 480_000
    assert ca["comfortable"] == 695_025  # 480K + 215 025 резерв


def test_manicure_home_900k_capital_returns_safe():
    """Капитал 900К > safe (без сезонного буфера = comfortable) → safe."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req(capital=900_000))
    ca = report["capital_adequacy"]
    assert ca["verdict_level"] == "safe"
    assert ca["gap_amount"] == 0


def test_manicure_home_capital_adequacy_block_structure():
    """Блок capital_adequacy содержит 3 уровня + reserve_breakdown + вердикт."""
    calc = QuickCheckCalculator(_db)
    report = calc.run(_make_req())
    ca = report["capital_adequacy"]
    assert set(["minimum", "comfortable", "safe", "reserve_breakdown",
                "verdict_level", "verdict_color", "verdict_label",
                "verdict_message", "gap_amount", "user_capital"]).issubset(ca.keys())
    rb = ca["reserve_breakdown"]
    assert rb["ip_min_taxes_per_month"] == 21_675  # из YAML
    assert rb["total_for_period"] == rb["total_per_month"] * rb["months"]


def test_barber_response_has_no_growth_scenarios():
    """У BARBER нет growth_scenarios в YAML → ключ отсутствует в ответе."""
    calc = QuickCheckCalculator(_db)
    req = _make_req(
        city_id="aktobe", niche_id="BARBER", format_id="BARBER_STANDARD",
        area_m2=60, loc_type="street", capital=10_000_000, start_month=4,
        specific_answers={"experience": "some", "entrepreneur_role": "owner_only"},
    )
    report = calc.run(req)
    assert "growth_scenarios" not in report
