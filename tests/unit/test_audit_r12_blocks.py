"""Unit-тесты R12.5 audit rules (audit/rules/r12_blocks.py).

Эмулируем pdf_text страничной разбивкой реального Jinja-рендера
(WeasyPrint локально может быть недоступен, поэтому из HTML по
`<section class="page">` собираем массив страниц-текстов).

Контракт: каждое правило срабатывает только когда engine_result.is_r12=True
и условия триггера выполнены. На «правильных» сценариях ноль findings.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from audit.rules.r12_blocks import (  # noqa: E402
    check_r12_antipattern_visible,
    check_r12_explanation_block_for_novice,
    check_r12_strategy_block_on_marketing,
    check_r12_level_label_on_passport,
    check_r12_strategy_label_on_passport,
)


_PAGE_PAT = re.compile(
    r'<section class="(?:cover|page)[^"]*"[^>]*>(.*?)</section>',
    re.DOTALL,
)
_TAG_PAT = re.compile(r"<[^>]+>")


def _html_to_pages(html: str):
    """HTML → список текстов страниц (грубая имитация pdftotext постранично).

    Включаем `<section class="cover">` чтобы индексация страниц совпадала
    с реальным PDF (cover = page 0, Паспорт = 1, Итог = 2, …).
    """
    pages = []
    for m in _PAGE_PAT.finditer(html):
        body = m.group(1)
        text = _TAG_PAT.sub(" ", body)
        text = re.sub(r"\s+", " ", text).strip()
        pages.append(text)
    return pages


def _render(scenario_inputs):
    """Прогнать сценарий через QuickCheckCalculator + Jinja → (pages, engine_flat)."""
    import logging
    logging.disable(logging.CRITICAL)
    from main import db, db_error  # noqa: WPS433
    if not db:
        pytest.skip(f"DB не загрузилась: {db_error}")
    from validators.input_validator import QuickCheckRequest
    from calculators.quick_check import QuickCheckCalculator
    from renderers.pdf_renderer_weasyprint import (
        build_pdf_context, create_jinja_env, TEMPLATE_FILE,
    )
    from audit.runner import _flatten_engine

    sa = {"experience": scenario_inputs.get("experience") or "none"}
    if scenario_inputs.get("strategy"):
        sa["strategy"] = scenario_inputs["strategy"]
    if scenario_inputs.get("level"):
        sa["level"] = scenario_inputs["level"]
    req = QuickCheckRequest(
        niche_id=scenario_inputs["niche"],
        format_id=scenario_inputs["format"],
        city_id=scenario_inputs["city"],
        area_m2=10, loc_type="retail_med",
        capital=int(scenario_inputs.get("capital") or 700_000),
        start_month=int(scenario_inputs.get("start_month") or 5),
        capex_level="стандарт",
        specific_answers=sa,
    )
    result = QuickCheckCalculator(db).run(req)
    ctx = build_pdf_context(result)
    env = create_jinja_env()
    html = env.get_template(TEMPLATE_FILE).render(**ctx)
    pages = _html_to_pages(html)
    engine_flat = _flatten_engine(result, ctx)
    return pages, engine_flat


# ────────────────────────────────────────────────────────────────────────────
# Сценарий A: HOME × none × middle × Astana — explanation_block ✓, antipattern нет.
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def s_home_none_middle():
    return _render({
        "niche": "MANICURE", "format": "MANICURE_HOME", "city": "ASTANA",
        "experience": "none", "strategy": "middle", "capital": 700_000,
    })


def test_explanation_block_visible_for_novice(s_home_none_middle):
    pages, eng = s_home_none_middle
    findings = check_r12_explanation_block_for_novice(pages, eng)
    assert findings == [], findings


def test_no_antipattern_for_middle(s_home_none_middle):
    pages, eng = s_home_none_middle
    # триггер не сработал — правило молчит
    assert eng["r12_has_antipattern"] is False
    findings = check_r12_antipattern_visible(pages, eng)
    assert findings == [], findings


def test_strategy_block_visible(s_home_none_middle):
    pages, eng = s_home_none_middle
    findings = check_r12_strategy_block_on_marketing(pages, eng)
    assert findings == [], findings


def test_strategy_row_on_passport(s_home_none_middle):
    pages, eng = s_home_none_middle
    findings = check_r12_strategy_label_on_passport(pages, eng)
    assert findings == [], findings


# ────────────────────────────────────────────────────────────────────────────
# Сценарий V: HOME × none × aggressive — антипаттерн виден.
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def s_home_none_aggressive():
    return _render({
        "niche": "MANICURE", "format": "MANICURE_HOME", "city": "ASTANA",
        "experience": "none", "strategy": "aggressive", "capital": 700_000,
    })


def test_antipattern_visible_for_novice_aggressive(s_home_none_aggressive):
    pages, eng = s_home_none_aggressive
    assert eng["r12_has_antipattern"] is True
    findings = check_r12_antipattern_visible(pages, eng)
    assert findings == [], findings


def test_explanation_block_still_visible_for_aggressive_novice(s_home_none_aggressive):
    pages, eng = s_home_none_aggressive
    findings = check_r12_explanation_block_for_novice(pages, eng)
    assert findings == [], findings


# ────────────────────────────────────────────────────────────────────────────
# Сценарий S6: SALON_RENT × experienced × auto-premium — level_label виден.
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def s_salon_experienced():
    return _render({
        "niche": "MANICURE", "format": "MANICURE_SOLO", "city": "ASTANA",
        "experience": "experienced", "strategy": "middle", "capital": 700_000,
    })


def test_level_label_premium_on_passport(s_salon_experienced):
    pages, eng = s_salon_experienced
    assert eng["r12_level"] == "premium"
    assert "Премиум" in eng["r12_level_label"]
    findings = check_r12_level_label_on_passport(pages, eng)
    assert findings == [], findings


def test_no_explanation_block_for_experienced(s_salon_experienced):
    pages, eng = s_salon_experienced
    # триггер experience=none не сработал
    findings = check_r12_explanation_block_for_novice(pages, eng)
    assert findings == [], findings


# ────────────────────────────────────────────────────────────────────────────
# Сценарий S8: STUDIO × middle × nice + aggressive — level=nice + strategy=Агрессивная.
# ────────────────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def s_studio_nice_aggressive():
    return _render({
        "niche": "MANICURE", "format": "MANICURE_STANDARD", "city": "ASTANA",
        "experience": "middle", "strategy": "aggressive", "level": "nice",
        "capital": 1_500_000,
    })


def test_level_label_nice_on_passport(s_studio_nice_aggressive):
    pages, eng = s_studio_nice_aggressive
    assert eng["r12_level"] == "nice"
    findings = check_r12_level_label_on_passport(pages, eng)
    assert findings == [], findings


def test_strategy_aggressive_block_on_marketing(s_studio_nice_aggressive):
    pages, eng = s_studio_nice_aggressive
    assert eng["r12_strategy"] == "aggressive"
    findings = check_r12_strategy_block_on_marketing(pages, eng)
    assert findings == [], findings


# ────────────────────────────────────────────────────────────────────────────
# Не-A1 ниша: правила должны молчать (is_r12=False).
# ────────────────────────────────────────────────────────────────────────────


def test_non_a1_niche_skipped():
    """Для ниши без formats_r12 правила возвращают [] вообще без проверок."""
    pages = ["", "", "", ""]
    eng = {
        "is_r12": False,
        "r12_experience": "",
        "r12_strategy": "",
        "r12_level": "",
        "r12_level_label": "",
        "r12_strategy_label": "",
        "r12_has_antipattern": False,
        "r12_n_explanation_blocks": 0,
    }
    assert check_r12_antipattern_visible(pages, eng) == []
    assert check_r12_explanation_block_for_novice(pages, eng) == []
    assert check_r12_strategy_block_on_marketing(pages, eng) == []
    assert check_r12_level_label_on_passport(pages, eng) == []
    assert check_r12_strategy_label_on_passport(pages, eng) == []
