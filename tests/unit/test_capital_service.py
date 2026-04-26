"""Unit tests for capital_service (3-уровневая достаточность капитала)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.capital_service import compute_capital_adequacy  # noqa: E402


# Универсальные параметры MANICURE_HOME для 5 кейсов.
_BASE = dict(
    capex_total=480_000,
    marketing_monthly=45_000,
    other_opex_monthly=5_000,
    rent_monthly=0,
    rampup_months=3,
    worst_season_drawdown=50_000,  # seasonal_buffer = 100_000
)


def test_capital_above_safe_level_returns_safe_verdict():
    # safe = comfortable + max(drawdown × 2, comfortable × 30%).
    # comfortable = 480K + 215 025 = 695 025; buffer max(100K, 208K) = 208 507.
    # safe = 903 532. 1 000K > 903 532 → safe.
    r = compute_capital_adequacy(**_BASE, user_capital=1_000_000)
    assert r["verdict_level"] == "safe"
    assert r["verdict_color"] == "green"
    assert r["gap_amount"] == 0


def test_capital_between_comfortable_and_safe():
    r = compute_capital_adequacy(**_BASE, user_capital=700_000)
    assert r["verdict_level"] == "comfortable"
    assert r["verdict_color"] == "green"
    assert r["gap_to_level"] == "safe"
    assert r["gap_amount"] > 0


def test_capital_between_minimum_and_comfortable_returns_risky():
    # R12.5: verdict_color для risky = "amber" (5-зонная карта вместо
    # старой 3-цветной). См. capital_service compute_capital_adequacy.
    r = compute_capital_adequacy(**_BASE, user_capital=500_000)
    assert r["verdict_level"] == "risky"
    assert r["verdict_color"] == "amber"
    assert r["gap_to_level"] == "comfortable"
    assert r["gap_amount"] == 695_025 - 500_000


def test_capital_below_minimum_returns_insufficient():
    r = compute_capital_adequacy(**_BASE, user_capital=300_000)
    assert r["verdict_level"] == "insufficient"
    assert r["verdict_color"] == "red"
    assert r["gap_to_level"] == "minimum"
    assert r["gap_amount"] == 180_000  # 480 000 - 300 000


def test_capital_none_returns_unknown():
    r = compute_capital_adequacy(**_BASE, user_capital=None)
    assert r["verdict_level"] == "unknown"
    assert r["verdict_color"] == "gray"
    assert r["gap_amount"] == 0
    assert r["gap_to_level"] is None


def test_capital_zero_returns_unknown():
    """0 трактуется как «не указал» (аналогично None)."""
    r = compute_capital_adequacy(**_BASE, user_capital=0)
    assert r["verdict_level"] == "unknown"


def test_reserve_uses_ip_minimum_tax_not_mature_income():
    """MANICURE_HOME baseline: marketing 45K + opex 5K + ip_min 21 675 = 71 675/мес; × 3 = 215 025."""
    r = compute_capital_adequacy(
        capex_total=480_000,
        marketing_monthly=45_000,
        other_opex_monthly=5_000,
        rent_monthly=0,
        rampup_months=3,
        worst_season_drawdown=0,
        user_capital=500_000,
    )
    assert r["reserve_3_months"] == 215_025
    assert r["comfortable"] == 480_000 + 215_025
    assert r["minimum"] == 480_000


def test_reserve_breakdown_has_all_components():
    r = compute_capital_adequacy(**_BASE, user_capital=500_000)
    rb = r["reserve_breakdown"]
    assert rb["marketing_per_month"] == 45_000
    assert rb["other_opex_per_month"] == 5_000
    assert rb["ip_min_taxes_per_month"] == 21_675
    assert rb["rent_per_month"] == 0
    assert rb["total_per_month"] == 71_675
    assert rb["months"] == 3
    assert rb["total_for_period"] == 215_025


def test_safe_includes_seasonal_buffer():
    """safe = comfortable + max(drawdown × 2, 30% от comfortable)."""
    r = compute_capital_adequacy(**_BASE, user_capital=500_000)
    # comfortable = 480K + 215 025 = 695 025
    # drawdown × 2 = 100K, floor = 30% × 695 025 ≈ 208 507.
    # max выбирает floor → safe = 695 025 + 208 507 = 903 532.
    assert r["comfortable"] == 695_025
    assert r["seasonal_buffer"] == max(100_000, int(r["comfortable"] * 0.30))
    assert r["safe"] == r["comfortable"] + r["seasonal_buffer"]


def test_zero_worst_season_drawdown_uses_floor_buffer():
    """Даже если просадки нет — seasonal_buffer = max(0, 30% от comfortable)."""
    r = compute_capital_adequacy(
        capex_total=480_000,
        marketing_monthly=45_000,
        other_opex_monthly=5_000,
        rent_monthly=0,
        rampup_months=3,
        worst_season_drawdown=0,
        user_capital=500_000,
    )
    # Floor: 30% от comfortable = 30% × 695 025 ≈ 208 507.
    assert r["seasonal_buffer"] == int(r["comfortable"] * 0.30)
    assert r["safe"] > r["comfortable"], "safe должен быть СТРОГО больше comfortable"


def test_too_legal_form_sets_ip_taxes_to_zero():
    """Для ТОО ip_min_taxes=0 (расширим позже когда будет логика для ТОО)."""
    r = compute_capital_adequacy(
        capex_total=480_000,
        marketing_monthly=45_000,
        other_opex_monthly=5_000,
        rent_monthly=0,
        rampup_months=3,
        worst_season_drawdown=0,
        user_capital=500_000,
        legal_form="too",
    )
    rb = r["reserve_breakdown"]
    assert rb["ip_min_taxes_per_month"] == 0
    assert rb["total_per_month"] == 50_000  # 45K + 5K только
    assert r["reserve_3_months"] == 150_000


def test_rent_included_in_monthly_fixed():
    """Для STANDARD/PREMIUM с арендой — rent входит в monthly_fixed."""
    r = compute_capital_adequacy(
        capex_total=2_000_000,
        marketing_monthly=80_000,
        other_opex_monthly=15_000,
        rent_monthly=250_000,
        rampup_months=3,
        worst_season_drawdown=0,
        user_capital=2_500_000,
    )
    rb = r["reserve_breakdown"]
    assert rb["rent_per_month"] == 250_000
    # 80K + 15K + 21 675 (ИП мин) + 250K = 366 675
    assert rb["total_per_month"] == 366_675
    assert r["reserve_3_months"] == 366_675 * 3
