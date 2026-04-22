"""Unit tests for api/services/action_plan_service.py — Block 10 план."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.action_plan_service import (  # noqa: E402
    _final_farewell,
    _green_action_plan,
    _upsell_block,
    _yellow_conditions,
)


def test_experience_none_includes_training():
    """experience=none + training_required=True → план начинается с обучения."""
    block2 = {"finance": {"capex_needed": 500_000}, "format_type": "HOME"}
    block1 = {"color": "green"}
    result = {"input": {"niche_id": "MANICURE", "training_required": True}}
    plan = _green_action_plan(block2, block1,
                              adaptive={"experience": "none"},
                              result=result)
    titles = [b["title"] for b in plan]
    assert "Обучение и практика" in titles
    # Обучение первое
    assert plan[0]["title"] == "Обучение и практика"


def test_experience_pro_no_training():
    """experience=pro → нет блока обучения."""
    block2 = {"finance": {"capex_needed": 500_000}, "format_type": "HOME"}
    block1 = {"color": "green"}
    result = {"input": {"niche_id": "MANICURE", "training_required": True}}
    plan = _green_action_plan(block2, block1,
                              adaptive={"experience": "pro"},
                              result=result)
    titles = [b["title"] for b in plan]
    assert "Обучение и практика" not in titles


def test_no_training_required_skips_training_even_for_none():
    """Если ниша не требует training_required — обучение не добавляется."""
    block2 = {"finance": {"capex_needed": 500_000}, "format_type": "STANDARD"}
    block1 = {"color": "green"}
    result = {"input": {"niche_id": "COFFEE", "training_required": False}}
    plan = _green_action_plan(block2, block1,
                              adaptive={"experience": "none"},
                              result=result)
    titles = [b["title"] for b in plan]
    assert "Обучение и практика" not in titles


def test_yellow_conditions_returns_max_3():
    """_yellow_conditions возвращает не более 3 условий."""
    block1 = {"scoring": {"weakest": [
        {"label": "Капитал vs ориентир"},
        {"label": "Точка безубыточности"},
        {"label": "Маркетинговый бюджет"},
        {"label": "Опыт предпринимателя"},  # 4-й, должен отсечься
    ]}}
    block2 = {"finance": {"capital_diff": -500_000, "capex_needed": 1_000_000}}
    out = _yellow_conditions(block1, block2)
    assert len(out) <= 3


def test_upsell_has_finmodel_and_bizplan():
    """_upsell_block возвращает finmodel + bizplan."""
    out = _upsell_block("green", {}, {"niche_name_rus": "Маникюр"})
    assert "finmodel" in out
    assert "bizplan" in out
    assert out["finmodel"]["price_kzt"] == 9000
    assert out["bizplan"]["price_kzt"] == 15000


def test_farewell_color_specific():
    """Напутствие зависит от цвета вердикта."""
    block2 = {"niche_name_rus": "Маникюр"}
    green = _final_farewell("green", block2)
    yellow = _final_farewell("yellow", block2)
    red = _final_farewell("red", block2)
    assert green != yellow
    assert yellow != red
    assert "окупиться" in green.lower()
    assert "переход" in yellow.lower() or "пересчитайте" in yellow.lower()
