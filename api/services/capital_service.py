"""Capital adequacy service — логика блока «Достаточность капитала».

Заменяет примитивный «капитал хватает на CAPEX ✅» на 3-уровневую оценку:
- minimum: только CAPEX (открыться)
- comfortable: CAPEX + резерв на rampup-месяцы (пережить разгон)
- safe: + сезонный буфер (пережить просадки)

Вердикт зависит от user_capital и сравнения с уровнями. Соцплатежи ИП
берутся из tax_constants_loader (единый источник истины, не хардкод).
"""
from __future__ import annotations
import os
import sys
from typing import Any, Dict, Optional

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from loaders.tax_constants_loader import get_ip_minimum_monthly_payment  # noqa: E402


def _fmt_kzt(n: int) -> str:
    """«71 675» — разделитель тысяч пробел, для встраивания в сообщения."""
    return f"{int(n):,}".replace(",", " ")


def compute_capital_adequacy(
    capex_total: int,
    marketing_monthly: int,
    other_opex_monthly: int,
    rent_monthly: int,
    rampup_months: int,
    worst_season_drawdown: int,
    user_capital: Optional[int],
    legal_form: str = "ip",
) -> Dict[str, Any]:
    """Считает достаточность капитала в 3 уровнях.

    - minimum = capex_total
    - comfortable = minimum + (marketing + opex + ip_min_taxes + rent) × rampup
    - safe = comfortable + worst_season_drawdown × 2

    Для ТОО ip_min_taxes пока = 0 (все ниши сейчас на ИП; расширим позже).
    """
    ip_min_taxes = int(get_ip_minimum_monthly_payment()) if legal_form == "ip" else 0

    monthly_fixed = (
        int(marketing_monthly)
        + int(other_opex_monthly)
        + ip_min_taxes
        + int(rent_monthly)
    )
    reserve_3_months = monthly_fixed * int(rampup_months)
    # seasonal_buffer = max(worst_monthly_loss × 2, comfortable × 30%).
    # Для высокомаржинальных ниш где worst_month прибылен — floor даёт
    # 30% от comfortable, чтобы safe ВСЕГДА было строго больше comfortable.
    minimum = int(capex_total)
    comfortable = minimum + reserve_3_months
    drawdown_buffer = int(worst_season_drawdown) * 2 if worst_season_drawdown and worst_season_drawdown > 0 else 0
    floor_buffer = int(comfortable * 0.30)
    seasonal_buffer = max(drawdown_buffer, floor_buffer)
    safe = comfortable + seasonal_buffer

    reserve_breakdown = {
        "marketing_per_month": int(marketing_monthly),
        "other_opex_per_month": int(other_opex_monthly),
        "ip_min_taxes_per_month": ip_min_taxes,
        "rent_per_month": int(rent_monthly),
        "total_per_month": monthly_fixed,
        "months": int(rampup_months),
        "total_for_period": reserve_3_months,
    }

    verdict = _compute_verdict(
        user_capital=user_capital,
        minimum=minimum,
        comfortable=comfortable,
        safe=safe,
    )

    return {
        "capex": minimum,
        "minimum": minimum,
        "comfortable": comfortable,
        "safe": safe,
        "reserve_3_months": reserve_3_months,
        "seasonal_buffer": seasonal_buffer,
        "reserve_breakdown": reserve_breakdown,
        "user_capital": user_capital,
        **verdict,
    }


def _compute_verdict(
    user_capital: Optional[int],
    minimum: int,
    comfortable: int,
    safe: int,
) -> Dict[str, Any]:
    """Определяет уровень и формирует сообщение для клиента."""
    if user_capital is None or user_capital == 0:
        return {
            "verdict_level": "unknown",
            "verdict_color": "gray",
            "verdict_label": "Укажите капитал",
            "verdict_message": (
                "Укажите ваш стартовый капитал чтобы получить "
                "персональную оценку достаточности."
            ),
            "gap_amount": 0,
            "gap_to_level": None,
        }

    if user_capital >= safe:
        return {
            "verdict_level": "safe",
            "verdict_color": "green",
            "verdict_label": "Безопасно",
            "verdict_message": (
                "У вас есть запас на разгон и сезонные провалы. "
                "Это редкая ситуация — большинство предпринимателей "
                "стартуют с меньшими суммами."
            ),
            "gap_amount": 0,
            "gap_to_level": None,
        }

    if user_capital >= comfortable:
        gap = safe - user_capital
        return {
            "verdict_level": "comfortable",
            "verdict_color": "green",
            "verdict_label": "Комфортно",
            "verdict_message": (
                "На разгон хватает. Но в худший сезонный месяц "
                f"может быть тяжело — держите резерв ещё {_fmt_kzt(gap)} ₸ "
                "на экстренные расходы."
            ),
            "gap_amount": gap,
            "gap_to_level": "safe",
        }

    if user_capital >= minimum:
        gap = comfortable - user_capital
        return {
            "verdict_level": "risky",
            "verdict_color": "yellow",
            "verdict_label": "Рискованно",
            "verdict_message": (
                "Капитала хватает на стартовые вложения, но НЕ на "
                "разгон. Первые 3 месяца вы будете в минусе — без "
                f"подушки рискуете закрыться. Нужно ещё {_fmt_kzt(gap)} ₸ "
                "чтобы дожить до выхода на мощность."
            ),
            "gap_amount": gap,
            "gap_to_level": "comfortable",
        }

    gap = minimum - user_capital
    return {
        "verdict_level": "insufficient",
        "verdict_color": "red",
        "verdict_label": "Недостаточно",
        "verdict_message": (
            f"Не хватает даже на стартовые вложения. Найти ещё "
            f"{_fmt_kzt(gap)} ₸ или пересмотреть формат на более лёгкий."
        ),
        "gap_amount": gap,
        "gap_to_level": "minimum",
    }
