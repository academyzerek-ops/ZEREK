"""api/loaders/knowledge_loader.py — R12.6 единый загрузчик knowledge/.

Читает markdown-файлы с YAML frontmatter из `knowledge/` и возвращает
dict-структуры для движка. Backward-compatible: для ниш мигрированных
в knowledge/ (R12.6 пилот: MANICURE) возвращает структуру identical
с legacy YAML — engine не должен видеть разницу.

Публичные функции:
    load_knowledge_archetype(arch_id)     → dict совместимый с
                                              data/archetypes/*.yaml
    load_knowledge_niche(niche_id)        → dict совместимый с
                                              data/niches/{NICHE}_data.yaml
    load_knowledge_region(city_id)        → dict (frontmatter + body)
    load_knowledge_taxes(year=2026)       → dict (frontmatter + body)

Если knowledge/ файла нет — возвращает None. Вызывающий код в
niche_loader.py подхватывает None и фолбэчит на legacy YAML.

Парсер frontmatter: между двух `---` строк, парсится через yaml.safe_load.
Body парсится по секциям `## Section Name` для info_blocks_r12 (только
для ниш — в R12.6 пилоте только MANICURE).
"""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

_log = logging.getLogger("zerek.knowledge_loader")

_API_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _API_DIR.parent
_KNOWLEDGE_DIR = _REPO_ROOT / "knowledge"

# In-process кеши — knowledge/-файлы парсятся 1 раз за процесс.
_ARCH_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_NICHE_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_REGION_CACHE: Dict[str, Optional[Dict[str, Any]]] = {}
_TAXES_CACHE: Dict[int, Optional[Dict[str, Any]]] = {}


_FRONTMATTER_PAT = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[Optional[Dict[str, Any]], str]:
    """Извлекает YAML frontmatter + остаток body. (None, full_text) если
    frontmatter не найден.
    """
    if not text:
        return None, ""
    m = _FRONTMATTER_PAT.match(text)
    if not m:
        return None, text
    try:
        import yaml
    except ImportError:
        _log.warning("PyYAML not installed; cannot parse frontmatter")
        return None, text
    try:
        fm = yaml.safe_load(m.group(1))
    except Exception as exc:  # noqa: BLE001
        _log.warning("frontmatter parse failed: %s", exc)
        return None, text
    return fm or {}, m.group(2)


_SECTION_HEADER_PAT = re.compile(r"^(#{1,6})\s+(.+?)\s*$", re.MULTILINE)


def _parse_body_sections(body: str) -> Dict[str, str]:
    """Разбивает markdown body на секции по заголовкам `## Section`.

    Возвращает {section_title: section_text}. Заголовки # / ## / ###
    нормализуются по уровню — берём только верхний уровень (## ).
    """
    if not body:
        return {}
    sections: Dict[str, str] = {}
    matches = list(_SECTION_HEADER_PAT.finditer(body))
    for i, m in enumerate(matches):
        level = len(m.group(1))
        if level != 2:  # только ## — игнорируем ### и #
            continue
        title = m.group(2).strip()
        start = m.end()
        # До следующего ## заголовка того же или верхнего уровня
        end = len(body)
        for nxt in matches[i + 1:]:
            if len(nxt.group(1)) <= 2:
                end = nxt.start()
                break
        sections[title] = body[start:end].strip()
    return sections


# ═══════════════════════════════════════════════════════════════════════
# ARCHETYPE
# ═══════════════════════════════════════════════════════════════════════

# Маппинг внутренний (legacy) → файл в knowledge/.
_ARCHETYPE_FILE_MAP = {
    "a1": "A1_BEAUTY_SOLO.md",
}


