"""api/models — TypedDict схемы для документации структур данных.

Только типизация для IDE / Sphinx, никаких runtime-проверок (Pydantic
для этого использовать не нужно — внутренние data structures).

Pydantic-модели — только для входов API в api/validators/.
"""
from .block import (
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
from .calc_result import (
    CalcCapex,
    CalcFinancials,
    CalcInput,
    CalcMarket,
    CalcResult,
    CalcScenarios,
    CalcStaff,
    CalcTax,
    MaturePnl,
    PnlAggregates,
    UserInputs,
    YearlyAvgPnl,
)
from .result import HealthBlock, HealthIndicator, QuickCheckResult

__all__ = [
    # Calc-side
    "CalcInput", "CalcMarket", "CalcCapex", "CalcStaff", "CalcFinancials",
    "CalcScenarios", "PnlAggregates", "MaturePnl", "YearlyAvgPnl",
    "CalcTax", "UserInputs", "CalcResult",
    # Block-side
    "Block1Verdict", "Block2Passport", "Block3Market", "Block4UnitEconomics",
    "Block5PnL", "Block6Capital", "BlockSeason", "Block8Stress",
    "Block9Risks", "Block10Plan",
    # API result
    "HealthIndicator", "HealthBlock", "QuickCheckResult",
]
