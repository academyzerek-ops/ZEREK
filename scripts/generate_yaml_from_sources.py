"""scripts/generate_yaml_from_sources.py — массовая генерация YAML по нишам.

Источники:
1. xlsx (data/kz/niches/niche_formats_*.xlsx + 08_niche_formats.xlsx) — числа
2. knowledge/kz/niches/{NICHE}_insight.md — риски, ошибки, ловушки
3. wiki/kz/ZEREK_*.html — формат, структура (минимально)

Вывод: data/niches/{NICHE}_data.yaml по структуре MANICURE_data.yaml.

Запуск:
    python3 scripts/generate_yaml_from_sources.py NICHE_ID
    python3 scripts/generate_yaml_from_sources.py --all
"""
import argparse
import math
import os
import re
import sys
from typing import Optional

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "api"))

from engine import ZerekDB  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data", "kz")
OUT_DIR = os.path.join(ROOT, "data", "niches")
INSIGHTS_DIR = os.path.join(ROOT, "knowledge", "kz", "niches")
WIKI_DIR = os.path.join(ROOT, "wiki", "kz")

# Защищённые YAML — не перезаписывать (MANICURE откалиброван вручную).
PROTECTED = {"MANICURE"}


# ═══════════════════════════════════════════════════════════════════════
# Хелперы конвертации
# ═══════════════════════════════════════════════════════════════════════


def _safe(v, default=None):
    """NaN/None → default. Pandas/numpy типы → Python primitives."""
    if v is None:
        return default
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return default
    if hasattr(v, "item"):
        v = v.item()
    if isinstance(v, str) and v.lower() in ("nan", ""):
        return default
    return v


def _safe_int(v, default=None):
    v = _safe(v, default)
    if v is None:
        return default
    try:
        return int(v)
    except (ValueError, TypeError):
        return default


def _safe_float(v, default=None):
    v = _safe(v, default)
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def _format_short_id(format_id, niche_id):
    """MANICURE_HOME → HOME, BARBER_STANDARD → STANDARD."""
    if not isinstance(format_id, str):
        return str(format_id) if format_id is not None else ""
    prefix = f"{niche_id}_"
    return format_id[len(prefix):] if format_id.startswith(prefix) else format_id


# ═══════════════════════════════════════════════════════════════════════
# Маппинг tax_regime → YAML type
# ═══════════════════════════════════════════════════════════════════════


def _tax_type(tax_regime_str):
    """'Упрощённая (3%)' → 'ip_simplified', 'ОУР' → 'too_oer'."""
    if not tax_regime_str or not isinstance(tax_regime_str, str):
        return "ip_simplified"
    s = tax_regime_str.lower()
    if "оур" in s or "ou" in s:
        return "too_oer"
    if "тоо" in s and "упрощ" in s:
        return "too_simplified"
    return "ip_simplified"


# ═══════════════════════════════════════════════════════════════════════
# Парсинг insight.md → список рисков
# ═══════════════════════════════════════════════════════════════════════


_RISK_HEADERS = (
    "Финансовые риски и ловушки",
    "Красные флаги",
    "Типичные ошибки новичков",
    "Операционные риски",
    "Риски",
    "Подводные камни",
    "Причины провала",
)


