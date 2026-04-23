"""Danger zone service — расчёт зоны риска (разгон + сезонность).

Берёт 12-месячный cashflow (уже обогащённый profit/is_rampup в calculator),
находит:
- worst_month — месяц с минимальной месячной прибылью
- max_drawdown — максимальная просадка cumulative-суммы (CAPEX + потери)
- break_even_month — в каком месяце cumulative становится ≥ 0
- loss_months — все месяцы где profit < 0

Не показываем блок если has_cashflow_risk=False.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional


def compute_danger_zone(
    cashflow_year1: List[Dict[str, Any]],
    capex_total: int,
) -> Optional[Dict[str, Any]]:
    """Анализ 12-месячного cashflow → dict c зонами риска.

    Аргументы:
        cashflow_year1: 12 dict'ов с ключами revenue, total_costs, profit,
                        month_index (1..12), calendar_label, is_rampup.
        capex_total: стартовые вложения (₸) — начальная точка cumulative.

    Возвращает None если cashflow пустой. Иначе dict со статистикой.
    """
    if not cashflow_year1 or len(cashflow_year1) == 0:
        return None

    # 1. Cumulative cashflow: стартуем с -capex, суммируем profit по месяцам.
    cumulative = -int(capex_total)
    max_drawdown = abs(cumulative)  # как минимум = CAPEX до первого положительного profit
    max_drawdown_month = 0
    break_even_month: Optional[int] = None

    for i, month in enumerate(cashflow_year1):
        profit = int(month.get("profit") or 0)
        cumulative += profit
        if cumulative < 0 and abs(cumulative) > max_drawdown:
            max_drawdown = abs(cumulative)
            max_drawdown_month = i + 1
        if cumulative >= 0 and break_even_month is None:
            break_even_month = i + 1

    # 2. Худший месяц — минимальная месячная прибыль.
    worst = min(cashflow_year1, key=lambda m: int(m.get("profit") or 0))
    worst_profit = int(worst.get("profit") or 0)
    worst_month = {
        "label": worst.get("calendar_label", "?"),
        "month_index": int(worst.get("month_index") or 0),
        "revenue": int(worst.get("revenue") or 0),
        "costs": int(worst.get("total_costs") or 0),
        "profit": worst_profit,
    }

    # 3. Убыточные месяцы.
    loss_months: List[Dict[str, Any]] = []
    for month in cashflow_year1:
        p = int(month.get("profit") or 0)
        if p < 0:
            loss_months.append({
                "label": month.get("calendar_label", "?"),
                "month_index": int(month.get("month_index") or 0),
                "loss": abs(p),
                "is_rampup": bool(month.get("is_rampup", False)),
            })

    has_cashflow_risk = len(loss_months) > 0

    return {
        "worst_month": worst_month,
        "max_drawdown": int(max_drawdown),
        "max_drawdown_month": int(max_drawdown_month),
        "loss_months": loss_months,
        "break_even_month": break_even_month,
        "advice_reserve": int(max_drawdown),
        "has_cashflow_risk": has_cashflow_risk,
    }


def get_wisdom_note_ru() -> str:
    """Поясняющий текст для клиента."""
    return (
        "Самая частая причина закрытия малого бизнеса в первый год — "
        "не плохая идея и не низкий спрос, а кассовый разрыв. Бизнес "
        "зарабатывает, но в конкретный месяц не хватает денег на "
        "аренду, маркетинг или зарплаты — владелец берёт в долг, "
        "растёт хвост, через 2-3 месяца закрывается с минусом."
    )
