"""Premium PDF renderer — WeasyPrint + Jinja2 через HTML-шаблон.

Заменяет ReportLab-вариант. Шаблон в api/templates/pdf/quick_check.html
(2276 строк, инлайн SVG, консалтинговая типографика navy+gold).

Экспортирует:
- generate_quick_check_pdf(result, niche_id, ai_risks=None) — совместимо
  с main.py: возвращает (pdf_bytes, report_id, filename).
- render_pdf(result, output_path=None) — прямой вариант.
- build_pdf_context(result) — маппинг result dict → Jinja2 context.
- _register_fonts_once() — no-op (совместимость с pdf-health endpoint).
- generate_pdf_filename(niche, city, fmt) — сохранено из прошлой итерации.

WeasyPrint импортируется лениво (внутри render_pdf) — локально без
системных библиотек Pango/Cairo модуль загружается нормально, ошибка
появляется только при фактическом вызове.
"""
from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from jinja2 import (
        ChainableUndefined, Environment, FileSystemLoader, select_autoescape,
    )
except ImportError:  # pragma: no cover — dev-fallback
    Environment = None
    ChainableUndefined = None

_API_DIR = Path(__file__).parent.parent
_REPO_ROOT = _API_DIR.parent
TEMPLATE_DIR = _API_DIR / "templates" / "pdf"
TEMPLATE_FILE = "quick_check.html"


# ═══════════════════════════════════════════════════════════════════════
# Jinja2-фильтры
# ═══════════════════════════════════════════════════════════════════════


def _coerce_number(value):
    """Undefined / None / '' → 0; остальное пытается привестись к int."""
    if value is None or value == "":
        return 0
    try:
        # ChainableUndefined и другие Undefined классы не int-абельны
        from jinja2 import Undefined
        if isinstance(value, Undefined):
            return 0
    except ImportError:
        pass
    try:
        return int(value)
    except (ValueError, TypeError):
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0


def filter_money(value) -> str:
    """480000 → '480 000'. Undefined/None → '0'."""
    n = _coerce_number(value)
    return f"{n:,}".replace(",", " ")


def filter_money_short(value) -> str:
    """840000 → '840K', 2500000 → '2.5М'. Undefined/None → '0'."""
    v = _coerce_number(value)
    if abs(v) >= 1_000_000:
        s = f"{v / 1_000_000:.1f}М"
        return s.replace(".0М", "М")
    if abs(v) >= 1_000:
        return f"{int(v / 1000)}K"
    return str(v)


# ═══════════════════════════════════════════════════════════════════════
# Константы
# ═══════════════════════════════════════════════════════════════════════


MONTHS_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]
MONTHS_SHORT_RU = [
    "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]
MONTHS_GENITIVE_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]


def _month_ru(n: int) -> str:
    return MONTHS_RU[n - 1] if 1 <= n <= 12 else "Январь"


def _month_short_ru(n: int) -> str:
    return MONTHS_SHORT_RU[n - 1] if 1 <= n <= 12 else "янв"


def _format_date_ru(dt: datetime) -> str:
    return f"{dt.day} {MONTHS_GENITIVE_RU[dt.month - 1]} {dt.year}"


def _is_solo_format(format_id: str) -> bool:
    return any(x in (format_id or "").upper() for x in ("HOME", "SOLO"))


# ═══════════════════════════════════════════════════════════════════════
# Лейблы
# ═══════════════════════════════════════════════════════════════════════


_EXPERIENCE_LABELS = {
    "none":   "Нет опыта — открываю с нуля",
    "some":   "Есть опыт в нише",
    "has":    "Есть опыт в нише",
    "pro":    "Эксперт (5+ лет)",
    "expert": "Эксперт (5+ лет)",
}


_CAPEX_LEVEL_LABELS = {
    "эконом": "Эконом", "economy": "Эконом",
    "стандарт": "Стандарт", "standard": "Стандарт", "Стандарт": "Стандарт",
    "премиум": "Премиум", "premium": "Премиум",
}


