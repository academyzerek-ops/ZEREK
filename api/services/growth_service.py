"""Growth scenarios service — блок «А что дальше?».

Читает `growth_scenarios` из `data/niches/{NICHE}_data.yaml` через niche_loader
и формирует готовый для фронта dict с двумя сценариями (стагнация/развитие),
5 факторами роста и CTA на FinModel.

Если у ниши нет `growth_scenarios` в YAML — возвращает None (блок не рендерится).
"""
from __future__ import annotations
import os
import sys
from typing import Any, Dict, Optional

# api/ в sys.path — повторяем паттерн других сервисов
_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from loaders.niche_loader import load_niche_yaml  # noqa: E402


# R12 Сессия 1: маппинг суффиксов xlsx-форматов на канон R12 для
# выбора description_by_format в growth_scenarios. Тот же словарь
# что в staff_paradox_service.
_FORMAT_SUFFIX_TO_R12 = {
    "_HOME":     "HOME",
    "_SOLO":     "SALON_RENT",
    "_STANDARD": "STUDIO",
    "_PREMIUM":  None,  # PREMIUM ≠ MALL_SOLO; в Сессии 4 будет переделан
}


def _r12_format_key(format_id: str) -> Optional[str]:
    fmt = (format_id or "").upper()
    for suffix, key in _FORMAT_SUFFIX_TO_R12.items():
        if fmt.endswith(suffix):
            return key
    return None


def compute_growth_block(
    niche_id: str,
    format_id: str = "",
    base_profit_monthly: int = 0,
) -> Optional[Dict[str, Any]]:
    """Блок «А что дальше?» на основе growth_scenarios из YAML ниши.

    R12 Сессия 1: development.description выбирается по format_id из
    development.description_by_format[KEY], где KEY = R12-канон
    (HOME/STUDIO/SALON_RENT/MALL_SOLO). Если для формата нет специфики —
    fallback на общий development.description_ru.

    - `base_profit_monthly` зарезервирован под будущую персонализацию
      outcomes по текущей прибыли.
    - Возвращает None если нет growth_scenarios в YAML.
    """
    data = load_niche_yaml(niche_id)
    if not data:
        return None
    growth = data.get("growth_scenarios")
    if not growth:
        return None

    stag = growth.get("stagnation") or {}
    dev = growth.get("development") or {}
    factors = growth.get("growth_factors") or []

    # R12 Сессия 1: format-specific «Рост».
    dev_default = (dev.get("description_ru", "") or "").strip()
    dev_by_format = dev.get("description_by_format") or {}
    r12_key = _r12_format_key(format_id)
    dev_description = (
        (dev_by_format.get(r12_key) or "").strip() if r12_key else ""
    ) or dev_default

    return {
        "stagnation": {
            "label": stag.get("label_ru", ""),
            "description": (stag.get("description_ru", "") or "").strip(),
            "outcome": stag.get("outcome_ru", ""),
            "warning": stag.get("warning_ru", ""),
        },
        "development": {
            "label": dev.get("label_ru", ""),
            "description": dev_description,
            "outcome_year2": dev.get("outcome_year2_ru", ""),
            "outcome_year3": dev.get("outcome_year3_ru", ""),
        },
        "growth_factors": [
            {
                "id": f.get("id", ""),
                "title": f.get("title_ru", ""),
                "body": (f.get("body_ru", "") or "").strip(),
                "universal": bool(f.get("universal", True)),
            }
            for f in factors
        ],
        # UX #3: finmodel_cta убран из growth_scenarios — CTA дублировался
        # с block10 в хвосте отчёта. Оставляем финальный в block10.
    }
