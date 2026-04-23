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


def compute_growth_block(
    niche_id: str,
    format_id: str = "",
    base_profit_monthly: int = 0,
) -> Optional[Dict[str, Any]]:
    """Блок «А что дальше?» на основе growth_scenarios из YAML ниши.

    - `format_id` и `base_profit_monthly` зарезервированы под будущую
      персонализацию outcomes по формату / текущей прибыли.
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

    return {
        "stagnation": {
            "label": stag.get("label_ru", ""),
            "description": (stag.get("description_ru", "") or "").strip(),
            "outcome": stag.get("outcome_ru", ""),
            "warning": stag.get("warning_ru", ""),
        },
        "development": {
            "label": dev.get("label_ru", ""),
            "description": (dev.get("description_ru", "") or "").strip(),
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