def _niche_name_ru(niche_id: str) -> str:
    """Русское имя ниши. Читаем из config/niches.yaml."""
    try:
        import yaml
        with open(_REPO_ROOT / "config" / "niches.yaml", "r", encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh) or {}
        niches = (cfg.get("niches") or {}).get("niches") or cfg.get("niches") or {}
        meta = niches.get((niche_id or "").upper())
        if isinstance(meta, dict):
            return meta.get("name_rus") or meta.get("name_ru") or niche_id
    except Exception:
        pass
    return niche_id or ""


def _format_name_ru(result: dict, format_id: str) -> str:
    """Русское имя формата — из block2.passport или просто format_id."""
    b2 = result.get("block2") or {}
    fn = (b2.get("format") or {}).get("name_rus") or b2.get("format_name_rus")
    if fn:
        return fn
    inp_fn = (result.get("input") or {}).get("format_name")
    if inp_fn:
        return inp_fn
    return format_id or ""


# ═══════════════════════════════════════════════════════════════════════
# Jinja2 environment
# ═══════════════════════════════════════════════════════════════════════


_ENV_CACHE: Optional["Environment"] = None


def create_jinja_env():
    """Создаёт Jinja2 Environment (один раз за процесс)."""
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE
    if Environment is None:
        raise RuntimeError("Jinja2 не установлен — `pip install Jinja2>=3.1`")
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html"]),
        # ChainableUndefined: разрешает `a.b.c` когда a или b отсутствуют —
        # шаблон ZEREK PDF делает глубокую навигацию по опциональным блокам,
        # без chainable любой missing-key роняет рендер.
        undefined=ChainableUndefined,
    )
    env.filters["money"] = filter_money
    env.filters["money_short"] = filter_money_short
    _ENV_CACHE = env
    return env


# ═══════════════════════════════════════════════════════════════════════
# Mapping helpers — result → context sections
# ═══════════════════════════════════════════════════════════════════════


def _build_inp_ctx(result: dict) -> dict:
    inp = result.get("input") or {}
    niche_id = (inp.get("niche_id") or "").upper()
    format_id = (inp.get("format_id") or "").upper()
    return {
        "niche_id": niche_id,
        "niche_name_ru": _niche_name_ru(niche_id),
        "format_id": format_id,
        "format_name_ru": _format_name_ru(result, format_id),
        "city_id": inp.get("city_id") or "",
        "city_name": inp.get("city_name") or "",
        "capital": inp.get("capital"),
        "experience": inp.get("experience") or "",
        "experience_ru": _EXPERIENCE_LABELS.get(
            (inp.get("experience") or "").lower(), "Не указан"
        ),
        "legal_form_ru": "ИП" if (inp.get("legal_form") or "ip") == "ip" else "ТОО",
        "capex_level_ru": _CAPEX_LEVEL_LABELS.get(
            inp.get("class") or inp.get("capex_level") or "стандарт", "Стандарт"
        ),
        "loc_type_ru": inp.get("loc_type") or "не указан",
        "area_m2": inp.get("area_m2"),
        "team_solo": _is_solo_format(format_id),
        "start_month_ru": _month_ru(int(inp.get("start_month") or 5)),
    }


def _build_cap_ctx(result: dict) -> dict:
    """CAPEX: total (= block6.capex_needed с обучением) + breakdown + все уровни."""
    b6 = result.get("block6") or {}
    cap = result.get("capex") or {}
    total = int(b6.get("capex_needed") or cap.get("total") or cap.get("capex_med") or 0)
    breakdown_raw = b6.get("capex_structure") or []
    breakdown = []
    for it in breakdown_raw:
        if not isinstance(it, dict):
            continue
        amount = int(it.get("amount") or 0)
        if amount <= 0:
            continue
        pct = int(round(amount / max(total, 1) * 100))
        breakdown.append({
            "label": it.get("label") or it.get("name") or "",
            "amount": amount,
            "pct": pct,
        })
    # Все уровни (эконом/стандарт/премиум) — пока берём из cap, fallback пустой.
    all_levels = cap.get("все_уровни") or cap.get("all_levels") or {}
    return {"total": total, "breakdown": breakdown, "all_levels": all_levels}


