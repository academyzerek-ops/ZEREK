"""Staff paradox service — блок «Парадокс штата» для beauty-ниш (A1).

Показывает клиенту потолок мастера-одиночки и варианты роста. Глубина
блока зависит от формата:
- HOME:     короткий (потолок + note о невозможности найма)
- SOLO:     средний  (потолок + 2 стратегии без аренды)
- STANDARD: полный   (потолок + 4 стратегии + warning про найм на оклад)
- PREMIUM:  полный

Для не-A1 архетипов возвращает None (другие продуктовые сообщения —
отдельными задачами).
"""
from __future__ import annotations
import os
import sys
from typing import Any, Dict, Optional

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from loaders import marketing_loader  # noqa: E402


# Физический потолок мастера-одиночки в сутки (экспертная оценка Адиля).
MAX_CLIENTS_PER_DAY_BEAUTY = {
    "MANICURE":    7,  # ~1 час на сессию
    "BARBER":      8,  # 30-40 мин
    "LASH":        3,  # 2-3 часа на наращивание
    "BROW":        8,  # 30 мин
    "SUGARING":    5,  # 60-90 мин
    "MASSAGE":     5,  # 60-90 мин
    "COSMETOLOGY": 4,  # разные процедуры, в среднем 1.5 часа
    "BEAUTY":      6,  # универсальный салон
}
MAX_CLIENTS_DEFAULT = 6

# R6 A.5/A.6: 22 — устойчивый режим (5/2, рекомендуем как базу).
# 26 — предельный режим (6 рабочих, без отдыха), по нему считается
# отдельная цифра «потолок предельный» с предупреждением о выгорании.
WORK_DAYS_SUSTAINABLE = 22
WORK_DAYS_PEAK = 26
# Совместимость с прежним кодом (не используется в расчёте, но мы
# не можем удалить имя — на него могут опираться импорты).
WORK_DAYS_PER_MONTH = WORK_DAYS_SUSTAINABLE


def compute_staff_paradox(
    niche_id: str,
    format_id: str,
    avg_check: int,
    rent_monthly: int,
    city_id: str,
) -> Optional[Dict[str, Any]]:
    """Блок «Парадокс штата» для beauty-ниш (архетип A1).

    Возвращает None для не-A1 или неизвестных форматов.
    """
    archetype = marketing_loader.get_niche_archetype((niche_id or "").upper())
    if archetype != "A1":
        return None

    fmt_up = (format_id or "").upper()
    if fmt_up.endswith("_HOME"):
        block_type = "short"
    elif fmt_up.endswith("_SOLO"):
        block_type = "medium"
    elif fmt_up.endswith("_STANDARD") or fmt_up.endswith("_PREMIUM"):
        block_type = "full"
    else:
        return None

    max_per_day = MAX_CLIENTS_PER_DAY_BEAUTY.get((niche_id or "").upper(), MAX_CLIENTS_DEFAULT)
    check = int(avg_check or 0)
    # R6 A.5: два потолка (устойчивый 22 дня + предельный 26)
    # вместо одного «идеального». Реалистично — 80% от устойчивого.
    sustainable_monthly_revenue = max_per_day * WORK_DAYS_SUSTAINABLE * check
    peak_monthly_revenue = max_per_day * WORK_DAYS_PEAK * check
    realistic_monthly_revenue = int(sustainable_monthly_revenue * 0.80)

    capacity = {
        "max_clients_per_day": max_per_day,
        "work_days_per_month": WORK_DAYS_SUSTAINABLE,
        "work_days_peak": WORK_DAYS_PEAK,
        "sustainable_monthly_revenue": sustainable_monthly_revenue,
        "peak_monthly_revenue": peak_monthly_revenue,
        "realistic_monthly_revenue": realistic_monthly_revenue,
        "avg_check": check,
    }

    strategies = _build_strategies(block_type, int(rent_monthly or 0))
    warning = _build_warning(block_type)
    hire_impossible_note = _build_hire_impossible_note(block_type)

    return {
        "applicable": True,
        "archetype_id": archetype,
        "niche_id": (niche_id or "").upper(),
        "format_id": fmt_up,
        "block_type": block_type,
        "capacity": capacity,
        "strategies": strategies,
        "warning": warning,
        "hire_impossible_note": hire_impossible_note,
    }


