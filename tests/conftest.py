"""ZEREK Quick Check · pytest fixtures для регрессионных тестов.

Оборачиваем фактический pipeline `QuickCheckCalculator(db).run(req)` +
`build_pdf_context(result)` в одну функцию `engine_compute(scenario)`,
возвращающую плоский dict с полями для матчеров YAML.

Никакого магического engine.compute() — точку входа адаптируем под
реальный API.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

# api/ в PYTHONPATH чтобы импорты внутри проекта работали
_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

# Один глобальный db на сессию — загрузка ZerekDB(data/) занимает ~3 сек,
# не хотим перезагружать на каждый тест.
_db_singleton = None


def _get_db():
    global _db_singleton
    if _db_singleton is None:
        from main import db, db_error  # noqa: WPS433 — нужно после sys.path
        if not db:
            pytest.exit(f"DB не загрузилась: {db_error}", returncode=2)
        _db_singleton = db
    return _db_singleton


# ── Маппинг title из vrd.direction_title → канон-код градации ──
# Должен совпадать с _direction_character в pdf_renderer_weasyprint.py.
_GRADE_MAP = {
    "Низкий доход":       "LOW",
    "Невысокий доход":    "MODEST",
    "Средний доход":      "MIDDLE",
    "Достойный доход":    "DECENT",
    "Высокий доход":      "HIGH",
    "Очень высокий":      "VERY_HIGH",
    "Сомнительная":       "BAD",
}


def _grade_from_title(title: str) -> str:
    for prefix, code in _GRADE_MAP.items():
        if (title or "").startswith(prefix):
            return code
    return "?"


def _phase_avg(monthly_plan, lo, hi):
    items = (monthly_plan or [])[lo:hi]
    if not items:
        return 0
    return int(round(sum(int(m.get("total_marketing", 0) or 0) for m in items) / len(items)))


def _education_label(breakdown):
    """Возвращает label строки CAPEX, относящейся к обучению/квалификации.
    R9 L.2: для опытных — «Повышение квалификации», для новичков — «Обучение и курсы»."""
    for it in (breakdown or []):
        label = (it.get("label") or "").lower()
        if "обучение" in label or "квалификации" in label:
            return it.get("label") or ""
    return ""


def engine_compute(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Прогнать сценарий через ZEREK pipeline и собрать плоский dict
    полей для матчеров golden_scenarios.yaml.

    Сценарий: {niche, format, city, capital, experience, start_month}.
    Возвращает: словарь с полями capex/avg_y1/mature_monthly/... которые
    адресуются по точкам в FIELD_MAP в test_engine_regression.py.
    """
    from main import QCReq  # noqa: WPS433
    from calculators.quick_check import QuickCheckCalculator
    from renderers.pdf_renderer_weasyprint import build_pdf_context

    inp = scenario["inputs"]
    db = _get_db()

    # R12.5 S5: golden_scenarios.yaml может задавать strategy / level
    # для соло-beauty (A1) сценариев. Если поле в inputs отсутствует —
    # используем дефолты (strategy="middle", level не передаётся).
    sa: Dict[str, Any] = {"experience": str(inp.get("experience") or "none")}
    if inp.get("strategy"):
        sa["strategy"] = str(inp["strategy"])
    if inp.get("level"):
        sa["level"] = str(inp["level"])
    req = QCReq(
        city_id=str(inp["city"]).lower(),
        niche_id=str(inp["niche"]).upper(),
        format_id=str(inp["format"]).upper(),
        loc_type="дома",
        area_m2=0,
        capital=int(inp.get("capital") or 0),
        start_month=int(inp.get("start_month") or 4),
        capex_level="стандарт",
        specific_answers=sa,
    )
    result = QuickCheckCalculator(db).run(req)
    ctx = build_pdf_context(result)

    cap = ctx.get("cap") or {}
    fin = ctx.get("fin") or {}
    vrd = ctx.get("vrd") or {}
    cadq = ctx.get("cadq") or {}
    mp = result.get("marketing_plan") or {}
    monthly_plan = mp.get("monthly_plan") or []
    summary = mp.get("summary") or {}
    ei = (result.get("block5") or {}).get("entrepreneur_income") or {}

    return {
        "capex":                  int(cap.get("total") or 0),
        "capex_education_label":  _education_label(cap.get("breakdown") or []),
        "avg_y1":                 int(ei.get("total_monthly") or 0),
        "mature_monthly":         int(ei.get("mature_monthly") or 0),
        "breakeven_clients":      int(fin.get("break_even_clients") or 0),
        "safety_mature":          float(fin.get("safety_multiplier") or 0),
        "safety_ramp":            float(fin.get("safety_multiplier_ramp") or 0),
        "capital_zone":           cadq.get("capital_zone") or "UNKNOWN",
        "income_grade":           _grade_from_title(vrd.get("direction_title") or ""),
        "income_ratio_pct":       int(vrd.get("income_ratio_pct") or 0),
        "marketing_year_total":   int(summary.get("total_year_budget") or 0),
        "marketing_phase_ramp":   _phase_avg(monthly_plan, 0, 3),
        "marketing_phase_tuning": _phase_avg(monthly_plan, 3, 6),
        "marketing_phase_mature": _phase_avg(monthly_plan, 6, 12),
    }


@pytest.fixture(scope="session")
def compute():
    """pytest fixture: даёт функцию-обёртку для прогона одного сценария."""
    return engine_compute