def _build_cadq_ctx(result: dict) -> Optional[dict]:
    ca = result.get("capital_adequacy")
    if not ca:
        return None
    # Реструктурируем reserve_breakdown в list of {label, amount} для шаблона.
    rb = ca.get("reserve_breakdown") or {}
    reserve_items: List[Dict[str, Any]] = []
    if isinstance(rb, dict):
        months = int(rb.get("months") or 3)
        mapping = [
            ("marketing_per_month", "Маркетинг"),
            ("other_opex_per_month", "Прочие расходы"),
            ("ip_min_taxes_per_month", "Соцплатежи ИП (мин)"),
            ("rent_per_month", "Аренда"),
        ]
        for key, label in mapping:
            monthly = int(rb.get(key) or 0)
            if monthly <= 0:
                continue
            reserve_items.append({
                "label": f"{label} × {months} мес",
                "amount": monthly * months,
            })
    elif isinstance(rb, list):
        reserve_items = rb
    return {
        "minimum": int(ca.get("minimum") or 0),
        "comfortable": int(ca.get("comfortable") or 0),
        "safe": int(ca.get("safe") or 0),
        "verdict_level": ca.get("verdict_color") or ca.get("verdict_level") or "amber",
        "verdict_text": ca.get("verdict_message") or ca.get("verdict_text") or "",
        "gap_amount": int(ca.get("gap_amount") or 0),
        "gap_to": ca.get("gap_to_level") or ca.get("gap_to") or "comfortable",
        "reserve_breakdown": reserve_items,
        "reserve_total": int(ca.get("reserve_3_months") or 0),
    }


def _build_dz_ctx(result: dict) -> Optional[dict]:
    dz = result.get("danger_zone")
    if not dz or not dz.get("has_cashflow_risk"):
        return None
    wm = dz.get("worst_month") or {}
    return {
        "applicable": True,
        "break_even_month": dz.get("break_even_month"),
        "worst_month_ru": wm.get("label") or "",
        "worst_month_profit": int(wm.get("profit") or 0),
        "max_drawdown": abs(int(dz.get("max_drawdown") or 0)),
        "loss_months": dz.get("loss_months") or [],
    }


def _build_mp_ctx(result: dict) -> Optional[dict]:
    mp = result.get("marketing_plan")
    if not mp or not mp.get("archetype_id"):
        return None
    monthly = mp.get("monthly_plan") or []
    # 3 фазы для удобства шаблона (ramp / tune / mature).
    def _phase_avg(slice_):
        if not slice_:
            return 0
        return int(sum(m.get("total_marketing", 0) for m in slice_) / len(slice_))
    phases = [
        {"label": "Разгон (м.1-3)",   "avg_budget": _phase_avg(monthly[0:3])},
        {"label": "Настройка (м.4-6)", "avg_budget": _phase_avg(monthly[3:6])},
        {"label": "Зрелый (м.7-12)",   "avg_budget": _phase_avg(monthly[6:12])},
    ]
    # Топ-каналы (% > 0, отсортированы).
    paid = (mp.get("channels_allocation") or {}).get("paid_budget_allocation") or {}
    channels_list = [
        {"name": "Instagram таргет",        "pct": paid.get("instagram", 0)},
        {"name": "Покупка постов в пабликах", "pct": paid.get("pabliki", 0)},
        {"name": "Блогеры (коллаборации)",   "pct": paid.get("bloggers", 0)},
        {"name": "Google / Яндекс реклама",  "pct": paid.get("google_yandex", 0)},
        {"name": "2GIS продвижение",         "pct": paid.get("gis_paid", 0)},
        {"name": "OLX / Krisha",             "pct": paid.get("olx_krisha", 0)},
    ]
    channels_list = [c for c in channels_list if c["pct"] > 0]
    channels_list.sort(key=lambda c: c["pct"], reverse=True)
    return {
        "archetype_id": mp["archetype_id"],
        "archetype_name": mp.get("archetype_name") or "",
        "archetype_note": mp.get("archetype_note") or "",
        "choice_drivers": mp.get("choice_drivers") or {},
        "summary": mp.get("summary") or {},
        "phases": phases,
        "channels_where_to_invest": channels_list,
        "what_not_to_do_ru": mp.get("what_not_to_do_ru") or "",
        "content_advice_ru": mp.get("content_advice_ru") or "",
    }


def _build_sp_ctx(result: dict) -> Optional[dict]:
    sp = result.get("staff_paradox")
    if not sp or not sp.get("applicable"):
        return None
    return sp


