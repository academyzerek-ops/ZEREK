"""api/renderers/quick_check_renderer.py — рендер Quick Check отчёта.

Преобразует чистые данные от QuickCheckCalculator в UI-структуру:
- block_1..block_12 (legacy формат для PDF, через render_report_v4)
- block1..block10 (новый формат для UI Mini App, оверлеится calculator)
- compute_block2_passport (паспорт бизнеса — чистая трансформация input)

Извлечено в Этапе 5 рефакторинга:
- из api/report.py: render_report_v4, fmt
- из api/engine.py: compute_block2_passport, LOCATION_TYPES_META,
  _fmt_kzt, _fmt_kzt_short, _fmt_range_kzt,
  _parse_typical_staff, _split_staff_into_groups,
  _subtract_entrepreneur_role, _entrepreneur_role_text,
  _payroll_label, _experience_label, _format_location

Контракт: только форматирование/трансформация, никакой бизнес-логики.
"""
import logging
import os
import sys
from typing import TYPE_CHECKING

import pandas as pd

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import _safe, _safe_float, _safe_int  # noqa: E402

if TYPE_CHECKING:
    from models import CalcResult, QuickCheckResult  # noqa: F401

_log = logging.getLogger("zerek.quick_check_renderer")


# ═══════════════════════════════════════════════════════════════════════
# Справочники для рендера
# ═══════════════════════════════════════════════════════════════════════

# LOCATION_TYPES_META переехал в api/config.py (Этап 8.6).
from config import LOCATION_TYPES_META  # noqa: F401


# ═══════════════════════════════════════════════════════════════════════
# Форматтеры цифр (₸, тыс, млн)
# ═══════════════════════════════════════════════════════════════════════


def fmt(n) -> str:
    """Форматирует число в строку с пробелами как разделители тысяч.

    None / ошибка → '—'.
    """
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return str(n) if n else "—"


def _fmt_kzt(v):
    """Форматирует число в '12 тыс ₸' / '1,5 млн ₸'."""
    if v is None:
        return "—"
    v = int(v)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f} млн ₸".replace(".0 млн", "  млн").rstrip().replace(".", ",")
    if abs(v) >= 1_000:
        return f"{v//1_000} тыс ₸"
    return f"{v} ₸"


def _fmt_kzt_short(v):
    """Форматирует число в '12 тыс' / '1.5 млн' (без ₸)."""
    if v is None:
        return "—"
    v = int(v)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}".rstrip("0").rstrip(".") + " млн"
    if abs(v) >= 1_000:
        return f"{v//1_000} тыс"
    return f"{v}"


def _fmt_range_kzt(low, high):
    """Форматирует диапазон 'X–Y тыс/млн ₸'."""
    if low is None or high is None:
        return "—"
    if low == high:
        return _fmt_kzt(low)
    return f"{_fmt_kzt_short(low)}–{_fmt_kzt_short(high)}"


# ═══════════════════════════════════════════════════════════════════════
# Block 2 — Паспорт бизнеса (чистая трансформация)
# ═══════════════════════════════════════════════════════════════════════


def _parse_typical_staff(staff_str):
    """'барбер:4|администратор:1' → [{role,count}]."""
    out = []
    if not staff_str:
        return out
    for chunk in str(staff_str).split("|"):
        if ":" in chunk:
            role, count = chunk.split(":", 1)
            try:
                out.append({"role": role.strip(), "count": int(count.strip())})
            except Exception:
                pass
    return out


def _split_staff_into_groups(staff_list):
    """Делит на masters/assistants. Мастер = первая роль; админ/помощник/ассистент/курьер → assistant."""
    if not staff_list:
        return {"masters": [], "assistants": []}
    assistant_keywords = [
        "администратор", "админ", "помощник", "ассистент", "курьер",
        "уборщик", "грумер", "консультант", "методист", "водитель",
        "диспетчер", "механик",
    ]
    masters, assistants = [], []
    for s in staff_list:
        role = s.get("role", "").lower()
        if any(kw in role for kw in assistant_keywords):
            assistants.append(s)
        else:
            masters.append(s)
    if not masters and assistants:
        masters = [assistants.pop(0)]
    return {"masters": masters, "assistants": assistants}


