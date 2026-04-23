"""api/services/economics_service.py — P&L, окупаемость, breakeven, юнит-эко.

Ядро расчётов Quick Check согласно `ZEREK_QuickCheck_Calculation_Spec.md`:
- Шаг 3: зрелый месячный P&L (ramp=1, season=1)
- Шаг 4: 12-мес P&L с ramp+season (через calc_cashflow)
- Шаг 5: средние годовые показатели
- Шаг 6: окупаемость — ОДНА формула `ceil(capex / monthly_income_avg)`
- Шаг 7: breakeven через unit-экономику
- Блоки 4/5/6: юнит-экономика, P&L таблица, CAPEX структура

Извлечено из engine.py в Этапе 3 рефакторинга.
"""
import logging
import math
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    AVG_SALARY_2025,
    AVG_SALARY_DEFAULT,
    CAPEX_BREAKDOWN_LABELS_RUS,
    DEFAULTS,
    OWNER_CLOSURE_POCKET,
    OWNER_GROWTH_POCKET,
    SEASON_LABELS,
    TRAINING_COSTS_BY_EXPERIENCE,
    _safe_float,
    _safe_int,
)
from renderers.quick_check_renderer import _fmt_kzt  # noqa: E402
from loaders.niche_loader import _archetype_of  # noqa: E402
from services.pricing_service import calc_owner_social_payments  # noqa: E402
from services.seasonality_service import calc_revenue_monthly  # noqa: E402

_log = logging.getLogger("zerek.economics_service")


# ═══════════════════════════════════════════════════════════════════════
# ПРИМИТИВЫ (Шаги 3-7 спеки)
# ═══════════════════════════════════════════════════════════════════════


def calc_cashflow(fin, staff, capex_total, tax_rate, start_month=1, months=12, qty=1):
    """12-мес cashflow с ramp-up и сезонностью.

    Возвращает list of dict со всеми статьями расходов + выручка + прибыль
    + нарастающий итог.
    """
    results = []
    cumulative = -capex_total

    fot = _safe_int(staff.get("fot_net_med"), 0)
    fot_full = _safe_int(staff.get("fot_full_med"), 0)
    if fot_full == 0 and fot > 0:
        fot_full = int(fot * DEFAULTS["fot_multiplier"])

    rent = _safe_int(fin.get("rent_med"), 0) * qty
    cogs_pct = _safe_float(fin.get("cogs_pct"), DEFAULTS["cogs_pct"])
    utilities = _safe_int(fin.get("utilities"), 0) * qty
    marketing = _safe_int(fin.get("marketing"), 0)
    consumables = _safe_int(fin.get("consumables"), 0) * qty
    software = _safe_int(fin.get("software"), 0)
    transport = _safe_int(fin.get("transport"), 0)
    loss_pct = _safe_float(fin.get("loss_pct"), DEFAULTS["loss_pct"])
    sez = _safe_int(fin.get("sez_month"), DEFAULTS["sez_month"])

    for i in range(months):
        razgon_month = i + 1
        cal_month = ((start_month - 1 + i) % 12) + 1

        rev = calc_revenue_monthly(fin, cal_month, razgon_month) * qty
        cogs = int(rev * cogs_pct)
        gross = rev - cogs
        losses = int(rev * loss_pct)
        tax = int(rev * tax_rate)

        total_opex = fot_full + rent + utilities + marketing + consumables + software + transport + losses + sez + tax
        profit = gross - total_opex
        cumulative += profit

        results.append({
            "месяц": i + 1,
            "кал_месяц": SEASON_LABELS[cal_month - 1],
            "выручка": rev,
            "cogs": cogs,
            "валовая_прибыль": gross,
            "фот": fot_full,
            "аренда": rent,
            "коммуналка": utilities,
            "маркетинг": marketing,
            "расходники": consumables,
            "софт": software,
            "транспорт": transport,
            "потери": losses,
            "сэз": sez,
            "налог": tax,
            "opex": total_opex,
            "прибыль": profit,
            "нарастающий": cumulative,
        })

    return results


def calc_breakeven(fin, staff, tax_rate, qty=1):
    """Точка безубыточности — включает все постоянные расходы."""
    check = _safe_int(fin.get("check_med"), 1000)
    cogs_pct = _safe_float(fin.get("cogs_pct"), DEFAULTS["cogs_pct"])
    loss_pct = _safe_float(fin.get("loss_pct"), DEFAULTS["loss_pct"])

    fot_full = _safe_int(staff.get("fot_full_med"), 0)
    if fot_full == 0:
        fot_full = int(_safe_int(staff.get("fot_net_med"), 0) * DEFAULTS["fot_multiplier"])

    rent = _safe_int(fin.get("rent_med"), 0) * qty
    utilities = _safe_int(fin.get("utilities"), 0) * qty
    marketing = _safe_int(fin.get("marketing"), 0)
    consumables = _safe_int(fin.get("consumables"), 0) * qty
    software = _safe_int(fin.get("software"), 0)
    transport = _safe_int(fin.get("transport"), 0)
    sez = _safe_int(fin.get("sez_month"), 0)

    fixed = fot_full + rent + utilities + marketing + consumables + software + transport + sez
    variable_pct = cogs_pct + loss_pct + tax_rate

    if variable_pct >= 1.0:
        return {"тб_₸": 0, "тб_чеков_день": 0, "запас_прочности_%": 0, "чек_для_тб": check, "fixed_total": fixed}

    tb_revenue = int(fixed / (1 - variable_pct))
    tb_checks_day = int(tb_revenue / 30 / check) if check > 0 else 0

    traffic = _safe_int(fin.get("traffic_med"), 50)
    rev_full = check * traffic * 30 * qty
    safety = round((rev_full - tb_revenue) / rev_full * 100, 1) if rev_full > 0 else 0

    return {
        "тб_₸": tb_revenue,
        "тб_чеков_день": tb_checks_day,
        "запас_прочности_%": safety,
        "чек_для_тб": check,
        "fixed_total": fixed,
    }


