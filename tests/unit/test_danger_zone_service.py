"""Unit tests for danger_zone_service (зона риска: разгон + сезонность)."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.danger_zone_service import compute_danger_zone, get_wisdom_note_ru  # noqa: E402


def test_finds_worst_month():
    cashflow = [
        {"month_index": 1, "calendar_label": "Май", "revenue": 150000,
         "total_costs": 100000, "profit": 50000, "is_rampup": True},
        {"month_index": 2, "calendar_label": "Июнь", "revenue": 120000,
         "total_costs": 100000, "profit": 20000, "is_rampup": True},
        {"month_index": 3, "calendar_label": "Июль", "revenue": 80000,
         "total_costs": 100000, "profit": -20000, "is_rampup": True},
    ]
    result = compute_danger_zone(cashflow, capex_total=300000)
    assert result["worst_month"]["label"] == "Июль"
    assert result["worst_month"]["profit"] == -20000
    assert result["worst_month"]["month_index"] == 3


def test_max_drawdown_from_capex():
    cashflow = [
        {"month_index": 1, "profit": -50000, "calendar_label": "Май"},
        {"month_index": 2, "profit": -30000, "calendar_label": "Июнь"},
        {"month_index": 3, "profit": 100000, "calendar_label": "Июль"},
    ]
    result = compute_danger_zone(cashflow, capex_total=300000)
    # -300000 - 50000 - 30000 = -380000 max drawdown
    assert result["max_drawdown"] == 380000
    assert result["max_drawdown_month"] == 2


def test_break_even_month():
    cashflow = [
        {"month_index": 1, "profit": -100000, "calendar_label": "Май"},
        {"month_index": 2, "profit": 150000, "calendar_label": "Июнь"},
        {"month_index": 3, "profit": 200000, "calendar_label": "Июль"},
    ]
    result = compute_danger_zone(cashflow, capex_total=150000)
    # -150000 → -250000 → -100000 → +100000 (break-even на 3-м месяце)
    assert result["break_even_month"] == 3


def test_no_break_even_when_still_negative_after_12_months():
    """Если весь год в минусе — break_even_month=None."""
    cashflow = [
        {"month_index": i, "profit": -10000, "calendar_label": f"мес{i}"}
        for i in range(1, 13)
    ]
    result = compute_danger_zone(cashflow, capex_total=100000)
    assert result["break_even_month"] is None


def test_loss_months_detected():
    cashflow = [
        {"month_index": 1, "profit": -50000, "calendar_label": "Май", "is_rampup": True},
        {"month_index": 2, "profit": 10000, "calendar_label": "Июнь", "is_rampup": True},
        {"month_index": 8, "profit": -20000, "calendar_label": "Декабрь", "is_rampup": False},
    ]
    result = compute_danger_zone(cashflow, capex_total=300000)
    assert len(result["loss_months"]) == 2
    assert result["has_cashflow_risk"] is True
    # Убыточные месяцы идут в порядке cashflow (not sorted by loss size).
    assert result["loss_months"][0]["label"] == "Май"
    assert result["loss_months"][0]["is_rampup"] is True
    assert result["loss_months"][1]["label"] == "Декабрь"
    assert result["loss_months"][1]["is_rampup"] is False


def test_no_loss_months_flag():
    """12 прибыльных месяцев → has_cashflow_risk=False, loss_months=[]."""
    cashflow = [
        {"month_index": i, "profit": 50000, "calendar_label": "мес"}
        for i in range(1, 13)
    ]
    result = compute_danger_zone(cashflow, capex_total=100000)
    assert result["has_cashflow_risk"] is False
    assert len(result["loss_months"]) == 0


def test_empty_cashflow_returns_none():
    assert compute_danger_zone([], capex_total=300000) is None
    assert compute_danger_zone(None, capex_total=300000) is None


def test_advice_reserve_equals_max_drawdown():
    cashflow = [
        {"month_index": 1, "profit": -50000, "calendar_label": "Май"},
    ]
    result = compute_danger_zone(cashflow, capex_total=200000)
    # cumulative: -200K → -250K; max_drawdown=250000
    assert result["advice_reserve"] == result["max_drawdown"] == 250000


def test_all_profitable_still_has_drawdown_from_capex():
    """Даже при 12 прибыльных месяцах max_drawdown = CAPEX (до первого plus-a)."""
    cashflow = [
        {"month_index": i, "profit": 10000, "calendar_label": "мес"}
        for i in range(1, 13)
    ]
    result = compute_danger_zone(cashflow, capex_total=500000)
    # Never recovers to 0 in 12 months (10K × 12 = 120K vs 500K CAPEX).
    assert result["max_drawdown"] >= 500000
    assert result["has_cashflow_risk"] is False


def test_wisdom_note_returns_text():
    note = get_wisdom_note_ru()
    assert isinstance(note, str)
    assert "кассовый разрыв" in note
