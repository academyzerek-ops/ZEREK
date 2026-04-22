"""api/pdf_gen.py — Thin re-export для legacy импортов.

Реальная реализация переехала в Этапе 8.5 в:
- api/renderers/pdf_renderer.py

Этот файл сохраняется для обратной совместимости (импорты
`from pdf_gen import generate_quick_check_pdf` продолжают работать).
"""
from renderers.pdf_renderer import *  # noqa: F401, F403
from renderers.pdf_renderer import generate_quick_check_pdf, _register_fonts_once  # noqa: F401
