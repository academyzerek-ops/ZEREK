"""api/models/calc_result.py — TypedDict для CalcResult (выход QuickCheckCalculator).

CalcResult — «сырой» результат расчёта от QuickCheckCalculator.run().
Не содержит legacy block_1..block_12 (это добавляет renderer).

Только типизация для IDE / документации.
"""
from typing import Any, Dict, List, Optional, TypedDict


class CalcInput(TypedDict, total=False):
    """Эхо параметров входа + резолвенные мета-поля."""
    city_id: str
    city_name: str
    city_population: int
    niche_id: str
    format_id: str
    format_name: str
    cls: str
    class_: str  # alias
    area_m2: float
    loc_type: str
    capital: int
    qty: int
    founder_works: bool
    start_month: int
    capex_standard: int
    masters_canon: int
    seats_mult: float
    training_required: bool


class CompetitorsData(TypedDict, total=False):
    уровень: int
    сигнал: str
    кол_во: Any
    competitors_count: int
    density_per_10k: float
    лидеры: str


class CalcMarket(TypedDict, total=False):
    population: int
    competitors: CompetitorsData
    target_audience: str
    competition_1_5: int
    utp: str


class CapexBreakdown(TypedDict, total=False):
    equipment: int
    renovation: int
    furniture: int
    first_stock: int
    permits_sez: int
    working_cap: int
    marketing: int
    deposit: int
    legal: int


class InvestmentRange(TypedDict):
    min: int
    max: int
    note: str


class CalcCapex(TypedDict, total=False):
    capex_min: int
    capex_med: int
    capex_max: int
    deposit: int
    total: int
    capital: int
    gap: int
    signal: str
    reserve_months: float
    breakdown: CapexBreakdown
    investment_range: InvestmentRange


class CalcStaff(TypedDict, total=False):
    positions: str
    headcount: int
    founder_role: str
    fot_net_med: int
    fot_full_med: int
    schedule: str


class CalcFinancials(TypedDict, total=False):
    check_med: int
    traffic_med: int
    cogs_pct: float
    margin_pct: float
    rent_month: int
    opex_med: int
    marketing: int
    marketing_min: int
    marketing_med: int
    marketing_max: int
    other_opex_min: int
    other_opex_med: int
    other_opex_max: int
    sez_month: int
    revenue_year1: int
    profit_year1: int
    tax_rate_pct: float
    rampup_months: int
    rampup_start_pct: float
    # s01..s12: сезонность (динамические ключи)


class ScenarioData(TypedDict, total=False):
    трафик_день: int
    чек: int
    выручка_год: int
    прибыль_год: int
    прибыль_среднемес: int
    окупаемость: Dict[str, Any]


class CalcScenarios(TypedDict):
    pess: ScenarioData
    base: ScenarioData
    opt: ScenarioData


class MaturePnl(TypedDict):
    revenue_monthly: int
    materials_monthly: int
    tax_monthly: int
    fixed_monthly: int
    profit_monthly: int
    revenue_yearly: int
    profit_yearly: int
    fot_monthly: int
    rent_monthly: int
    marketing_monthly: int
    other_opex_monthly: int
    cogs_pct: float
    tax_rate: float


class YearlyAvgPnl(TypedDict):
    revenue_yearly: int
    profit_yearly: int
    profit_monthly: int


class PnlAggregates(TypedDict):
    """Шаги 3-5 спеки: зрелый + средний год."""
    mature: MaturePnl
    yearly_avg: YearlyAvgPnl
    is_home: bool


class CalcTax(TypedDict):
    regime: str
    simplified_ok: str
    b2b: str
    nds_risk: str
    rate_pct: float


class UserInputs(TypedDict, total=False):
    """Адаптивные поля v2."""
    has_license: str
    staff_mode: str
    staff_count: int
    specific_answers: Dict[str, Any]


class CalcResult(TypedDict, total=False):
    """Полный raw результат QuickCheckCalculator.run().

    Содержит:
    - Базовые секции от engine.run_quick_check_v3 (input/market/capex/...)
    - pnl_aggregates (Шаги 3-5)
    - block1..block10, block_season (overlay от calculator)
    - user_inputs (адаптивные поля v2)

    Renderer (render_for_api) добавит legacy block_1..block_12 поверх.
    """
    # Базовые секции от engine.run_quick_check_v3:
    input: CalcInput
    market: CalcMarket
    capex: CalcCapex
    staff: CalcStaff
    financials: CalcFinancials
    scenarios: CalcScenarios
    breakeven: Dict[str, Any]
    payback: Dict[str, Any]
    owner_economics: Dict[str, Any]
    tax: CalcTax
    verdict: Dict[str, Any]   # legacy verdict (overwritten by block1)
    alternatives: List[str]
    risks: Dict[str, Any]
    products: List[Dict[str, Any]]
    insights: List[Dict[str, Any]]
    marketing: List[Dict[str, Any]]
    cashflow: List[Dict[str, Any]]
    # Этап 3 спеки:
    pnl_aggregates: PnlAggregates
    # Overlay блоков (Этап 4):
    block1: Dict[str, Any]    # Block1Verdict
    block2: Dict[str, Any]    # Block2Passport
    block3: Dict[str, Any]    # Block3Market
    block4: Dict[str, Any]    # Block4UnitEconomics
    block5: Dict[str, Any]    # Block5PnL + first_year_chart
    block6: Dict[str, Any]    # Block6Capital
    block_season: Dict[str, Any]  # BlockSeason
    block8: Dict[str, Any]    # Block8Stress
    block9: Dict[str, Any]    # Block9Risks
    block10: Dict[str, Any]   # Block10Plan
    user_inputs: UserInputs


__all__ = [
    "CalcInput",
    "CalcMarket",
    "CalcCapex",
    "CalcStaff",
    "CalcFinancials",
    "CalcScenarios",
    "PnlAggregates",
    "MaturePnl",
    "YearlyAvgPnl",
    "CalcTax",
    "UserInputs",
    "CalcResult",
]
