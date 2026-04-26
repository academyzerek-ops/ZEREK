"""Unit tests for api/services/verdict_service.py — Block 1 светофор."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.verdict_service import (  # noqa: E402
    _score_breakeven,
    _score_capital,
    _score_experience,
    _score_marketing,
    _score_roi,
)


def test_score_capital_surplus_returns_3():
    """R8 H.1: ratio ≥ 2.0 → 3 балла «комфортный запас на разгон»."""
    s = _score_capital(capital_own=1_000_000, capex_needed=500_000)
    assert s["score"] == 3


def test_score_capital_yellow_returns_2():
    """R8 H.1: 1.1 ≤ ratio < 2.0 → 2 балла «на запуск и часть разгона»."""
    s = _score_capital(capital_own=600_000, capex_needed=500_000)
    assert s["score"] == 2


def test_score_capital_match_returns_1():
    """R8 H.1: 0.9 ≤ ratio < 1.1 → 1 балл «хватает на запуск, на разгон — желательно добрать»."""
    s = _score_capital(capital_own=500_000, capex_needed=500_000)
    assert s["score"] == 1


def test_score_capital_deficit_returns_0():
    """Капитал < 0.75 → 0 баллов «критический дефицит»."""
    s = _score_capital(capital_own=300_000, capex_needed=1_000_000)
    assert s["score"] == 0


def test_score_capital_unspecified_returns_2():
    """capital_own=None → 2 балла «не указан, расчёт условный»."""
    s = _score_capital(capital_own=None, capex_needed=500_000)
    assert s["score"] == 2


def test_score_roi_solo_returns_3():
    """SOLO/HOME форматы → 3/3 без расчёта ROI."""
    s = _score_roi(profit_year=1_000_000, total_investment=500_000, is_solo=True)
    assert s["score"] == 3
    assert "сами" in s["note"]


def test_score_breakeven_fast_returns_3():
    """Окупаемость <= 6 мес → 3 балла."""
    s = _score_breakeven(2)
    assert s["score"] == 3
    assert s["months"] == 2


def test_score_breakeven_none_returns_0():
    """Не окупается → 0 баллов."""
    s = _score_breakeven(None)
    assert s["score"] == 0


def test_score_experience_levels():
    """experienced=3, some=2, none=0."""
    assert _score_experience("experienced")["score"] == 3
    assert _score_experience("some")["score"] == 2
    assert _score_experience("none")["score"] == 0


def test_score_marketing_express_full():
    """В Quick Check маркетинг = полный балл (2/2)."""
    s = _score_marketing("express")
    assert s["score"] == 2
    assert s["max"] == 2