def parse_risks_from_insight(niche_id):
    """Извлекает риски из knowledge/kz/niches/{NICHE}_insight.md.

    Ищет секции по типичным заголовкам, парсит bullet-points с **жирным**
    заголовком в начале → структурный список с id/title/body.
    Возвращает list или [] если файла нет.
    """
    path = os.path.join(INSIGHTS_DIR, f"{niche_id}_insight.md")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    risks = []
    header_pat = (
        r"#+\s*(?:\d+\.\s*)?"
        r"(" + "|".join(_RISK_HEADERS) + r")"
    )
    section_pat = header_pat + r"[\s\S]*?(?=\n#+\s|\Z)"

    seen_titles = set()
    for m in re.finditer(section_pat, content, re.IGNORECASE):
        section = m.group(0)
        items = re.findall(
            r"(?:^|\n)[-*\d.]+\s+\*\*([^*]+)\*\*([\s\S]*?)(?=\n[-*\d.]+|\n#+|\Z)",
            section,
        )
        for title, body in items:
            title = title.strip().rstrip(".:")
            if title in seen_titles:
                continue
            seen_titles.add(title)
            body_text = re.sub(r"\n\s*", " ", body).strip()[:500]
            # Сгенерировать id из title (транслит-like)
            risk_id = re.sub(r"[^a-z0-9_]", "_", title.lower())[:40].strip("_")
            risks.append({
                "id": risk_id,
                "title_ru": title,
                "body_ru": body_text,
                "probability": "medium",
                "impact": "medium",
                "what_to_do_ru": "TODO: добавить рекомендацию",
            })
            if len(risks) >= 10:
                return risks
    return risks


# ═══════════════════════════════════════════════════════════════════════
# Сборка YAML format из xlsx-rows
# ═══════════════════════════════════════════════════════════════════════


def build_yaml_format(db, niche_id, format_id, cls):
    """Собирает один format-блок YAML из xlsx-rows."""
    fmt_row = db.get_format_row(niche_id, "FORMATS", format_id, cls) or {}
    fin_row = db.get_format_row(niche_id, "FINANCIALS", format_id, cls) or {}
    staff_row = db.get_format_row(niche_id, "STAFF", format_id, cls) or {}
    capex_row = db.get_format_row(niche_id, "CAPEX", format_id, cls) or {}
    tax_row = db.get_format_row(niche_id, "TAXES", format_id, cls) or {}

    fmt_short = _format_short_id(format_id, niche_id)
    loc_type_raw = _safe(fmt_row.get("loc_type"), "") or ""
    if not isinstance(loc_type_raw, str):
        loc_type_raw = ""
    needs_loc = bool(loc_type_raw and loc_type_raw not in ("дома", "home"))

    # Архетип формата → archetype YAML
    fmt_class_raw = _safe(fmt_row.get("class"), "") or ""
    fmt_class = fmt_class_raw.lower() if isinstance(fmt_class_raw, str) else ""
    size_desc_raw = _safe(fmt_row.get("size_desc"), "") or ""
    size_desc_lower = size_desc_raw.lower() if isinstance(size_desc_raw, str) else ""
    if fmt_short in ("HOME", "SOLO") or "соло" in fmt_class:
        archetype = "solo"
    elif fmt_class in ("эконом",) and "соло" not in size_desc_lower:
        archetype = "owner_works"
    else:
        archetype = "with_staff"

    # Legal form: ИП для self-employed, ТОО для STANDARD/PREMIUM
    legal_form = "ip" if archetype == "solo" else "too"

    out = {
        "id": fmt_short,
        "label_ru": _safe(fmt_row.get("format_name"), fmt_short),
        "description_short": _safe(fmt_row.get("size_desc"), "TODO: описание формата"),
        "archetype": archetype,
        "legal_form": legal_form,
        "needs_location": needs_loc,
        "avg_check": {
            "min": _safe_int(fin_row.get("check_min")),
            "med": _safe_int(fin_row.get("check_med")),
            "max": _safe_int(fin_row.get("check_max")),
            "currency": "KZT",
        },
        "traffic": {
            "max_per_day": _safe_int(fin_row.get("traffic_max")) or _safe_int(fin_row.get("traffic_med")),
            "load_med": 0.50,  # дефолт; xlsx не хранит load_pct отдельно
            "working_days_per_month": 26,
        },
        "capex": _build_capex_section(capex_row),
        "ramp_up": {
            "months": _safe_int(fin_row.get("rampup_months"), 3),
            "start_pct": _safe_float(fin_row.get("rampup_start_pct"), 0.30),
            "curve": "linear",
        },
        "marketing": {
            "med_monthly": _safe_int(fin_row.get("marketing_med")) or _safe_int(fin_row.get("marketing")),
            "min_monthly": _safe_int(fin_row.get("marketing_min")),
            "max_monthly": _safe_int(fin_row.get("marketing_max")),
        },
        "other_opex": {
            "med_monthly": _safe_int(fin_row.get("other_opex_med")),
            "min_monthly": _safe_int(fin_row.get("other_opex_min")),
            "max_monthly": _safe_int(fin_row.get("other_opex_max")),
        },
        "fot": _build_fot_section(staff_row),
        "cogs_pct": _safe_float(fin_row.get("cogs_pct"), 0.30),
        "tax_regime": {
            "type": _tax_type(tax_row.get("tax_regime")),
            "rate_pct": 3.0,  # default УСН; ОУР будет другим
        },
    }
    if needs_loc:
        out["rent"] = {
            "use_external_data": True,
            "area_m2": _safe_int(fmt_row.get("area_med")) or _safe_int(fmt_row.get("area_max")),
            "location_type_for_rent": _safe(fmt_row.get("loc_type"), "retail_first_line"),
        }
    return out


