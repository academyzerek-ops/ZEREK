"""Tax constants loader — единый источник истины для налоговых ставок КЗ 2026.

Читает `data/external/kz_tax_constants_2026.yaml` один раз через @lru_cache и
возвращает значения по запросу. Любой код, которому нужны МРП/МЗП/ставки НДС/УСН —
читает ИЗ ЭТОГО loader, а не из констант в engine.py/config.yaml.

При изменении законодательства обновляем ТОЛЬКО YAML-файл. Никаких хардкодов.

Graceful degradation: если YAML не найден/битый — выбрасывается FileNotFoundError
с понятным сообщением (включая путь к файлу).
"""
from __future__ import annotations
import logging
import os
from functools import lru_cache
from typing import Any, Dict, Optional

_log = logging.getLogger("zerek.tax_constants_loader")

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_REPO_ROOT = os.path.dirname(_API_DIR)
_YAML_PATH = os.path.join(_REPO_ROOT, "data", "external", "kz_tax_constants_2026.yaml")


@lru_cache(maxsize=1)
def _load() -> Dict[str, Any]:
    """Читает YAML один раз за процесс (lru_cache). Выбрасывает при ошибке."""
    if not os.path.exists(_YAML_PATH):
        raise FileNotFoundError(
            f"Файл налоговых констант не найден. Проверьте {_YAML_PATH}"
        )
    try:
        import yaml
    except ImportError as e:
        raise RuntimeError(
            f"PyYAML не установлен — нужен для чтения {_YAML_PATH}: {e}"
        )
    try:
        with open(_YAML_PATH, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as e:
        raise RuntimeError(
            f"Файл налоговых констант битый: {_YAML_PATH}\n{e}"
        )
    if not isinstance(data, dict):
        raise RuntimeError(f"Неожиданный формат YAML в {_YAML_PATH}: ожидается dict")
    return data


def clear_cache() -> None:
    """Сброс кеша (для тестов/hot-reload)."""
    _load.cache_clear()


# ═══════════════════════════════════════════════════════════════════════
# Базовые показатели
# ═══════════════════════════════════════════════════════════════════════


def get_mrp() -> int:
    """МРП 2026 (месячный расчётный показатель), ₸. = 4 325."""
    return int(_load()["base_units"]["mrp"]["value"])


def get_mzp() -> int:
    """МЗП 2026 (минимальная заработная плата), ₸. = 85 000."""
    return int(_load()["base_units"]["mzp"]["value"])


# ═══════════════════════════════════════════════════════════════════════
# Минимальный платёж ИП за себя
# ═══════════════════════════════════════════════════════════════════════


def get_ip_minimum_monthly_payment() -> int:
    """Минимальный обязательный платёж ИП в месяц (ОПВ+ОПВР+СО+ВОСМС от 1 МЗП).

    = 21 675 ₸ для 2026 года. Используется для расчёта подушки безопасности
    (стартовый резерв = ×3 мес × этот платёж + прочие OPEX).
    """
    return int(_load()["ip_minimum_monthly_payment"]["total_kzt"])


def get_ip_minimum_components() -> Dict[str, int]:
    """Компоненты минимального платежа ИП: {opv, opvr, so, vosms} → суммы ₸/мес."""
    raw = _load()["ip_minimum_monthly_payment"]["components"]
    out: Dict[str, int] = {}
    for item in raw:
        if isinstance(item, dict):
            for k, v in item.items():
                out[k] = int(v)
    return out


# ═══════════════════════════════════════════════════════════════════════
# УСН (упрощёнка) по городам
# ═══════════════════════════════════════════════════════════════════════


def get_usn_rate_for_city(city_id: str) -> float:
    """Ставка УСН для города, % (например 3.0 для Астаны).

    Принимает city_id в любом регистре (astana / ASTANA / Astana).
    Если город не найден в YAML — возвращает базовую ставку (4.0%).
    """
    data = _load()["usn"]
    cities = data.get("municipality_rates") or {}
    key = (city_id or "").upper().strip()
    city_cfg = cities.get(key)
    if city_cfg and "rate_pct" in city_cfg:
        return float(city_cfg["rate_pct"])
    return float(data.get("default_rate_pct", 4.0))


def get_usn_base_rate() -> float:
    """Базовая ставка УСН (4%) — для городов без решения маслихата."""
    return float(_load()["usn"]["base_rate_pct"])


def get_usn_default_rate() -> float:
    """Ставка по умолчанию (используется в калькуляторе если город не найден)."""
    return float(_load()["usn"].get("default_rate_pct", 4.0))


# ═══════════════════════════════════════════════════════════════════════
# НДС
# ═══════════════════════════════════════════════════════════════════════


def get_nds_rate() -> float:
    """Ставка НДС 2026 в долях (0.16 = 16%)."""
    return float(_load()["nds"]["base_rate_pct"]) / 100.0


def get_nds_threshold_kzt() -> int:
    """Порог обязательной регистрации плательщиком НДС, ₸. = 43 250 000."""
    return int(_load()["nds"]["registration_threshold_kzt"])


# ═══════════════════════════════════════════════════════════════════════
# Зарплата / налоги работодателя
# ═══════════════════════════════════════════════════════════════════════


def get_employer_payroll_multiplier() -> float:
    """Множитель для брутто ФОТ: net × этот коэф = полная нагрузка на ФОТ.

    Считается из employee_payments: OPVR 3.5% + СО 5% + ООСМС 3% + соц.налог.
    На 2026 прикидочный коэффициент ≈ 1.115 (3.5 + 5 + 3 = 11.5% сверху net).
    """
    emp = _load()["employee_payments"]
    opvr = float(emp["opvr_employer"]["rate_pct"]) / 100.0
    so = float(emp["so_employee"]["rate_pct"]) / 100.0
    oosms = float(emp["oosms_employer"]["rate_pct"]) / 100.0
    return round(1.0 + opvr + so + oosms, 4)
