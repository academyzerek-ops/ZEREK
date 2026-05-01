"""api/calculators/finmodel.py — FinModel $20 калькулятор.

Перенесено из api/main.py в Этапе 8.4 рефакторинга.

Что делает:
- compute_finmodel_data — расчёт месячных P&L/CF на 36 мес (зеркало Excel)
- apply_adaptive_answers — маппит specific_answers v2 анкеты → FMReq поля
- _parse_pct / _parse_int — парсеры значений из адаптивной анкеты
- _FM_FIELD_MAP — маппинг qid → поле FMReq + парсер
- FinModelCalculator — фасад: собирает params, считает данные, формирует output

xlsx-генерация (через api/gen_finmodel.py) и HTML-отчёт
(api/finmodel_report.py) остаются отдельными модулями,
endpoint в main.py их оркестрирует.
"""
import logging
import os
import sys
from datetime import datetime

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import FINMODEL_DEFAULTS_CFG  # noqa: E402

_log = logging.getLogger("zerek.finmodel")


# ═══════════════════════════════════════════════════════════════════════
# Дефолты финмодели — читаются из config/finmodel_defaults.yaml
# ═══════════════════════════════════════════════════════════════════════

_FM = (FINMODEL_DEFAULTS_CFG.get("finmodel", {}) or {})
_FM_OPEX = _FM.get("opex", {}) or {}
_FM_FOT = _FM.get("fot", {}) or {}
_FM_CAPEX = _FM.get("capex", {}) or {}
_FM_CREDIT = _FM.get("credit", {}) or {}
_FM_GROWTH = _FM.get("growth", {}) or {}
_FM_SEASONALITY = _FM.get(
    "default_seasonality",
    [0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20],
)


# ═══════════════════════════════════════════════════════════════════════
# Парсеры адаптивной анкеты
# ═══════════════════════════════════════════════════════════════════════


def _parse_pct(val):
    """'30%' / '0.3' / 30 → 0.30. Возвращает None если не парсится."""
    if val is None:
        return None
    try:
        s = str(val).strip().rstrip("%").replace(",", ".")
        f = float(s)
        return f / 100 if f > 1 else f
    except Exception:
        return None


def _parse_int(val):
    """'3-5' → 4 (midpoint), '200+' → 250, '100' → 100, '10-20' → 15."""
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return None
    if s.endswith("+"):
        try:
            base = int(s.rstrip("+").strip())
            return int(base * 1.25)
        except Exception:
            return None
    if "-" in s:
        try:
            a, b = s.split("-", 1)
            return (int(a.strip()) + int(b.strip())) // 2
        except Exception:
            pass
    try:
        return int(float(s))
    except Exception:
        return None


# Маппинг qid → поле FMReq + парсер
_FM_FIELD_MAP = {
    # cogs / fudcost (%)
    "O_FOODCOST": ("cogs_pct", _parse_pct),
    "F_COGS":     ("cogs_pct", _parse_pct),
    "D_COGS":     ("cogs_pct", _parse_pct),
    "A_COGS":     ("cogs_pct", _parse_pct),
    "H_COGS":     ("cogs_pct", _parse_pct),
    # check / средний чек
    "A_CHECK": ("check_med", _parse_int),
    "O_CHECK": ("check_med", _parse_int),
    "D_CHECK": ("check_med", _parse_int),
    "E_CHECK": ("check_med", _parse_int),
    "H_CHECK": ("check_med", _parse_int),
    "P_CHECK_OR_RATE": ("check_med", _parse_int),
    "F_CHECK_OR_UNIT": ("check_med", _parse_int),
    "G_FEE":           ("check_med", _parse_int),
    "B_REP_AVG_PRICE": ("check_med", _parse_int),
    "B_PHOTO_CHECK":   ("check_med", _parse_int),
    "B_FIT_SUB_PRICE": ("check_med", _parse_int),
    "B_CC_RATE":       ("check_med", _parse_int),
    # traffic / volume
    "O_TRAFFIC": ("traffic_med", _parse_int),
    "E_TRAFFIC": ("traffic_med", _parse_int),
    "H_VOLUME":  ("traffic_med", _parse_int),
    "F_VOLUME":  ("traffic_med", _parse_int),
    "D_LOAD":    ("traffic_med", _parse_int),
    "P_CLIENTS_PER_MONTH": ("traffic_med", _parse_int),
    "G_KIDS_COUNT": ("traffic_med", _parse_int),
    # rent
    "A_RENT":     ("rent_override", _parse_int),
    "O_RENT_VAL": ("rent_override", _parse_int),
    "D_RENT":     ("rent_override", _parse_int),
    "E_RENT":     ("rent_override", _parse_int),
    "F_RENT":     ("rent_override", _parse_int),
    "G_RENT":     ("rent_override", _parse_int),
    "H_RENT":     ("rent_override", _parse_int),
    "P_RENT":     ("rent_override", _parse_int),
    # headcount
    "A_CHAIRS":       ("headcount", _parse_int),
    "D_POSTS":        ("headcount", _parse_int),
    "O_STAFF_COUNT":  ("headcount", _parse_int),
    "E_STAFF_COUNT":  ("headcount", _parse_int),
    "G_STAFF_COUNT":  ("headcount", _parse_int),
    "F_STAFF_COUNT":  ("headcount", _parse_int),
    "H_STAFF_COUNT":  ("headcount", _parse_int),
    "D_STAFF_COUNT":  ("headcount", _parse_int),
    # credit
    "U_CREDIT_AMOUNT": ("credit_amount", _parse_int),
    "U_CREDIT_RATE":   ("credit_rate",   _parse_pct),
    "U_CREDIT_TERM":   ("credit_term",   _parse_int),
    # capex / working cap
    "F_EQUIPMENT_CAPEX": ("capex",       _parse_int),
    "E_INITIAL_STOCK":   ("working_cap", _parse_int),
}