def load_knowledge_archetype(archetype_id: str) -> Optional[Dict[str, Any]]:
    """Читает knowledge/archetypes/{ID}.md и возвращает frontmatter dict
    в формате совместимом с legacy data/archetypes/*.yaml.

    Возвращает None если файла нет.
    """
    aid = (archetype_id or "").lower()
    if aid in _ARCH_CACHE:
        return _ARCH_CACHE[aid]
    fname = _ARCHETYPE_FILE_MAP.get(aid)
    if not fname:
        _ARCH_CACHE[aid] = None
        return None
    path = _KNOWLEDGE_DIR / "archetypes" / fname
    if not path.exists():
        _ARCH_CACHE[aid] = None
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to read %s: %s", path, exc)
        _ARCH_CACHE[aid] = None
        return None
    fm, _body = _parse_frontmatter(text)
    if fm is None:
        _ARCH_CACHE[aid] = None
        return None
    # Архетип уже в нужном формате — возвращаем frontmatter напрямую
    _ARCH_CACHE[aid] = fm
    return fm


# ═══════════════════════════════════════════════════════════════════════
# NICHE
# ═══════════════════════════════════════════════════════════════════════


def _convert_niche_to_legacy(fm: Dict[str, Any], body_sections: Dict[str, str]) -> Dict[str, Any]:
    """Конвертирует knowledge/niches/{NICHE}.md frontmatter → legacy
    YAML структура data/niches/{NICHE}_data.yaml.

    Engine читает legacy-формат, поэтому переводим:
      · `formats[X]` → `formats_r12[]` (R12.5 канон, который читает
        `_apply_r12_5_overrides` в engine).
      · `formats[X].capex_items.equipment: 150000` → `{equipment: {med: 150000}}`
      · `formats[X].marketing_phases.ramp_m1_m3` → `marketing_phases.ramp_m1_m3_base`
      · `formats[X].levels.simple.capex_extras.{furniture,renovation,marketing_start}`
          → `levels.simple.capex_furniture_extra`, `capex_renovation_extra`,
            `capex_marketing_start_extra`
      · `formats[X].levels.standard.capex_overrides.{equipment,marketing_start}`
          → `levels.standard.capex_equipment`, `capex_marketing_start`
      · SALON_RENT: `levels.standard.capex_base_total` → top-level
        `capex_base_total_standard`/`_premium`; `marketing_phases` уровней
        → `marketing_phases_standard`/`marketing_phases_premium` сверху.
      · `seasonality.s01..s12` → `pattern: [s01, ..., s12]` + сохраняем
        s01..s12 в fin для совместимости.
      · `info_blocks_r12` собирается из markdown body (секций
        «### Про материалы», «### Две модели аренды», «### Сценарий
        стойки»).

    Возвращает legacy-эквивалентный dict.
    """
    out: Dict[str, Any] = {}

    # ── Метаданные ниши ──
    if "id" in fm:
        out["id"] = fm["id"]
    if "name_rus" in fm:
        out["niche_name"] = fm["name_rus"]
    if "icon" in fm:
        out["icon"] = fm["icon"]
    if "archetype" in fm:
        out["archetype"] = fm["archetype"]
    if "available" in fm:
        out["available"] = fm["available"]

    # ── Сезонность ──
    if "seasonality" in fm:
        s = fm["seasonality"] or {}
        pattern = [float(s.get(f"s{m:02d}", 1.0)) for m in range(1, 13)]
        out["seasonality"] = {"pattern": pattern}
        if "best_start_months" in fm:
            out["seasonality"]["best_start_months"] = fm["best_start_months"]
        if "worst_start_months" in fm:
            out["seasonality"]["worst_start_months"] = fm["worst_start_months"]

    # ── Форматы → formats_r12 (канон R12.5 для engine) ──
    formats_r12: List[Dict[str, Any]] = []
    fmts = fm.get("formats") or {}
    for fmt_id, fmt_data in fmts.items():
        r12 = _convert_format_to_r12(fmt_id, fmt_data)
        if r12:
            formats_r12.append(r12)
    if formats_r12:
        out["formats_r12"] = formats_r12

    # ── Risks (плоский список) ──
    if "risks_table" in fm:
        out["risks_table"] = fm["risks_table"]

    # ── Growth scenarios ──
    if "growth_scenarios" in fm:
        out["growth_scenarios"] = fm["growth_scenarios"]

    # ── info_blocks_r12 — извлекаем из markdown body ──
    info_blocks = _extract_info_blocks_from_body(body_sections)
    if info_blocks:
        out["info_blocks_r12"] = info_blocks

    return out


