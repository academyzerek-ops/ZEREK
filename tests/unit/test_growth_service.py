"""Unit tests for growth_service (блок «А что дальше?»)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.growth_service import compute_growth_block  # noqa: E402


def test_growth_block_for_manicure_returns_data():
    """MANICURE YAML содержит growth_scenarios → блок не пустой."""
    block = compute_growth_block("MANICURE")
    assert block is not None
    assert isinstance(block, dict)
    assert "stagnation" in block
    assert "development" in block
    assert "growth_factors" in block
    # UX #3: finmodel_cta удалён (дублировался с block10).
    assert "finmodel_cta" not in block


def test_growth_block_for_other_niche_returns_none():
    """BARBER YAML не содержит growth_scenarios → None."""
    block = compute_growth_block("BARBER")
    assert block is None


def test_growth_block_for_unknown_niche_returns_none():
    """Несуществующая ниша → None (нет YAML файла)."""
    assert compute_growth_block("NONEXISTENT_XYZ") is None


def test_growth_block_has_both_scenarios():
    """Сценарии stagnation + development с непустыми label/description/outcome."""
    block = compute_growth_block("MANICURE")
    stag = block["stagnation"]
    dev = block["development"]
    assert stag["label"]
    assert stag["description"]
    assert stag["outcome"]
    assert dev["label"]
    assert dev["description"]
    assert dev["outcome_year2"]
    assert dev["outcome_year3"]


def test_growth_factors_count_at_least_3():
    """Минимум 3 фактора роста (универсальные + ниша-специфичные)."""
    block = compute_growth_block("MANICURE")
    factors = block["growth_factors"]
    assert len(factors) >= 3
    # каждый фактор имеет обязательные поля
    for f in factors:
        assert f["id"]
        assert f["title"]
        assert f["body"]
        assert isinstance(f["universal"], bool)


def test_growth_factors_manicure_contains_universal_and_niche_specific():
    """MANICURE имеет и универсальные, и ниша-специфичные факторы."""
    block = compute_growth_block("MANICURE")
    universals = [f for f in block["growth_factors"] if f["universal"]]
    specifics = [f for f in block["growth_factors"] if not f["universal"]]
    assert len(universals) >= 1
    assert len(specifics) >= 1


def test_finmodel_cta_removed_from_growth_block():
    """UX #3: CTA убран из growth_scenarios — дублировался с block10."""
    block = compute_growth_block("MANICURE")
    assert "finmodel_cta" not in block