def _subtract_entrepreneur_role(staff_list, role_name):
    """Вычитает одну ставку указанной роли (для owner_plus_*)."""
    if not role_name or role_name == "multi":
        return staff_list
    out = []
    subtracted = False
    for s in staff_list:
        if not subtracted and s.get("role", "").lower() == role_name.lower() and s.get("count", 0) > 0:
            new_count = s["count"] - 1
            if new_count > 0:
                out.append({"role": s["role"], "count": new_count})
            subtracted = True
        else:
            out.append(dict(s))
    return out


def _entrepreneur_role_text(role_id, staff_list):
    """owner_only / owner_plus_{role} / owner_multi → (label, description)."""
    if not role_id or role_id == "owner_only":
        total = sum(s.get("count", 0) for s in staff_list)
        return {
            "label_rus": "Только владелец",
            "description_rus": f"Нанимаю всех {total} сотрудников. Не работаю операционно.",
            "subtract_role": None,
        }
    if role_id == "owner_multi":
        return {
            "label_rus": "Владелец на нескольких позициях",
            "description_rus": "Вы закрываете 2+ ставки. Детализация штата — в финмодели.",
            "subtract_role": "multi",
        }
    if role_id.startswith("owner_plus_"):
        role = role_id[len("owner_plus_"):]
        return {
            "label_rus": f"Владелец + {role}",
            "description_rus": f"Вы закрываете 1 ставку {role}",
            "subtract_role": role,
        }
    return {"label_rus": role_id, "description_rus": "", "subtract_role": None}


def _payroll_label(pt):
    return {
        "salary": "Оклад (фиксированная зарплата)",
        "piece":  "Сдельно / процент с выручки",
        "mixed":  "Смешанно (оклад + %)",
    }.get(pt, "—")


def _experience_label(exp):
    return {
        "none":        "Нет опыта — открываю с нуля",
        "some":        "1–2 года опыта в найме",
        "experienced": "3+ лет опыта / был свой бизнес",
    }.get(exp, "—")


def _format_location(city_name, location_type, location_line, format_type, configs_locations):
    """Собирает строку «Город · Район · Линия» или специальные формулировки."""
    if format_type == "HOME":
        return f"{city_name} · На дому у мастера" if city_name else "На дому у мастера"
    if format_type == "MOBILE":
        return f"{city_name} · Выездной формат / доставка" if city_name else "Выездной формат / доставка"
    if format_type == "SOLO" or location_type == "rent_in_salon":
        return f"Аренда в салоне{('  ·  ' + city_name) if city_name else ''}"
    if format_type == "HIGHWAY":
        return f"{city_name} · Трасса / промзона" if city_name else "Трасса / промзона"
    if format_type == "PRODUCTION":
        return f"{city_name} · Промзона / своё здание" if city_name else "Промзона / своё здание"

    loc_rus = ""
    if configs_locations and location_type:
        meta = configs_locations.get(location_type, {}) or {}
        loc_rus = meta.get("label_rus", location_type)

    parts = []
    if city_name:
        parts.append(city_name)
    if loc_rus:
        parts.append(loc_rus)
    if location_line in ("line_1", "line_2"):
        parts.append("1-я линия" if location_line == "line_1" else "2-я линия")
    return " · ".join(parts) if parts else "—"


