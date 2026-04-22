"""api/report.py — Thin re-export для legacy импортов.

Реальная реализация переехала в Этапе 5 в:
- api/renderers/quick_check_renderer.py: render_report_v4, fmt

Этот файл сохраняется для обратной совместимости (импорты в main.py
и pdf_gen.py по-прежнему делают `from report import render_report_v4`).
В Этапе 8 (cleanup) этот shim удалится.
"""
from renderers.quick_check_renderer import fmt, render_report_v4  # noqa: F401