def calc_payback(capex_total, cashflow):
    """Окупаемость через cashflow — первый месяц где cumulative ≥ 0.

    Legacy-fallback после спеки (обычно заменён `compute_unified_payback_months`).
    """
    for cf in cashflow:
        if cf["нарастающий"] >= 0:
            return {"месяц": cf["месяц"], "статус": f"✅ Окупается на {cf['месяц']}-й месяц"}
    avg_profit = sum(cf["прибыль"] for cf in cashflow[-3:]) / 3 if cashflow else 0
    if avg_profit > 0:
        remaining = abs(cashflow[-1]["нарастающий"])
        extra = remaining / avg_profit
        m = round(12 + extra, 1)
        return {"месяц": m, "статус": f"⚠️ Окупаемость ~{m} мес."}
    return {"месяц": None, "статус": "🔴 Не окупается при текущих параметрах"}


def calc_owner_economics(fin, staff, tax_rate, rent_month_total, qty=1,
                         traffic_k=1.0, check_k=1.0, rent_k=1.0, social=None):
    """Месячная экономика собственника с полной разбивкой OPEX.

    Коэффициенты *_k используются в стресс-тесте для «плохо/хорошо».
    """
    check = _safe_int(fin.get("check_med"), 1000) * check_k
    traffic = _safe_float(fin.get("traffic_med"), 50) * traffic_k
    revenue = int(check * traffic * 30 * qty)

    cogs_pct = _safe_float(fin.get("cogs_pct"), DEFAULTS["cogs_pct"])
    cogs = int(revenue * cogs_pct)
    gross = revenue - cogs

    fot_full = _safe_int(staff.get("fot_full_med"), 0)
    if fot_full == 0:
        fot_full = int(_safe_int(staff.get("fot_net_med"), 0) * DEFAULTS["fot_multiplier"])

    rent = int(rent_month_total * rent_k)
    utilities = _safe_int(fin.get("utilities"), 0) * qty
    marketing = _safe_int(fin.get("marketing"), 0)
    consumables = _safe_int(fin.get("consumables"), 0) * qty
    software = _safe_int(fin.get("software"), 0)
    transport = _safe_int(fin.get("transport"), 0)
    sez = _safe_int(fin.get("sez_month"), DEFAULTS["sez_month"])
    other = consumables + software + transport + sez

    opex_total = fot_full + rent + marketing + utilities + other
    profit_before_tax = gross - opex_total
    tax_amount = int(revenue * tax_rate)
    social_amount = social if social is not None else calc_owner_social_payments()
    net_in_pocket = profit_before_tax - tax_amount - social_amount

    return {
        "revenue": revenue, "cogs": cogs, "gross": gross,
        "opex_breakdown": {
            "rent": rent,
            "fot": fot_full,
            "marketing": marketing,
            "utilities": utilities,
            "other": other,
        },
        "opex_total": opex_total,
        "profit_before_tax": profit_before_tax,
        "tax_amount": tax_amount,
        "tax_rate_pct": round(tax_rate * 100, 2),
        "social_payments": social_amount,
        "net_in_pocket": net_in_pocket,
    }


def calc_closure_growth_points(owner_eco):
    """Переводит пороги «в карман» в пороги месячной выручки."""
    pocket = owner_eco.get("net_in_pocket", 0)
    revenue = owner_eco.get("revenue", 0)
    if pocket <= 0 or revenue <= 0:
        return {
            "closure_pocket": OWNER_CLOSURE_POCKET, "closure_revenue": 0,
            "growth_pocket": OWNER_GROWTH_POCKET, "growth_revenue": 0,
        }
    ratio = revenue / pocket
    return {
        "closure_pocket": OWNER_CLOSURE_POCKET,
        "closure_revenue": int(OWNER_CLOSURE_POCKET * ratio),
        "growth_pocket": OWNER_GROWTH_POCKET,
        "growth_revenue": int(OWNER_GROWTH_POCKET * ratio),
    }


# ═══════════════════════════════════════════════════════════════════════
# PNL-АГРЕГАТЫ И ОКУПАЕМОСТЬ (Шаги 3-6 спеки)
# ═══════════════════════════════════════════════════════════════════════


