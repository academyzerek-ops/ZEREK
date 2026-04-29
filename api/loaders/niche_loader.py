"""api/loaders/niche_loader.py — Ниши: метаданные, форматы, анкета.

Извлечено из engine.py в Этапе 2 рефакторинга. Самый большой loader:
объединяет чтение per-niche xlsx + 07_niches + 08_niche_formats +
09_surveys + YAML-конфигов.

Контракт: чтение источников и тривиальное структурирование (разбор
строк `typical_staff` вида 'барбер:4|админ:1' и т.п.). Расчётной
логики нет.

Источники:
- `data/kz/niches/niche_formats_{NICHE}.xlsx` (per-niche шаблоны)
- `data/kz/07_niches.xlsx` (adaptive-survey конфиг v2)
- `data/kz/08_niche_formats.xlsx` (канонические метаданные форматов)
- `data/kz/09_surveys.xlsx` (каталог вопросов / применимость / зависимости)
- `data/kz/niches_registry.yaml` — единый реестр ниш (синтезируется в db.configs["niches"])
- `config/archetypes.yaml`, `config/locations.yaml`,
  `config/questionnaire.yaml` (через db.configs)
- `data/niches/{NICHE}_data.yaml` (новый YAML-первый источник — Этап 7)
"""
import logging
import os
import sys

import pandas as pd

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

_REPO_ROOT = os.path.dirname(_API_DIR)

from engine import LOCATION_TYPES_META, _safe_float, _safe_int  # noqa: E402

_log = logging.getLogger("zerek.niche_loader")


# ═══════════════════════════════════════════════════════════════════════
# Базовая мета ниши
# ═══════════════════════════════════════════════════════════════════════


def _archetype_of(db, niche_id):
    """Архетип ниши (A/B/C/D/E/F) из data/kz/niches_registry.yaml.

    Возвращает пустую строку если ниши нет в реестре.
    """
    configs = getattr(db, "configs", {}) or {}
    return (
        ((configs.get("niches", {}) or {}).get("niches", {}) or {})
        .get(niche_id, {})
        .get("archetype", "")
    )


def _niche_name_from_registry(db, niche_id):
    """Русское название ниши из db.niche_registry (читается при _load_niches)."""
    info = db.niche_registry.get(niche_id, {})
    return info.get("name", niche_id)


def _get_canonical_format_meta(db, niche_id, format_id):
    """Канонические атрибуты формата из 08_niche_formats.xlsx.

    Возвращает {capex_standard, typical_staff, masters_count, area_m2,
    format_type, format_name}. Если запись не найдена — пустой dict.

    Источник истины для (a) CAPEX-бенчмарка и (b) «эталонного» кол-ва
    мастеров: per-niche xlsx может содержать несколько строк под одним
    format_id (разные варианты класса), и `get_format_row` всегда берёт
    первую. 08_niche_formats.xlsx даёт один канонический ориентир.
    """
    try:
        df = getattr(db, "niches_formats_fallback", None)
    except Exception:
        df = None
    if df is None or getattr(df, "empty", True):
        return {}
    try:
        rows = df[
            (df["niche_id"].astype(str) == niche_id)
            & (df["format_id"].astype(str) == format_id)
        ]
    except Exception:
        return {}
    if rows.empty:
        return {}
    r = rows.iloc[0]
    ts_raw = str(r.get("typical_staff", "") or "").strip()
    # Кол-во «мастеров» = первая группа в typical_staff (основная роль,
    # админы/ассистенты не считаются). Формат: 'роль:N|роль2:M'.
    masters_count = 0
    if ts_raw and ts_raw.lower() != "nan":
        first = ts_raw.split("|")[0]
        if ":" in first:
            try:
                masters_count = int(first.split(":", 1)[1].strip())
            except Exception:
                masters_count = 0
    return {
        "niche_id": niche_id,
        "format_id": format_id,
        "format_name": str(r.get("format_name", "") or ""),
        "capex_standard": _safe_int(r.get("capex_standard"), 0),
        "typical_staff": ts_raw if ts_raw.lower() != "nan" else "",
        "masters_count": masters_count,
        "area_m2": _safe_int(r.get("area_m2"), 0),
        "format_type": str(r.get("format_type", "") or ""),
    }


