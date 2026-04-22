"""Unit tests for api/services/scenario_service.py — 3 сценария."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.scenario_service import compute_3_scenarios  # noqa: E402


# Realistic MANICURE_HOME inputs
FIN = {
    "check_med": 5250,
    "traffic_med": 3,
    "cogs_pct": 0.12,
    "rent_med": 0,
    "marketing": 45_000,
    "loss_pct": 0,
    "s01": 1.0, "s02": 1.0, "s03": 1.0, "s04": 1.0,
    "s05": 1.0, "s06": 1.0, "s07": 1.0, "s08": 1.0,
    "s09": 1.0, "s10": 1.0, "s11": 1.0, "s12": 1.0,
    "rampup_months": 0,  # без ramp для простоты
    "rampup_start_pct": 1.0,
}
STAFF = {"fot_full_med": 0, "fot_net_med": 0}
CAPEX = 330_000
TAX_RATE = 0.03


def test_three_scenarios_returned():
    """compute_3_scenarios возвращает dict с ключами pess/base/opt."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    assert set(s.keys()) == {"pess", "base", "opt"}


def test_revenue_pess_less_than_base_less_than_opt():
    """Выручка: pess < base < opt."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    assert s["pess"]["выручка_год"] < s["base"]["выручка_год"] < s["opt"]["выручка_год"]


def test_profit_pess_less_than_base_less_than_opt():
    """Прибыль: pess < base < opt (при положительных значениях)."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    assert s["pess"]["прибыль_год"] < s["base"]["прибыль_год"] < s["opt"]["прибыль_год"]


def test_scenario_has_all_required_fields():
    """Каждый сценарий содержит: трафик_день, чек, выручка_год, прибыль_год,
    прибыль_среднемес, окупаемость."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    for label in ("pess", "base", "opt"):
        for key in ("трафик_день", "чек", "выручка_год", "прибыль_год",
                    "прибыль_среднемес", "окупаемость"):
            assert key in s[label], f"{label} missing {key}"


def test_base_scenario_uses_raw_check_and_traffic():
    """База не меняет чек и трафик (коэффициенты = 1.0, 1.0)."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    assert s["base"]["чек"] == FIN["check_med"]
    assert s["base"]["трафик_день"] == FIN["traffic_med"]


def test_pess_traffic_is_less_than_base():
    """Пессимист: traffic_k = 0.75 → трафик меньше базового."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    assert s["pess"]["трафик_день"] < s["base"]["трафик_день"]


def test_opt_check_is_greater_than_base():
    """Оптимист: check_k = 1.10 → чек выше базового."""
    s = compute_3_scenarios(FIN, STAFF, CAPEX, TAX_RATE)
    assert s["opt"]["чек"] > s["base"]["чек"]