def compute_pnl_aggregates(result):
    """Шаги 3-5 спеки: зрелый месячный P&L + средний год.

    mature — зрелый режим (ramp=1, season=1): основа для стресс-теста и breakeven.
    yearly_avg — средний первый год (из scenarios.base через calc_cashflow).
    fixed_monthly — постоянные расходы/мес (для Шагов 6, 7, 8).
    """
    inp = result.get("input", {}) or {}
    fin = result.get("financials", {}) or {}
    staff = result.get("staff", {}) or {}
    tax = result.get("tax", {}) or {}
    scenarios = result.get("scenarios", {}) or {}

    avg_check = _safe_int(fin.get("check_med"), 0) or 3000
    traffic = _safe_int(fin.get("traffic_med"), 0) or 30
    cogs_pct = _safe_float(fin.get("cogs_pct"), 0.30)
    tax_rate = (tax.get("rate_pct", 3) or 3) / 100
    rent = _safe_int(fin.get("rent_month"), 0)
    fot = (_safe_int(staff.get("fot_full_med"), 0)
           or _safe_int(staff.get("fot_net_med"), 0))

    fin_mk = _safe_int(fin.get("marketing_med"), 0) or _safe_int(fin.get("marketing"), 0)
    fin_ox = _safe_int(fin.get("other_opex_med"), 0)
    opex_med = _safe_int(fin.get("opex_med"), 0)
    fmt_up = (inp.get("format_id") or "").upper()
    is_home = fmt_up.endswith("_HOME") or fmt_up.endswith("_SOLO")
    if is_home:
        mk_monthly = fin_mk
        ox_monthly = fin_ox
    else:
        mk_monthly = fin_mk if fin_mk > 0 else (int(opex_med * 0.2) if opex_med else 100_000)
        ox_monthly = fin_ox if fin_ox > 0 else (
            max(0, opex_med - rent - mk_monthly) if opex_med else 100_000)

    # Шаг 3: зрелый месячный P&L.
    rev_mature_m = avg_check * traffic * 30
    materials_m = int(rev_mature_m * cogs_pct)
    tax_m = int(rev_mature_m * tax_rate)
    fixed_m = fot + rent + mk_monthly + ox_monthly
    profit_mature_m = rev_mature_m - materials_m - tax_m - fixed_m

    # Шаг 5: средний первый год.
    rev_year_avg = _safe_int((scenarios.get("base") or {}).get("выручка_год"), 0)
    profit_year_avg = _safe_int((scenarios.get("base") or {}).get("прибыль_год"), 0)
    profit_month_avg = profit_year_avg // 12 if profit_year_avg else 0

    return {
        "mature": {
            "revenue_monthly":  rev_mature_m,
            "materials_monthly": materials_m,
            "tax_monthly":       tax_m,
            "fixed_monthly":     fixed_m,
            "profit_monthly":    profit_mature_m,
            "revenue_yearly":    rev_mature_m * 12,
            "profit_yearly":     profit_mature_m * 12,
            "fot_monthly":       fot,
            "rent_monthly":      rent,
            "marketing_monthly": mk_monthly,
            "other_opex_monthly": ox_monthly,
            "cogs_pct":          cogs_pct,
            "tax_rate":          tax_rate,
        },
        "yearly_avg": {
            "revenue_yearly":  rev_year_avg,
            "profit_yearly":   profit_year_avg,
            "profit_monthly":  profit_month_avg,
        },
        "is_home": is_home,
    }


def compute_unified_payback_months(result, adaptive):
    """Кумулятивная окупаемость — первый месяц в котором Σ profit ≥ startup.

    Вместо наивной формулы ceil(startup / avg_profit), которая для
    MANICURE_HOME давала 2 мес (игнорируя rampup), считаем по реальному
    cashflow первого года. Если CAPEX не покрыт за 12 мес — возвращаем 13
    (UI показывает «более 12 мес»).

    Источник profit по месяцам:
    1. scenarios.base.cashflow[i].прибыль (из engine.calc_cashflow — уже
       учитывает ramp + сезонность).
    2. Fallback: scenarios.base.прибыль_среднемес × 12 распределённо.
    """
    inp = result.get("input", {}) or {}
    capex = result.get("capex", {}) or {}
    scenarios = result.get("scenarios", {}) or {}
    staff = result.get("staff", {}) or {}
    adaptive = adaptive or {}

    startup = _safe_int(capex.get("total"), 0)
    if startup <= 0:
        startup = _safe_int(capex.get("capex_med"), 0) or _safe_int(inp.get("capex_standard"), 0)
    if bool(inp.get("training_required")):
        exp = (adaptive.get("experience") or "").lower()
        startup += TRAINING_COSTS_BY_EXPERIENCE.get(exp, 0)
    if startup <= 0:
        return None

    base = (scenarios.get("base") or {})
    cashflow = base.get("cashflow") or []
    monthly_profits = []
    if cashflow:
        monthly_profits = [_safe_int(m.get("прибыль"), 0) for m in cashflow[:12]]

    # Добавляем role_salary для owner_plus_* форматов.
    fmt_up = (inp.get("format_id") or "").upper()
    is_solo = bool(inp.get("founder_works")) and (fmt_up.endswith("_HOME") or fmt_up.endswith("_SOLO"))
    role_salary = 0
    if not is_solo:
        ent_role = (adaptive.get("entrepreneur_role") or "owner_only").lower()
        if ent_role.startswith("owner_plus_"):
            fot_full = _safe_int(staff.get("fot_full_med"), 0) or _safe_int(staff.get("fot_net_med"), 0)
            hc = max(
                _safe_int(staff.get("headcount"), 1) or 1,
                _safe_int(inp.get("masters_canon"), 0) or 0,
                1,
            )
            role_salary = int(fot_full / hc) if fot_full else 0

    if not monthly_profits:
        # Fallback: равномерное распределение avg прибыли × 12.
        avg = _safe_int(base.get("прибыль_среднемес"), 0)
        if avg <= 0:
            return None
        monthly_profits = [avg] * 12

    cumulative = 0
    for i, p in enumerate(monthly_profits, start=1):
        cumulative += int(p) + role_salary
        if cumulative >= startup:
            return i
    return 13  # не окупается за первый год — UI покажет «более 12 мес»