# ═══════════════════════════════════════════════════════════════════════
# Форматы (списки)
# ═══════════════════════════════════════════════════════════════════════


def _formats_from_per_niche_xlsx(db, niche_id):
    """Форматы из data/kz/niches/niche_formats_{NICHE}.xlsx (лист FORMATS)."""
    df = db.get_niche_sheet(niche_id, "FORMATS")
    if df.empty or "format_id" not in df.columns:
        return []
    cols = [
        c for c in ["format_id", "format_name", "area_m2", "loc_type",
                    "capex_standard", "class"]
        if c in df.columns
    ]
    return df[cols].drop_duplicates(subset=["format_id"]).to_dict("records")


def _formats_from_fallback_xlsx(db, niche_id):
    """Форматы из data/kz/08_niche_formats.xlsx, если per-niche xlsx пуст."""
    df = getattr(db, "niches_formats_fallback", pd.DataFrame())
    if df is None or df.empty or "niche_id" not in df.columns:
        return []
    rows = df[df["niche_id"].astype(str) == niche_id]
    if rows.empty:
        return []
    keep = [
        c for c in ["format_id", "format_name", "area_m2", "loc_type",
                    "capex_standard", "class"]
        if c in rows.columns
    ]
    return rows[keep].to_dict("records")


def get_formats_v2(db, niche_id):
    """Читает 08_niche_formats.xlsx и возвращает форматы ниши с расширенными
    полями (format_type, allowed_locations, typical_staff разбит в список)."""
    df = getattr(db, "niches_formats_fallback", pd.DataFrame())
    if df is None or df.empty or "niche_id" not in df.columns:
        return []
    rows = df[df["niche_id"].astype(str) == niche_id]
    out = []
    for _, r in rows.iterrows():
        staff_raw = str(r.get("typical_staff", "") or "").strip()
        staff = []
        if staff_raw and staff_raw.lower() != "nan":
            for chunk in staff_raw.split("|"):
                if ":" in chunk:
                    role, count = chunk.split(":", 1)
                    try:
                        staff.append({"role": role.strip(), "count": int(count.strip())})
                    except Exception:
                        pass
        allowed_raw = str(r.get("allowed_locations", "") or "").strip()
        allowed = (
            [a.strip() for a in allowed_raw.split(",")]
            if allowed_raw and allowed_raw not in ("auto", "nan")
            else []
        )
        out.append({
            "format_id":         str(r.get("format_id", "") or "").strip(),
            "format_name":       str(r.get("format_name", "") or "").strip(),
            "area_m2":           _safe_float(r.get("area_m2", 0)),
            "capex_standard":    _safe_int(r.get("capex_standard", 0)),
            "class":             str(r.get("class", "") or "").strip().lower(),
            "format_type":       str(r.get("format_type", "STANDARD") or "STANDARD").strip(),
            "allowed_locations": allowed if allowed_raw != "auto" else [],
            "auto_location":     allowed_raw == "auto",
            "typical_staff":     staff,
        })
    return [f for f in out if f["format_id"]]


# ═══════════════════════════════════════════════════════════════════════
# Адаптивная анкета v2
# ═══════════════════════════════════════════════════════════════════════


