"""api/services/stress_service.py — Стресс-тест Quick Check.

Согласно спеке (Часть 2.6, Шаг 8):
- База = ЗРЕЛЫЙ РЕЖИМ (revenue × 1 × 1, без ramp и сезонности)
- Параметры: Загрузка/трафик −20%, Средний чек −15%
- Формулы:
  * Трафик −X%: revenue и materials падают пропорционально
  * Чек −X%: revenue падает, materials НЕ меняются (услуг столько же)
- Импакт в ₸/год (отрицательный = потеря)

Извлечено из engine.py в Этапе 3 рефакторинга.

В Этапе 8 (cleanup) удалены:
- death_points (Ноа решение Этапа 3, см. OQ-O — baseline обновлён)
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import _safe_float, _safe_int  # noqa: E402

_log = logging.getLogger("zerek.stress_service")


# ═══════════════════════════════════════════════════════════════════════
# BLOCK 8 — чувствительность по 2 параметрам (Шаг 8 спеки)
# ═══════════════════════════════════════════════════════════════════════


def compute_block8_stress_test(result):
    """Анализ чувствительности от ЗРЕЛОГО режима (аксиома 2.6 спеки).

    Принимает result с pnl_aggregates.mature (сформирован в Шаге 3-5).
    Возвращает dict с sensitivities, death_points, critical_param, recs.

    Формулы:
      Трафик −X%: revenue и materials падают пропорционально; налог от
      новой выручки; фиксированные расходы не меняются.
      Чек −X%: revenue падает, materials НЕ меняются (услуг столько же).
    """
    fin = result.get("financials", {}) or {}
    scenarios = result.get("scenarios", {}) or {}
    tax = result.get("tax", {}) or {}

    mature = (result.get("pnl_aggregates") or {}).get("mature") or {}
    rev_mature_m = _safe_int(mature.get("revenue_monthly"), 0) or 1
    materials_mature_m = _safe_int(mature.get("materials_monthly"), 0)
    profit_mature_m = _safe_int(mature.get("profit_monthly"), 0)
    fixed_monthly = _safe_int(mature.get("fixed_monthly"), 0)
    cogs_pct = _safe_float(mature.get("cogs_pct"), _safe_float(fin.get("cogs_pct"), 0.30))
    tax_rate = _safe_float(mature.get("tax_rate"), (tax.get("rate_pct", 3) or 3) / 100)

    # Базовая прибыль стресс-теста = entrepreneur_income.total_monthly
    # (средняя за первый год, с учётом rampup и реального маркетинга).
    # Raньше бралось scenarios.base.прибыль_год / 12, что давало другую
    # цифру из-за YAML marketing_med. BUG #6 фикс.
    block5 = result.get("block5") or {}
    ei = block5.get("entrepreneur_income") or {}
    base_profit_month = _safe_int(ei.get("total_monthly"), 0) or 1

    rev_mature_y = rev_mature_m * 12
    materials_mature_y = materials_mature_m * 12
    fixed_year = fixed_monthly * 12

    # Компоненты fixed_monthly — для отдельных params (Аренда/ФОТ/Маркетинг)
    rent_monthly = _safe_int(mature.get("rent_monthly"), 0)
    fot_monthly = _safe_int(mature.get("fot_monthly"), 0)
    mk_monthly = _safe_int(mature.get("marketing_monthly"), 0)

    def impact_traffic(delta_pct):
        frac = abs(delta_pct) / 100.0
        rev_new_m = rev_mature_m * (1 - frac)
        materials_new_m = materials_mature_m * (1 - frac)
        tax_new_m = rev_new_m * tax_rate
        profit_new_m = rev_new_m - materials_new_m - tax_new_m - fixed_monthly
        return -int(round((profit_mature_m - profit_new_m) * 12))

    def impact_avg_check(delta_pct):
        frac = abs(delta_pct) / 100.0
        rev_new_m = rev_mature_m * (1 - frac)
        materials_new_m = materials_mature_m  # без изменений
        tax_new_m = rev_new_m * tax_rate
        profit_new_m = rev_new_m - materials_new_m - tax_new_m - fixed_monthly
        return -int(round((profit_mature_m - profit_new_m) * 12))

    def impact_cost_up(cost_monthly, delta_pct):
        """Рост фикс-статьи (rent/marketing/fot) — прямо уменьшает прибыль."""
        frac = abs(delta_pct) / 100.0
        delta_m = cost_monthly * frac
        return -int(round(delta_m * 12))

    # Round-3: 5 параметров. Для HOME-форматов rent/fot = 0 → impact=0,
    # строки всё равно показываем (клиент видит «аренды нет — плюс»).
    sensitivities = [
        {"param": "Загрузка / трафик", "change": -20, "impact_annual": impact_traffic(-20)},
        {"param": "Средний чек",        "change": -15, "impact_annual": impact_avg_check(-15)},
        {"param": "Аренда (рост)",      "change":  20, "impact_annual": impact_cost_up(rent_monthly, 20)},
        {"param": "Маркетинг (рост)",   "change":  20, "impact_annual": impact_cost_up(mk_monthly, 20)},
        {"param": "ФОТ (рост)",         "change":  20, "impact_annual": impact_cost_up(fot_monthly, 20)},
    ]
    sensitivities.sort(key=lambda x: x["impact_annual"])

    critical = sensitivities[0]

    recommendations_by_param = {
        "Загрузка / трафик": [
            "Минимум 3 первых месяца — фокус на маркетинге",
            "Следите за загрузкой еженедельно с 1-й недели",
            "Если загрузка <45% к 3-му мес — срочно пересматривайте маркетинг",
        ],
        "Средний чек": [
            "Разработать upsell / апсейлы (пакеты, комплексные услуги)",
            "Регулярно пересматривать прайс раз в 3 мес",
            "Не бояться поднимать цену на 5-10% после набора базы",
        ],
        "ФОТ (рост)": [
            "Сдельная система мотивации — привязана к выручке",
            "Не брать сотрудников про запас",
            "Готовить замену ключевым мастерам",
        ],
    }
    recs = recommendations_by_param.get(critical["param"], ["Следите за параметром ежемесячно"])

    return {
        "base_profit_month": base_profit_month,
        "base_profit_year": base_profit_month * 12,
        "sensitivities": sensitivities,
        "critical_param": critical,
        "recommendations": recs,
    }


