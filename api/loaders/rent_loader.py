"""api/loaders/rent_loader.py — Rent benchmark access.

Извлечено из engine.py в Этапе 2 рефакторинга.
Источник: `data/kz/11_rent_benchmarks.xlsx` (лист «Калькулятор для движка»).
Контракт: только чтение, никакой расчётной логики.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from loaders.city_loader import normalize_city_id  # noqa: E402

_log = logging.getLogger("zerek.rent_loader")

# Фолбэк ставок (₸/м² в месяц) — использовались в engine.py если xlsx пуст.
_RENT_FALLBACK_PER_M2 = 3000
_UTILITIES_FALLBACK_PER_M2 = 500


def get_rent_median(db, city_id, loc_type):
    """Медианная ставка аренды (₸/м²/мес) + коммунальные для города × типа локации.

    Возвращает tuple `(rent_per_m2_median, utilities_per_m2)`.
    Фолбэк `(3000, 500)` если данных нет.
    """
    cid = normalize_city_id(city_id)
    if db.rent.empty:
        _log.warning("rent df empty; fallback (%s, %s) for %s/%s",
                     _RENT_FALLBACK_PER_M2, _UTILITIES_FALLBACK_PER_M2, cid, loc_type)
        return (_RENT_FALLBACK_PER_M2, _UTILITIES_FALLBACK_PER_M2)
    try:
        df = db.rent
        rows = df[(df["city_id"] == cid) & (df["loc_type"] == loc_type)]
        if rows.empty:
            rows = df[df["city_id"] == cid]
        if rows.empty:
            _log.warning("rent row not found for %s/%s; fallback", cid, loc_type)
            return (_RENT_FALLBACK_PER_M2, _UTILITIES_FALLBACK_PER_M2)
        r = rows.iloc[0]
        return (
            int(r.get("rent_per_m2_median", _RENT_FALLBACK_PER_M2)),
            int(r.get("utilities_per_m2", _UTILITIES_FALLBACK_PER_M2)),
        )
    except KeyError as e:
        _log.warning("rent df missing column %s; fallback", e)
        return (_RENT_FALLBACK_PER_M2, _UTILITIES_FALLBACK_PER_M2)
