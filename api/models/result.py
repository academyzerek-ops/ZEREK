"""api/models/result.py — TypedDict для финального API-ответа Quick Check.

QuickCheckResult — то что возвращает render_for_api(calc_result):
- Legacy block_1..block_12 (для PDF) — структура от render_report_v4
- Новый block1..block10 + block_season (overlay из calc_result)
- input, owner_economics, health (из render_report_v4)
- user_inputs (адаптивные поля v2)

Только типизация для IDE / документации.
"""
from typing import Any, Dict, List, Optional, TypedDict

from .block import (  # noqa: F401
    Block1Verdict,
    Block2Passport,
    Block3Market,
    Block4UnitEconomics,
    Block5PnL,
    Block6Capital,
    Block8Stress,
    Block9Risks,
    Block10Plan,
    BlockSeason,
)


# ═══════════════════════════════════════════════════════════════════════
# Legacy блоки (для PDF, render_report_v4)
# ═══════════════════════════════════════════════════════════════════════


class HealthIndicator(TypedDict):
    name: str
    status: str               # "green" | "yellow" | "red"
    value: str


class HealthBlock(TypedDict):
    title: str
    indicators: List[HealthIndicator]


class LegacyScenario(TypedDict):
    key: str                  # "pess" | "base" | "opt"
    label: str
    color: str
    traffic: int
    check: int
    revenue_year: int
    profit_monthly: int
    payback: str
    mkt_desc: str
    mkt_budget: str


# (Полная типизация всех 12 legacy-блоков пропущена — это огромный объём
#  PDF-структур, легче ссылаться на render_report_v4 как канон.)


# ═══════════════════════════════════════════════════════════════════════
# Главный ответ API
# ═══════════════════════════════════════════════════════════════════════


class QuickCheckResult(TypedDict, total=False):
    """Финальная структура {result: ...} в API-ответе /quick-check.

    После clean() оборачивается в {"status": "ok", "result": ...}.
    """
    # Эхо input + базовые секции (из render_report_v4):
    input: Dict[str, Any]
    owner_economics: Dict[str, Any]
    health: HealthBlock

    # Legacy block_1..block_12 (для PDF):
    block_1: Dict[str, Any]
    block_2: Dict[str, Any]
    block_3: Dict[str, Any]
    block_4: Dict[str, Any]
    block_5: Dict[str, Any]
    block_6: Dict[str, Any]
    block_7: Dict[str, Any]
    block_8: Dict[str, Any]
    block_9: Dict[str, Any]
    block_10: Dict[str, Any]
    block_11_season: Dict[str, Any]
    block_12_checklist: Dict[str, Any]

    # Новый формат block1..block10 (для UI Mini App):
    block1: Block1Verdict
    block2: Block2Passport
    block3: Block3Market
    block4: Block4UnitEconomics
    block5: Block5PnL
    block6: Block6Capital
    block_season: BlockSeason
    block8: Block8Stress
    block9: Block9Risks
    block10: Block10Plan

    # Адаптивные поля v2 (если были):
    user_inputs: Dict[str, Any]


__all__ = [
    "HealthIndicator",
    "HealthBlock",
    "LegacyScenario",
    "QuickCheckResult",
]