def _split_csv(val):
    """'a, b,c' → ['a','b','c']; пусто / NaN → []."""
    if val is None:
        return []
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _specific_questions_for_niche(db, niche_id, qids):
    """По списку question_id собирает полные определения вопросов."""
    out = []
    if not qids:
        return out
    df = getattr(db, "niches_questions", pd.DataFrame())
    if df is None or df.empty or "question_id" not in df.columns:
        return out
    for qid in qids:
        row = df[df["question_id"].astype(str) == qid]
        if row.empty:
            continue
        r = row.iloc[0]
        opts_raw = str(r.get("options", "")).strip()
        options = (
            [o.strip() for o in opts_raw.split("|")]
            if opts_raw and opts_raw.lower() != "nan" else []
        )
        out.append({
            "question_id": qid,
            "question_text": str(r.get("question_text", qid)).strip(),
            "options": options,
        })
    return out


def get_niche_config(db, niche_id):
    """Конфиг адаптивной анкеты Quick Check v2 для ниши.

    Агрегирует db.niches_config (07_niches.xlsx), per-niche xlsx формат и
    LOCATION_TYPES_META. Возвращает dict со всеми полями адаптивной анкеты.
    """
    cfg_df = getattr(db, "niches_config", pd.DataFrame())

    fallback_loc = ["street", "own_building"]
    config = {
        "niche_id": niche_id,
        "niche_name": _niche_name_from_registry(db, niche_id),
        "requires_license": "no",
        "license_description": "",
        "self_operation_possible": "no",
        "class_grades_applicable": "yes",
        "allowed_location_types": fallback_loc,
        "default_location_type": "street",
        "area_question_mode": "required",
        "staff_question_mode": "choice",
        "specific_questions": [],
        "formats": [],
        "location_types_meta": LOCATION_TYPES_META,
        "niche_notes": "",
    }

    if cfg_df is not None and not cfg_df.empty and "niche_id" in cfg_df.columns:
        rows = cfg_df[cfg_df["niche_id"].astype(str) == niche_id]
        if not rows.empty:
            r = rows.iloc[0]
            allowed = _split_csv(r.get("allowed_location_types", ""))
            default_loc = str(r.get("default_location_type", "") or "").strip() or (
                allowed[0] if allowed else "street"
            )
            qids = _split_csv(r.get("specific_questions_ids", ""))
            name_override = str(r.get("niche_name", "") or "").strip()
            config.update({
                "niche_name": name_override or config["niche_name"],
                "requires_license": str(r.get("requires_license", "no") or "no").strip(),
                "license_description": str(r.get("license_description", "") or "").strip(),
                "self_operation_possible": str(r.get("self_operation_possible", "no") or "no").strip(),
                "class_grades_applicable": str(r.get("class_grades_applicable", "yes") or "yes").strip(),
                "allowed_location_types": allowed or fallback_loc,
                "default_location_type": default_loc,
                "area_question_mode": str(r.get("area_question_mode", "required") or "required").strip(),
                "staff_question_mode": str(r.get("staff_question_mode", "choice") or "choice").strip(),
                "specific_questions": _specific_questions_for_niche(db, niche_id, qids),
                "niche_notes": str(r.get("niche_notes", "") or "").strip(),
            })

    # Форматы: сначала per-niche xlsx (реальные данные движка), потом fallback-каталог.
    formats = _formats_from_per_niche_xlsx(db, niche_id)
    if not formats:
        formats = _formats_from_fallback_xlsx(db, niche_id)

    # Нормализуем поля
    normalized = []
    for f in formats:
        normalized.append({
            "format_id": str(f.get("format_id", "")).strip(),
            "name": str(f.get("format_name", "") or "").strip(),
            "area_m2": _safe_float(f.get("area_m2", 0)),
            "loc_type": str(f.get("loc_type", "") or "").strip(),
            "capex_standard": _safe_int(f.get("capex_standard", 0)),
            "class": str(f.get("class", "") or "").strip().lower(),
        })
    config["formats"] = [f for f in normalized if f["format_id"]]

    # Отфильтруем location_types_meta до только разрешённых типов
    allowed_types = set(config["allowed_location_types"])
    config["location_types_meta"] = {
        k: v for k, v in LOCATION_TYPES_META.items() if k in allowed_types
    }

    return config


