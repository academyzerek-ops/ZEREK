"""api/loaders/competitor_loader.py — Competitor market data.

Извлечено из engine.py в Этапе 2 рефакторинга.
Источник: `data/kz/14_competitors.xlsx` (лист «Конкуренты по городам»).
Контракт: только чтение, никакой расчётной логики.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import _safe_float, _safe_int  # noqa: E402
from loaders.city_loader import normalize_city_id  # noqa: E402

_log = logging.getLogger("zerek.competitor_loader")

_FALLBACK = {
    "уровень": 3,
    "сигнал": "Нет данных о конкуренции",
    "кол_во": "н/д",
    "competitors_count": 0,
    "density_per_10k": 0.0,
    "лидеры": "",
}

_SIGNALS = {
    1: "🟢 Рынок свободен",
    2: "🟢 Есть место",
    3: "🟡 Нужна дифференциация",
    4: "🟠 Высокая конкуренция",
    5: "🔴 Рынок насыщен",
}


def get_competitors(db, niche_id, city_id):
    """Уровень насыщенности + число конкурентов + плотность на 10К жителей.

    Возвращает dict с полями:
    - уровень (1–5), сигнал (emoji + текст)
    - кол_во (raw строка из xlsx, может быть диапазон '20-30')
    - competitors_count (int, нижняя граница)
    - density_per_10k (float, колонка «на 10 000»)
    - лидеры (строка)
    """
    cid = normalize_city_id(city_id)
    if db.competitors.empty:
        _log.warning("competitors df empty; fallback for %s/%s", niche_id, cid)
        return dict(_FALLBACK)
    try:
        rows = db.competitors[
            (db.competitors["niche_id"] == niche_id) & (db.competitors["city_id"] == cid)
        ]
    except KeyError as e:
        _log.warning("competitors df missing column %s; fallback", e)
        return dict(_FALLBACK)
    if rows.empty:
        _log.warning("no competitors row for %s/%s; fallback", niche_id, cid)
        return dict(_FALLBACK)
    row = rows.iloc[0]
    sat = _safe_int(row.get("Уровень насыщения (1-5)"), 3)
    # «Кол-во конкурентов (оценка)» в xlsx — диапазон «20-30» или число.
    # Берём нижнюю границу как числовое значение.
    raw_count = row.get("Кол-во конкурентов (оценка)", "")
    count_int = 0
    try:
        s = str(raw_count).strip()
        if s and s.lower() != "nan":
            count_int = int(s.split("-")[0].strip()) if "-" in s else int(float(s))
    except Exception:
        count_int = 0
    density = _safe_float(row.get("Кол-во на 10 000 жителей"), 0.0)
    return {
        "уровень": sat,
        "сигнал": _SIGNALS.get(sat, ""),
        "кол_во": raw_count,
        "competitors_count": count_int,
        "density_per_10k": density,
        "лидеры": row.get("Лидеры рынка", ""),
    }