# ═══════════════════════════════════════════════════════════════════════
# BLOCK 4 — ЮНИТ-ЭКОНОМИКА (6 архетипов A–F)
# ═══════════════════════════════════════════════════════════════════════


def compute_block4_unit_economics(db, result, adaptive, block2=None):
    """Юнит-экономика + breakeven по архетипу.

    db передан для `_archetype_of` (читает config/niches.yaml). В Этапе 4+
    архетип будет частью `result`, зависимость от db уйдёт.
    """
    inp = result.get("input", {}) or {}
    fin = result.get("financials", {}) or {}
    staff = result.get("staff", {}) or {}
    tax = result.get("tax", {}) or {}
    arch = _archetype_of(db, inp.get("niche_id", ""))

    avg_check = _safe_int(fin.get("check_med"), 0) or 3000
    traffic = _safe_int(fin.get("traffic_med"), 0) or 30
    cogs_pct = _safe_float(fin.get("cogs_pct"), 0.30)
    tax_rate = (tax.get("rate_pct", 3) or 3) / 100
    rent_month = _safe_int(fin.get("rent_month"), 0)
    fot_month = _safe_int(staff.get("fot_full_med"), 0)
    opex_month = _safe_int(fin.get("opex_med"), 0)

    staff_total = 0
    if block2:
        staff_total = ((block2.get("typical_staff") or {}).get("total")) or 0
    if staff_total == 0:
        staff_total = max(1, _safe_int(staff.get("headcount"), 1))

    work_days = 26

    is_solo_unit = bool(inp.get("founder_works")) and (
        (block2 or {}).get("is_solo")
        or (inp.get("format_id") or "").upper().endswith(("_HOME", "_SOLO"))
    )

    if arch == "A":
        unit_label = "одна услуга"
        masters_count = max(staff_total, 1)
        checks_per_day = max(int(traffic / masters_count), 1)
        load_pct = 0.80
        gross_rev_per_unit = int(checks_per_day * avg_check * work_days * load_pct)
        materials = int(avg_check * 0.12)
        rent_share = int(rent_month / masters_count / (checks_per_day * work_days)) if masters_count else 0
        overhead_share = int(opex_month * 0.5 / masters_count / (checks_per_day * work_days)) if masters_count else 0
        tax_per_check = int(avg_check * tax_rate)
        if is_solo_unit:
            in_pocket = max(0, avg_check - materials - rent_share - overhead_share - tax_per_check)
            breakdown = [
                {"label": "Материалы", "amount": materials, "pct": round(materials / avg_check * 100)},
                {"label": "Аренда (доля)", "amount": rent_share, "pct": round(rent_share / avg_check * 100)},
                {"label": "Прочие расходы", "amount": overhead_share, "pct": round(overhead_share / avg_check * 100)},
                {"label": "Налог", "amount": tax_per_check, "pct": round(tax_per_check / avg_check * 100)},
                {"label": "Чистыми вам", "amount": in_pocket, "pct": round(in_pocket / avg_check * 100)},
            ]
            piece_rate = 0
        else:
            piece_rate = int(avg_check * 0.40)
            business = max(0, avg_check - piece_rate - materials - rent_share - overhead_share - tax_per_check)
            breakdown = [
                {"label": "Мастеру (сдельно)", "amount": piece_rate, "pct": round(piece_rate / avg_check * 100)},
                {"label": "Материалы", "amount": materials, "pct": round(materials / avg_check * 100)},
                {"label": "Аренда (доля)", "amount": rent_share, "pct": round(rent_share / avg_check * 100)},
                {"label": "Прочие расходы", "amount": overhead_share, "pct": round(overhead_share / avg_check * 100)},
                {"label": "Налог", "amount": tax_per_check, "pct": round(tax_per_check / avg_check * 100)},
                {"label": "Бизнесу", "amount": business, "pct": round(business / avg_check * 100)},
            ]
        pnl_agg = (result.get("pnl_aggregates") or {}).get("mature") or {}
        fixed_monthly_total = _safe_int(pnl_agg.get("fixed_monthly"), 0)
        if not fixed_monthly_total:
            fixed_monthly_total = int(rent_month + opex_month * 0.5)
        fixed_per_master = (fixed_monthly_total / masters_count) if masters_count else 0
        var_margin = avg_check - piece_rate - materials - tax_per_check
        if var_margin > 0 and fixed_per_master > 0:
            min_checks_month = int(math.ceil(fixed_per_master / var_margin))
        elif var_margin > 0:
            min_checks_month = 0
        else:
            min_checks_month = 9999
        min_load = min_checks_month / max(checks_per_day * work_days, 1)
        planned_checks = int(checks_per_day * work_days * load_pct)
        safety = planned_checks / max(min_checks_month, 1)
        metrics = {
            "checks_per_day": checks_per_day, "avg_check": avg_check,
            "load_pct": int(load_pct * 100), "work_days": work_days,
            "gross_revenue_per_unit": gross_rev_per_unit,
            "breakeven_value": min_checks_month,
            "breakeven_label": f"{min_checks_month} услуг/мес на мастера",
            "planned_value": planned_checks,
            "planned_label": f"{planned_checks} услуг планируется",
            "safety_margin": round(safety, 1),
            "min_load_pct": int(min_load * 100),
        }
        if is_solo_unit:
            metrics["checks_per_day_note"] = "медиана"
            metrics["max_checks_per_day"] = max(
                int(round(checks_per_day / max(load_pct, 0.01))),
                checks_per_day + 1,
                6,
            )
    elif arch == "B":
        unit_label = "один чек"
        food_cost = int(avg_check * cogs_pct)
        fot_per_check = int(fot_month / max(traffic * work_days, 1))
        rent_per_check = int(rent_month / max(traffic * work_days, 1))
        overhead_per_check = int(opex_month * 0.4 / max(traffic * work_days, 1))
        tax_per_check = int(avg_check * tax_rate)
        business = max(0, avg_check - food_cost - fot_per_check - rent_per_check - overhead_per_check - tax_per_check)
        breakdown = [
            {"label": "Food cost", "amount": food_cost, "pct": round(food_cost / avg_check * 100)},
            {"label": "ФОТ на чек", "amount": fot_per_check, "pct": round(fot_per_check / avg_check * 100)},
            {"label": "Аренда (доля)", "amount": rent_per_check, "pct": round(rent_per_check / avg_check * 100)},
            {"label": "Прочие расходы", "amount": overhead_per_check, "pct": round(overhead_per_check / avg_check * 100)},
            {"label": "Налог", "amount": tax_per_check, "pct": round(tax_per_check / avg_check * 100)},
            {"label": "Бизнесу", "amount": business, "pct": round(business / avg_check * 100)},
        ]
        fixed_costs = fot_month + rent_month + int(opex_month * 0.6)
        var_margin = avg_check - food_cost - tax_per_check
        be_checks_day = int(fixed_costs / max(var_margin * work_days, 1)) if var_margin > 0 else 0
        safety = traffic / max(be_checks_day, 1)
        metrics = {
            "avg_check": avg_check,
            "breakeven_value": be_checks_day,
            "breakeven_label": f"{be_checks_day} чеков/день",
            "planned_value": traffic,
            "planned_label": f"{traffic} чеков/день",
            "safety_margin": round(safety, 1),
        }
    elif arch == "C":
        unit_label = "100 ₸ выручки"
        markup_pct = 50
        cogs_pct_r = 100 / (100 + markup_pct) if markup_pct else 0.5
        c_cogs = int(100 * cogs_pct_r)
        c_fot = int(100 * 0.10)
        c_rent = int(100 * 0.12)
        c_over = int(100 * 0.08)
        c_tax = int(100 * tax_rate)
        c_loss = int(100 * 0.05)
        c_bus = max(0, 100 - c_cogs - c_fot - c_rent - c_over - c_tax - c_loss)
        breakdown = [
            {"label": "Закупка (COGS)", "amount": c_cogs, "pct": c_cogs},
            {"label": "ФОТ", "amount": c_fot, "pct": c_fot},
            {"label": "Аренда", "amount": c_rent, "pct": c_rent},
            {"label": "Прочие расходы", "amount": c_over, "pct": c_over},
            {"label": "Налог", "amount": c_tax, "pct": c_tax},
            {"label": "Списания/порча", "amount": c_loss, "pct": c_loss},
            {"label": "Бизнесу", "amount": c_bus, "pct": c_bus},
        ]
        metrics = {
            "markup_pct": markup_pct, "inventory_turnover_days": 28, "gross_margin_pct": 100 - c_cogs,
            "breakeven_label": "По обороту запасов",
            "planned_label": f"Средний чек ~{_fmt_kzt(avg_check)}",
            "safety_margin": 2.0,
        }
    elif arch == "D":
        unit_label = "один клиент (LTV)"
        monthly_fee = avg_check
        churn_pct = 0.08
        lifetime = 1 / churn_pct
        ltv = int(monthly_fee * lifetime * 0.6)
        marketing = int(opex_month * 0.25) or 150_000
        new_per_month = max(int(marketing / 12000), 1)
        cac = int(marketing / new_per_month)
        ltv_cac = round(ltv / max(cac, 1), 2)
        payback = round(cac / (monthly_fee * 0.6), 1) if monthly_fee else 0
        breakdown = [
            {"label": "LTV клиента", "amount": ltv, "pct": 100},
        ]
        metrics = {
            "monthly_fee": monthly_fee, "churn_pct": int(churn_pct * 100),
            "lifetime_months": round(lifetime, 1),
            "ltv": ltv, "cac": cac, "ltv_cac_ratio": ltv_cac, "payback_months": payback,
            "breakeven_label": "LTV/CAC > 3", "planned_label": f"LTV/CAC = {ltv_cac}",
            "safety_margin": round(ltv_cac / 3, 1),
        }
    elif arch == "E":
        unit_label = "один проект"
        project = avg_check
        mat = int(project * 0.40)
        fotp = int(project * 0.20)
        rent_p = int(project * 0.10)
        over = int(project * 0.05)
        taxp = int(project * tax_rate)
        bus = max(0, project - mat - fotp - rent_p - over - taxp)
        breakdown = [
            {"label": "Материалы", "amount": mat, "pct": 40},
            {"label": "ФОТ", "amount": fotp, "pct": 20},
            {"label": "Аренда (доля)", "amount": rent_p, "pct": 10},
            {"label": "Прочие расходы", "amount": over, "pct": 5},
            {"label": "Налог", "amount": taxp, "pct": round(taxp / project * 100)},
            {"label": "Бизнесу", "amount": bus, "pct": round(bus / project * 100)},
        ]
        projects_per_month = max(1, int(traffic))
        min_projects = max(1, int((rent_month + fot_month) / max(bus, 1)))
        safety = projects_per_month / max(min_projects, 1)
        metrics = {
            "avg_project": project, "projects_per_month": projects_per_month,
            "breakeven_value": min_projects,
            "breakeven_label": f"{min_projects} проектов/мес",
            "planned_value": projects_per_month,
            "planned_label": f"{projects_per_month} проектов/мес",
            "safety_margin": round(safety, 1),
        }
    else:  # F — мощность
        unit_label = "одна единица мощности"
        capacity = max(staff_total, 1)
        per_unit_revenue = int((fin.get("revenue_year1") or 0) / 12 / capacity) if capacity else 0
        occupancy = 0.65
        breakdown = [
            {"label": "Переменные затраты", "amount": int(avg_check * 0.30), "pct": 30},
            {"label": "ФОТ (сдельно)", "amount": int(avg_check * 0.25), "pct": 25},
            {"label": "Аренда (доля)", "amount": int(avg_check * 0.14), "pct": 14},
            {"label": "Коммуналка", "amount": int(avg_check * 0.08), "pct": 8},
            {"label": "Прочие", "amount": int(avg_check * 0.05), "pct": 5},
            {"label": "Налог", "amount": int(avg_check * tax_rate), "pct": round(tax_rate * 100)},
            {"label": "Бизнесу", "amount": int(avg_check * 0.18), "pct": 18},
        ]
        metrics = {
            "capacity_units": capacity,
            "avg_check": avg_check,
            "occupancy_pct": int(occupancy * 100),
            "per_unit_revenue_month": per_unit_revenue,
            "breakeven_label": "Заполняемость ≥35%",
            "planned_label": f"Заполняемость {int(occupancy * 100)}%",
            "safety_margin": round(occupancy / 0.35, 1),
        }

    return {
        "archetype": arch,
        "unit_label": unit_label,
        "avg_check": avg_check,
        "breakdown": breakdown,
        "metrics": metrics,
    }