# ═══════════════════════════════════════════════════════════════════════
# Survey (per-niche question list) — 09_surveys.xlsx
# ═══════════════════════════════════════════════════════════════════════


def _question_to_dict(row):
    """Превращает строку из листа «Вопросы» в JSON-friendly dict."""
    opts_raw = str(row.get("options", "") or "").strip()
    options = (
        [o.strip() for o in opts_raw.split("|")]
        if opts_raw and opts_raw.lower() != "nan" else []
    )

    def num(v):
        try:
            return float(v) if v is not None and str(v).lower() != "nan" else None
        except Exception:
            return None

    return {
        "qid":          str(row.get("qid", "")).strip(),
        "question_text": str(row.get("question_text", "") or "").strip(),
        "input_type":   str(row.get("input_type", "") or "").strip(),
        "options":      options,
        "placeholder":  str(row.get("placeholder", "") or "").strip(),
        "min":          num(row.get("min")),
        "max":          num(row.get("max")),
        "step":         num(row.get("step")),
        "unit":         str(row.get("unit", "") or "").strip(),
        "help":         str(row.get("help", "") or "").strip(),
    }


def _dependencies_for(deps_df, qid):
    """Список зависимостей для qid из листа «Зависимости»."""
    if deps_df is None or deps_df.empty:
        return []
    rows = deps_df[deps_df["qid"].astype(str) == qid]
    out = []
    for _, r in rows.iterrows():
        out.append({
            "depends_on": str(r.get("depends_on", "") or "").strip(),
            "condition":  str(r.get("condition", "") or "").strip(),
            "action":     str(r.get("action", "") or "show").strip(),
        })
    return out


def get_entrepreneur_roles(typical_staff):
    """Из typical_staff ([{role,count}]) генерирует варианты роли предпринимателя."""
    if not typical_staff:
        return []
    staff_parts = [f"{s['count']} {s['role']}" for s in typical_staff]
    staff_list_text = " + ".join(staff_parts)
    opts = [
        {
            "id": "owner_only",
            "label_rus": f"Только владелец (нанимаю всех: {staff_list_text})",
            "fot_reduction_role": None,
        }
    ]
    unique_roles = []
    for s in typical_staff:
        if s["role"] not in unique_roles:
            unique_roles.append(s["role"])
    for role in unique_roles:
        opts.append({
            "id": f"owner_plus_{role}",
            "label_rus": f"Владелец + {role} (закрываю 1 ставку)",
            "fot_reduction_role": role,
        })
    if len(unique_roles) >= 2:
        opts.append({
            "id": "owner_multi",
            "label_rus": "Владелец работает на нескольких позициях",
            "fot_reduction_role": "multi",
        })
    return opts


def get_quickcheck_survey(db, niche_id, format_id=None):
    """Полная конфигурация Quick Check анкеты (8 вопросов) для ниши.

    Если format_id указан — добавляет резолвенные метаданные
    (entrepreneur_roles сгенерированные). Фронт применяет visibility logic
    на основе format_type.
    """
    configs = getattr(db, "configs", {})
    niches_cfg = configs.get("niches", {}).get("niches", {})
    archetypes_cfg = configs.get("archetypes", {}).get("archetypes", {})
    locations_cfg = configs.get("locations", {}).get("locations", {})
    questionnaire_cfg = configs.get("questionnaire", {}).get("questionnaire", {})
    qc_cfg = questionnaire_cfg.get("quickcheck", {})

    niche_meta = niches_cfg.get(niche_id, {})
    archetype = niche_meta.get("archetype", "")
    archetype_meta = archetypes_cfg.get(archetype, {})

    formats = get_formats_v2(db, niche_id)
    selected_format = None
    if format_id:
        for f in formats:
            if f["format_id"] == format_id:
                selected_format = f
                break

    entrepreneur_roles = []
    if selected_format:
        entrepreneur_roles = get_entrepreneur_roles(selected_format.get("typical_staff", []))

    return {
        "niche_id": niche_id,
        "niche_name": niche_meta.get("name_ru", niche_id),
        "archetype": archetype,
        "archetype_name": archetype_meta.get("name_rus", ""),
        "revenue_formula": archetype_meta.get("revenue_formula", ""),
        "category": niche_meta.get("category", ""),
        "icon": niche_meta.get("icon", ""),
        "questions": qc_cfg.get("questions", []),
        "formats": formats,
        "selected_format_id": format_id,
        "selected_format": selected_format,
        "entrepreneur_roles": entrepreneur_roles,
        "locations_meta": locations_cfg,
    }