def compute_block2_passport(db, result, adaptive):
    """Block 2 — «Паспорт бизнеса»: что именно оценивается.

    Чистая трансформация input → структура для UI. Использует loaders для
    получения данных формата (08_niche_formats.xlsx).
    """
    from loaders.niche_loader import _formats_from_fallback_xlsx
    adaptive = adaptive or {}
    inp = result.get("input", {}) or {}
    niche_id = inp.get("niche_id") or ""
    format_id = inp.get("format_id") or ""

    configs = getattr(db, "configs", {}) or {}
    niches_cfg = (configs.get("niches", {}) or {}).get("niches", {}) or {}
    locations_cfg = (configs.get("locations", {}) or {}).get("locations", {}) or {}

    niche_meta = niches_cfg.get(niche_id, {}) or {}
    niche_icon = niche_meta.get("icon", "📋")
    niche_name_rus = niche_meta.get("name_rus", niche_id)

    formats = _formats_from_fallback_xlsx(db, niche_id)
    fm = next((f for f in formats if f.get("format_id") == format_id), {})
    format_name_rus = fm.get("format_name", format_id)
    class_level = (fm.get("class", "") or "").strip().lower()
    area_m2 = _safe_int(fm.get("area_m2"), 0)
    format_type = ""
    df_fb = getattr(db, "niches_formats_fallback", pd.DataFrame())
    if df_fb is not None and not df_fb.empty and "format_type" in df_fb.columns:
        row = df_fb[(df_fb["niche_id"].astype(str) == niche_id) & (df_fb["format_id"].astype(str) == format_id)]
        if not row.empty:
            format_type = str(row.iloc[0].get("format_type", "") or "").strip()
    if not format_type:
        format_type = "STANDARD"

    typical_staff_raw = ""
    if df_fb is not None and not df_fb.empty and "typical_staff" in df_fb.columns:
        row = df_fb[(df_fb["niche_id"].astype(str) == niche_id) & (df_fb["format_id"].astype(str) == format_id)]
        if not row.empty:
            typical_staff_raw = str(row.iloc[0].get("typical_staff", "") or "").strip()
    staff_list = _parse_typical_staff(typical_staff_raw)
    staff_groups = _split_staff_into_groups(staff_list)

    ent_role_id = adaptive.get("entrepreneur_role") or "owner_only"
    ent = _entrepreneur_role_text(ent_role_id, staff_list)
    staff_after = _subtract_entrepreneur_role(staff_list, ent["subtract_role"])
    staff_after_groups = _split_staff_into_groups(staff_after)

    city_name = inp.get("city_name", "") or ""
    loc_type = inp.get("loc_type", "") or adaptive.get("loc_type", "")
    loc_line = adaptive.get("location_line", "")
    location_rus = _format_location(city_name, loc_type, loc_line, format_type, locations_cfg)

    capex_block = result.get("capex", {}) or {}
    capex_needed = _safe_int(capex_block.get("capex_med")) or _safe_int(capex_block.get("capex_total"))
    if capex_needed < 500_000:
        capex_needed = _safe_int(fm.get("capex_standard"), 0) or capex_needed
    capital_own = _safe_int(adaptive.get("capital_own")) if adaptive.get("capital_own") else None

    if capital_own is None:
        capital_diff_status = "not_specified"
        capital_diff = None
        capital_diff_pct = None
    else:
        capital_diff = capital_own - capex_needed
        capital_diff_pct = (capital_diff / capex_needed) if capex_needed else 0
        if capital_diff_pct >= 0.05:
            capital_diff_status = "surplus"
        elif capital_diff_pct >= -0.05:
            capital_diff_status = "match"
        elif capital_diff_pct >= -0.30:
            capital_diff_status = "deficit"
        else:
            capital_diff_status = "critical_deficit"

    return {
        "niche_id": niche_id,
        "niche_name_rus": niche_name_rus,
        "niche_icon": niche_icon,
        "format_id": format_id,
        "format_name_rus": format_name_rus,
        "class_level_rus": class_level or "стандарт",
        "area_m2": area_m2 if area_m2 > 0 and format_type not in ("HOME", "SOLO", "MOBILE") else 0,
        "area_visible": area_m2 > 0 and format_type not in ("HOME", "SOLO"),
        "location_rus": location_rus,
        "format_type": format_type,
        "is_solo": format_type in ("SOLO", "HOME") or not staff_list,
        "typical_staff": {
            "masters":    staff_groups["masters"],
            "assistants": staff_groups["assistants"],
            "total":      sum(s.get("count", 0) for s in staff_list),
        },
        "staff_after_entrepreneur": {
            "masters":    staff_after_groups["masters"],
            "assistants": staff_after_groups["assistants"],
            "total":      sum(s.get("count", 0) for s in staff_after),
        },
        "entrepreneur_role": {
            "id": ent_role_id,
            "label_rus": ent["label_rus"],
            "description_rus": ent["description_rus"],
        },
        "finance": {
            "capital_own": capital_own,
            "capex_needed": capex_needed,
            "capital_diff": capital_diff,
            "capital_diff_status": capital_diff_status,
        },
        "payroll_type_rus": _payroll_label(adaptive.get("payroll_type")),
        "experience_rus": _experience_label(adaptive.get("experience")),
    }


# ═══════════════════════════════════════════════════════════════════════
# render_for_api — главная точка рендера (Этап 5)
# ═══════════════════════════════════════════════════════════════════════


# Ключи нового формата (block1..block10 + block_season + user_inputs),
# которые QuickCheckCalculator кладёт в calc_result. render_for_api
# копирует их поверх legacy-структуры.
_NEW_FORMAT_KEYS = (
    "block1", "block2", "block3", "block4", "block5", "block6",
    "block_season", "block8", "block9", "block10",
    "growth_scenarios", "capital_adequacy", "user_inputs",
)


