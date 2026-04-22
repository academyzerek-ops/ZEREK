"""api/loaders/content_loader.py — Контент ниши (риски, разрешения, инсайты).

Извлечено из engine.py в Этапе 2 рефакторинга.
Контракт: только чтение файлов/xlsx, никакой парсинг-логики.

Источники:
- `data/kz/15_failure_cases.xlsx` (get_failure_pattern)
- `data/kz/17_permits.xlsx` (get_permits)
- `knowledge/kz/niches/{NICHE}_insight.md` (load_insight_md)
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

# repo_root = worktree/  (3 уровня вверх от api/loaders/content_loader.py)
_REPO_ROOT = os.path.dirname(_API_DIR)

_log = logging.getLogger("zerek.content_loader")


def get_failure_pattern(db, niche_id):
    """Паттерн провалов ниши из 15_failure_cases.xlsx (одна строка, dict).

    Пустой dict если ниша не найдена — НЕ падает.
    """
    if db.failure_patterns.empty:
        return {}
    try:
        rows = db.failure_patterns[db.failure_patterns["niche_id"] == niche_id]
        if rows.empty:
            return {}
        return rows.iloc[0].to_dict()
    except KeyError as e:
        _log.warning("failure_patterns missing column %s", e)
        return {}


def get_permits(db, niche_id):
    """Разрешения и лицензии для ниши из 17_permits.xlsx → list[dict].

    Фильтр: `niche_id` содержит искомый ID, ИЛИ строка с niche_id='ALL'.
    Пустой list если данных нет.
    """
    if db.permits.empty:
        return []
    try:
        df = db.permits
        rows = df[df["niche_id"].str.contains(niche_id, na=False) | (df["niche_id"] == "ALL")]
        return rows.to_dict("records") if not rows.empty else []
    except KeyError as e:
        _log.warning("permits missing column %s", e)
        return []


def load_insight_md(niche_id):
    """Читает `knowledge/kz/niches/{NICHE}_insight.md` → str.

    Возвращает пустую строку если файла нет или чтение упало.
    Парсинг секций (риски, красные флаги и т.д.) — в risk_service (Этап 3).
    """
    path = os.path.join(_REPO_ROOT, "knowledge", "kz", "niches", f"{niche_id}_insight.md")
    if not os.path.exists(path):
        _log.info("insight.md not found for %s at %s", niche_id, path)
        return ""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception as e:
        _log.warning("failed to read %s: %s", path, e)
        return ""