def get_niche_survey(db, niche_id, tier="express"):
    """Упорядоченный список вопросов для ниши и tier (express|finmodel)."""
    tier = (tier or "express").lower()
    if tier not in ("express", "finmodel"):
        tier = "express"

    catalog = getattr(db, "surveys_questions", pd.DataFrame())
    applic = getattr(db, "surveys_applic", pd.DataFrame())
    deps = getattr(db, "surveys_deps", pd.DataFrame())

    out = {"niche_id": niche_id, "tier": tier, "questions": []}

    if catalog is None or catalog.empty or applic is None or applic.empty:
        return out

    # 1. Берём строки applicability для (niche, tier) или wildcard niche='*'
    mask = ((applic["niche_id"].astype(str) == niche_id) | (applic["niche_id"].astype(str) == "*")) \
           & (applic["tier"].astype(str) == tier)
    rows = applic[mask].copy()
    if rows.empty:
        return out

    # 2. Сортируем по order
    rows = rows.sort_values("order")

    # 3. Для каждой строки — подтягиваем из каталога метаданные вопроса
    catalog_idx = {str(r["qid"]).strip(): r for _, r in catalog.iterrows()}
    for _, ar in rows.iterrows():
        qid = str(ar.get("qid", "")).strip()
        cat_row = catalog_idx.get(qid)
        if cat_row is None:
            continue
        q = _question_to_dict(cat_row)
        q["order"] = int(ar.get("order") or 0)
        q["required"] = str(ar.get("required", "yes") or "yes").strip()
        q["depends_on"] = _dependencies_for(deps, qid)
        out["questions"].append(q)

    return out


# ═══════════════════════════════════════════════════════════════════════
# Niche-level inflation (19_inflation_by_niche.xlsx)
# ═══════════════════════════════════════════════════════════════════════


def get_inflation_niche(db, niche_id):
    """OPEX-инфляция ниши из 19_inflation_by_niche.xlsx.

    Возвращает строку dict или пустой dict если ниша не найдена.
    """
    df = getattr(db, "inflation_niche", pd.DataFrame())
    if df is None or df.empty or "niche_id" not in df.columns:
        return {}
    rows = df[df["niche_id"].astype(str) == niche_id]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


# ═══════════════════════════════════════════════════════════════════════
# YAML-first: data/niches/{NICHE}_data.yaml (Этап 7)
# ═══════════════════════════════════════════════════════════════════════


_YAML_CACHE = {}


# R12.5 Сессия 2: загрузчик архетипа A1 (универсальные параметры
# опыта/стратегий для всех соло-beauty ниш). Отдельный кеш чтобы не
# смешивать с per-niche YAML.
_ARCHETYPE_CACHE = {}