def _convert_format_to_r12(fmt_id: str, fmt: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Один формат new → legacy formats_r12 entry."""
    if not fmt:
        return None
    out: Dict[str, Any] = {"id": fmt_id}
    # Базовые поля
    if "label_rus" in fmt:
        out["label_ru"] = fmt["label_rus"]
    if "description_short" in fmt:
        out["description_short"] = fmt["description_short"]
    for k in ("available_for_experience", "working_days_per_month",
              "deposit_months", "utilities_per_month",
              "other_opex_per_month", "extra_payments_per_month",
              "cogs_pct", "tax_regime_id"):
        if k in fmt:
            out[k] = fmt[k]
    # base_check_astana → base_check.astana (для top-level форматов без уровней)
    if "base_check_astana" in fmt:
        out["base_check"] = {"astana": fmt["base_check_astana"]}
    # MALL_SOLO: base_check_average_astana
    if fmt_id == "MALL_SOLO" and "base_check_astana" in fmt:
        out["base_check_average_astana"] = fmt["base_check_astana"]
    # Аренда HOME: rent_per_month=0 (legacy — топ-уровень для HOME); STUDIO/MALL_SOLO — rent_per_month_astana
    if "rent_per_month_astana" in fmt:
        out["rent_per_month_astana"] = fmt["rent_per_month_astana"]
    elif fmt_id == "HOME":
        out["rent_per_month"] = 0
    # CAPEX items: новый плоский → legacy {key: {med: val}}
    if "capex_items" in fmt:
        items = {}
        for k, v in (fmt["capex_items"] or {}).items():
            items[k] = {"med": int(v)}
        # SALON_RENT хранит общие items в capex_items_common
        if fmt_id == "SALON_RENT":
            out["capex_items_common"] = items
        else:
            out["capex_items"] = items
    if "capex_base_total" in fmt:
        # SALON_RENT — capex_base_total per уровню (см. levels ниже)
        if fmt_id != "SALON_RENT":
            out["capex_base_total"] = fmt["capex_base_total"]
    # Marketing phases (top-level): rampX → rampX_base
    if "marketing_phases" in fmt:
        mp = fmt["marketing_phases"] or {}
        out_mp = {}
        for src, dst in (("ramp_m1_m3", "ramp_m1_m3_base"),
                         ("tuning_m4_m6", "tuning_m4_m6_base"),
                         ("mature_m7_m12", "mature_m7_m12_base")):
            if src in mp:
                out_mp[dst] = mp[src]
        if out_mp:
            # Для SALON_RENT — фазы хранятся per уровню; для остальных — на формате.
            if fmt_id != "SALON_RENT":
                out["marketing_phases"] = out_mp

    # ── Levels — конвертируем в legacy-структуру по format_id ──
    levels_in = fmt.get("levels") or {}
    if levels_in:
        levels_out: Dict[str, Dict[str, Any]] = {}
        for lvl_id, lvl in levels_in.items():
            lvl_out: Dict[str, Any] = {}
            if "label_rus" in lvl:
                lvl_out["label_ru"] = lvl["label_rus"]
            if "description_short" in lvl:
                lvl_out["description_short"] = lvl["description_short"]
            if "base_check_astana" in lvl:
                lvl_out["base_check_astana"] = lvl["base_check_astana"]
            if "rent_per_month_astana" in lvl:
                lvl_out["rent_per_month_astana"] = lvl["rent_per_month_astana"]
            if "deposit_months" in lvl:
                lvl_out["deposit_months"] = lvl["deposit_months"]
            if "available_experience" in lvl:
                lvl_out["available_experience"] = lvl["available_experience"]
            # capex_extras (для STUDIO simple/nice) → capex_*_extra ключи
            extras = lvl.get("capex_extras") or {}
            for k, v in extras.items():
                lvl_out[f"capex_{k}_extra"] = int(v)
            # capex_overrides (для SALON_RENT standard/premium) → capex_<key>
            overrides = lvl.get("capex_overrides") or {}
            for k, v in overrides.items():
                lvl_out[f"capex_{k}"] = int(v)
            # SALON_RENT capex_base_total per-уровню → top-level capex_base_total_<lvl>
            if fmt_id == "SALON_RENT" and "capex_base_total" in lvl:
                out[f"capex_base_total_{lvl_id}"] = lvl["capex_base_total"]
            # SALON_RENT marketing_phases per-уровню → top-level marketing_phases_<lvl>
            if fmt_id == "SALON_RENT" and "marketing_phases" in lvl:
                mp = lvl["marketing_phases"] or {}
                top_mp = {}
                for src, dst in (("ramp_m1_m3", "ramp_m1_m3_base"),
                                 ("tuning_m4_m6", "tuning_m4_m6_base"),
                                 ("mature_m7_m12", "mature_m7_m12_base")):
                    if src in mp:
                        top_mp[dst] = mp[src]
                if top_mp:
                    out[f"marketing_phases_{lvl_id}"] = top_mp
            # STUDIO nice не имеет capex_*_extra на простой → 0 по умолчанию
            if fmt_id == "STUDIO" and lvl_id == "simple":
                lvl_out.setdefault("capex_furniture_extra", 0)
                lvl_out.setdefault("capex_renovation_extra", 0)
                lvl_out.setdefault("capex_marketing_start_extra", 0)
            levels_out[lvl_id] = lvl_out
        out["levels"] = levels_out

    # available_for_levels (флаг для UI — есть ли вообще уровни)
    out["available_for_levels"] = bool(levels_in)

    return out


def _extract_info_blocks_from_body(sections: Dict[str, str]) -> Dict[str, Dict[str, Any]]:
    """Из markdown body (секций) собирает info_blocks_r12 dict.

    Конвенция: внутри `## Информационные блоки PDF` ищем `### Про материалы`,
    `### Две модели аренды`, `### Сценарий стойки`. Привязываем к
    block_id по содержимому заголовка.
    """
    info_section = sections.get("Информационные блоки PDF") or ""
    if not info_section:
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    # Парсим под-секции `### Title (...)`
    sub_pat = re.compile(r"^###\s+(.+?)\s*$", re.MULTILINE)
    matches = list(sub_pat.finditer(info_section))
    for i, m in enumerate(matches):
        title_full = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(info_section)
        body = info_section[start:end].strip()
        # Убираем `>` блок-цитату — это контент info_block
        body_clean_lines = []
        for line in body.split("\n"):
            if line.startswith("> "):
                body_clean_lines.append(line[2:])
            elif line.strip() == ">":
                body_clean_lines.append("")
            elif line.startswith(">"):
                body_clean_lines.append(line[1:].lstrip())
            else:
                body_clean_lines.append(line)
        body_clean = "\n".join(body_clean_lines).strip()

        title_lower = title_full.lower()
        if "материал" in title_lower:
            out["materials"] = {
                "page": 7,
                "show_for_formats": ["STUDIO", "SALON_RENT", "MALL_SOLO"],
                "title_ru": "Про материалы",
                "body_ru": body_clean,
            }
        elif "аренд" in title_lower or "salon_rent" in title_lower or "модели аренды" in title_lower:
            out["salon_rent_models"] = {
                "page": 7,
                "show_for_formats": ["SALON_RENT"],
                "title_ru": "Две модели аренды в салоне",
                "body_ru": body_clean,
            }
        elif "стойк" in title_lower or "сценарий стойки" in title_lower:
            out["mall_solo_scenarios"] = {
                "page": 13,
                "show_for_formats": ["MALL_SOLO"],
                "title_ru": "Сценарий вашей стойки в ТЦ",
                "body_ru": body_clean,
            }
    return out


def _load_legacy_compat_yaml(niche_id: str) -> Dict[str, Any]:
    """R12.6 backward-compat: читает knowledge/niches/{NICHE}.legacy.yaml
    с legacy `formats:` блоком + рисками + failure_patterns.

    Это переходный файл — после миграции engine с legacy `formats:` на
    `formats_r12:` (R12.7+) можно удалить.

    Возвращает dict (возможно пустой). Не None.
    """
    path = _KNOWLEDGE_DIR / "niches" / f"{niche_id}.legacy.yaml"
    if not path.exists():
        return {}
    try:
        import yaml
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return data
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to load %s: %s", path, exc)
        return {}


def load_knowledge_niche(niche_id: str) -> Optional[Dict[str, Any]]:
    """Читает knowledge/niches/{NICHE}.md и возвращает legacy-dict.

    Возвращает None если файла нет (вызывающий fallback на legacy YAML).

    R12.6: дополнительно подмешивает поля из knowledge/niches/{NICHE}.legacy.yaml
    (legacy `formats:` блок, который ещё нужен engine — будет удалён в R12.7).
    """
    nid = (niche_id or "").upper()
    if nid in _NICHE_CACHE:
        return _NICHE_CACHE[nid]
    path = _KNOWLEDGE_DIR / "niches" / f"{nid}.md"
    if not path.exists():
        _NICHE_CACHE[nid] = None
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to read %s: %s", path, exc)
        _NICHE_CACHE[nid] = None
        return None
    fm, body = _parse_frontmatter(text)
    if fm is None:
        _NICHE_CACHE[nid] = None
        return None
    sections = _parse_body_sections(body)
    legacy = _convert_niche_to_legacy(fm, sections)
    # R12.6 backward-compat: подмешиваем legacy_formats / risks / failure_patterns
    compat = _load_legacy_compat_yaml(nid)
    if compat.get("legacy_formats"):
        legacy["formats"] = compat["legacy_formats"]
    if compat.get("risks"):
        legacy["risks"] = compat["risks"]
    if compat.get("failure_patterns"):
        legacy["failure_patterns"] = compat["failure_patterns"]
    if compat.get("expansion_options"):
        legacy["expansion_options"] = compat["expansion_options"]
    _NICHE_CACHE[nid] = legacy
    return legacy


# ═══════════════════════════════════════════════════════════════════════
# REGION
# ═══════════════════════════════════════════════════════════════════════


def load_knowledge_region(city_id: str) -> Optional[Dict[str, Any]]:
    """Читает knowledge/regions/{city}.md → frontmatter dict."""
    cid = (city_id or "").lower()
    if cid in _REGION_CACHE:
        return _REGION_CACHE[cid]
    path = _KNOWLEDGE_DIR / "regions" / f"{cid}.md"
    if not path.exists():
        _REGION_CACHE[cid] = None
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to read %s: %s", path, exc)
        _REGION_CACHE[cid] = None
        return None
    fm, _body = _parse_frontmatter(text)
    _REGION_CACHE[cid] = fm
    return fm


# ═══════════════════════════════════════════════════════════════════════
# TAXES
# ═══════════════════════════════════════════════════════════════════════


def load_knowledge_taxes(year: int = 2026) -> Optional[Dict[str, Any]]:
    """Читает knowledge/taxes/KZ_{year}.md → frontmatter dict."""
    if year in _TAXES_CACHE:
        return _TAXES_CACHE[year]
    path = _KNOWLEDGE_DIR / "taxes" / f"KZ_{year}.md"
    if not path.exists():
        _TAXES_CACHE[year] = None
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to read %s: %s", path, exc)
        _TAXES_CACHE[year] = None
        return None
    fm, _body = _parse_frontmatter(text)
    _TAXES_CACHE[year] = fm
    return fm


# ═══════════════════════════════════════════════════════════════════════
# Cache management (для тестов)
# ═══════════════════════════════════════════════════════════════════════


def _clear_caches():
    """Очистка кэшей. Для тестов."""
    _ARCH_CACHE.clear()
    _NICHE_CACHE.clear()
    _REGION_CACHE.clear()
    _TAXES_CACHE.clear()
