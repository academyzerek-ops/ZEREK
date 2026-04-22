"""api/services/pricing_service.py — Расчёт соцплатежей и налогов.

Извлечено из engine.py в Этапе 3 рефакторинга.
Сервисы возвращают чистые числа, без UI-форматирования.

Зависит от: констант КЗ 2026 (MRP_2026, OWNER_SOCIAL_RATE,
OWNER_SOCIAL_BASE_MRP) — импортируются из engine до Этапа 3 финала,
потом переедут в api/config.py.

Что покрывает:
- calc_owner_social_payments — ОПВ + ОПВР + ОСМС + СО для ИП на упрощёнке

TODO (Этап 7+): build_tax_recommendation — логика выбора режима
(ИП-патент отменён с 01.01.2026, переход на «Самозанятый» / УСН).
В текущем engine.py отдельной функции нет, будет новый код.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    MRP_2026,
    OWNER_SOCIAL_BASE_MRP,
    OWNER_SOCIAL_RATE,
)

_log = logging.getLogger("zerek.pricing_service")


def calc_owner_social_payments(declared_monthly_base=None):
    """Обязательные соцплатежи ИП на Упрощёнке (РК 2026).

    ОПВ 10% + ОПВР 3.5% + ОСМС ~5% от 1.4 МРП + СО 3.5% ≈ 18-22% от базы.

    База и ставка читаются из `config/constants.yaml` (owner.social_base_mrp
    × MRP_2026; owner.social_rate). Если `declared_monthly_base` не передан —
    используется максимальная база (50 МРП × 4 325 = 216 250 ₸).

    Возвращает ₸/мес (int).
    """
    cap = MRP_2026 * OWNER_SOCIAL_BASE_MRP
    if declared_monthly_base is None:
        declared_monthly_base = cap
    base = min(declared_monthly_base, cap)
    return int(base * OWNER_SOCIAL_RATE)