# ═══════════════════════════════════════════════════════════════════════
# BLOCK 5 — P&L за год, 3 сценария
# ═══════════════════════════════════════════════════════════════════════


def _cogs_label_by_archetype(archetype):
    return {
        "A": "Расходные материалы",
        "B": "Food cost",
        "C": "Себестоимость товара",
        "D": "Расходники",
        "E": "Материалы проектов",
        "F": "Переменные материалы",
    }.get(archetype, "Материалы / COGS")


def _scenario_pnl_row(revenue_y, cogs_pct, fot_monthly, rent_monthly,
                      marketing_monthly, other_opex_monthly, tax_rate):
    """Годовая P&L строка для одного сценария."""
    cogs_y = int(revenue_y * (cogs_pct or 0.30))
    fot_y = int(fot_monthly * 12)
    rent_y = int(rent_monthly * 12)
    marketing_y = int(marketing_monthly * 12)
    other_y = int(other_opex_monthly * 12)
    tax_y = int(revenue_y * (tax_rate or 0.03))
    net_profit = revenue_y - cogs_y - fot_y - rent_y - marketing_y - other_y - tax_y
    return {
        "revenue":   revenue_y,
        "cogs":      cogs_y,
        "fot":       fot_y,
        "rent":      rent_y,
        "marketing": marketing_y,
        "other_opex": other_y,
        "tax":       tax_y,
        "net_profit": net_profit,
    }