def render_for_api(calc_result: "CalcResult") -> "QuickCheckResult":
    """Берёт calc_result от QuickCheckCalculator → возвращает финальный report для API.

    Структура report:
    - Legacy block_1..block_12 (через render_report_v4) — для PDF
    - Новый block1..block10 + block_season + user_inputs (из calc_result) — для UI
    - input, owner_economics, health (из render_report_v4)

    Порядок ключей сохраняется идентичным предыдущей реализации
    (когда render_report_v4 вызывался внутри calculator).
    """
    report = render_report_v4(calc_result)
    for k in _NEW_FORMAT_KEYS:
        if k in calc_result:
            report[k] = calc_result[k]
    return report


# ═══════════════════════════════════════════════════════════════════════
# render_report_v4 — legacy block_1..block_12 (для PDF и обратной совместимости)
# ═══════════════════════════════════════════════════════════════════════


def render_report_v4(result: dict) -> dict:
    """Генератор структурированных данных для отчёта Quick Check.
    14 блоков, дисклеймеры, пояснения, связка сценариев с маркетингом.
    Принимает result dict от run_quick_check_v3 → возвращает dict для фронтенда.

    Legacy формат block_1..block_12 (с подчёркиваниями) — используется PDF.
    Новый формат block1..block10 — оверлеится calculator'ом поверх.
    """
    inp = result.get("input", {})
    fin = result.get("financials", {})
    sf = result.get("staff", {})
    cap = result.get("capex", {})
    be = result.get("breakeven", {})
    sc = result.get("scenarios", {})
    tx = result.get("tax", {})
    vd = result.get("verdict", {})
    pr = result.get("products", [])
    ins = result.get("insights", [])
    mk = result.get("marketing", [])
    al = result.get("alternatives", [])
    mkt = result.get("market", {})
    comp = result.get("competitors", {})
    cf = result.get("cashflow", [])

    check_med = fin.get("check_med", 0)
    traffic_med = fin.get("traffic_med", 0)
    cogs_pct = fin.get("cogs_pct", 0.35)
    margin_pct = fin.get("margin_pct", 0.65)
    rent_month = fin.get("rent_month", 0)
    niche_id = inp.get("niche_id", "")
    format_id = inp.get("format_id", "")
    cls = inp.get("class", "") or inp.get("cls", "")
    city_name = inp.get("city_name", "")
    revenue_med = check_med * traffic_med * 30

    core_products = [p for p in pr if p.get("category") == "core"]
    upsell_products = [p for p in pr if p.get("category") == "upsell"]
    locomotive = core_products[0].get("product_name", "") if core_products else "Основная услуга"

    # Структура выручки 100%
    rev_struct = []
    for p in core_products:
        s = p.get("share_pct", 0)
        if s:
            rev_struct.append({"name": p.get("product_name", ""), "share": round(float(s) * 100), "type": "core"})
    ups_total = sum(float(p.get("upsell_check_pct", 0)) for p in upsell_products)
    if ups_total > 0:
        rev_struct.append({"name": "Допродажи", "share": round(ups_total * 100), "type": "upsell", "note": f"+{round(ups_total * 100)}% к чеку"})

    # Прямые расходы
    cogs_m = int(revenue_med * cogs_pct)
    loss_m = int(revenue_med * fin.get("loss_pct", 0.03))

    # Постоянные расходы
    fot_full = sf.get("fot_full_med", 0) or int(sf.get("fot_net_med", 0) * 1.175)
    utils = fin.get("utilities", 0)
    mkt_b = fin.get("marketing", 0)
    cons = fin.get("consumables", 0)
    soft = fin.get("software", 0)
    trans = fin.get("transport", 0)
    sez = fin.get("sez_month", 0)
    fixed = fot_full + rent_month + utils + mkt_b + cons + soft + trans + sez

    # CAPEX
    bk = cap.get("breakdown", {})
    capital = inp.get("capital", 0) or 0
    capex_total = cap.get("total", 0)
    inv_range = cap.get("investment_range", {})
    gap = capital - capex_total if capital > 0 else 0

    eq_notes = {
        'COFFEE': 'Кофемашина, кофемолка, холодильная витрина, блендер',
        'BAKERY': 'Печь конвекционная, тестомес, расстоечный шкаф, витрина',
        'DONER': 'Гриль вертикальный, фритюрница, холодильник, вытяжка',
        'PIZZA': 'Печь для пиццы, тестомес, холодильный стол',
        'SUSHI': 'Рисоварка, холодильная витрина, проф. ножи',
        'FASTFOOD': 'Гриль, фритюрница, тепловая витрина, вытяжка',
        'CANTEEN': 'Плита промышленная, пароконвектомат, мармит',
        'BARBER': 'Кресла барберские, зеркала, инструменты, стерилизатор',
        'MANICURE': 'Маникюрный стол, лампа UV/LED, фрезер',
        'LASH': 'Кушетка, лампа, пинцеты, материалы',
        'SUGARING': 'Кушетка, воскоплав, паста, расходники',
        'BROW': 'Кресло, лампа, инструменты, краски',
        'MASSAGE': 'Массажный стол, масла, полотенца',
        'DENTAL': 'Стом. кресло, бормашина, автоклав, рентген',
        'FITNESS': 'Тренажёры, свободные веса, кардио, зеркала',
        'CARWASH': 'АВД Kärcher, пылесос, пеногенератор, химия',
        'AUTOSERVICE': 'Подъёмник, компрессор, инструмент, диагностика',
        'TIRESERVICE': 'Шиномонтажный станок, балансировочный, компрессор',
        'GROCERY': 'Холодильники, стеллажи, касса, весы',
        'PHARMACY': 'Витрины, холодильник, касса, софт учёта',
        'FLOWERS': 'Холодильная камера, вёдра, упаковка',
        'FRUITSVEGS': 'Стеллажи, весы, холодильник, ящики',
        'CLEAN': 'Проф. пылесос Kärcher, парогенератор, моющий пылесос',
        'DRYCLEAN': 'Стиральная проф., сушильная, гладильный пресс',
        'REPAIR_PHONE': 'Паяльная станция, микроскоп, инструменты, запчасти',
        'KINDERGARTEN': 'Детская мебель, игрушки, посуда, спальное',
        'PVZ': 'Стеллажи, сканер, ПК, принтер этикеток',
        'SEMIFOOD': 'Тестомес, формовочный аппарат, морозильная камера',
        'CONFECTION': 'Миксер планетарный, духовой шкаф, формы',
        'WATERPLANT': 'Система обратного осмоса, бутыли, помпы',
        'TAILOR': 'Швейная машина, оверлок, утюг, манекен',
        'COMPCLUB': 'Игровые ПК, мониторы 144Hz, кресла, сеть',
        'FURNITURE': 'Форматно-раскроечный, фрезер, кромочник, дрели',
    }

    capex_items = []
    if bk.get("equipment"):
        capex_items.append({"name": "Оборудование", "amount": bk["equipment"], "note": eq_notes.get(niche_id, "Проф. оборудование")})
    if bk.get("renovation"):
        capex_items.append({"name": "Ремонт помещения", "amount": bk["renovation"]})
    if bk.get("furniture"):
        capex_items.append({"name": "Мебель и интерьер", "amount": bk["furniture"]})
    if bk.get("first_stock"):
        capex_items.append({"name": "Первый закуп", "amount": bk["first_stock"]})
    if bk.get("permits_sez"):
        capex_items.append({"name": "Разрешения и СЭЗ", "amount": bk["permits_sez"]})
    if bk.get("working_cap"):
        capex_items.append({"name": "Оборотный капитал", "amount": bk["working_cap"]})

    inv_min = inv_range.get("min", capex_total)
    inv_max = inv_range.get("max", capex_total)
    if capital > 0 and gap >= 0:
        budget_txt = f"Ваш бюджет {fmt(capital)} ₸ покрывает стартовые вложения {fmt(capex_total)} ₸. Остаток {fmt(gap)} ₸ рекомендуем сохранить как резерв."
    elif capital > 0:
        budget_txt = f"Стартовые вложения {fmt(capex_total)} ₸, ваш бюджет {fmt(capital)} ₸. Рассмотрите снижение класса или формат с меньшими вложениями."
    else:
        budget_txt = f"Потребуется инвестиций: от {fmt(inv_min)} до {fmt(inv_max)} ₸ (оборудование, ремонт, депозит аренды + резерв 3 мес.)."

    # Сценарии
    sc_descs = {
        "pess": {"label": "Пессимистичный", "color": "red",   "mkt_desc": "Минимум: Instagram сами + сарафан. Без вложений.", "mkt_budget": "0–15 тыс ₸/мес"},
        "base": {"label": "Базовый",        "color": "blue",  "mkt_desc": "Таргет, Reels, ведение соцсетей, базовый 2ГИС.",  "mkt_budget": "30–80 тыс ₸/мес"},
        "opt":  {"label": "Оптимистичный",  "color": "green", "mkt_desc": "Полный SMM, платный 2ГИС, продакшн, акции.",      "mkt_budget": "80–150 тыс ₸/мес"},
    }
    scenarios_out = []
    for k in ["pess", "base", "opt"]:
        s = sc.get(k, {})
        d = sc_descs[k]
        pb = s.get("окупаемость", {})
        scenarios_out.append({
            "key": k, "label": d["label"], "color": d["color"],
            "traffic": s.get("трафик_день", 0), "check": s.get("чек", 0),
            "revenue_year": s.get("выручка_год", 0),
            "profit_monthly": s.get("прибыль_среднемес", 0),
            "payback": pb.get("статус", ""),
            "mkt_desc": d["mkt_desc"], "mkt_budget": d["mkt_budget"],
        })

    # Налоги
    tax_rate = tx.get("rate_pct", 3)
    tax_oked = tx.get("oked", "")
    tax_txt = f"Рекомендуем {tx.get('regime', 'Упрощённую')}. ОКЭД {tax_oked} входит в перечень разрешённых. Для г. {city_name} ставка {tax_rate}%."
    if tx.get("nds_risk") and str(tx.get("nds_risk")) not in ['nan', 'Нет', '']:
        tax_txt += " При работе с юрлицами — они не смогут принять НДС к вычету."

    # Маркетинг
    main_ch = [{"channel": m.get("channel", ""), "effect": m.get("expected_effect", ""), "budget_month": m.get("budget_month", 0), "notes": m.get("notes", "")} for m in mk if m.get("priority") == "основной"]
    skip_ch = [m.get("channel", "") for m in mk if m.get("priority") == "не_нужен"]

    # Советы
    tips_inc = [t.get("insight_text", "") for t in ins if t.get("insight_type") == "lifehack" and str(t.get("insight_text", "")) != "nan"][:3]
    tips_risk = [t.get("insight_text", "") for t in ins if t.get("insight_type") == "risk" and str(t.get("insight_text", "")) != "nan"][:3]
    tips_err = [t.get("insight_text", "") for t in ins if t.get("insight_type") == "newbie_mistake" and str(t.get("insight_text", "")) != "nan"][:3]

    # Здоровье проекта
    health = []
    pb_m = sc.get("base", {}).get("окупаемость", {}).get("месяц")
    health.append({"name": "Окупаемость", "status": "green" if pb_m and pb_m <= 18 else "yellow" if pb_m and pb_m <= 30 else "red", "value": f"{pb_m} мес" if pb_m else ">30 мес"})
    gm = round((1 - cogs_pct) * 100)
    health.append({"name": "Маржинальность", "status": "green" if gm >= 60 else "yellow" if gm >= 40 else "red", "value": f"{gm}%"})
    cl = comp.get("уровень", 3)
    health.append({"name": "Конкуренция", "status": "green" if cl <= 2 else "yellow" if cl <= 3 else "red", "value": ["", "Низкая", "Низкая", "Средняя", "Высокая", "Очень высокая"][min(cl, 5)]})
    sp = be.get("запас_прочности_%", 0)
    health.append({"name": "Запас прочности", "status": "green" if sp >= 30 else "yellow" if sp >= 10 else "red", "value": f"{sp}%"})
    if capital > 0:
        health.append({"name": "Капитал", "status": "green" if gap >= 0 else "red", "value": "Достаточно" if gap >= 0 else f"Нехватка {fmt(abs(gap))} ₸"})
    else:
        health.append({"name": "Инвестиции", "status": "yellow", "value": f"от {fmt(inv_min)} ₸"})

    # Сезонность
    season = [{"month": c.get("кал_месяц", ""), "revenue": c.get("выручка", 0), "profit": c.get("прибыль", 0)} for c in cf[:12]]

    # Чеклист
    checklist = [{"item": "Регистрация ИП/ТОО", "done": False}, {"item": f"ОКЭД {tax_oked}", "done": False}]
    if sez > 0:
        checklist.append({"item": "СЭЗ (санитарное заключение)", "done": False})
        checklist.append({"item": "Медкнижки персонала", "done": False})

    return {
        "input": inp,
        "owner_economics": result.get("owner_economics", {}),
        "health": {"title": "Здоровье проекта", "indicators": health},
        "block_1": {
            "title": "На чём зарабатываете", "subtitle": "Структура выручки",
            "check_med": check_med, "traffic_med": traffic_med, "revenue_monthly": revenue_med,
            "locomotive": locomotive, "revenue_structure": rev_struct,
            "disclaimer": f"Средний чек {fmt(check_med)} ₸ — типовая корзина для класса «{cls}» в г. {city_name}. Локомотив: {locomotive}. ЦА: {mkt.get('target_audience', 'массовый потребитель')}, {mkt.get('age_range', '18-50')}, доход {mkt.get('income_level', 'средний')}.",
        },
        "block_2": {
            "title": "Прямые расходы", "subtitle": "Зависят от объёма продаж",
            "cogs_pct": round(cogs_pct * 100), "cogs_monthly": cogs_m, "loss_monthly": loss_m,
            "gross_profit": revenue_med - cogs_m, "gross_margin_pct": round((1 - cogs_pct) * 100),
            "disclaimer": f"Себестоимость ~{round(cogs_pct * 100)}% от выручки. Валовая маржа {round((1 - cogs_pct) * 100)}% — это ДО вычета аренды, зарплат, налогов.",
        },
        "block_3": {
            "title": "Постоянные расходы", "subtitle": "Платите каждый месяц",
            "items": [
                {"name": "ФОТ (зарплаты+налоги)", "amount": fot_full, "note": sf.get("positions", "")},
                {"name": "Аренда", "amount": rent_month},
                {"name": "Коммунальные", "amount": utils},
                {"name": "Маркетинг", "amount": mkt_b},
                {"name": "Расходники", "amount": cons},
                {"name": "Софт/касса", "amount": soft},
            ] + ([{"name": "СЭЗ", "amount": sez}] if sez > 0 else []),
            "total": fixed,
            "disclaimer": f"ФОТ включает чистую зарплату + налоги работодателя. Штат: {sf.get('positions', '')}.",
        },
        "block_4": {
            "title": "Стартовые вложения", "subtitle": "До открытия",
            "items": capex_items, "total": capex_total, "budget": capital, "gap": gap,
            "budget_text": budget_txt, "reserve_months": cap.get("reserve_months", 0),
            "investment_min": inv_min, "investment_max": inv_max,
        },
        "block_5": {
            "title": "Три сценария", "subtitle": "Прогноз на 12 месяцев",
            "scenarios": scenarios_out,
            "disclaimer": "Маркетинговый бюджет и качество продвижения определяют сценарий. Реклама играет огромную роль наряду с качеством продукта.",
        },
        "block_6": {
            "title": "Точка безубыточности", "subtitle": "Минимум чтобы выйти в ноль",
            "tb_revenue": be.get("тб_₸", 0), "tb_checks_day": be.get("тб_чеков_день", 0),
            "safety_margin": be.get("запас_прочности_%", 0),
            "disclaimer": f"При чеке {fmt(check_med)} ₸ нужно минимум {be.get('тб_чеков_день', 0)} клиентов/день чтобы покрыть все расходы ({fmt(fixed)} ₸/мес).",
        },
        "block_7": {"title": "Налоги", "text": tax_txt, "regime": tx.get("regime", ""), "rate_pct": tax_rate},
        "block_8": {
            "title": "Как продвигать", "main": main_ch, "skip": skip_ch,
            "disclaimer": "Бюджет на маркетинг определяет сценарий. Пессимист = 0. Базовый = 30-80 тыс. Оптимист = 80-150 тыс.",
        },
        "block_9": {"title": "Полезные советы", "income": tips_inc, "risks": tips_risk, "mistakes": tips_err},
        "block_10": {
            "title": "Выводы", "verdict_color": vd.get("color", "yellow"), "verdict_text": vd.get("text", ""),
            "reasons": vd.get("reasons", []), "alternatives": al,
            "next_steps": ["Проверьте локацию лично в часы пик", "Получите 3 предложения по аренде", "Уточните стоимость оборудования у 2-3 поставщиков"],
        },
        "block_11_season": {"title": "Сезонность", "data": season},
        "block_12_checklist": {"title": "Что оформить", "items": checklist},
    }