def _build_vrd_ctx(result: dict) -> dict:
    """Вердикт — berём block1 (новый формат) как канон."""
    b1 = result.get("block1") or {}
    b10 = result.get("block10") or {}
    color = (b1.get("color") or b10.get("color") or "amber").lower()
    # Нормализация yellow → amber для шаблона.
    if color == "yellow":
        color = "amber"
    return {
        "level": color,
        "title": b10.get("headline_rus") or b1.get("verdict_statement") or "",
        "message": b1.get("verdict_statement") or "",
        "priorities": [],
        "key_insight": None,
        "pros": b1.get("strengths") or [],
        "cons": b1.get("risks") or [],
    }


def _build_fin_ctx(result: dict) -> dict:
    fin = result.get("financials") or {}
    b4 = result.get("block4") or {}
    b4m = b4.get("metrics") or {}
    agg_m = (result.get("pnl_aggregates") or {}).get("mature") or {}
    b5 = result.get("block5") or {}
    ei = b5.get("entrepreneur_income") or {}
    b5_scn = (b5.get("scenarios") or {}).get("base") or {}
    b6_legacy = result.get("block_6") or {}
    return {
        "mature_revenue": int(agg_m.get("revenue_monthly") or 0),
        "mature_profit": int(agg_m.get("profit_monthly") or 0),
        "mature_clients": int(b4m.get("max_checks_per_day") or 0) * 26,
        "avg_year_profit": int(ei.get("total_monthly") or 0) * 12,
        "net_margin_pct": int(round(((b5.get("margins") or {}).get("net") or 0) * 100)),
        "break_even_clients": int(b6_legacy.get("tb_checks_day") or 0),
        "safety_ratio": int(b6_legacy.get("safety_margin") or 0),
        "avg_check": int(fin.get("check_med") or b4m.get("avg_check") or 0),
        "unit_materials": int(int(fin.get("check_med") or 0) * float(fin.get("cogs_pct") or 0.30)),
        "unit_rent_share": 0,
        "unit_other": 0,
        "unit_tax": int(int(fin.get("check_med") or 0) * ((result.get("tax") or {}).get("rate_pct", 3) or 3) / 100),
        "unit_net": int((ei.get("mature_monthly") or 0) / max(b4m.get("max_checks_per_day") or 1, 1) / 26),
    }


def _build_opx_ctx(result: dict) -> dict:
    """Monthly OPEX breakdown + total."""
    agg_m = (result.get("pnl_aggregates") or {}).get("mature") or {}
    fin = result.get("financials") or {}
    revenue = max(int(agg_m.get("revenue_monthly") or 1), 1)
    items = [
        ("Аренда",             int(agg_m.get("rent_monthly") or fin.get("rent_month") or 0)),
        ("ФОТ с налогами",     int(agg_m.get("fot_monthly") or 0)),
        ("Маркетинг",          int(agg_m.get("marketing_monthly") or 0)),
        ("Коммунальные",       0),
        ("Прочие расходы",     int(agg_m.get("other_opex_monthly") or 0)),
    ]
    breakdown = []
    total = 0
    for label, amount in items:
        if amount <= 0:
            continue
        breakdown.append({
            "label": label,
            "amount": amount,
            "pct_of_revenue": int(round(amount / revenue * 100)),
        })
        total += amount
    return {
        "breakdown": breakdown,
        "total": total,
        "total_pct": int(round(total / revenue * 100)) if revenue else 0,
    }


def _build_tax_ctx(result: dict) -> dict:
    tax = result.get("tax") or {}
    inp = result.get("input") or {}
    agg_m = (result.get("pnl_aggregates") or {}).get("mature") or {}
    revenue_y = int(agg_m.get("revenue_yearly") or 0)
    tax_rate_pct = float(tax.get("rate_pct") or 3)
    # IP минимальный платёж в год — 21 675 × 12.
    ip_min_year = 21_675 * 12
    annual_usn = int(revenue_y * tax_rate_pct / 100)
    return {
        "legal_form_ru": "ИП" if (inp.get("legal_form") or "ip") == "ip" else "ТОО",
        "usn_rate": tax_rate_pct,
        "usn_threshold": 2_595_000_000,  # 600 000 МРП × 4325
        "nds_rate": 16,
        "nds_threshold": 43_250_000,
        "annual_usn": annual_usn,
        "ip_min_monthly": 21_675,
        "total_annual": annual_usn + ip_min_year,
        "notes": "",
    }


