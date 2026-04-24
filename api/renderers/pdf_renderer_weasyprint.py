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
    """480000 → '480 000'. Undefined/None → '0'.

    Точная сумма — для «законных» величин (МРП, МЗП, соцплатежи,
    пороги НДС/УСН) и юнит-экономики (чек, материалы, налог/чек).
    Для прогнозов используйте money_round.
    """
    n = _coerce_number(value)
    return f"{n:,}".replace(",", " ")


def _round_bucket(n: int) -> int:
    """Правила округления Round-3: прогнозные суммы не должны быть
    точными до тенге.

    < 1 000              → до 10
    1 000 – 10 000       → до 100
    10 000 – 100 000     → до 500
    100 000 – 1 000 000  → до 1 000
    > 1 000 000          → до 10 000
    """
    n = int(n)
    av = abs(n)
    if av < 1_000:
        step = 10
    elif av < 10_000:
        step = 100
    elif av < 100_000:
        step = 500
    elif av < 1_000_000:
        step = 1_000
    else:
        step = 10_000
    sign = -1 if n < 0 else 1
    return sign * int(round(av / step) * step)


def filter_money_round(value) -> str:
    """Бакетное округление + пробельный разделитель.

    480 123 → '480 000', 259 719 → '260 000', 5 250 → '5 300',
    21 675 → '22 000' (для соцплатежей используйте money — исключение)."""
    n = _coerce_number(value)
    return f"{_round_bucket(n):,}".replace(",", " ")


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
    env.filters["money_round"] = filter_money_round
    env.filters["money_exact"] = filter_money  # alias для читаемости в шаблоне
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
    training_amount = 0
    for it in breakdown_raw:
        if not isinstance(it, dict):
            continue
        amount = int(it.get("amount") or 0)
        if amount <= 0:
            continue
        pct = int(round(amount / max(total, 1) * 100))
        label = it.get("label") or it.get("name") or ""
        breakdown.append({"label": label, "amount": amount, "pct": pct})
        if "Обучение" in label:
            training_amount = amount
    # Round-3 §1.3: показываем сноску «если опыт есть — можно исключить
    # 150K» только если клиент не pro (иначе training_amount=0).
    exp = (result.get("input") or {}).get("experience") or ""
    exp_pro = str(exp).lower() in ("pro", "expert", "has", "some")
    learning_note_visible = training_amount > 0 and not exp_pro
    all_levels = cap.get("все_уровни") or cap.get("all_levels") or {}
    return {
        "total": total,
        "breakdown": breakdown,
        "all_levels": all_levels,
        "training_amount": training_amount,
        "learning_note_visible": learning_note_visible,
    }


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
    """Вердикт — berём block1 (новый формат) как канон.

    Round-4 bug 1: светофор block1 не может быть зеленее чем результат
    capital_adequacy. Если capital < comfortable — верхний предел yellow.
    Scoring block1 этого не учитывает, отсюда «ЗЕЛЁНЫЙ СИГНАЛ» вместе с
    текстом «Средний риск — не хватает подушки».
    """
    b1 = result.get("block1") or {}
    b10 = result.get("block10") or {}
    ca = result.get("capital_adequacy") or {}
    color = (b1.get("color") or b10.get("color") or "amber").lower()
    # yellow / amber — синонимы, приводим к одному значению для тесплейта.
    if color == "yellow":
        color = "amber"
    severity = {"red": 3, "amber": 2, "green": 1, "gray": 0}
    ca_color = (ca.get("verdict_color") or "").lower()
    if ca_color == "yellow":
        ca_color = "amber"
    if severity.get(ca_color, 0) >= severity.get("amber", 2) and severity.get(color, 0) < severity.get(ca_color, 0):
        color = ca_color
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
    be = result.get("breakeven") or {}
    # Net margin — считаем из зрелого P&L с учётом соцплатежей ИП,
    # чтобы цифра совпадала с тем, что видно в OPEX / юнит-экономике.
    # Legacy block5.margins.net не вычитал 21 675 × 12 — отсюда
    # инфляция маржи (≈70% вместо реальных ≈43%).
    rev_mature_m = int(agg_m.get("revenue_monthly") or 0)
    profit_mature_m = int(agg_m.get("profit_monthly") or 0)
    social_monthly = 21_675  # ОПВ + ВОСМС + ИПН минимум ИП, 2026
    legal_form = (result.get("input") or {}).get("legal_form") or "ip"
    social_hit = social_monthly if legal_form == "ip" else 0
    net_margin_pct = 0
    if rev_mature_m > 0:
        net_margin_pct = int(round((profit_mature_m - social_hit) / rev_mature_m * 100))
    return {
        "mature_revenue": rev_mature_m,
        "mature_profit":  profit_mature_m - social_hit,
        "mature_clients": int(b4m.get("max_checks_per_day") or 0) * 26,
        "avg_year_profit": int(ei.get("total_monthly") or 0) * 12,
        "net_margin_pct": net_margin_pct,
        "break_even_clients": int(be.get("тб_чеков_день") or 0),
        "safety_ratio": int(round(float(be.get("запас_прочности_%") or 0))),
        "avg_check": int(fin.get("check_med") or b4m.get("avg_check") or 0),
        "unit_materials": int(int(fin.get("check_med") or 0) * float(fin.get("cogs_pct") or 0.30)),
        "unit_rent_share": 0,
        "unit_other": 0,
        "unit_tax": int(int(fin.get("check_med") or 0) * ((result.get("tax") or {}).get("rate_pct", 3) or 3) / 100),
        "unit_net": int(((ei.get("mature_monthly") or 0) - social_hit) / max(b4m.get("max_checks_per_day") or 1, 1) / 26),
    }


