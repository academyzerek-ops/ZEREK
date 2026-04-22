"""api/loaders/tax_loader.py — Tax data access (КЗ 2026).

Извлечено из engine.py в Этапе 2 рефакторинга.
Источник: `data/kz/05_tax_regimes.xlsx` + `config/constants.yaml`.
Контракт: только чтение, никакой расчётной логики.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    DEFAULT_TAX_RATE_PCT,
    FALLBACK_TAX_RATE_PCT,
    FOT_MULTIPLIER,
    MRP_2026,
    MZP_2026,
    NDS_RATE,
    OWNER_SOCIAL_BASE_MRP,
    OWNER_SOCIAL_RATE,
)
from loaders.city_loader import normalize_city_id  # noqa: E402

_log = logging.getLogger("zerek.tax_loader")


def get_city_tax_rate(db, city_id):
    """Ставка УСН в процентах для города из 05_tax_regimes.xlsx.

    Источник: лист `city_ud_rates_2026`, колонка `ud_rate_pct`.
    Фолбэк: `FALLBACK_TAX_RATE_PCT` (4%) если город не найден.
    """
    cid = normalize_city_id(city_id)
    if db.city_tax_rates.empty:
        _log.warning("city_tax_rates df empty; fallback %s%% for %s",
                     FALLBACK_TAX_RATE_PCT, cid)
        return FALLBACK_TAX_RATE_PCT
    rows = db.city_tax_rates[db.city_tax_rates["city_id"] == cid]
    if rows.empty:
        _log.warning("city %s not in city_tax_rates; fallback %s%%",
                     cid, FALLBACK_TAX_RATE_PCT)
        return FALLBACK_TAX_RATE_PCT
    return float(rows.iloc[0].get("ud_rate_pct", FALLBACK_TAX_RATE_PCT))


def get_key_params():
    """Ключевые константы КЗ 2026 → dict.

    Читается из `config/constants.yaml` при загрузке engine.py.
    Потребуется в Этапе 3 (pricing_service, verdict_service).
    """
    return {
        "mrp_2026": MRP_2026,
        "mzp_2026": MZP_2026,
        "nds_rate": NDS_RATE,
        "default_tax_rate_pct": DEFAULT_TAX_RATE_PCT,
        "fallback_tax_rate_pct": FALLBACK_TAX_RATE_PCT,
        "owner_social_rate": OWNER_SOCIAL_RATE,
        "owner_social_base_mrp": OWNER_SOCIAL_BASE_MRP,
        "fot_multiplier": FOT_MULTIPLIER,
    }
