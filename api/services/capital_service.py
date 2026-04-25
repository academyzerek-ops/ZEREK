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
    """Round-4 bug 5: прогнозные gap-суммы в verdict_message должны
    быть округлены до тысячи (иначе в PDF видны 39 719, 39 500 и
    т.п. — несогласованное округление).
    """
    n = int(n)
    av = abs(n)
    if av < 1_000:
        step = 10
    elif av < 10_000:
        step = 100
    elif av < 100_000:
        step = 500
    elif av < 1_000_000:
        step = 1_000
    else:
        step = 10_000
    sign = -1 if n < 0 else 1
    rounded = sign * int(round(av / step) * step)
    return f"{rounded:,}".replace(",", " ")


def compute_capital_adequacy(
    capex_total: int,
    marketing_monthly: int,
    other_opex_monthly: int,
    rent_monthly: int,
    rampup_months: int,
    worst_season_drawdown: int,
    user_capital: Optional[int],
    legal_form: str = "ip",
    ramp_marketing_total: int = 0,
) -> Dict[str, Any]:
    """Считает достаточность капитала в 3 уровнях.

    - minimum = capex_total
    - comfortable = minimum + резерв на разгон
        резерв = ramp_marketing_total (M1-M3 из marketing_plan)
                 + (other_opex + ip_min_taxes + rent) × rampup_months
        Если ramp_marketing_total не передан — fallback на
        marketing_monthly × rampup_months (старая логика).
    - safe = comfortable + worst_season_drawdown × 2 (или 30% floor).

    R6 C.1: для HOME-форматов avg-маркетинг (60K) × 3 = 180K, а
    реальный разгонный (152K/мес × 3 ≈ 460K) — занижение резерва
    в 2.5 раза. Используем сумму первых 3 месяцев из marketing_plan.
    """
    ip_min_taxes = int(get_ip_minimum_monthly_payment()) if legal_form == "ip" else 0

    other_fixed_per_month = (
        int(other_opex_monthly)
        + ip_min_taxes
        + int(rent_monthly)
    )
    if ramp_marketing_total and ramp_marketing_total > 0:
        marketing_for_reserve = int(ramp_marketing_total)
    else:
        marketing_for_reserve = int(marketing_monthly) * int(rampup_months)
    reserve_3_months = marketing_for_reserve + other_fixed_per_month * int(rampup_months)
    monthly_fixed = int(marketing_monthly) + other_fixed_per_month  # legacy для breakdown
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
        "marketing_ramp_total": int(marketing_for_reserve),
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
    """R8 H.1: единая позиция по капиталу через 5 зон.

    Зоны (граничные множители вокруг CAPEX даны в ТЗ R8 H.1):
      RED       capital < CAPEX × 0.9      «критически не хватает на запуск»
      AMBER     0.9·CAPEX ≤ < 1.1·CAPEX    «хватает на запуск, на разгон — нет»
      YELLOW    1.1·CAPEX ≤ < comfortable  «на запуск + часть разгона»
      GREEN     comfortable ≤ < safe       «комфортный запас на разгон»
      GREEN+    capital ≥ safe             «безопасный запас с подушкой»

    Возвращает три текста для одной и той же оценки:
      verdict_short   — одна-две строки для priorities на стр. «Итог»
      verdict_message — компактный текст для блока «Достаточность капитала»
      verdict_full    — полный текст с числами для правого блока стр. 8

    Поля verdict_level / gap_amount / gap_to_level сохранены для
    обратной совместимости (action_plan_service, verdict_service).

    Тон: «критически» — только в RED. «дефицит» / «не хватает» вне RED
    запрещены (G.3 R7 + H.1 R8). Заменяются на «желательно добрать».
    """
    if user_capital is None or user_capital == 0:
        return {
            "capital_zone": "UNKNOWN",
            "verdict_level": "unknown",
            "verdict_color": "gray",
            "verdict_label": "Укажите капитал",
            "verdict_short": (
                "Капитал не указан. Укажите сумму, чтобы получить "
                "персональную оценку достаточности."
            ),
            "verdict_message": (
                "Укажите ваш стартовый капитал чтобы получить "
                "персональную оценку достаточности."
            ),
            "verdict_full": (
                "Укажите ваш стартовый капитал чтобы получить "
                "персональную оценку достаточности."
            ),
            "gap_amount": 0,
            "gap_to_level": None,
        }

    capital = int(user_capital)
    capex = int(minimum)
    cap_txt = _fmt_kzt(capital)
    capex_txt = _fmt_kzt(capex)
    comf_txt = _fmt_kzt(comfortable)

    # ── RED: критически не хватает даже на минимальный запуск ──
    if capital < int(capex * 0.9):
        gap = capex - capital
        return {
            "capital_zone": "RED",
            "verdict_level": "insufficient",
            "verdict_color": "red",
            "verdict_label": "Критически не хватает",
            "verdict_short": (
                f"Не хватает {_fmt_kzt(gap)} ₸ даже на минимальный запуск "
                f"({capex_txt} ₸). Без этой суммы открыть бизнес "
                "физически невозможно."
            ),
            "verdict_message": (
                f"Капитал {cap_txt} ₸ ниже минимума на запуск "
                f"({capex_txt} ₸) — не хватает {_fmt_kzt(gap)} ₸. "
                "Без этой суммы CAPEX (оборудование, обучение, "
                "первый месяц аренды) физически не закрыть."
            ),
            "verdict_full": (
                f"Ваш капитал {cap_txt} ₸ ниже минимума на запуск "
                f"({capex_txt} ₸). Не хватает {_fmt_kzt(gap)} ₸ — это "
                "деньги на CAPEX (оборудование, обучение, первый "
                "платёж за аренду). Начинать рано: либо найти "
                "недостающую сумму, либо пересмотреть формат на более "
                "лёгкий (дома вместо аренды места)."
            ),
            "gap_amount": gap,
            "gap_to_level": "minimum",
        }

    # ── AMBER: хватает на запуск, на разгон — нет ──
    if capital < int(capex * 1.1):
        ramp_gap = max(0, comfortable - capital)
        post_capex = capital - capex
        return {
            "capital_zone": "AMBER",
            "verdict_level": "risky",
            "verdict_color": "amber",
            "verdict_label": "Хватает на запуск, на разгон — нет",
            "verdict_short": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX ({capex_txt} ₸) "
                f"и оставляет {_fmt_kzt(post_capex)} ₸ на старт разгона. "
                f"До комфортного уровня желательно добрать {_fmt_kzt(ramp_gap)} ₸ "
                "к М2-М3 — это разница между спокойным и стрессовым "
                "прохождением разгона."
            ),
            "verdict_message": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX ({capex_txt} ₸). "
                f"На разгон М1-М3 желательно добрать {_fmt_kzt(ramp_gap)} ₸ — "
                "иначе высокий риск кассового разрыва на 2-3 месяце "
                "если воронка не сработает с первого раза."
            ),
            "verdict_full": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX ({capex_txt} ₸) "
                f"и оставляет {_fmt_kzt(post_capex)} ₸ на старт разгона. "
                f"До комфортного уровня ({comf_txt} ₸) желательно добрать "
                f"{_fmt_kzt(ramp_gap)} ₸ к М2-М3 — именно тогда маркетинг "
                "разгона на пике, а выручка ещё не на потолке. Это не "
                "блокер, но фактор риска: «спокойный разгон» становится "
                "«напряжённым»."
            ),
            "gap_amount": ramp_gap,
            "gap_to_level": "comfortable",
        }

    # ── YELLOW: на запуск + часть разгона ──
    if capital < comfortable:
        ramp_gap = comfortable - capital
        ramp_reserve = comfortable - capex  # резерв на разгон полностью
        # доля разгонного резерва, покрытая капиталом сверх CAPEX
        post_capex = capital - capex
        if ramp_reserve > 0:
            ramp_pct = int(round(post_capex / ramp_reserve * 100))
        else:
            ramp_pct = 0
        return {
            "capital_zone": "YELLOW",
            "verdict_level": "risky",
            "verdict_color": "yellow",
            "verdict_label": "На запуск и часть разгона хватает",
            "verdict_short": (
                f"Капитал {cap_txt} ₸ покрывает запуск и около {ramp_pct}% "
                "разгонного резерва. До комфортного уровня желательно "
                f"добрать {_fmt_kzt(ramp_gap)} ₸ — ориентируйтесь на М2-М3 "
                "как точку, когда подушка особенно нужна."
            ),
            "verdict_message": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX и часть разгона "
                f"(около {ramp_pct}% резерва М1-М3). До комфортного "
                f"уровня желательно добрать {_fmt_kzt(ramp_gap)} ₸ к М2-М3."
            ),
            "verdict_full": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX ({capex_txt} ₸) "
                f"и около {ramp_pct}% разгонного резерва. До комфортного "
                f"уровня ({comf_txt} ₸) желательно добрать "
                f"{_fmt_kzt(ramp_gap)} ₸ к М2-М3, когда маркетинг на пике, "
                "а выручка ещё не на потолке. Разгон проходим, но без "
                "права на ошибку: если воронка не сработает с первого "
                "раза, нужны дополнительные средства."
            ),
            "gap_amount": ramp_gap,
            "gap_to_level": "comfortable",
        }

    # ── GREEN: комфортный запас на разгон ──
    if capital < safe:
        cushion = safe - capital
        return {
            "capital_zone": "GREEN",
            "verdict_level": "comfortable",
            "verdict_color": "green",
            "verdict_label": "Комфортный запас на разгон",
            "verdict_short": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX и весь резерв "
                "разгона М1-М3. Сезонные просадки потребуют дисциплины, "
                "но не угрозы."
            ),
            "verdict_message": (
                f"Капитала достаточно для комфортного прохождения "
                "разгона. Сезонные просадки потребуют дисциплины, "
                "но не угрозы."
            ),
            "verdict_full": (
                f"Капитал {cap_txt} ₸ покрывает CAPEX ({capex_txt} ₸) "
                f"и весь резерв разгона — комфортный уровень {comf_txt} ₸ "
                f"пройден. До безопасного уровня остаётся {_fmt_kzt(cushion)} ₸, "
                "но это не критично: сезонные провалы потребуют дисциплины "
                "(контроль OPEX в худший месяц), но не угрожают бизнесу."
            ),
            "gap_amount": cushion,
            "gap_to_level": "safe",
        }

    # ── GREEN+: безопасный запас с подушкой на просадки ──
    return {
        "capital_zone": "GREEN_PLUS",
        "verdict_level": "safe",
        "verdict_color": "green",
        "verdict_label": "Безопасный запас с подушкой",
        "verdict_short": (
            f"Капитал {cap_txt} ₸ покрывает запуск, разгон и сезонные "
            "просадки. Можно проходить год спокойно."
        ),
        "verdict_message": (
            "Капитал с подушкой. Можете спокойно проходить разгон "
            "и сезонные просадки."
        ),
        "verdict_full": (
            f"Капитал {cap_txt} ₸ покрывает CAPEX ({capex_txt} ₸), "
            f"полный резерв разгона ({comf_txt} ₸) и сезонный буфер. "
            "Типичный риск на этом уровне — потратить подушку до "
            "открытия на «красоту» (премиум-оборудование, дорогой "
            "ремонт). Часть капитала держите нетронутой до М4."
        ),
        "gap_amount": 0,
        "gap_to_level": None,
    }