def _build_capex_section(capex_row):
    """CAPEX из xlsx → YAML section с items."""
    base_total = _safe_int(capex_row.get("capex_med"))
    items = {}
    item_keys = [
        ("equipment", "Оборудование"),
        ("renovation", "Ремонт"),
        ("furniture", "Мебель и интерьер"),
        ("first_stock", "Первый запас материалов"),
        ("permits_sez", "Разрешения и регистрация"),
        ("working_cap_3m", "Оборотные средства"),
        ("marketing", "Стартовый маркетинг"),
        ("deposit", "Депозит за аренду"),
        ("legal", "Юридическое оформление"),
    ]
    capex_to_yaml = {
        "permits_sez": "permits",
        "working_cap_3m": "working_capital",
        "marketing": "marketing_start",
    }
    for xls_key, label in item_keys:
        val = _safe_int(capex_row.get(xls_key))
        if val and val > 0:
            yaml_key = capex_to_yaml.get(xls_key, xls_key)
            items[yaml_key] = {"label_ru": label, "med": val}
    return {
        "base_total": base_total,
        "items": items,
        "training": {
            "required": False,  # default; для бьюти-ниш в ручной правке
            "amounts_by_experience": {"none": 0, "some": 0, "pro": 0},
        },
    }


def _build_fot_section(staff_row):
    """STAFF row → YAML fot."""
    fot_full = _safe_int(staff_row.get("fot_full_med"), 0)
    fot_net = _safe_int(staff_row.get("fot_net_med"), 0)
    headcount = _safe_int(staff_row.get("headcount"), 0)
    monthly = fot_full or int(fot_net * 1.175) if fot_net else 0
    return {
        "monthly": monthly,
        "headcount": headcount,
        "employer_taxes_pct": 0.175 if monthly else 0,
    }


# ═══════════════════════════════════════════════════════════════════════
# Главная функция: один YAML
# ═══════════════════════════════════════════════════════════════════════


_DEFAULT_SEASONALITY = [0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]


def build_niche_yaml(db, niche_id):
    """Собирает полный YAML-dict для ниши из всех источников."""
    # 1. Список форматов из FORMATS sheet (уникальные format_id)
    fmts_df = db.niche_data.get(niche_id, {}).get("FORMATS")
    if fmts_df is None or fmts_df.empty:
        # Нет xlsx — создаём пустой скелет
        return _build_skeleton_yaml(niche_id)

    seen_format_ids = set()
    formats = []
    for _, row in fmts_df.iterrows():
        fid = row.get("format_id")
        if not isinstance(fid, str) or not fid or fid in seen_format_ids:
            continue
        seen_format_ids.add(fid)
        cls_raw = _safe(row.get("class"), "стандарт") or "стандарт"
        cls = cls_raw if isinstance(cls_raw, str) else "стандарт"
        try:
            f_yaml = build_yaml_format(db, niche_id, fid, cls)
            formats.append(f_yaml)
        except Exception as e:
            print(f"  ⚠ {fid}: {e}", file=sys.stderr)

    # 2. Сезонность (s01..s12 первого формата с заполненными)
    seasonality = _extract_seasonality(db, niche_id)

    # 3. Риски из insight.md
    risks = parse_risks_from_insight(niche_id)

    return {
        "niche": {
            "id": niche_id,
            "name_ru": _niche_name_from_xlsx(db, niche_id) or niche_id.title(),
            "industry": _niche_industry(niche_id),
            "trend": "stable",
            "trend_note_ru": "TODO: добавить trend note",
        },
        "seasonality": seasonality,
        "formats": formats,
        "risks": risks,
        "meta": {
            "version": "0.1",
            "last_updated": "2026-04-23",
            "data_sources": [
                f"data/kz/niches/niche_formats_{niche_id}.xlsx",
                f"knowledge/kz/niches/{niche_id}_insight.md",
            ],
            "notes_ru": (
                "Авто-генерация скриптом scripts/generate_yaml_from_sources.py. "
                "TODO: ручная калибровка risks.what_to_do_ru, training, upsells, action_plan."
            ),
        },
    }