def _build_strategies(block_type: str, rent_monthly: int) -> list:
    """Список стратегий по block_type.

    short (HOME):   []  — только потолок + note
    medium (SOLO):  grow_to_standard + cross_niches_in_host
    full (STANDARD/PREMIUM): sharing + cross_niches + teaching_model + mentorship_shift
    """
    if block_type == "short":
        return []

    if block_type == "medium":
        return [
            {
                "id": "grow_to_standard",
                "title": "Перейти из SOLO в STANDARD",
                "body": (
                    "Арендовать помещение на 2-3 кресла и взять мастеров на "
                    "процент с выручки (30-50%). Вы растёте как организатор, "
                    "не как мастер — потолок снимается."
                ),
            },
            {
                "id": "cross_niches_in_host",
                "title": "Войти в host-салон и расширить услуги",
                "body": (
                    "Арендовать кресло в действующем салоне. Добавить смежные "
                    "услуги (педикюр, покрытие, дизайн) — повышает средний чек "
                    "без увеличения кол-ва клиентов."
                ),
            },
        ]

    # full
    half_rent = rent_monthly // 2
    return [
        {
            "id": "sharing",
            "title": "Делить аренду с другим мастером / салоном",
            "body": (
                "Утренние и вечерние смены — разные мастера. Аренда делится "
                "пополам. Клиенты не пересекаются. Модель рабочая для маникюра, "
                "барбершопа, лаш-мастеров."
            ),
            "savings": {
                "monthly": half_rent,
                "yearly": half_rent * 12,
            },
        },
        {
            "id": "cross_niches",
            "title": "Добавить смежные услуги",
            "body": (
                "Маникюр + педикюр + бровист в одном пространстве. "
                "Общая аренда делится на 3. Клиентская база растёт "
                "за счёт перекрёстных рекомендаций."
            ),
        },
        {
            "id": "teaching_model",
            "title": "Обучать мастеров за деньги",
            "body": (
                "Продавать курс / интенсив / наставничество на 30-50K ₸. "
                "Каждый выпуск — 5-10 человек. Это второй канал дохода, "
                "не зависит от физического потолка."
            ),
        },
        {
            "id": "mentorship_shift",
            "title": "Уйти от «я — мастер» к «я — хозяин»",
            "body": (
                "Перестать стричь/красить/делать самому. Взять 3-5 "
                "мастеров на процент. Ваша роль: маркетинг, обучение, "
                "клиентский сервис. Доход выше, потолок снят."
            ),
        },
    ]


def _build_warning(block_type: str) -> Optional[Dict[str, str]]:
    """Warning про найм на оклад — только для full (STANDARD/PREMIUM)."""
    if block_type != "full":
        return None
    return {
        "title": "Осторожно: найм на оклад",
        "text": (
            "Beauty-ниша плохо совместима с окладной моделью. Оклад = мастер "
            "не заинтересован в клиенте, уходит к конкуренту через 3-6 "
            "месяцев вместе с базой. Рабочие модели в КЗ: аренда кресла "
            "(30-80K ₸/мес), процент с выручки (30-50%), франшиза. "
            "Оклад работает только в сетях с устоявшимся брендом и маркетингом."
        ),
    }


def _build_hire_impossible_note(block_type: str) -> Optional[str]:
    """Note для HOME — нельзя нанять другого мастера в свой дом."""
    if block_type != "short":
        return None
    return (
        "Нельзя нанять другого мастера работать у вас дома — это ваш дом, "
        "и клиент доверяет лично вам. Рост возможен только через рост "
        "среднего чека или переход в формат SOLO (арендованный кабинет)."
    )