def load_archetype_yaml(archetype_id):
    """Читает архетип → dict (с кешем).

    R12.6: сначала пробует knowledge/archetypes/{ID}.md (новый канон),
    при отсутствии — fallback на data/archetypes/{id}_*.yaml (legacy).

    Возвращает `None` если архетип не найден ни там, ни там.

    R12.5 канон поддерживается только A1 (соло-beauty: маникюр, барбер,
    бровист, лэшмейкер, сахарист, массажист, косметолог). Параметры:
      experience_levels    (none / middle / experienced)
      marketing_strategies (conservative / middle / aggressive)
      antipatterns         (например novice_aggressive)
      explanation_blocks   (для опыта none — «почему ниже знакомых»)
    """
    aid = (archetype_id or "").lower()
    if aid in _ARCHETYPE_CACHE:
        return _ARCHETYPE_CACHE[aid]
    # R12.6: knowledge/-первая попытка
    try:
        from loaders.knowledge_loader import load_knowledge_archetype  # noqa: WPS433
        kn_data = load_knowledge_archetype(aid)
        if kn_data is not None:
            _ARCHETYPE_CACHE[aid] = kn_data
            return kn_data
    except ImportError:
        pass
    # A1 → a1_beauty_solo.yaml. Если в будущем появятся другие архетипы
    # (B/C/D...) — просто добавим маппинг здесь.
    file_map = {
        "a1": "a1_beauty_solo.yaml",
    }
    fname = file_map.get(aid)
    if not fname:
        _log.info("archetype YAML mapping not found for %s", aid)
        _ARCHETYPE_CACHE[aid] = None
        return None
    path = os.path.join(_REPO_ROOT, "data", "archetypes", fname)
    if not os.path.exists(path):
        _log.info("archetype YAML not found at %s", path)
        _ARCHETYPE_CACHE[aid] = None
        return None
    try:
        import yaml  # noqa: WPS433
    except ImportError:
        _log.warning("PyYAML not installed; cannot load %s", path)
        _ARCHETYPE_CACHE[aid] = None
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as exc:  # noqa: BLE001
        _log.warning("failed to parse %s: %s", path, exc)
        _ARCHETYPE_CACHE[aid] = None
        return None
    _ARCHETYPE_CACHE[aid] = data
    return data


def load_niche_yaml(niche_id):
    """Читает данные ниши → dict (с in-process кешем).

    Архитектура post-cleanup 2026-04-30:
      · `data/niches/<CODE>_data.yaml` — ИСТОЧНИК ИСТИНЫ для
        структурированных бизнес-данных (formats, formats_r12,
        seasonality, risks, growth_scenarios и т.п.).
      · `knowledge/niches/<CODE>.md` — текстовый материал + frontmatter-meta
        (name_ru, icon, archetype). Может содержать те же ключи, что и
        yaml (исторически), но при наличии yaml он ПОБЕЖДАЕТ.

    Логика:
      1. Читаем оба источника, если оба есть.
      2. Merge: knowledge как база, yaml перезаписывает все совпадающие
         ключи. Knowledge-only ключи (icon, etc.) сохраняются.
      3. Возвращаем `None` если ниша отсутствует и там, и там.
    """
    if niche_id in _YAML_CACHE:
        return _YAML_CACHE[niche_id]

    # Knowledge md (textual + meta)
    kn_data = None
    try:
        from loaders.knowledge_loader import load_knowledge_niche  # noqa: WPS433
        kn_data = load_knowledge_niche(niche_id)
    except ImportError:
        pass

    # data/niches yaml (structured canon)
    yml_data = None
    path = os.path.join(_REPO_ROOT, "data", "niches", f"{niche_id}_data.yaml")
    if os.path.exists(path):
        try:
            import yaml
            with open(path, "r", encoding="utf-8") as fh:
                yml_data = yaml.safe_load(fh) or None
        except ImportError:
            _log.warning("PyYAML not installed; cannot load %s", path)
        except Exception as e:
            _log.warning("failed to parse %s: %s", path, e)

    if kn_data is None and yml_data is None:
        _log.info("no niche data for %s (neither knowledge md nor data yaml)", niche_id)
        _YAML_CACHE[niche_id] = None
        return None
    if yml_data is None:
        _YAML_CACHE[niche_id] = kn_data
        return kn_data
    if kn_data is None:
        _YAML_CACHE[niche_id] = yml_data
        return yml_data

    # Both exist: merge with yaml priority on every common key.
    merged = dict(kn_data)
    for k, v in yml_data.items():
        merged[k] = v
    _YAML_CACHE[niche_id] = merged
    return merged


