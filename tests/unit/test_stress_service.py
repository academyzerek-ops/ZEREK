"""Unit tests for api/services/stress_service.py — стресс-тест от зрелого режима."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.stress_service import compute_block8_stress_test  # noqa: E402


# MANICURE_HOME mature из спеки (Часть 4):
# revenue_mature = 472 500 ₸/мес
# materials = 56 700, tax = 14 175, fixed = 50 000
# profit_mature = 351 625 ₸/мес
MANICURE_HOME_RESULT = {
    "financials": {"cogs_pct": 0.12},
    "tax": {"rate_pct": 3},
    "scenarios": {"base": {"прибыль_год": 3_915_671, "выручка_год": 5_312_554}},
    "pnl_aggregates": {
        "mature": {
            "revenue_monthly": 472_500,
            "materials_monthly": 56_700,
            "profit_monthly": 351_625,
            "fixed_monthly": 50_000,
            "cogs_pct": 0.12,
            "tax_rate": 0.03,
        }
    },
}


def test_traffic_minus_20_manicure_home():
    """Трафик -20% MANICURE_HOME = -963 900 ₸/год (спека Часть 4 Шаг 8).

    Формула: revenue и materials падают на 20%, tax от новой выручки,
    fixed не меняется.
    """
    b8 = compute_block8_stress_test(MANICURE_HOME_RESULT)
    traffic_imp = next(s for s in b8["sensitivities"] if s["param"] == "Загрузка / трафик")
    assert traffic_imp["impact_annual"] == -963_900


def test_avg_check_minus_15_manicure_home():
    """Чек -15% MANICURE_HOME = -824 985 ₸/год.

    Формула: revenue падает, materials НЕ меняются (услуг столько же).
    """
    b8 = compute_block8_stress_test(MANICURE_HOME_RESULT)
    check_imp = next(s for s in b8["sensitivities"] if s["param"] == "Средний чек")
    assert check_imp["impact_annual"] == -824_985


def test_stress_independent_from_start_month():
    """Стресс-тест от зрелого режима → не зависит от start_month."""
    r1 = dict(MANICURE_HOME_RESULT)
    r1["input"] = {"start_month": 1}
    r2 = dict(MANICURE_HOME_RESULT)
    r2["input"] = {"start_month": 7}
    # pnl_aggregates.mature — тот же (не зависит от start_month)
    b8_1 = compute_block8_stress_test(r1)
    b8_2 = compute_block8_stress_test(r2)
    assert b8_1["sensitivities"] == b8_2["sensitivities"]


def test_critical_param_is_traffic_for_solo():
    """Для HOME/SOLO с низкими fixed трафик ударяет сильнее чека (−964 < −825)."""
    b8 = compute_block8_stress_test(MANICURE_HOME_RESULT)
    assert b8["critical_param"]["param"] == "Загрузка / трафик"


def test_death_points_removed():
    """death_points удалены в Этапе 8 (per Noa OQ-O)."""
    b8 = compute_block8_stress_test(MANICURE_HOME_RESULT)
    assert "death_points" not in b8
