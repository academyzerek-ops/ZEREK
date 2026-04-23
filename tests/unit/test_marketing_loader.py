"""Unit tests for marketing_loader (YAML + CAC tables)."""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from loaders import marketing_loader as m  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    m.clear_cache()
    yield


def test_load_yaml_has_16_archetypes():
    assert len(m.get_all_archetypes()) == 16


def test_load_yaml_has_55_niches():
    niches = m._load().get("niches", {})
    assert len(niches) == 55


def test_archetype_a1_is_beauty():
    a1 = m.get_archetype("A1")
    assert a1 is not None
    assert a1["name_ru"] == "Beauty & Personal Care"
    assert a1["formula_type"] == "ramp_up_with_retention"


def test_manicure_maps_to_a1():
    assert m.get_niche_archetype("MANICURE") == "A1"
    assert m.get_niche_archetype("manicure") == "A1"  # case-insensitive


def test_unknown_niche_returns_none():
    assert m.get_niche_archetype("FAKE_NICHE_XYZ") is None
    assert m.get_niche_marketing("FAKE_NICHE_XYZ") is None
    assert m.get_retention_metrics("FAKE_NICHE_XYZ") is None


def test_manicure_has_full_retention_metrics():
    r = m.get_retention_metrics("MANICURE")
    assert r is not None
    assert set(r.keys()) >= {"ncs_m1", "ncs_m6", "ncs_m12", "r30", "rc12"}
    assert r["ncs_m1"] == 95
    assert r["ncs_m12"] == 30


def test_manicure_choice_drivers_visual_trust_top():
    cd = m.get_choice_drivers("MANICURE")
    assert cd["visual"] == 5
    assert cd["trust"] == 5
    assert cd["top_driver"] == "Visual+Trust"


def test_manicure_paid_allocation_sums_to_100():
    ch = m.get_channels_allocation("MANICURE")
    paid = ch["paid_budget_allocation"]
    total = sum(paid.values())
    assert total == 100, f"paid allocation sum != 100: {total}"


def test_pizza_has_platform_commission():
    ch = m.get_channels_allocation("PIZZA")
    assert ch["platform_commission_pct"]["delivery"] == 25


def test_cargo_has_platform_dependency_high():
    dep = m.get_platform_dependency("CARGO")
    assert dep is not None
    assert dep["risk_level"] == "HIGH"
    assert "OLX" in dep["main_platforms"]


def test_base_cac_manicure_1200():
    assert m.get_base_cac("MANICURE") == 1200


def test_base_cac_unknown_returns_default():
    assert m.get_base_cac("UNKNOWN") == m.DEFAULT_CAC_FALLBACK


def test_city_cac_multiplier_almaty_higher_than_aktobe():
    assert m.get_city_cac_multiplier("almaty") > m.get_city_cac_multiplier("aktobe")


def test_city_cac_multiplier_unknown_returns_default():
    assert m.get_city_cac_multiplier("unknown") == m.DEFAULT_CITY_CAC_MULTIPLIER


def test_real_cac_manicure_astana_1440():
    """CAC * city_multiplier = 1200 * 1.2 = 1440."""
    assert m.get_real_cac("MANICURE", "astana") == 1200 * 1.2


def test_niche_has_marketing_data_flag():
    assert m.niche_has_marketing_data("MANICURE") is True
    assert m.niche_has_marketing_data("FAKE") is False


def test_cache_is_used():
    """Повторные вызовы read-YAML функций → 1 miss + hits (lru_cache)."""
    m.clear_cache()
    _ = m.get_niche_archetype("MANICURE")
    _ = m.get_niche_archetype("BARBER")
    _ = m.get_all_archetypes()
    info = m._load.cache_info()
    assert info.misses == 1, f"ожидается 1 miss, got {info}"
    assert info.hits >= 2, f"ожидается ≥2 hits, got {info}"