# ═══════════════════════════════════════════════════════════════════════
# YAML-first: маппер YAML format → flat-dict совместимый с xlsx-row
# ═══════════════════════════════════════════════════════════════════════


def _find_yaml_format(yaml_data, format_id, niche_id):
    """Находит YAML-секцию формата по format_id.

    format_id из xlsx — 'MANICURE_HOME', 'MANICURE_SOLO' и т.п.
    YAML id — 'HOME', 'SOLO', 'STANDARD', 'PREMIUM'.
    """
    if not yaml_data or not yaml_data.get("formats"):
        return None
    short = format_id.replace(f"{niche_id}_", "", 1)
    for f in yaml_data["formats"]:
        if f.get("id") == short:
            return f
    return None


# Маппинг YAML.tax_regime.type → русское название для xlsx-совместимости
_TAX_REGIME_MAP = {
    "ip_simplified": "Упрощёнка ИП",
    "too_simplified": "Упрощёнка ТОО",
    "too_oer": "ОУР ТОО",
}


def _map_yaml_to_financials(yaml_format, yaml_data):
    """YAML format → плоский dict совместимый с xlsx FINANCIALS row.

    Возвращает только non-None поля чтобы merge не затирал xlsx значения
    которых нет в YAML (например loss_pct, sez_month, utilities).
    """
    avg = yaml_format.get("avg_check", {}) or {}
    traffic = yaml_format.get("traffic", {}) or {}
    market = yaml_format.get("marketing", {}) or {}
    other = yaml_format.get("other_opex", {}) or {}
    ramp = yaml_format.get("ramp_up", {}) or {}
    seasonality = (yaml_data or {}).get("seasonality", {}) or {}
    pattern = seasonality.get("pattern") or []

    max_per_day = traffic.get("max_per_day")
    load_min = traffic.get("load_min")
    load_med = traffic.get("load_med")
    load_max = traffic.get("load_max")

    out = {
        "check_min": avg.get("min"),
        "check_med": avg.get("med"),
        "check_max": avg.get("max"),
        "cogs_pct": yaml_format.get("cogs_pct"),
        "marketing":     market.get("med_monthly"),
        "marketing_min": market.get("min_monthly"),
        "marketing_med": market.get("med_monthly"),
        "marketing_max": market.get("max_monthly"),
        "other_opex_min": other.get("min_monthly"),
        "other_opex_med": other.get("med_monthly"),
        "other_opex_max": other.get("max_monthly"),
        "rampup_months": ramp.get("months"),
        "rampup_start_pct": ramp.get("start_pct"),
    }
    # Traffic — берём только если в YAML есть max_per_day + соответствующий load
    if max_per_day is not None:
        if load_min is not None:
            out["traffic_min"] = int(round(max_per_day * load_min))
        if load_med is not None:
            out["traffic_med"] = int(round(max_per_day * load_med))
        if load_max is not None:
            out["traffic_max"] = int(round(max_per_day * load_max))
    # Сезонность s01..s12 — если pattern в YAML заполнен (12 значений)
    if len(pattern) == 12:
        for i in range(12):
            out[f"s{i+1:02d}"] = pattern[i]
    # Drop None
    return {k: v for k, v in out.items() if v is not None}


def _map_yaml_to_staff(yaml_format):
    """YAML format → плоский dict совместимый с xlsx STAFF row."""
    fot = yaml_format.get("fot", {}) or {}
    monthly = fot.get("monthly", 0)
    headcount = fot.get("headcount", 0)
    employer_pct = fot.get("employer_taxes_pct", 0.175)
    out = {
        "fot_net_med": monthly,
        "fot_full_med": int(monthly * (1 + employer_pct)) if monthly else 0,
        "headcount": headcount,
    }
    return out


