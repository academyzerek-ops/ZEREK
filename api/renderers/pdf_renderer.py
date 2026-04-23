"""PDF renderer — try WeasyPrint premium template, fallback to ReportLab.

Railway сейчас игнорирует railway.json с DOCKERFILE builder и остаётся
на Nixpacks, где WeasyPrint не может найти libgobject-2.0-0. До момента
когда builder переключится (через Railway Dashboard или другой способ),
мы используем ReportLab как основной рендерер.

Два модуля:
- pdf_renderer_weasyprint — премиум HTML-шаблон (требует libpango/libcairo)
- pdf_renderer_reportlab — рабочий Big4-стиль на чистом Python

Публичный API (для main.py) не меняется:
- generate_quick_check_pdf(result, niche_id, ai_risks=None) → (bytes, id, name)
- generate_pdf_filename / _register_fonts_once / _today_ru / _report_id
"""
from __future__ import annotations
import logging
import os
from typing import Any, Dict, Optional, Tuple

_log = logging.getLogger("zerek.pdf_renderer")


def _weasyprint_available() -> bool:
    """Пытается импортировать WeasyPrint. True если все C-библиотеки доступны."""
    try:
        import weasyprint  # noqa: F401
        return True
    except Exception as e:
        _log.debug("WeasyPrint unavailable: %s", e)
        return False


# ═══════════════════════════════════════════════════════════════════════
# Re-exports для совместимости с main.py (и старыми импортами)
# ═══════════════════════════════════════════════════════════════════════

# ReportLab-путь — всегда доступен, используется как fallback.
from renderers.pdf_renderer_reportlab import (  # noqa: E402,F401
    _register_fonts_once,
    _report_id,
    _today_ru,
    generate_pdf_filename,
)
from renderers.pdf_renderer_reportlab import (  # noqa: E402
    generate_quick_check_pdf as _generate_reportlab,
)

# WeasyPrint helpers — re-export для tests/unit/test_pdf_renderer.py и других
# модулей которые могут использовать Jinja2-путь. Импорт ленивый через
# __getattr__ чтобы не требовать jinja2 на старте если его нет.
_WEASY_EXPORTS = (
    "_is_solo_format", "_month_ru", "_month_short_ru", "_format_date_ru",
    "build_pdf_context", "create_jinja_env", "filter_money", "filter_money_short",
    "render_pdf", "TEMPLATE_FILE", "TEMPLATE_DIR",
)


def __getattr__(name: str):
    if name in _WEASY_EXPORTS:
        from renderers import pdf_renderer_weasyprint as _weasy
        return getattr(_weasy, name)
    raise AttributeError(f"module 'pdf_renderer' has no attribute {name!r}")


def generate_quick_check_pdf(
    result: Dict[str, Any], niche_id: str, ai_risks=None,
) -> Tuple[bytes, str, str]:
    """Рендерит PDF.

    Приоритет: WeasyPrint (премиум HTML-шаблон) → ReportLab fallback.
    ReportLab не падает на Railway и гарантированно работает.

    Принимает calc_result от QuickCheckCalculator (новый формат) — для
    ReportLab применяет render_report_v4 чтобы получить legacy
    block_1..block_12 структуру.

    Возвращает (pdf_bytes, report_id, filename).
    """
    if _weasyprint_available():
        try:
            from renderers.pdf_renderer_weasyprint import (
                generate_quick_check_pdf as _generate_weasy,
            )
            return _generate_weasy(result, niche_id, ai_risks=ai_risks)
        except Exception as e:
            _log.warning(
                "WeasyPrint render failed, falling back to ReportLab: %s", e
            )
    # ReportLab ждёт legacy block_1..block_12 из render_report_v4.
    rendered = result
    if "block_1" not in result:
        try:
            from renderers.quick_check_renderer import render_report_v4
            rendered = render_report_v4(result)
        except Exception as e:
            _log.warning("render_report_v4 failed, using raw result: %s", e)
    return _generate_reportlab(rendered, niche_id, ai_risks=ai_risks)


def which_engine() -> str:
    """Возвращает активный движок для /pdf-health."""
    return "weasyprint" if _weasyprint_available() else "reportlab"