def _extract_seasonality(db, niche_id):
    """Берёт s01..s12 из первого FINANCIALS row с заполненными значениями."""
    fin_df = db.niche_data.get(niche_id, {}).get("FINANCIALS")
    if fin_df is None or fin_df.empty:
        return {"pattern": _DEFAULT_SEASONALITY}
    for _, row in fin_df.iterrows():
        pattern = []
        for m in range(1, 13):
            v = _safe_float(row.get(f"s{m:02d}"), 0.0)
            pattern.append(v if v and v > 0 else None)
        if all(p is not None for p in pattern):
            return {"pattern": [round(p, 2) for p in pattern]}
    return {"pattern": _DEFAULT_SEASONALITY}


def _niche_name_from_xlsx(db, niche_id):
    """Имя ниши из niche_registry."""
    reg = db.niche_registry.get(niche_id, {}) or {}
    return reg.get("name")


_INDUSTRY_BY_PREFIX = {
    # Beauty
    "MANICURE": "beauty", "BARBER": "beauty", "BROW": "beauty", "LASH": "beauty",
    "SUGARING": "beauty", "MASSAGE": "beauty", "COSMETOLOGY": "beauty",
    "BEAUTY": "beauty", "EPILATION": "beauty",
    # Food
    "BAKERY": "food", "COFFEE": "food", "CANTEEN": "food", "DONER": "food",
    "FASTFOOD": "food", "PIZZA": "food", "SUSHI": "food", "BUBBLETEA": "food",
    "CONFECTION": "food", "SEMIFOOD": "food", "CATERING": "food", "MEATSHOP": "food",
    # Retail
    "GROCERY": "retail", "PHARMACY": "retail", "FLOWERS": "retail",
    "FRUITSVEGS": "retail", "OPTICS": "retail", "PETSHOP": "retail",
    "AUTOPARTS": "retail", "BUILDMAT": "retail",
    # Health/Med
    "DENTAL": "medical", "HOTEL": "hospitality",
    # Auto
    "CARWASH": "auto", "AUTOSERVICE": "auto", "TIRESERVICE": "auto",
    "DETAILING": "auto", "REPAIR_PHONE": "services", "REPAIRPHONE": "services",
    # Services
    "CLEAN": "services", "DRYCLEAN": "services", "TAILOR": "services",
    "LAUNDRY": "services", "CARPETCLEAN": "services", "CARGO": "services",
    "PVZ": "services", "PHOTO": "services", "PRINTING": "services",
    "ACCOUNTING": "services", "NOTARY": "services", "REALTOR": "services",
    "EVALUATION": "services", "DRIVING": "services",
    # Education / kids
    "KINDERGARTEN": "education", "KIDSCENTER": "education",
    "FOOTBALLSCHOOL": "education", "LANGUAGES": "education",
    "MARTIALARTS": "education",
    # Fitness
    "FITNESS": "fitness", "YOGA": "fitness", "CROSSFIT": "fitness",
    "GROUPFITNESS": "fitness",
    # Tech / other
    "COMPCLUB": "entertainment", "WATERPLANT": "production",
    "FURNITURE": "production", "LOFTFURNITURE": "production",
}