def _map_yaml_to_capex(yaml_format):
    """YAML format → плоский dict совместимый с xlsx CAPEX row."""
    capex = yaml_format.get("capex", {}) or {}
    items = capex.get("items", {}) or {}
    base = capex.get("base_total", 0)

    def item_med(key):
        return (items.get(key, {}) or {}).get("med", 0)

    out = {
        "capex_min": int(base * 0.8) if base else 0,
        "capex_med": base,
        "capex_max": int(base * 1.3) if base else 0,
        "equipment":      item_med("equipment"),
        "renovation":     item_med("renovation"),
        "furniture":      item_med("furniture"),
        "first_stock":    item_med("first_stock"),
        "permits_sez":    item_med("permits"),
        "working_cap_3m": item_med("working_capital"),
        "marketing":      item_med("marketing_start"),
        "deposit":        item_med("deposit"),
        "legal":          item_med("legal"),
    }
    return {k: v for k, v in out.items() if v}  # drop zero/empty


def _map_yaml_to_formats(yaml_format):
    """YAML format → плоский dict совместимый с xlsx FORMATS row."""
    out = {
        "format_name": yaml_format.get("label_ru", ""),
        "training_required": bool(
            (yaml_format.get("capex", {}) or {}).get("training", {}).get("required", False)
        ),
    }
    rent = yaml_format.get("rent", {}) or {}
    if rent.get("area_m2"):
        out["area_med"] = rent["area_m2"]
    return {k: v for k, v in out.items() if v not in (None, "")}


def _map_yaml_to_taxes(yaml_format):
    """YAML format → плоский dict совместимый с xlsx TAXES row."""
    tax = yaml_format.get("tax_regime", {}) or {}
    return {
        "tax_regime": _TAX_REGIME_MAP.get(tax.get("type"), "Упрощёнка"),
    }


_SHEET_MAPPERS = {
    "FINANCIALS": _map_yaml_to_financials,
    "STAFF":      lambda fmt, _data: _map_yaml_to_staff(fmt),
    "CAPEX":      lambda fmt, _data: _map_yaml_to_capex(fmt),
    "FORMATS":    lambda fmt, _data: _map_yaml_to_formats(fmt),
    "TAXES":      lambda fmt, _data: _map_yaml_to_taxes(fmt),
}


# Форматы где xlsx — канон (баseline регрессии). YAML-overlay не применяется.
# В Этапе 7 это только MANICURE_HOME (откалиброван за 7 раундов и в baseline).
_YAML_SKIP_FORMATS = {"MANICURE_HOME"}


def overlay_yaml_on_xlsx(xlsx_row, niche_id, sheet, format_id, cls=None):
    """Накладывает YAML значения на xlsx-row для ниш с YAML-источником.

    Стратегия:
    - Не-MANICURE → xlsx как есть.
    - MANICURE_HOME → xlsx как есть (baseline регрессии, калиброван 7 раундов).
    - Остальные MANICURE форматы (SOLO/STANDARD/PREMIUM) → YAML-overlay
      поверх xlsx (xlsx часто NaN или некалиброван для этих форматов).

    Возвращает merged dict.
    """
    if niche_id != "MANICURE":
        return xlsx_row
    if format_id in _YAML_SKIP_FORMATS:
        return xlsx_row

    yaml_data = load_niche_yaml(niche_id)
    if not yaml_data:
        return xlsx_row

    yaml_format = _find_yaml_format(yaml_data, format_id, niche_id)
    if not yaml_format:
        return xlsx_row

    mapper = _SHEET_MAPPERS.get(sheet)
    if not mapper:
        return xlsx_row

    yaml_row = mapper(yaml_format, yaml_data)
    if not yaml_row:
        return xlsx_row

    merged = dict(xlsx_row) if xlsx_row else {}
    for k, v in yaml_row.items():
        merged[k] = v
    # Гарантируем format_id и class в результирующем dict (нужны движку)
    merged.setdefault("format_id", format_id)
    if cls and "class" not in merged:
        merged["class"] = cls
    return merged
