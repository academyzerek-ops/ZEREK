"""api/renderers/pdf_renderer.py — Тонкая обёртка над api/pdf_gen.py.

PDF-рендер использует legacy block_1..block_12 формат (через render_report_v4)
+ дополнительные секции AI-рисков от gemini_rag.

Согласно решению Ноа OQ-2 (Этап 1): дизайн PDF дорабатывается отдельной
задачей, в Этап 5 — только структурный перенос (re-export).

Реальная реализация — api/pdf_gen.py (1370 LOC). В Этапе 8 (cleanup):
- если PDF получит свой реворк — содержимое pdf_gen переедет сюда
- иначе остаётся как есть, этот файл — точка входа для слоистой архитектуры
"""
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

# Re-export публичных функций pdf_gen
from pdf_gen import (  # noqa: E402, F401
    _register_fonts_once,
    generate_quick_check_pdf,
)
