"""Unit tests for marketing_service (dynamic monthly budget)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.marketing_service import compute_marketing_plan  # noqa: E402


_CLIENTS_STABLE = [30] * 12
_CLIENTS_RAMP = [18, 30, 45, 55, 60, 60, 60, 60, 60, 60, 60, 60]


def test_manicure_astana_returns_a1_beauty():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_RAMP,
        experience="none", content_self_produced=True,
    )
    assert plan["archetype_id"] == "A1"
    assert plan["archetype_name"] == "Beauty & Personal Care"
    assert plan["base_cac"] == 1200
    assert plan["city_cac"] == int(1200 * 1.2)


def test_manicure_budget_decreases_over_year():
    """A1 Beauty: retention растёт → paid budget в м.12 << м.1."""
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_RAMP,
        experience="none", content_self_produced=True,
    )
    m = plan["monthly_plan"]
    assert m[0]["total_marketing"] > m[11]["total_marketing"] * 1.5


def test_cargo_budget_drops_less_than_manicure():
    """A6 transactional: retention слабее чем A1 Beauty → m1/m12 ratio ниже."""
    cargo = compute_marketing_plan(
        niche_id="CARGO", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    manicure = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    cargo_ratio = cargo["monthly_plan"][0]["total_marketing"] / max(cargo["monthly_plan"][11]["total_marketing"], 1)
    manicure_ratio = manicure["monthly_plan"][0]["total_marketing"] / max(manicure["monthly_plan"][11]["total_marketing"], 1)
    # CARGO ниже MANICURE — retention weaker, снижение меньше относительно.
    assert cargo_ratio < manicure_ratio, f"cargo={cargo_ratio:.2f} should be < manicure={manicure_ratio:.2f}"


def test_expert_has_lower_cac_than_novice():
    novice = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    expert = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="pro", content_self_produced=True,
    )
    assert expert["monthly_plan"][0]["paid_budget"] < novice["monthly_plan"][0]["paid_budget"]


def test_content_cost_zero_when_self_produced():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    assert plan["monthly_plan"][0]["content_cost"] == 0


def test_content_cost_nonzero_when_not_self_produced():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=False,
    )
    # Для A1 (MANICURE) контент = 15 000 / мес.
    assert plan["monthly_plan"][0]["content_cost"] == 15_000


def test_almaty_cac_higher_than_aktobe():
    plan_almaty = compute_marketing_plan(
        niche_id="MANICURE", city_id="almaty",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    plan_aktobe = compute_marketing_plan(
        niche_id="MANICURE", city_id="aktobe",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    assert plan_almaty["city_cac"] > plan_aktobe["city_cac"]


def test_food_delivery_has_platform_commission():
    """PIZZA (A3) → delivery platforms 25% commission."""
    plan = compute_marketing_plan(
        niche_id="PIZZA", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    assert plan["monthly_plan"][0]["platform_commission_rate_pct"] >= 20.0


def test_unknown_niche_returns_error():
    plan = compute_marketing_plan(
        niche_id="FAKE_NICHE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    assert "error" in plan
    assert plan["archetype_id"] is None


def test_summary_has_avg_and_total():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    s = plan["summary"]
    assert "avg_monthly_budget" in s
    assert "total_year_budget" in s
    assert "peak_month" in s
    assert s["total_year_budget"] == sum(m["total_marketing"] for m in plan["monthly_plan"])


def test_manicure_what_not_to_do_excludes_gis_google():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    msg = plan["what_not_to_do_ru"]
    # MANICURE paid: instagram 65, pabliki 15, bloggers 20, GIS 0 → должен быть в списке "не работает"
    assert "2GIS" in msg
    assert "Google" in msg or "Яндекс" in msg


def test_content_advice_for_visual_niche():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=False,
    )
    assert "визуал" in plan["content_advice_ru"].lower()


def test_pharmacy_content_advice_about_location():
    """PHARMACY (A7) — про локацию, не про визуал."""
    plan = compute_marketing_plan(
        niche_id="PHARMACY", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    msg = plan["content_advice_ru"].lower()
    assert "локац" in msg


def test_plan_length_is_12_months():
    plan = compute_marketing_plan(
        niche_id="MANICURE", city_id="astana",
        total_clients_per_month=_CLIENTS_STABLE,
        experience="none", content_self_produced=True,
    )
    assert len(plan["monthly_plan"]) == 12