def _build_opx_ctx(result: dict) -> dict:
    """Monthly OPEX breakdown + total.

    Для ИП добавляем минимальные соцплатежи 21 675 ₸/мес (ОПВ+ВОСМС+ИПН) —
    они обязательны даже при нулевом доходе и в шаблоне на стр. «Налоги»
    явно сказано «Учтено в OPEX».
    """
    agg_m = (result.get("pnl_aggregates") or {}).get("mature") or {}
    fin = result.get("financials") or {}
    revenue = max(int(agg_m.get("revenue_monthly") or 1), 1)
    legal_form = (result.get("input") or {}).get("legal_form") or "ip"
    ip_social = 21_675 if legal_form == "ip" else 0
    items = [
        ("Аренда",                 int(agg_m.get("rent_monthly") or fin.get("rent_month") or 0)),
        ("ФОТ с налогами",         int(agg_m.get("fot_monthly") or 0)),
        ("Маркетинг",              int(agg_m.get("marketing_monthly") or 0)),
        ("Соцплатежи ИП (мин.)",   ip_social),
        ("Прочие расходы",         int(agg_m.get("other_opex_monthly") or 0)),
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


def _short_to_full_months(names) -> str:
    """['мар', 'май'] → 'Март, Май'. Принимает list, строку или None."""
    if not names:
        return ""
    if isinstance(names, str):
        return names
    mapping = dict(zip(MONTHS_SHORT_RU, MONTHS_RU))
    out = []
    for n in names:
        s = str(n).strip().lower()
        out.append(mapping.get(s, s.capitalize()))
    return ", ".join(out)


def _load_niche_commentary(niche_id: str) -> Dict[str, List[Dict[str, str]]]:
    """Читает seasonality.commentary из data/niches/{NICHE}_data.yaml.

    Round-3 §3.2: пики/просадки теперь сопровождаются человеческим
    объяснением «почему» (8 марта, свадьбы, Наурыз и т.п.). Возвращает
    {"peaks":[{month,reason}], "troughs":[{month,reason}]} или пустой.
    """
    try:
        from loaders.niche_loader import load_niche_yaml
    except Exception:
        return {"peaks": [], "troughs": []}
    data = load_niche_yaml(niche_id) or {}
    seas = (data.get("seasonality") or {}).get("commentary") or {}
    peaks_raw = seas.get("peaks") or []
    troughs_raw = seas.get("troughs") or []
    norm = lambda items: [
        {"month": str(x.get("month") or "").strip(),
         "reason": str(x.get("reason") or "").strip()}
        for x in items if isinstance(x, dict) and x.get("month")
    ]
    return {"peaks": norm(peaks_raw), "troughs": norm(troughs_raw)}


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
    niche_id = (result.get("input") or {}).get("niche_id") or ""
    commentary = _load_niche_commentary(niche_id)
    return {
        "population": int((result.get("input") or {}).get("city_population") or 0),
        "working_age": 0,
        "competitors": competitors,
        "consumer_behavior": {},
        "seasonality": seasonality,
        "seasonal_peaks": _short_to_full_months(b_season.get("peaks")),
        "seasonal_lows": _short_to_full_months(b_season.get("troughs")),
        "seasonal_peaks_commentary": commentary.get("peaks") or [],
        "seasonal_lows_commentary": commentary.get("troughs") or [],
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


def _build_growth_scenarios_ctx(result: dict) -> Optional[List[Dict[str, Any]]]:
    """Приводит growth_service.compute_growth_block к формату шаблона.

    Источник — result['growth_scenarios'] — это DICT
    {stagnation: {label, description, outcome, warning},
     development: {label, description, outcome_year2, outcome_year3},
     growth_factors: [...]}.

    Шаблон ждёт LIST со сценариями с ключами:
      {icon, color, title, description, projection, warning?}.

    Когда шаблон итерировал dict, Jinja возвращал строки-ключи
    "stagnation"/"development"; {{ scenario.title }} превращалось в
    `<built-in method title of str>` — отсюда Round-3 баг 1.1.

    Формируем 3 сценария: Стагнация / Развитие / Рост. Тексты пока
    заглушки из правок Ноа; когда придёт deterministic_texts.yaml —
    подхватим оттуда.
    """
    raw = result.get("growth_scenarios")
    if not raw or not isinstance(raw, dict):
        return None
    stag = raw.get("stagnation") or {}
    dev = raw.get("development") or {}

    dev_outcome = (dev.get("outcome_year3") or dev.get("outcome_year2")
                   or dev.get("description") or "").strip()

    scenarios = [
        {
            "icon": "·",
            "color": "#F59E0B",
            "title": stag.get("label") or "Стагнация",
            "description": (stag.get("description") or
                "Работаете как в первый год, без изменений. "
                "Выручка держится на мощности базового сценария."),
            "projection": (stag.get("outcome") or
                "Та же прибыль месяц в месяц. Риск — выгорание и "
                "постепенная потеря клиентов к конкурентам с более "
                "агрессивным маркетингом."),
            "warning": stag.get("warning") or "",
        },
        {
            "icon": "·",
            "color": "#10B981",
            "title": dev.get("label") or "Развитие",
            "description": (dev.get("description") or
                "Растёт средний чек за счёт ретеншена и допуслуг. "
                "Клиентская база расширяется через сарафан."),
            "projection": dev_outcome or (
                "Прибыль выше базового сценария. Требует дисциплины "
                "в ведении клиентов и регулярного обучения."),
            "warning": "",
        },
        {
            "icon": "·",
            "color": "#7C6CFF",
            "title": "Рост",
            "description": (
                "Переход в формат SOLO — арендованный кабинет. "
                "Физический потолок выручки увеличивается примерно "
                "вдвое, появляется возможность принимать параллельные "
                "визиты."),
            "projection": (
                "Требует дополнительного CAPEX на ремонт и оборудование "
                "и принятия риска долгосрочной аренды."),
            "warning": "",
        },
    ]
    return scenarios


def _build_stress_ctx(result: dict) -> Optional[Dict[str, Any]]:
    """Приводит block8 (stress_service) к формату шаблона.

    stress_service возвращает:
      {base_profit_month, base_profit_year, sensitivities:[{param,change,
      impact_annual}], critical_param:{param,change,impact_annual}, recs}.

    Шаблон ждёт:
      {base_annual_profit, tests:[{label,delta,loss}], critical_param:str,
      recommendations}.

    Баг 1.2: шаблон читал stress.critical_param как строку, а сервис
    клал туда dict → рендерился как `{'param': 'Загрузка / трафик',
    'change': -20, 'impact_annual': -963900}`. Заодно base_annual_profit
    не существовало в сервисе — отсюда «Прибыль в год (база) 0 ₸».
    """
    s = result.get("block8") or {}
    if not s:
        return None
    sens = s.get("sensitivities") or []
    tests: List[Dict[str, Any]] = []
    for item in sens:
        if not isinstance(item, dict):
            continue
        change = int(item.get("change") or 0)
        loss = abs(int(item.get("impact_annual") or 0))
        tests.append({
            "label": item.get("param") or "",
            "delta": f"{change}%" if change else "0%",
            "loss": loss,
        })
    crit = s.get("critical_param") or {}
    if isinstance(crit, dict):
        critical_str = crit.get("param") or ""
    else:
        critical_str = str(crit)
    return {
        "base_annual_profit": int(s.get("base_profit_year") or 0),
        "tests": tests,
        "critical_param": critical_str,
        "recommendations": s.get("recommendations") or [],
    }


def _maybe_rag_slot(slot_type: str, niche_id: str) -> Optional[str]:
    """Unified generator — any slot returns None on any failure.

    Fallback-контракт: template `{% if {slot} %}` просто не рендерит
    блок когда None — никаких placeholder'ов.
    """
    import logging
    log = logging.getLogger("zerek.pdf_rag")
    try:
        from services.pdf_rag_service import generate_slot
    except Exception as e:
        log.warning("pdf_rag_service import failed: %s", e)
        return None
    try:
        diag: Dict[str, Any] = {}
        text = generate_slot(slot_type, niche_id, diag=diag)
        log.info(
            "pdf-rag slot=%s diag=%s",
            slot_type, {k: v for k, v in diag.items() if k != "raw_text"},
        )
        return text
    except Exception as e:
        log.warning("%s slot crashed: %s", slot_type, e)
        return None


def build_pdf_context(result: Dict[str, Any]) -> Dict[str, Any]:
    """Маппинг result → Jinja2 context для шаблона."""
    inp_ctx = _build_inp_ctx(result)
    vrd_ctx = _build_vrd_ctx(result)
    now = datetime.now(timezone(timedelta(hours=5)))
    report_id = _generate_report_id(now)
    opx_ctx = _build_opx_ctx(result)
    fin_ctx = _build_fin_ctx(result)
    # Пересчитываем маржу из opx_total чтобы цифра совпадала с
    # таблицей OPEX. mature.profit_monthly считается engine'ом до того
    # как marketing_service патчит marketing_monthly, поэтому прямое
    # деление mature_profit/revenue даёт искажённую маржу.
    agg_m = (result.get("pnl_aggregates") or {}).get("mature") or {}
    rev_m = int(agg_m.get("revenue_monthly") or 0)
    cogs_pct = float(agg_m.get("cogs_pct") or (result.get("financials") or {}).get("cogs_pct") or 0.30)
    tax_rate = float(agg_m.get("tax_rate") or ((result.get("tax") or {}).get("rate_pct", 3) or 3) / 100)
    avg_check = int(fin_ctx.get("avg_check") or 0)
    if rev_m > 0:
        cogs_m = int(rev_m * cogs_pct)
        tax_m = int(rev_m * tax_rate)
        true_profit_m = rev_m - cogs_m - tax_m - int(opx_ctx.get("total") or 0)
        fin_ctx["mature_profit"] = true_profit_m
        fin_ctx["net_margin_pct"] = int(round(true_profit_m / rev_m * 100))
        if avg_check > 0:
            fin_ctx["unit_net"] = int(round(avg_check * true_profit_m / rev_m))
    # Round-4 bug 4: в юнит-экономике раньше не было строки «Доля OPEX» —
    # клиент-финансист видел 5250−630−157=4463, а в чистых было 3501.
    # Разница = доля постоянных расходов (marketing+соцпл+прочие) на один
    # чек при актуальной загрузке. Показываем отдельной строкой.
    if avg_check > 0:
        _mat = int(fin_ctx.get("unit_materials") or 0)
        _tax = int(fin_ctx.get("unit_tax") or 0)
        _net = int(fin_ctx.get("unit_net") or 0)
        fin_ctx["unit_opex_share"] = max(0, avg_check - _mat - _tax - _net)
    # БЭП — пересчёт через opx.total (содержит реальный marketing из
    # marketing_service + соцплатежи ИП + аренду + ФОТ). Канонический
    # calc_breakeven читает fin['marketing'] = 0 для HOME-форматов и
    # не учитывает соцплатежи — отсюда "БЭП=0/1" артефакт для solo.
    #
    # Contribution margin = check − check×cogs_pct − check×tax_rate.
    # BE (клиентов/мес) = fixed_total / contribution_margin.
    # safety_% = (planned_month − be) / planned_month × 100.
    if avg_check > 0 and rev_m > 0:
        cogs_per_check = int(avg_check * cogs_pct)
        tax_per_check = int(avg_check * tax_rate)
        contribution = avg_check - cogs_per_check - tax_per_check
        fixed_total = int(opx_ctx.get("total") or 0)
        if contribution > 0 and fixed_total > 0:
            be_per_month = int(round(fixed_total / contribution))
            fin_ctx["break_even_clients"] = max(be_per_month, 1)
            planned_per_month = int(rev_m / avg_check)
            if planned_per_month > 0:
                fin_ctx["safety_ratio"] = max(0, int(round(
                    (planned_per_month - be_per_month) / planned_per_month * 100
                )))
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
        "fin": fin_ctx,
        "opx": opx_ctx,
        "tax": _build_tax_ctx(result),
        "scn": _build_scn_ctx(result),
        "pb": {"months": (result.get("block5") or {}).get("payback_months") or 12},
        "stf": _build_stf_ctx(result),
        "stress": _build_stress_ctx(result),
        "risks": (result.get("block9") or {}).get("risks") or [],
        "growth_scenarios": _build_growth_scenarios_ctx(result),
        "growth_tips": [],
        "fyc": _build_fyc_ctx(result),
        "action_plan": (result.get("block10") or {}).get("action_plan") or [],
        "report_id": report_id,
        "today_date": _format_date_ru(now),
        "verdict_class": vrd_ctx["level"],
        "city": {"name": inp_ctx["city_name"]},
        "common_mistakes":    _maybe_rag_slot("common_mistakes",    inp_ctx.get("niche_id") or ""),
        "first_year_reality": _maybe_rag_slot("first_year_reality", inp_ctx.get("niche_id") or ""),
        "market_insight":     _maybe_rag_slot("market_insight",     inp_ctx.get("niche_id") or ""),
        "real_experience":    _maybe_rag_slot("real_experience",    inp_ctx.get("niche_id") or ""),
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
