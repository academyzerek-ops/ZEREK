"""api/loaders/city_loader.py — City data access.

Извлечено из engine.py в Этапе 2 рефакторинга.
Контракт: только чтение; никакой расчётной логики.
Константы `CITY_LEGACY_TO_CANON` / `CITY_CHECK_COEF` остаются в engine.py
до Этапа 3 (потом переедут в api/config.py).
"""
import logging
import os
import sys

# sys.path шим — чтобы импорт работал из pytest / отдельных скриптов
_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    AVG_SALARY_2025,
    AVG_SALARY_DEFAULT,
    CITY_CHECK_COEF,
    CITY_LEGACY_TO_CANON,
)

_log = logging.getLogger("zerek.city_loader")


def normalize_city_id(city_id):
    """Нормализует city_id (legacy ALA/ALMATY/almaty → canonical 'almaty').

    Если id не найден — возвращает как есть, чтобы не ломать вызывающий код.
    """
    if city_id is None:
        return city_id
    s = str(city_id).strip()
    return CITY_LEGACY_TO_CANON.get(s, s)


def get_city_check_coef(city_id):
    """Ценовой коэффициент города. База = 1.00 (Актобе)."""
    canon = normalize_city_id(city_id)
    return CITY_CHECK_COEF.get(canon, 1.00)


def get_city(db, city_id):
    """Строка города из `01_cities.xlsx` → dict.

    Возвращает {city_id, Город, Регион, Население всего (чел.)} если есть,
    иначе minimal dict с нулевым населением (не падает).
    """
    cid = normalize_city_id(city_id)
    if db.cities.empty or "city_id" not in db.cities.columns:
        _log.warning("cities df empty / no city_id column; fallback for %s", cid)
        return {"city_id": cid, "Город": cid, "Население всего (чел.)": 0}
    rows = db.cities[db.cities["city_id"] == cid]
    if rows.empty:
        _log.warning("city %s not found in cities df", cid)
        return {"city_id": cid, "Город": cid, "Население всего (чел.)": 0}
    return rows.iloc[0].to_dict()


def get_inflation_region(db, city_id):
    """Региональная инфляция (пока хардкод 10% для КЗ, см. engine.py:1460).

    TODO (Этап 7+): подключить реальный расчёт из 13_macro_dynamics.xlsx.
    Сейчас db.inflation читается, но результат не используется — сохраняем
    идентичное поведение для регрессии.
    """
    if not db.inflation.empty:
        _ = db.inflation[db.inflation.get("region_id", db.inflation.columns[0]) == city_id]
    return 10.0


def get_avg_salary(city_id):
    """Средняя зарплата по городу (из config/constants.yaml).

    Используется в Block 5 (region_note) для SOLO/HOME форматов.
    Возвращает AVG_SALARY_DEFAULT (430К) если город неизвестен.
    """
    canon = normalize_city_id(city_id)
    return int(AVG_SALARY_2025.get(canon) or AVG_SALARY_DEFAULT)