def _build_scn_ctx(result: dict) -> dict:
    """3 сценария из block5 (pess/base/opt)."""
    b5_scn = (result.get("block5") or {}).get("scenarios") or {}
    def _flat(key):
        s = b5_scn.get(key) or {}
        return {
            "revenue":   int(s.get("revenue") or 0),
            "fot":       int(s.get("fot") or 0),
            "materials": int(s.get("cogs") or 0),
            "rent":      int(s.get("rent") or 0),
            "marketing": int(s.get("marketing") or 0),
            "other":     int(s.get("other_opex") or 0),
            "tax":       int(s.get("tax") or 0),
            "profit":    int(s.get("net_profit") or 0),
        }
    return {"pessim": _flat("pess"), "base": _flat("base"), "optim": _flat("opt")}


def _build_fyc_ctx(result: dict) -> list:
    fyc = ((result.get("block5") or {}).get("first_year_chart") or {}).get("months") or []
    out = []
    for i, m in enumerate(fyc, start=1):
        color = m.get("color") or ""
        if color == "ramp":
            phase = "ramp"
        elif color == "mature_high":
            phase = "peak"
        elif color == "season_low":
            phase = "low"
        else:
            phase = "normal"
        out.append({
            "month": int(m.get("n") or i),
            "month_short_ru": _month_short_ru(int(m.get("n") or i)),
            "revenue": int(m.get("revenue") or 0),
            "phase": phase,
        })
    return out


def _build_mkt_ctx(result: dict) -> dict:
    b3 = result.get("block3") or {}
    b_season = result.get("block_season") or {}
    saturation = b3.get("saturation") or {}
    competitors = {
        "count": int(saturation.get("competitors_count") or 0),
        "density_per_10k": float(saturation.get("density_city") or 0),
        "benchmark_per_10k": float(saturation.get("density_benchmark") or 0),
        "pct_of_benchmark": int(saturation.get("pct_of_benchmark") or 0),
    }
    # Seasonality: template expects list of {label, pct}.
    coefs = b_season.get("coefs") or []
    months_short = b_season.get("months") or MONTHS_SHORT_RU
    seasonality = []
    for i, coef in enumerate(coefs[:12]):
        try:
            pct = int(round(float(coef) * 100))
        except (TypeError, ValueError):
            pct = 100
        seasonality.append({
            "label": months_short[i] if i < len(months_short) else str(i + 1),
            "pct": pct,
        })
    return {
        "population": int((result.get("input") or {}).get("city_population") or 0),
        "working_age": 0,
        # tam_sam_som заглушки (детальный market-анализ только в FinModel).
        "tam_sam_som": {"tam": 0, "sam": 0, "som": 0},
        "competitors": competitors,
        "consumer_behavior": {},
        "seasonality": seasonality,
        "seasonal_peaks": b_season.get("peaks"),
        "seasonal_lows": b_season.get("troughs"),
        "seasonality_note": None,
        "start_note": None,
        "market_notes": None,
    }


def _build_loc_ctx(result: dict) -> dict:
    agg_m = (result.get("pnl_aggregates") or {}).get("mature") or {}
    fin = result.get("financials") or {}
    return {
        "rent_month": int(agg_m.get("rent_monthly") or fin.get("rent_month") or 0),
        "rent_benchmark_m2": None,
        "rent_per_m2": None,
        "rent_by_city": [],
        "location_note": None,
    }


def _build_stf_ctx(result: dict) -> Optional[dict]:
    """Staff stages (start/growth/scale) — если не передано, None."""
    stf = result.get("staff_stages") or {}
    if not stf:
        return None
    stages = []
    for key, label in [("start", "Старт"), ("growth", "Рост"), ("scale", "Масштаб")]:
        stage = stf.get(key) or {}
        if stage and stage.get("staff"):
            stages.append({
                "label": label,
                "staff": stage["staff"],
                "total_fot_with_taxes": stage.get("total_fot_with_taxes", 0),
            })
    return {"stages": stages} if stages else None


