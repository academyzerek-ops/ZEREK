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
