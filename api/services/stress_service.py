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

from engine import (  # noqa: E402
    SCENARIO_BASE,
    SCENARIO_OPT,
    SCENARIO_STRESS,
    _safe_float,
    _safe_int,
)
from services.economics_service import calc_owner_economics  # noqa: E402

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

    # Для UI-совместимости публикуем ещё и средний год (из scenarios.base).
    base_profit_year = _safe_int((scenarios.get("base") or {}).get("прибыль_год"), 0) or 1
    base_profit_month = base_profit_year // 12

    rev_mature_y = rev_mature_m * 12
    materials_mature_y = materials_mature_m * 12
    fixed_year = fixed_monthly * 12

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

    sensitivities = [
        {"param": "Загрузка / трафик", "change": -20, "impact_annual": impact_traffic(-20)},
        {"param": "Средний чек",        "change": -15, "impact_annual": impact_avg_check(-15)},
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
        "base_profit_year": base_profit_year,
        "sensitivities": sensitivities,
        "critical_param": critical,
        "recommendations": recs,
    }


# ═══════════════════════════════════════════════════════════════════════
# Legacy: calc_stress_test (3 сценария через calc_owner_economics)
# Используется в run_quick_check_v3 → result.owner_economics.stress_test.
# На фронт не рендерится; кандидат на удаление в Этапе 8.
# ═══════════════════════════════════════════════════════════════════════


def calc_stress_test(fin, staff, tax_rate, rent_month_total, qty=1):
    """Legacy 3-сценарный стресс (плохо/база/хорошо) через owner_economics."""
    def _desc(sc):
        parts = []
        t = sc.get("traffic_k", 1.0)
        c = sc.get("check_k", 1.0)
        r = sc.get("rent_k", 1.0)
        if t != 1.0:
            parts.append(f"трафик {'+' if t > 1 else '−'}{abs(int(round((t-1)*100)))}%")
        if c != 1.0:
            parts.append(f"чек {'+' if c > 1 else '−'}{abs(int(round((c-1)*100)))}%")
        if r != 1.0:
            parts.append(f"аренда {'+' if r > 1 else '−'}{abs(int(round((r-1)*100)))}%")
        return ", ".join(parts).capitalize() if parts else "Расчётные показатели"

    scenarios = [
        {"key": "bad",  "label": "Если всё плохо",   "color": "red",
         "params": _desc(SCENARIO_STRESS),
         **SCENARIO_STRESS},
        {"key": "base", "label": "Базовый сценарий", "color": "blue",
         "params": _desc(SCENARIO_BASE),
         **SCENARIO_BASE},
        {"key": "good", "label": "Если всё хорошо",  "color": "green",
         "params": _desc(SCENARIO_OPT),
         **SCENARIO_OPT},
    ]
    out = []
    for sc in scenarios:
        eco = calc_owner_economics(
            fin, staff, tax_rate, rent_month_total, qty,
            traffic_k=sc["traffic_k"], check_k=sc["check_k"], rent_k=sc["rent_k"],
        )
        out.append({
            "key": sc["key"], "label": sc["label"], "color": sc["color"],
            "params": sc["params"],
            "revenue": eco["revenue"],
            "net_in_pocket": eco["net_in_pocket"],
        })
    return out
