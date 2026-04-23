"""Unit tests for staff_paradox_service."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.staff_paradox_service import compute_staff_paradox  # noqa: E402


def test_manicure_home_returns_short_block():
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_HOME",
        avg_check=6000, rent_monthly=0, city_id="astana",
    )
    assert result is not None
    assert result["applicable"] is True
    assert result["block_type"] == "short"
    assert result["capacity"]["max_clients_per_day"] == 7
    assert len(result["strategies"]) == 0
    assert result["hire_impossible_note"]
    assert result["warning"] is None


def test_manicure_solo_returns_medium_block():
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_SOLO",
        avg_check=6000, rent_monthly=80000, city_id="astana",
    )
    assert result["block_type"] == "medium"
    assert len(result["strategies"]) == 2
    ids = [s["id"] for s in result["strategies"]]
    assert "grow_to_standard" in ids
    assert "cross_niches_in_host" in ids
    assert result["hire_impossible_note"] is None
    assert result["warning"] is None


def test_manicure_standard_returns_full_block():
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_STANDARD",
        avg_check=6000, rent_monthly=200000, city_id="astana",
    )
    assert result["block_type"] == "full"
    assert len(result["strategies"]) == 4
    ids = [s["id"] for s in result["strategies"]]
    assert "sharing" in ids
    assert "cross_niches" in ids
    assert "teaching_model" in ids
    assert "mentorship_shift" in ids
    assert result["warning"]
    assert "найм на оклад" in result["warning"]["title"].lower()


def test_manicure_premium_returns_full_block():
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_PREMIUM",
        avg_check=8000, rent_monthly=350000, city_id="astana",
    )
    assert result["block_type"] == "full"
    assert len(result["strategies"]) == 4


def test_sharing_savings_equals_half_rent():
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_STANDARD",
        avg_check=6000, rent_monthly=200000, city_id="astana",
    )
    sharing = next(s for s in result["strategies"] if s["id"] == "sharing")
    assert sharing["savings"]["monthly"] == 100000
    assert sharing["savings"]["yearly"] == 1200000


def test_non_beauty_niche_returns_none():
    """CARGO — архетип A6 (Transactional) — блок не показывается."""
    assert compute_staff_paradox(
        niche_id="CARGO", format_id="CARGO_STANDARD",
        avg_check=15000, rent_monthly=150000, city_id="astana",
    ) is None


def test_coffee_returns_none():
    """COFFEE — A2 (Food impulse) — пока без блока."""
    assert compute_staff_paradox(
        niche_id="COFFEE", format_id="COFFEE_STANDARD",
        avg_check=1500, rent_monthly=300000, city_id="astana",
    ) is None


def test_capacity_calculation_manicure():
    """7 клиентов × 26 дней × 6000 ₸ = 1 092 000 ₸ пиковая выручка."""
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_HOME",
        avg_check=6000, rent_monthly=0, city_id="astana",
    )
    assert result["capacity"]["peak_monthly_revenue"] == 1_092_000


def test_massage_has_lower_capacity_than_manicure():
    """MASSAGE: 5/день vs MANICURE: 7/день."""
    manicure = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_HOME",
        avg_check=6000, rent_monthly=0, city_id="astana",
    )
    massage = compute_staff_paradox(
        niche_id="MASSAGE", format_id="MASSAGE_HOME",
        avg_check=6000, rent_monthly=0, city_id="astana",
    )
    assert massage["capacity"]["max_clients_per_day"] == 5
    assert manicure["capacity"]["max_clients_per_day"] == 7
    assert massage["capacity"]["peak_monthly_revenue"] < manicure["capacity"]["peak_monthly_revenue"]


def test_realistic_revenue_smaller_than_peak():
    """Реалистичная выручка (будни 60% + выходные 90%) < пик (100%)."""
    result = compute_staff_paradox(
        niche_id="MANICURE", format_id="MANICURE_HOME",
        avg_check=6000, rent_monthly=0, city_id="astana",
    )
    cap = result["capacity"]
    assert cap["realistic_monthly_revenue"] < cap["peak_monthly_revenue"]
    # Формула: (18 × 7 × 0.6 + 8 × 7 × 0.9) × 6000 = 126 × 6000 = 756 000
    assert cap["realistic_monthly_revenue"] == 756_000
