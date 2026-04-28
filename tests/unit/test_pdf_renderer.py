"""Unit tests for new WeasyPrint + Jinja2 pdf_renderer."""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from renderers.pdf_renderer import (  # noqa: E402
    _is_solo_format,
    _month_ru,
    _month_short_ru,
    _format_date_ru,
    build_pdf_context,
    create_jinja_env,
    filter_money,
    filter_money_short,
    generate_pdf_filename,
)


# ═══ Фильтры ═══════════════════════════════════════════════════════════


def test_money_filter_basic():
    assert filter_money(480_000) == "480 000"
    assert filter_money(0) == "0"
    assert filter_money(None) == "0"


def test_money_filter_empty_string():
    assert filter_money("") == "0"


def test_money_filter_float():
    assert filter_money(480_000.5) == "480 000"


def test_money_short_thousands():
    assert filter_money_short(480_000) == "480K"
    assert filter_money_short(1_000) == "1K"


def test_money_short_millions():
    assert filter_money_short(2_500_000) == "2.5М"
    assert filter_money_short(1_000_000) == "1М"  # .0М убирается


def test_money_short_small():
    assert filter_money_short(500) == "500"
    assert filter_money_short(0) == "0"


def test_money_short_none_and_empty():
    assert filter_money_short(None) == "0"
    assert filter_money_short("") == "0"


# ═══ Хелперы ═══════════════════════════════════════════════════════════


def test_month_ru():
    assert _month_ru(5) == "Май"
    assert _month_ru(12) == "Декабрь"
    # out-of-range → январь
    assert _month_ru(0) == "Январь"
    assert _month_ru(13) == "Январь"


def test_month_short_ru():
    assert _month_short_ru(5) == "май"
    assert _month_short_ru(1) == "янв"


def test_is_solo_format():
    assert _is_solo_format("MANICURE_HOME") is True
    assert _is_solo_format("MANICURE_SOLO") is True
    assert _is_solo_format("MANICURE_STANDARD") is False
    assert _is_solo_format("") is False


def test_format_date_ru():
    from datetime import datetime
    dt = datetime(2026, 4, 23)
    assert _format_date_ru(dt) == "23 апреля 2026"


def test_generate_pdf_filename():
    name = generate_pdf_filename("Маникюр", "Астана", "На дому")
    assert name.startswith("ZEREK_Анализ_Маникюр_На_дому_Астана_")
    assert name.endswith(".pdf")


# ═══ Template loads ═══════════════════════════════════════════════════


def test_jinja_env_loads_template():
    """Шаблон quick_check.html загружается без синтаксических ошибок."""
    env = create_jinja_env()
    tmpl = env.get_template("quick_check.html")
    assert tmpl is not None


def test_build_pdf_context_minimal():
    """build_pdf_context работает на минимальном result."""
    minimal = {
        "input": {"niche_id": "MANICURE", "format_id": "MANICURE_HOME",
                   "city_name": "Астана", "start_month": 5},
    }
    ctx = build_pdf_context(minimal)
    # Обязательные ключи по спецификации шаблона.
    for key in ("inp", "cap", "vrd", "report_id", "today_date", "verdict_class"):
        assert key in ctx, f"отсутствует ключ {key!r}"
    assert ctx["inp"]["niche_name_ru"]  # из data/kz/niches_registry.yaml
    assert ctx["report_id"].startswith("QC-")


def test_template_renders_with_minimal_context():
    """Шаблон не падает на пустом minimal контексте (ChainableUndefined)."""
    minimal = {
        "input": {"niche_id": "MANICURE", "format_id": "MANICURE_HOME",
                   "city_name": "Астана", "start_month": 5},
        "capex": {},
        "block1": {"color": "green", "verdict_statement": "Test"},
        "block10": {"color": "green"},
    }
    ctx = build_pdf_context(minimal)
    env = create_jinja_env()
    tmpl = env.get_template("quick_check.html")
    html = tmpl.render(**ctx)
    assert "<html" in html.lower()
    assert len(html) > 10_000  # ≥ 10KB


@pytest.mark.skipif(
    True,
    reason="WeasyPrint требует системные Pango/Cairo — верифицируется на Railway",
)
def test_pdf_renders_bytes():  # pragma: no cover
    """End-to-end PDF. Пропускается локально без системных libs."""
    from renderers.pdf_renderer import render_pdf
    minimal = {
        "input": {"niche_id": "MANICURE", "format_id": "MANICURE_HOME",
                   "city_name": "Астана", "start_month": 5},
        "block1": {"color": "green"},
    }
    pdf_bytes = render_pdf(minimal)
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 50_000