def _niche_industry(niche_id):
    return _INDUSTRY_BY_PREFIX.get(niche_id, "services")


def _build_skeleton_yaml(niche_id):
    """Скелет YAML для ниши без xlsx-данных."""
    risks = parse_risks_from_insight(niche_id)
    return {
        "niche": {
            "id": niche_id,
            "name_ru": niche_id.title(),
            "industry": _niche_industry(niche_id),
            "trend": "stable",
            "trend_note_ru": "TODO: ниша без xlsx-данных, требуется калибровка с нуля",
        },
        "seasonality": {"pattern": _DEFAULT_SEASONALITY},
        "formats": [],  # TODO: ручная калибровка форматов
        "risks": risks,
        "meta": {
            "version": "0.0",
            "last_updated": "2026-04-23",
            "data_sources": [f"knowledge/kz/niches/{niche_id}_insight.md"],
            "notes_ru": (
                "СКЕЛЕТ — нет xlsx данных. Только риски из insight.md. "
                "TODO: добавить formats[] с avg_check/traffic/capex/fot."
            ),
        },
    }


# ═══════════════════════════════════════════════════════════════════════
# Запись YAML
# ═══════════════════════════════════════════════════════════════════════


def write_yaml(niche_id, data):
    """Сохраняет YAML с pretty-print (allow_unicode для русского)."""
    if niche_id in PROTECTED:
        print(f"  ⚠ {niche_id} защищён (PROTECTED) — не перезаписываем")
        return False
    out_path = os.path.join(OUT_DIR, f"{niche_id}_data.yaml")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# =============================================================================\n")
        f.write(f"# {niche_id}_data.yaml\n")
        f.write(f"# Auto-generated by scripts/generate_yaml_from_sources.py\n")
        f.write(f"# Версия: 0.1 | Дата: 2026-04-23\n")
        f.write(f"# =============================================================================\n\n")
        yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False, width=120)
    return True


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("niche", nargs="?", help="NICHE_ID или --all")
    parser.add_argument("--all", action="store_true", help="Все ниши из xlsx + insight")
    parser.add_argument("--list", action="store_true", help="Показать список ниш")
    args = parser.parse_args()

    db = ZerekDB(data_dir=DATA_DIR)

    # Список всех ниш = xlsx ∪ insight.md
    xlsx_niches = set(db.niche_registry.keys())
    insight_niches = set()
    for fn in os.listdir(INSIGHTS_DIR):
        if fn.endswith("_insight.md"):
            insight_niches.add(fn.replace("_insight.md", ""))
    all_niches = sorted(xlsx_niches | insight_niches)

    if args.list:
        for n in all_niches:
            xls = "✓" if n in xlsx_niches else "·"
            ins = "✓" if n in insight_niches else "·"
            print(f"  {n:<20} xlsx={xls} insight={ins}")
        return

    targets = []
    if args.all or (args.niche and args.niche.lower() == "--all"):
        targets = all_niches
    elif args.niche:
        targets = [args.niche.upper()]
    else:
        parser.print_help()
        return

    print(f"\nГенерация YAML для {len(targets)} ниш(и)...\n")
    written = 0
    skipped = 0
    failed = []
    for niche_id in targets:
        try:
            data = build_niche_yaml(db, niche_id)
            n_formats = len(data.get("formats", []))
            n_risks = len(data.get("risks", []))
            if write_yaml(niche_id, data):
                src = "xlsx" if niche_id in xlsx_niches else "insight-only"
                print(f"  ✅ {niche_id}: {n_formats} forms, {n_risks} risks ({src})")
                written += 1
            else:
                skipped += 1
        except Exception as e:
            print(f"  ❌ {niche_id}: {e}")
            failed.append(niche_id)

    print(f"\nИтог: {written} записано, {skipped} пропущено, {len(failed)} ошибок")
    if failed:
        print("Ошибки в:", ", ".join(failed))


if __name__ == "__main__":
    main()