def compute_block5_pnl(db, result, adaptive):
    """Блок 5 — P&L за год по 3 сценариям + ROI + доход предпринимателя."""
    adaptive = adaptive or {}
    fin = result.get("financials", {}) or {}
    scenarios = result.get("scenarios", {}) or {}
    staff = result.get("staff", {}) or {}
    tax = result.get("tax", {}) or {}
    inp = result.get("input", {}) or {}
    capex_block = result.get("capex", {}) or {}

    # Архетип через loader (в Этапе 4+ будет в result).
    archetype = _archetype_of(db, inp.get("niche_id", ""))

    # Базовые месячные параметры.
    # result.staff уже «подрезан» в run_quick_check_v3 (owner_plus_*): здесь
    # НЕ вычитаем повторно.
    fot_monthly_full = _safe_int(staff.get("fot_full_med"), 0) or _safe_int(staff.get("fot_net_med"), 0)
    row_hc = _safe_int(staff.get("headcount"), 1) or 1
    masters_canon = _safe_int(inp.get("masters_canon"), 0) or 0
    seats_mult_in = float(_safe_float(inp.get("seats_mult"), 1.0) or 1.0)
    effective_hc = max(masters_canon, int(round(row_hc * max(seats_mult_in, 1.0))), row_hc, 1)
    ent_role_id = adaptive.get("entrepreneur_role") or "owner_only"
    if ent_role_id not in ("owner_only", "owner_multi") and fot_monthly_full > 0 and effective_hc > 1:
        fot_unadj = int(fot_monthly_full * effective_hc / max(effective_hc - 1, 1))
        one_role_salary_full = int(fot_unadj / effective_hc)
    else:
        fot_unadj = fot_monthly_full
        one_role_salary_full = int(fot_unadj / effective_hc) if effective_hc else 0
    fot_monthly = fot_monthly_full
    mature = (result.get("pnl_aggregates") or {}).get("mature") or {}
    rent_monthly = _safe_int(mature.get("rent_monthly"), _safe_int(fin.get("rent_month"), 0))
    marketing_monthly = _safe_int(mature.get("marketing_monthly"), 0)
    other_opex_monthly = _safe_int(mature.get("other_opex_monthly"), 0)
    cogs_pct = _safe_float(mature.get("cogs_pct"), _safe_float(fin.get("cogs_pct"), 0.30))
    tax_rate = _safe_float(mature.get("tax_rate"), (tax.get("rate_pct", 3) or 3) / 100)

    rev_year_base = _safe_int((scenarios.get("base") or {}).get("выручка_год"), 0)
    rev_year_pess = _safe_int((scenarios.get("pess") or {}).get("выручка_год"), 0)
    rev_year_opt = _safe_int((scenarios.get("opt") or {}).get("выручка_год"), 0)

    if rev_year_base == 0:
        rev_year_base = _safe_int(fin.get("revenue_year1"), 0)
        rev_year_pess = int(rev_year_base * 0.75)
        rev_year_opt = int(rev_year_base * 1.25)

    pnl_base = _scenario_pnl_row(rev_year_base, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)
    pnl_pess = _scenario_pnl_row(rev_year_pess, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)
    pnl_opt = _scenario_pnl_row(rev_year_opt, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)

    def _safe_div(a, b):
        return (a / b) if b else 0

    gross_margin = _safe_div(rev_year_base - pnl_base["cogs"], rev_year_base)
    op_margin = _safe_div(
        rev_year_base - pnl_base["cogs"] - pnl_base["fot"] - pnl_base["rent"]
        - pnl_base["marketing"] - pnl_base["other_opex"],
        rev_year_base,
    )
    net_margin = _safe_div(pnl_base["net_profit"], rev_year_base)

    capital_own = _safe_int(adaptive.get("capital_own")) if adaptive.get("capital_own") else 0
    capex_standard_08 = _safe_int(inp.get("capex_standard"), 0)
    total_investment = (
        capital_own
        or capex_standard_08
        or _safe_int(capex_block.get("capex_med"), 0)
        or _safe_int(capex_block.get("capex_total"), 0)
    )
    if total_investment < 500_000:
        for k in ("capex_high", "total", "capital"):
            v = _safe_int(capex_block.get(k), 0)
            if v >= 500_000:
                total_investment = v
                break

    format_id_upper = (inp.get("format_id") or "").upper()
    is_solo_fmt = bool(inp.get("founder_works")) and (
        format_id_upper.endswith("_HOME") or format_id_upper.endswith("_SOLO")
    )

    payback_months = None
    if is_solo_fmt:
        annual_roi = None
        payback_months = compute_unified_payback_months(result, adaptive)
    elif total_investment < 500_000:
        annual_roi = None
    else:
        raw_roi = _safe_div(pnl_base["net_profit"], total_investment)
        annual_roi = min(raw_roi, 3.0) if raw_roi > 3.0 else raw_roi

    role_salary_monthly = 0
    role_breakdown = []
    if is_solo_fmt:
        pass
    elif ent_role_id not in ("owner_only", "owner_multi"):
        role_salary_monthly = one_role_salary_full
        if role_salary_monthly == 0:
            role_salary_monthly = 200_000
        role_breakdown.append({"role": ent_role_id.replace("owner_plus_", ""),
                               "salary_monthly": role_salary_monthly})
    elif ent_role_id == "owner_multi":
        role_salary_monthly = max(int(fot_monthly_full * 0.35), 300_000)
        role_breakdown.append({"role": "multi", "salary_monthly": role_salary_monthly})

    profit_monthly_base = pnl_base["net_profit"] // 12
    income_from_business = profit_monthly_base
    entrepreneur_income_monthly = role_salary_monthly + income_from_business
    mature_profit_monthly = _safe_int(mature.get("profit_monthly"), 0)
    mature_monthly = role_salary_monthly + mature_profit_monthly

    region_note = None
    if is_solo_fmt:
        city_id = (inp.get("city_id") or "").lower()
        avg_salary = int(AVG_SALARY_2025.get(city_id) or AVG_SALARY_DEFAULT)
        city_rus = inp.get("city_name") or ""
        salary_k = avg_salary // 1000
        if entrepreneur_income_monthly >= avg_salary:
            region_note = (
                f"Выше средней зарплаты по {city_rus} (~{salary_k} тыс ₸). "
                f"Неплохой уровень для самозанятости."
            )
        else:
            region_note = (
                f"Ниже средней зарплаты по {city_rus} (~{salary_k} тыс ₸). "
                f"Для старта и развития своего дела — рабочий вариант, "
                f"дальше растёт через рост чека или расширение."
            )

    return {
        "archetype": archetype,
        "cogs_label_rus": _cogs_label_by_archetype(archetype),
        "scenarios": {
            "pess": pnl_pess,
            "base": pnl_base,
            "opt": pnl_opt,
        },
        "margins": {
            "gross":     gross_margin,
            "operating": op_margin,
            "net":       net_margin,
        },
        "annual_roi": annual_roi,
        "solo_mode": is_solo_fmt,
        "payback_months": payback_months,
        "total_investment": total_investment,
        "entrepreneur_income": {
            "role_salary_monthly": role_salary_monthly,
            "profit_monthly":       income_from_business,
            "total_monthly":        entrepreneur_income_monthly,
            "mature_monthly":       mature_monthly,
            "total_yearly":         entrepreneur_income_monthly * 12,
            "role_breakdown":       role_breakdown,
            "region_note":          region_note,
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# BLOCK 6 — СТАРТОВЫЙ КАПИТАЛ
# ═══════════════════════════════════════════════════════════════════════


def compute_block6_capital(db, result, adaptive, block2=None):
    """CAPEX структура + обучение + дефицит/профицит vs капитал.

    `db` не используется в логике (сохраняется для сигнатуры Этапа 2).
    В Этапе 4+ уберётся.
    """
    capex = result.get("capex", {}) or {}
    inp = result.get("input", {}) or {}
    capex_needed = _safe_int(capex.get("capex_med")) or _safe_int(capex.get("capex_total"))
    # NB: block2.finance.capex_needed уже включает training (унификация BUG #1),
    # поэтому fallback без training_cost чтобы избежать двойного добавления.
    if capex_needed < 500_000 and block2:
        b2_fallback = _safe_int((block2.get("finance") or {}).get("capex_needed"))
        if b2_fallback > 0:
            # Если есть experience и training_required — b2_fallback содержит training,
            # вычитаем его чтобы последующее +training не дало double-count.
            try:
                exp_fb = (adaptive.get("experience") or "").lower()
                if bool(inp.get("training_required")):
                    tr_fb = TRAINING_COSTS_BY_EXPERIENCE.get(exp_fb, 0)
                    b2_fallback -= tr_fb
            except Exception:
                pass
            capex_needed = max(b2_fallback, capex_needed)
    capital_own = _safe_int(adaptive.get("capital_own")) if adaptive.get("capital_own") else None

    breakdown_src = capex.get("breakdown") or {}
    if isinstance(breakdown_src, dict) and breakdown_src:
        capex_structure = [
            {"label": CAPEX_BREAKDOWN_LABELS_RUS.get(k, k), "amount": _safe_int(v, 0),
             "pct": int(_safe_int(v, 0) / max(capex_needed, 1) * 100)}
            for k, v in breakdown_src.items() if _safe_int(v, 0) > 0
        ]
    else:
        items = [
            ("Оборудование", 0.32),
            ("Ремонт / обустройство", 0.22),
            ("Первичные закупки", 0.15),
            ("Маркетинг на старт", 0.10),
            ("Оборотный капитал (3 мес)", 0.12),
            ("Депозит + 1-я аренда", 0.04),
            ("Юр.расходы, лицензии", 0.05),
        ]
        capex_structure = [{"label": l, "amount": int(capex_needed * p), "pct": int(p * 100)} for l, p in items]

    training_required = bool(inp.get("training_required"))
    experience = (adaptive.get("experience") or "").lower()
    training_cost = TRAINING_COSTS_BY_EXPERIENCE.get(experience, 0) if training_required else 0
    if training_cost > 0:
        capex_needed += training_cost
        capex_structure.append({
            "label": CAPEX_BREAKDOWN_LABELS_RUS["training"],
            "amount": training_cost,
            "pct": int(training_cost / max(capex_needed, 1) * 100),
        })
        for it in capex_structure:
            it["pct"] = int(it["amount"] / max(capex_needed, 1) * 100)

    if capital_own is None:
        diff_status = "not_specified"
        diff = None
        diff_pct = None
        actions = []
    else:
        diff = capital_own - capex_needed
        diff_pct = (diff / capex_needed * 100) if capex_needed else 0
        if diff >= 0:
            diff_status = "surplus" if diff_pct > 5 else "match"
            actions = ["Отложить профицит в резервный фонд (3-6 мес расходов)", "Увеличить маркетинговый бюджет на старт"] if diff_status == "surplus" else []
        else:
            diff_status = "critical_deficit" if abs(diff_pct) > 30 else "deficit"
            gap = abs(diff)
            credit_monthly = int(gap * 0.035)
            actions = [
                f"Урезать формат до эконом-класса (бюджет ≈ {_fmt_kzt(int(capex_needed * 0.5))})",
                f"Кредит {_fmt_kzt(gap)} на 24 мес (платёж ~{_fmt_kzt(credit_monthly)}/мес)",
                "Найти партнёра с долей 20%",
                "Грант Astana Hub / Bastau Business до 5 млн ₸",
            ]

    return {
        "capex_needed": capex_needed,
        "capital_own": capital_own,
        "diff": diff,
        "diff_pct": round(diff_pct, 1) if diff_pct is not None else None,
        "diff_status": diff_status,
        "capex_structure": capex_structure,
        "actions": actions,
    }