# ═══════════════════════════════════════════════════════════════════════
# Главный маппер + рендер
# ═══════════════════════════════════════════════════════════════════════


def build_pdf_context(result: Dict[str, Any]) -> Dict[str, Any]:
    """Маппинг result → Jinja2 context для шаблона."""
    inp_ctx = _build_inp_ctx(result)
    vrd_ctx = _build_vrd_ctx(result)
    now = datetime.now(timezone(timedelta(hours=5)))
    report_id = _generate_report_id(now)
    return {
        "inp": inp_ctx,
        "cap": _build_cap_ctx(result),
        "cadq": _build_cadq_ctx(result),
        "dz": _build_dz_ctx(result),
        "mp": _build_mp_ctx(result),
        "sp": _build_sp_ctx(result),
        "vrd": vrd_ctx,
        "mkt": _build_mkt_ctx(result),
        "loc": _build_loc_ctx(result),
        "fin": _build_fin_ctx(result),
        "opx": _build_opx_ctx(result),
        "tax": _build_tax_ctx(result),
        "scn": _build_scn_ctx(result),
        "pb": {"months": (result.get("block5") or {}).get("payback_months") or 12},
        "stf": _build_stf_ctx(result),
        "stress": result.get("block8"),
        "risks": (result.get("block9") or {}).get("risks") or [],
        "growth_scenarios": result.get("growth_scenarios"),
        "growth_tips": [],
        "fyc": _build_fyc_ctx(result),
        "action_plan": (result.get("block10") or {}).get("action_plan") or [],
        "report_id": report_id,
        "today_date": _format_date_ru(now),
        "verdict_class": vrd_ctx["level"],
        "city": {"name": inp_ctx["city_name"]},
    }


def _generate_report_id(now: Optional[datetime] = None) -> str:
    """QC-2026-NNNNNN."""
    import random
    dt = now or datetime.now(timezone(timedelta(hours=5)))
    return f"QC-{dt.year}-{random.randint(100000, 999999)}"


def render_pdf(result: Dict[str, Any], output_path: Optional[str] = None) -> bytes:
    """Рендерит PDF из result. Raises RuntimeError если WeasyPrint недоступен."""
    env = create_jinja_env()
    template = env.get_template(TEMPLATE_FILE)
    context = build_pdf_context(result)
    html_content = template.render(**context)
    try:
        from weasyprint import HTML
    except ImportError as e:
        raise RuntimeError(
            f"WeasyPrint не установлен или системные библиотеки (Pango/Cairo) "
            f"недоступны: {e}. Установи deps из nixpacks.toml (Railway) или "
            f"brew install pango cairo gdk-pixbuf libffi (macOS)."
        )
    pdf_bytes = HTML(string=html_content, base_url=str(TEMPLATE_DIR)).write_pdf()
    if output_path:
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
    return pdf_bytes


# ═══════════════════════════════════════════════════════════════════════
# Совместимость с main.py (generate_quick_check_pdf)
# ═══════════════════════════════════════════════════════════════════════


def generate_pdf_filename(niche_name: str, city_name: str, format_label: str = "") -> str:
    """«ZEREK_Анализ_Маникюр_На_дому_Астана_2026-04-23.pdf»."""
    from datetime import date
    today = date.today().isoformat()
    parts = ["ZEREK", "Анализ"]
    for p in (niche_name, format_label, city_name):
        s = (p or "").strip().replace(" ", "_")
        if s:
            parts.append(s)
    parts.append(today)
    return "_".join(parts) + ".pdf"


def generate_quick_check_pdf(result: dict, niche_id: str, ai_risks=None) -> tuple:
    """Совместимая обёртка: возвращает (pdf_bytes, report_id, filename)."""
    pdf_bytes = render_pdf(result)
    now = datetime.now(timezone(timedelta(hours=5)))
    report_id = _generate_report_id(now)
    niche_name = _niche_name_ru(niche_id or "")
    city_name = (result.get("input") or {}).get("city_name") or ""
    format_name = _format_name_ru(result, (result.get("input") or {}).get("format_id") or "")
    filename = generate_pdf_filename(niche_name, city_name, format_name)
    return pdf_bytes, report_id, filename


def _register_fonts_once():
    """No-op (совместимость с pdf-health endpoint). WeasyPrint сам находит шрифты."""
    return