def apply_adaptive_answers(req):
    """Применяет specific_answers к полям FMReq. Возвращает тот же объект."""
    if not getattr(req, "specific_answers", None):
        return req
    for qid, raw in (req.specific_answers or {}).items():
        if qid not in _FM_FIELD_MAP:
            continue
        field, parser = _FM_FIELD_MAP[qid]
        parsed = parser(raw)
        if parsed is None:
            continue
        setattr(req, field, parsed)
    return req


# ═══════════════════════════════════════════════════════════════════════
# Расчёт финансовой модели на 36 месяцев
# ═══════════════════════════════════════════════════════════════════════


def compute_finmodel_data(params):
    """Вычисляет месячные P&L/CF из params (зеркало Excel-формул).

    Все дефолты читаются из config/finmodel_defaults.yaml.
    """
    seasonality = _FM_SEASONALITY
    horizon = params.get("horizon", _FM.get("horizon_months", 36))
    check0 = params.get("check_med", _FM.get("check_med", 1400))
    traffic0 = params.get("traffic_med", _FM.get("traffic_med", 70))
    work_days = params.get("work_days", _FM.get("work_days", 30))
    tg = params.get("traffic_growth", _FM_GROWTH.get("traffic_yr", 0.07))
    cg = params.get("check_growth", _FM_GROWTH.get("check_yr", 0.08))
    cogs_pct = params.get("cogs_pct", _FM.get("cogs_pct", 0.35))
    loss_pct = params.get("loss_pct", _FM.get("loss_pct", 0.03))
    rent = params.get("rent", _FM_OPEX.get("rent", 70000))
    fot = params.get("fot_gross", _FM_FOT.get("fot_gross", 200000)) * params.get("headcount", _FM_FOT.get("headcount", 2))
    utilities = params.get("utilities", _FM_OPEX.get("utilities", 15000))
    marketing = params.get("marketing", _FM_OPEX.get("marketing", 50000))
    consumables = params.get("consumables", _FM_OPEX.get("consumables", 3500))
    software = params.get("software", _FM_OPEX.get("software", 5000))
    other = params.get("other", _FM_OPEX.get("other", 10000))
    capex = params.get("capex", _FM_CAPEX.get("default_kzt", 1500000))
    deposit = rent * params.get("deposit_months", _FM_CAPEX.get("deposit_months", 2))
    working_cap = params.get("working_cap", _FM_CAPEX.get("working_cap_kzt", 1000000))
    amort_monthly = capex / (params.get("amort_years", _FM_CAPEX.get("amort_years", 7)) * 12)
    tax_rate = params.get("tax_rate", _FM.get("tax_rate", 0.03))
    credit_amt = params.get("credit_amount", _FM_CREDIT.get("default_amount", 0))
    credit_rate = params.get("credit_rate", _FM_CREDIT.get("rate", 0.22))
    credit_term = params.get("credit_term", _FM_CREDIT.get("term_months", 36))
    wacc = params.get("wacc", _FM.get("wacc", 0.20))

    # Credit annuity
    credit_pmt = 0
    if credit_amt > 0 and credit_term > 0:
        mr = credit_rate / 12
        if mr > 0:
            credit_pmt = credit_amt * mr / (1 - (1 + mr) ** -credit_term)
        else:
            credit_pmt = credit_amt / credit_term

    total_investment = capex + deposit + working_cap
    fixed_opex = rent + fot + utilities + marketing + consumables + software + other

    pl_monthly = []
    cf_monthly = []
    cumulative_profit = 0
    cumulative_cf = -total_investment
    payback_month = None

    for m in range(horizon):
        s_idx = m % 12
        check_m = check0 * (1 + cg) ** (m / 12)
        traffic_m = traffic0 * (1 + tg) ** (m / 12)
        season_coef = seasonality[s_idx]
        revenue = check_m * traffic_m * work_days * season_coef
        cogs = revenue * cogs_pct
        loss = revenue * loss_pct
        gross = revenue - cogs - loss
        opex = fixed_opex
        ebitda = gross - opex
        depreciation = amort_monthly
        ebt = ebitda - depreciation
        tax = max(0, revenue * tax_rate)
        net_profit = ebt - tax
        cumulative_profit += net_profit

        cf_ops = net_profit + depreciation
        cf_inv = -total_investment if m == 0 else 0
        cf_fin = -credit_pmt if credit_amt > 0 and m < credit_term else 0
        cf_net = cf_ops + cf_inv + cf_fin
        cumulative_cf += cf_ops + cf_fin
        if m == 0:
            cumulative_cf = -total_investment + cf_ops + cf_fin
        if payback_month is None and cumulative_cf >= 0:
            payback_month = m + 1

        pl_monthly.append({
            "month": m + 1, "revenue": round(revenue), "cogs": round(cogs),
            "gross_profit": round(gross), "opex": round(opex), "ebitda": round(ebitda),
            "net_profit": round(net_profit), "cumulative": round(cumulative_profit),
        })
        cf_monthly.append({
            "month": m + 1, "operating": round(cf_ops), "investing": round(cf_inv),
            "financing": round(cf_fin), "net": round(cf_net), "cumulative": round(cumulative_cf),
        })

    # Dashboard KPIs
    profit_y1 = sum(p["net_profit"] for p in pl_monthly[:12])
    profit_y2 = sum(p["net_profit"] for p in pl_monthly[12:24]) if horizon > 12 else 0
    profit_y3 = sum(p["net_profit"] for p in pl_monthly[24:36]) if horizon > 24 else 0
    total_profit = sum(p["net_profit"] for p in pl_monthly)
    roi = (total_profit / total_investment * 100) if total_investment > 0 else 0
    npv = -total_investment
    for m, p in enumerate(pl_monthly):
        npv += p["net_profit"] / (1 + wacc / 12) ** (m + 1)
    irr = (total_profit / total_investment / (horizon / 12) * 100) if total_investment > 0 else 0
    be_revenue = fixed_opex / (1 - cogs_pct - loss_pct) if (1 - cogs_pct - loss_pct) > 0 else 0

    return {
        "input": {
            "business_name": params.get("business_name", "Бизнес"),
            "city": params.get("city", ""),
            "horizon_months": horizon,
            "start_date": datetime.now().strftime("%Y"),
        },
        "capex": {
            "equipment": capex, "deposit": deposit,
            "working_capital": working_cap, "total": total_investment,
        },
        "dashboard": {
            "npv": round(npv), "irr": round(irr),
            "roi": round(roi), "payback_months": payback_month,
            "profit_year1": round(profit_y1), "profit_year2": round(profit_y2),
            "profit_year3": round(profit_y3),
            "revenue_month1": pl_monthly[0]["revenue"] if pl_monthly else 0,
            "breakeven_revenue": round(be_revenue),
        },
        "pl_monthly": pl_monthly,
        "cashflow_monthly": cf_monthly,
        "seasonality": seasonality,
        "opex_breakdown": {
            "rent": rent, "fot": fot, "utilities": utilities,
            "marketing": marketing, "consumables": consumables,
            "software": software, "other": other,
        },
        "staff": [{"role": "Сотрудник", "count": params.get("headcount", 2), "salary": params.get("fot_gross", 200000)}],
        "risks": [
            {"name": "Снижение трафика на 30%", "impact": "Убыток в первый год"},
            {"name": "Рост аренды на 20%", "impact": "Снижение маржи"},
            {"name": "Сезонный спад", "impact": "Кассовый разрыв зимой"},
        ],
        "recommendations": [
            "Контролируйте юнит-экономику ежемесячно",
            "Формируйте резерв минимум на 3 месяца",
            "Оптимизируйте маркетинг по ROI каналов",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
# Builder параметров из FMReq + Quick Check result
# ═══════════════════════════════════════════════════════════════════════


def build_params_from_request(req, qc_result):
    """Собирает params dict для compute_finmodel_data из FMReq + QC result.

    req — Pydantic FMReq (см. main.py / validators).
    qc_result — результат engine.run_quick_check_v3 (financials, tax, capex…).
    """
    fin = qc_result.get("financials", {})
    tx = qc_result.get("tax", {})
    capex_block = qc_result.get("capex", {})

    return {
        "entity_type": req.entity_type,
        "tax_regime": tx.get("regime", _FM.get("tax_regime", "УСН")),
        "nds_payer": _FM.get("nds_payer", "Нет"),
        "tax_rate": (tx.get("rate_pct", 3) or 3) / 100,
        "check_med":   req.check_med   if req.check_med   > 0 else fin.get("check_med",   _FM.get("check_med", 1400)),
        "traffic_med": req.traffic_med if req.traffic_med > 0 else fin.get("traffic_med", _FM.get("traffic_med", 70)),
        "work_days":      _FM.get("work_days", 30),
        "traffic_growth": _FM_GROWTH.get("traffic_yr", 0.07),
        "check_growth":   _FM_GROWTH.get("check_yr", 0.08),
        "cogs_pct": req.cogs_pct if req.cogs_pct > 0 else fin.get("cogs_pct", _FM.get("cogs_pct", 0.35)),
        "loss_pct":  fin.get("loss_pct",  _FM.get("loss_pct", 0.03)),
        "rent":        req.rent_override or fin.get("rent_month", _FM_OPEX.get("rent", 70000)),
        "fot_gross":   req.fot_gross,
        "headcount":   req.headcount,
        "utilities":   fin.get("utilities",   _FM_OPEX.get("utilities", 15000)),
        "marketing":   fin.get("marketing",   _FM_OPEX.get("marketing", 50000)),
        "consumables": fin.get("consumables", _FM_OPEX.get("consumables", 3500)),
        "software":    fin.get("software",    _FM_OPEX.get("software", 5000)),
        "other":       fin.get("transport",   _FM_OPEX.get("other", 10000)),
        "capex":       req.capex if req.capex > 0 else capex_block.get("capex_med", _FM_CAPEX.get("default_kzt", 1500000)),
        "deposit_months": _FM_CAPEX.get("deposit_months", 2),
        "working_cap":   req.working_cap,
        "amort_years":   _FM_CAPEX.get("amort_years", 7),
        "credit_amount": req.credit_amount,
        "credit_rate":   req.credit_rate,
        "credit_term":   req.credit_term,
        "wacc":          _FM.get("wacc", 0.20),
        "business_name": (req.niche_name + ": " + req.format_name) if req.niche_name else req.format_id,
        "city": qc_result.get("input", {}).get("city_name", req.city_id),
    }


# ═══════════════════════════════════════════════════════════════════════
# Класс-фасад (для будущего расширения)
# ═══════════════════════════════════════════════════════════════════════


class FinModelCalculator:
    """FinModel $20 — фасад для финмодели.

    Сейчас инкапсулирует основные шаги:
    - apply_adaptive_answers(req) — мутация req из specific_answers
    - build_params_from_request(req, qc_result) — params для compute
    - compute_finmodel_data(params) — расчёт 36 мес P&L/CF + KPI
    - run(req, qc_result) — оркестратор всего пайплайна

    xlsx-генерация (gen_finmodel.generate_finmodel) и HTML-отчёт
    (finmodel_report.render_finmodel_report) — отдельные модули,
    endpoint в main.py их вызывает.
    """

    def __init__(self, db=None):
        self.db = db

    def apply_adaptive_answers(self, req):
        return apply_adaptive_answers(req)

    def build_params_from_request(self, req, qc_result):
        return build_params_from_request(req, qc_result)

    def compute(self, params):
        return compute_finmodel_data(params)

    def run(self, req, qc_result):
        """Полный пайплайн: adaptive → params → finmodel data."""
        self.apply_adaptive_answers(req)
        params = self.build_params_from_request(req, qc_result)
        data = self.compute(params)
        return {"params": params, "data": data}
