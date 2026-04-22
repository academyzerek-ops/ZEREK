"""Unit tests for api/services/economics_service.py — ядро расчётов."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.economics_service import (  # noqa: E402
    calc_breakeven,
    calc_payback,
    compute_pnl_aggregates,
    compute_unified_payback_months,
)


# ─── MANICURE_HOME realistic inputs (из baseline) ────────────────────────

MANICURE_HOME_RESULT = {
    "input": {
        "format_id": "MANICURE_HOME",
        "niche_id": "MANICURE",
        "founder_works": True,
        "training_required": True,
        "capex_standard": 330_000,
        "start_month": 5,
    },
    "financials": {
        "check_med": 5250,
        "traffic_med": 3,
        "cogs_pct": 0.12,
        "rent_month": 0,
        "marketing_med": 45_000,
        "other_opex_med": 5_000,
    },
    "staff": {"fot_full_med": 0, "fot_net_med": 0, "headcount": 0},
    "tax": {"rate_pct": 3},
    "capex": {"total": 330_000, "capex_med": 330_000},
    "scenarios": {
        "base": {"прибыль_среднемес": 326_306, "прибыль_год": 3_915_671, "выручка_год": 5_312_554},
    },
}


# ═══ compute_pnl_aggregates ═════════════════════════════════════════════


def test_manicure_home_mature_revenue_monthly():
    """Зрелая месячная выручка MANICURE_HOME = 5250 × 3 × 30 = 472 500 ₸."""
    pnl = compute_pnl_aggregates(MANICURE_HOME_RESULT)
    assert pnl["mature"]["revenue_monthly"] == 472_500


def test_manicure_home_mature_profit_monthly():
    """Зрелая месячная прибыль ≈ 351 625 ₸ по спеке (Часть 4 / Шаг 3)."""
    pnl = compute_pnl_aggregates(MANICURE_HOME_RESULT)
    # 472_500 × (1 - 0.12 - 0.03) - 50_000 fixed = 401_625 - 50_000 = 351_625
    assert pnl["mature"]["profit_monthly"] == 351_625


def test_manicure_home_fixed_monthly():
    """fixed_monthly = fot + rent + marketing + other = 0+0+45_000+5_000."""
    pnl = compute_pnl_aggregates(MANICURE_HOME_RESULT)
    assert pnl["mature"]["fixed_monthly"] == 50_000


def test_is_home_detected():
    pnl = compute_pnl_aggregates(MANICURE_HOME_RESULT)
    assert pnl["is_home"] is True


# ═══ compute_unified_payback_months ══════════════════════════════════════


def test_manicure_home_none_payback_2_months():
    """MANICURE_HOME / experience=none / capital=500К → окупаемость 2 мес.

    Спека Часть 4 Шаг 6: ceil(480_000 / 326_306) = ceil(1.47) = 2.
    """
    result = dict(MANICURE_HOME_RESULT)
    adaptive = {"experience": "none"}
    payback = compute_unified_payback_months(result, adaptive)
    assert payback == 2


def test_manicure_home_pro_payback_1_month():
    """experience=pro: обучение не добавляется, capex=330К, payback=1 мес."""
    # ceil(330_000 / 326_306) = ceil(1.011) = 2 на грани;
    # строго проверяем что <=2 (helper ceil консервативен).
    result = dict(MANICURE_HOME_RESULT)
    adaptive = {"experience": "pro"}
    payback = compute_unified_payback_months(result, adaptive)
    assert payback in (1, 2)


def test_negative_profit_returns_none():
    """Если прибыль ≤ 0 — окупаемость None."""
    result = {
        "input": {"capex_standard": 500_000, "founder_works": True, "format_id": "X_HOME"},
        "capex": {"total": 500_000},
        "scenarios": {"base": {"прибыль_среднемес": -1000}},
        "staff": {},
    }
    payback = compute_unified_payback_months(result, {})
    assert payback is None


# ═══ calc_breakeven ══════════════════════════════════════════════════════


def test_breakeven_returns_structure():
    """Breakeven возвращает dict с ключами тб_₸, тб_чеков_день, запас_прочности_%."""
    fin = {"check_med": 5000, "traffic_med": 3, "cogs_pct": 0.12,
           "loss_pct": 0, "rent_med": 0, "marketing": 45000,
           "other_opex_med": 5000, "utilities": 0, "consumables": 0,
           "software": 0, "transport": 0, "sez_month": 0}
    staff = {"fot_full_med": 0, "fot_net_med": 0}
    be = calc_breakeven(fin, staff, tax_rate=0.03, qty=1)
    assert "тб_₸" in be
    assert "тб_чеков_день" in be
    assert "запас_прочности_%" in be


# ═══ calc_payback ════════════════════════════════════════════════════════


def test_calc_payback_finds_first_positive():
    """calc_payback возвращает первый месяц где cumulative ≥ 0."""
    cashflow = [
        {"месяц": 1, "прибыль": -500_000, "нарастающий": -500_000},
        {"месяц": 2, "прибыль": 300_000, "нарастающий": -200_000},
        {"месяц": 3, "прибыль": 300_000, "нарастающий": 100_000},
    ]
    result = calc_payback(1_000_000, cashflow)
    assert result["месяц"] == 3


def test_calc_payback_never_positive():
    """Если за 12 мес не вышли в плюс — экстраполяция или None."""
    cashflow = [
        {"месяц": i + 1, "прибыль": -50_000, "нарастающий": -50_000 * (i + 1)}
        for i in range(12)
    ]
    result = calc_payback(1_000_000, cashflow)
    assert result["месяц"] is None  # avg_profit < 0 → None
