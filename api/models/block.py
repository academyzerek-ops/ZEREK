"""api/models/block.py — TypedDict для каждого блока Quick Check отчёта.

Только типизация для IDE / документации. Никаких runtime-проверок
(Pydantic-схемы для блоков пока не нужны — они «внутренние», не
пересекают границу API).
"""
from typing import Any, Dict, List, Optional, TypedDict


# ═══════════════════════════════════════════════════════════════════════
# Block 1 — Светофор (вердикт)
# ═══════════════════════════════════════════════════════════════════════


class ScoringItem(TypedDict, total=False):
    """Один из 8 пунктов скоринга."""
    score: int               # 0..3
    max: int                 # обычно 3, для marketing = 2
    label: str               # «Капитал vs ориентир» и т.п.
    note: str                # пояснение
    # Дополнительные поля для конкретных пунктов:
    ratio: float
    gap_kzt: int
    months: int
    density: float
    roi: float
    roi_raw: float


class Block1Verdict(TypedDict):
    """Block 1 — Вердикт светофор."""
    color: str               # "green" | "yellow" | "red"
    score: int
    max_score: int
    verdict_statement: str
    strengths: List[str]
    risks: List[str]
    scoring: Dict[str, Any]  # {"items": [...], "strongest": [...], "weakest": [...]}


# ═══════════════════════════════════════════════════════════════════════
# Block 2 — Паспорт бизнеса
# ═══════════════════════════════════════════════════════════════════════


class StaffPosition(TypedDict):
    role: str
    count: int


class StaffGroups(TypedDict):
    masters: List[StaffPosition]
    assistants: List[StaffPosition]
    total: int


class EntrepreneurRole(TypedDict):
    id: str
    label_rus: str
    description_rus: str


class Block2Finance(TypedDict):
    capital_own: Optional[int]
    capex_needed: int
    capital_diff: Optional[int]
    capital_diff_status: str    # "not_specified" | "match" | "surplus" | "deficit" | "critical_deficit"


class Block2Passport(TypedDict):
    niche_id: str
    niche_name_rus: str
    niche_icon: str
    format_id: str
    format_name_rus: str
    class_level_rus: str
    area_m2: int
    area_visible: bool
    location_rus: str
    format_type: str            # "HOME" | "SOLO" | "STANDARD" | "PREMIUM" | ...
    is_solo: bool
    typical_staff: StaffGroups
    staff_after_entrepreneur: StaffGroups
    entrepreneur_role: EntrepreneurRole
    finance: Block2Finance
    payroll_type_rus: str
    experience_rus: str


# ═══════════════════════════════════════════════════════════════════════
# Block 3 — Рынок и конкуренты
# ═══════════════════════════════════════════════════════════════════════


class Saturation(TypedDict):
    competitors_count: int
    density_city: float
    density_benchmark: float
    pct_of_benchmark: int
    color: str               # "green" | "yellow" | "orange" | "red"
    text_rus: str


class Affordability(TypedDict):
    city_coef: float
    text_rus: str


class Block3Market(TypedDict, total=False):
    """Block 3 — рынок. Для HOME-формата — упрощённая структура."""
    # HOME-формат: type + message
    type: str                 # "home_market_note"
    message: str
    # Полная структура (STANDARD/PREMIUM):
    city: str
    saturation: Saturation
    competitors_list: List[Dict[str, Any]]
    affordability: Affordability


# ═══════════════════════════════════════════════════════════════════════
# Block 4 — Юнит-экономика
# ═══════════════════════════════════════════════════════════════════════


class BreakdownItem(TypedDict):
    label: str
    amount: int
    pct: int


class Block4Metrics(TypedDict, total=False):
    avg_check: int
    checks_per_day: int
    load_pct: int
    work_days: int
    gross_revenue_per_unit: int
    breakeven_value: int
    breakeven_label: str
    planned_value: int
    planned_label: str
    safety_margin: float
    min_load_pct: int
    checks_per_day_note: str
    max_checks_per_day: int


class Block4UnitEconomics(TypedDict):
    archetype: str
    unit_label: str
    avg_check: int
    breakdown: List[BreakdownItem]
    metrics: Block4Metrics


# ═══════════════════════════════════════════════════════════════════════
# Block 5 — P&L и first-year chart
# ═══════════════════════════════════════════════════════════════════════


class PnlScenario(TypedDict):
    revenue: int
    cogs: int
    fot: int
    rent: int
    marketing: int
    other_opex: int
    tax: int
    net_profit: int


class PnlScenarios(TypedDict):
    pess: PnlScenario
    base: PnlScenario
    opt: PnlScenario


class PnlMargins(TypedDict):
    gross: float
    operating: float
    net: float


