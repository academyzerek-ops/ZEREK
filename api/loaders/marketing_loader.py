"""Marketing loader — чтение marketing_archetypes_2026.yaml + CAC-таблицы.

YAML содержит 16 архетипов, 24 канала, 55 ниш с retention/drivers/channels.
BASE_CAC_KZT и CITY_CAC_MULTIPLIER сейчас захардкожены в loader — это v1.
Когда появятся реальные данные рекламных кампаний — вынесем в YAML отдельно.
"""
from __future__ import annotations
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

_log = logging.getLogger("zerek.marketing_loader")

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_API_DIR)
_YAML_PATH = os.path.join(_REPO_ROOT, "data", "external", "marketing_archetypes_2026.yaml")


# ═══════════════════════════════════════════════════════════════════════
# Базовый CAC по нишам (в тенге, Астана как референс, зрелый режим)
# v1 — калибруется по реальным рекламным кампаниям в будущем
# ═══════════════════════════════════════════════════════════════════════

BASE_CAC_KZT: Dict[str, int] = {
    # Beauty & Personal Care (A1)
    "MANICURE": 1200, "BARBER": 1000, "LASH": 1400, "BROW": 1200,
    "SUGARING": 1500, "MASSAGE": 1800, "COSMETOLOGY": 2500, "BEAUTY": 1500,
    # Impulse Food (A2)
    "COFFEE": 500, "BAKERY": 400, "BUBBLETEA": 600, "FASTFOOD": 400, "DONER": 400,
    # Food delivery (A3)
    "PIZZA": 800, "SUSHI": 1200, "SEMIFOOD": 900,
    # Urgent Health (A4)
    "DENTAL": 3500, "OPTICS": 2000, "VET": 1500,
    # Episodic Transactional (A6)
    "CARGO": 1000, "CARPETCLEAN": 1500,
    # Local Everyday (A7)
    "PHARMACY": 300, "DRYCLEAN": 800, "LAUNDRY": 500, "PVZ": 200,
    "PRINTING": 600, "CARWASH": 700, "TIRESERVICE": 1000, "AUTOSERVICE": 1500,
    "REPAIR_PHONE": 800, "TAILOR": 500,
    # Visual Gift (A8)
    "FLOWERS": 1000, "CONFECTION": 1500,
    # Staple Retail (A9)
    "GROCERY": 300, "MEATSHOP": 500, "FRUITSVEGS": 300, "PETSHOP": 700,
    # Subscription delivery (A10)
    "WATERPLANT": 2500,
    # High-Ticket (A11)
    "FURNITURE": 5000, "BUILDMAT": 3000, "AUTOPARTS": 2000, "PHOTO": 3000,
    "DETAILING": 2500, "DRIVING": 2500,
    # Subscription wellness & education (A12)
    "FITNESS": 2500, "YOGA": 2000, "LANGUAGES": 3000,
    "KINDERGARTEN": 5000, "KIDSCENTER": 2500,
    # B2B (A13)
    "CATERING": 8000, "ACCOUNTING": 5000,
    # Hospitality (A14)
    "HOTEL": 3000, "REALTOR": 10000,
    # Youth venue (A15)
    "COMPCLUB": 800,
    # Corporate canteen (A16)
    "CANTEEN": 500,
}

DEFAULT_CAC_FALLBACK = 1500


CITY_CAC_MULTIPLIER: Dict[str, float] = {
    "almaty": 1.3, "astana": 1.2, "shymkent": 0.9, "aktobe": 0.9,
    "karaganda": 0.9, "atyrau": 1.1, "oskemen": 0.85, "kostanay": 0.85,
    "pavlodar": 0.85, "uralsk": 0.85, "kyzylorda": 0.8, "taraz": 0.8,
    "semey": 0.85, "petropavl": 0.85, "kokshetau": 0.8, "turkestan": 0.8,
    "aktau": 1.0, "taldykorgan": 0.9, "konaev": 0.9, "zhezkazgan": 0.8,
}

DEFAULT_CITY_CAC_MULTIPLIER = 0.9


# ═══════════════════════════════════════════════════════════════════════
# YAML loader
# ═══════════════════════════════════════════════════════════════════════


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    """Читает YAML один раз (lru_cache). Raises FileNotFoundError если нет."""
    if not os.path.exists(_YAML_PATH):
        raise FileNotFoundError(
            f"Marketing archetypes file not found: {_YAML_PATH}"
        )
    import yaml
    with open(_YAML_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise RuntimeError(f"Invalid YAML format: {_YAML_PATH}")
    return data


def clear_cache() -> None:
    """Сброс кеша (для тестов)."""
    _load.cache_clear()


# ═══ Архетипы ═══════════════════════════════════════════════════════════


def get_archetype(archetype_id: str) -> Optional[Dict[str, Any]]:
    return _load().get("archetypes", {}).get(archetype_id)


def get_all_archetypes() -> Dict[str, Any]:
    return _load().get("archetypes", {}) or {}


# ═══ Каналы ═════════════════════════════════════════════════════════════


def get_channel(channel_id: str) -> Optional[Dict[str, Any]]:
    return _load().get("channels", {}).get(channel_id)


# ═══ Ниши ═══════════════════════════════════════════════════════════════


def get_niche_marketing(niche_id: str) -> Optional[Dict[str, Any]]:
    return _load().get("niches", {}).get((niche_id or "").upper())


def get_niche_archetype(niche_id: str) -> Optional[str]:
    data = get_niche_marketing(niche_id)
    return data.get("archetype") if data else None


def get_retention_metrics(niche_id: str) -> Optional[Dict[str, int]]:
    data = get_niche_marketing(niche_id)
    return data.get("retention_metrics") if data else None


def get_choice_drivers(niche_id: str) -> Optional[Dict[str, Any]]:
    data = get_niche_marketing(niche_id)
    return data.get("choice_drivers") if data else None


def get_channels_allocation(niche_id: str) -> Optional[Dict[str, Any]]:
    data = get_niche_marketing(niche_id)
    return data.get("channels") if data else None


def get_platform_dependency(niche_id: str) -> Optional[Dict[str, Any]]:
    data = get_niche_marketing(niche_id)
    return data.get("platform_dependency") if data else None


def niche_has_marketing_data(niche_id: str) -> bool:
    return (niche_id or "").upper() in (_load().get("niches") or {})


# ═══ CAC ════════════════════════════════════════════════════════════════


def get_base_cac(niche_id: str) -> int:
    return BASE_CAC_KZT.get((niche_id or "").upper(), DEFAULT_CAC_FALLBACK)


def get_city_cac_multiplier(city_id: str) -> float:
    return CITY_CAC_MULTIPLIER.get((city_id or "").lower(), DEFAULT_CITY_CAC_MULTIPLIER)


def get_real_cac(niche_id: str, city_id: str) -> float:
    return get_base_cac(niche_id) * get_city_cac_multiplier(city_id)
