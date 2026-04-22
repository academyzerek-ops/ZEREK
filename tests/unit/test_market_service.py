"""Unit tests for api/services/market_service.py — Block 3 рынок."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.market_service import compute_block3_market  # noqa: E402


def test_home_format_returns_note():
    """HOME-форматы получают специальную заметку вместо density-барчарта."""
    result = {
        "input": {"format_id": "MANICURE_HOME", "city_id": "astana"},
        "risks": {},
    }
    b3 = compute_block3_market(result)
    assert b3["type"] == "home_market_note"
    assert "Instagram" in b3["message"]


def test_standard_format_returns_saturation():
    """STANDARD — полная структура с saturation + competitors + affordability."""
    result = {
        "input": {
            "format_id": "BARBER_STANDARD",
            "city_id": "aktobe",
            "city_name": "Актобе",
            "city_population": 500_000,
        },
        "risks": {
            "competitors": {"competitors_count": 30, "density_per_10k": 0.6},
        },
    }
    b3 = compute_block3_market(result)
    assert "saturation" in b3
    assert "competitors_list" in b3
    assert "affordability" in b3
    assert b3["saturation"]["competitors_count"] == 30


def test_undersaturated_market_is_green():
    """saturation_pct <= 60 → зелёный цвет, «недонасыщен»."""
    result = {
        "input": {"format_id": "BARBER_STANDARD", "city_id": "aktobe", "city_population": 1_000_000},
        "risks": {"competitors": {"density_per_10k": 0.2}},
    }
    b3 = compute_block3_market(result)
    assert b3["saturation"]["color"] == "green"
    assert "недонасыщен" in b3["saturation"]["text_rus"]


def test_oversaturated_market_is_red():
    """saturation_pct > 150 → красный цвет, «перенасыщен»."""
    result = {
        "input": {"format_id": "BARBER_STANDARD", "city_id": "aktobe", "city_population": 100_000},
        "risks": {"competitors": {"density_per_10k": 2.0}},  # 0.75 bench → 266%
    }
    b3 = compute_block3_market(result)
    assert b3["saturation"]["color"] == "red"


def test_astana_high_check_coef_affordable():
    """Астана check_coef=1.05 → «на уровне / выше средней»."""
    result = {
        "input": {"format_id": "BARBER_STANDARD", "city_id": "astana", "city_population": 1_200_000},
        "risks": {"competitors": {"density_per_10k": 0.5}},
    }
    b3 = compute_block3_market(result)
    # city_coef = 1.05 → «на уровне средней по РК» (<1.15)
    assert "средней" in b3["affordability"]["text_rus"]