class EntrepreneurIncome(TypedDict):
    role_salary_monthly: int
    profit_monthly: int
    total_monthly: int       # средний первый год (с учётом разгона)
    mature_monthly: int      # после выхода на мощность (ramp=1)
    total_yearly: int
    role_breakdown: List[Dict[str, Any]]
    region_note: Optional[str]


class FirstYearMonth(TypedDict):
    n: int                    # 1..12
    calendar_label: str       # "Янв"..."Дек"
    revenue: int
    color: str                # "ramp" | "mature" | "mature_high" | "season_low"


class FirstYearChart(TypedDict):
    start_month: int
    start_month_label: str
    months: List[FirstYearMonth]
    narrative: str


class Block5PnL(TypedDict, total=False):
    archetype: str
    cogs_label_rus: str
    scenarios: PnlScenarios
    margins: PnlMargins
    annual_roi: Optional[float]
    solo_mode: bool
    payback_months: Optional[int]
    total_investment: int
    entrepreneur_income: EntrepreneurIncome
    first_year_chart: FirstYearChart


# ═══════════════════════════════════════════════════════════════════════
# Block 6 — CAPEX
# ═══════════════════════════════════════════════════════════════════════


class CapexStructureItem(TypedDict):
    label: str
    amount: int
    pct: int


class Block6Capital(TypedDict):
    capex_needed: int
    capital_own: Optional[int]
    diff: Optional[int]
    diff_pct: Optional[float]
    diff_status: str            # "not_specified" | "surplus" | "match" | "deficit" | "critical_deficit"
    capex_structure: List[CapexStructureItem]
    actions: List[str]


# ═══════════════════════════════════════════════════════════════════════
# Block Season
# ═══════════════════════════════════════════════════════════════════════


class BlockSeason(TypedDict):
    coefs: List[float]          # 12 значений
    months: List[str]           # "янв"..."дек"
    peaks: List[str]            # подмножество months где coef > 1.05
    troughs: List[str]          # подмножество months где coef < 0.95
    source: str                 # "niche" | "default"


# ═══════════════════════════════════════════════════════════════════════
# Block 8 — Стресс-тест
# ═══════════════════════════════════════════════════════════════════════


class Sensitivity(TypedDict):
    param: str                  # "Загрузка / трафик" | "Средний чек"
    change: int                 # -20 / -15
    impact_annual: int          # отрицательное = потеря


class DeathPoint(TypedDict):
    param: str
    threshold: str              # "падение на >87% ведёт в минус"


class CriticalParam(TypedDict):
    param: str
    change: int
    impact_annual: int


class Block8Stress(TypedDict):
    base_profit_month: int
    base_profit_year: int
    sensitivities: List[Sensitivity]
    death_points: List[DeathPoint]   # NOTE Этап 8: Ноа просила удалить
    critical_param: CriticalParam
    recommendations: List[str]


# ═══════════════════════════════════════════════════════════════════════
# Block 9 — Риски
# ═══════════════════════════════════════════════════════════════════════


class RiskItem(TypedDict):
    title: str
    probability: str            # "ВЫСОКАЯ" | "СРЕДНЯЯ" | "НИЗКАЯ"
    impact: str                 # "КРИТИЧНОЕ" | "ВЫСОКОЕ" | "СРЕДНЕЕ" | "ЗАМЕТНОЕ" | "ТЕРПИМОЕ"
    text: str
    mitigation: str


class Block9Risks(TypedDict):
    niche_id: str
    source: str                 # "insight" | "generic"
    risks: List[RiskItem]


# ═══════════════════════════════════════════════════════════════════════
# Block 10 — План действий
# ═══════════════════════════════════════════════════════════════════════


class ActionPlanWeek(TypedDict):
    week_range: str             # "1-2" | "3-4" | ... | "Запуск"
    title: str
    actions: List[str]


class YellowCondition(TypedDict):
    title: str
    options: List[str]


class RedAlternative(TypedDict):
    category: str               # "ФОРМАТ" | "ГОРОД" | "РОЛЬ"
    title: str
    options: List[str]


class UpsellProduct(TypedDict):
    name_rus: str
    price_kzt: int
    description_rus: str
    prefilled_pct: int


class UpsellBlock(TypedDict):
    finmodel: UpsellProduct
    bizplan: UpsellProduct


class CTAButton(TypedDict):
    label_rus: str
    action: str


class Block10Plan(TypedDict, total=False):
    color: str
    farewell_rus: str
    upsell: UpsellBlock
    headline_rus: str
    cta_buttons: List[CTAButton]
    # Conditional fields (по color):
    action_plan: List[ActionPlanWeek]   # green
    conditions: List[YellowCondition]   # yellow
    alternatives: List[RedAlternative]  # red
