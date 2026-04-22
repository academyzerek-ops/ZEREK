"""Unit tests for api/services/risk_service.py — Block 9 риски."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.risk_service import (  # noqa: E402
    FORMAT_RISK_FILTERS,
    GENERIC_RISKS_BY_ARCHETYPE,
    HOME_SPECIFIC_RISKS,
    _filter_risks_by_format,
)


def test_home_filter_excludes_rent_and_hiring():
    """MANICURE_HOME исключает риски с 'аренд', 'найм', 'договор'."""
    risks = [
        {"title": "Аренда дорогая", "text": "проблема с арендой"},
        {"title": "Найм мастеров", "text": "найм проблематичен"},
        {"title": "Болезнь", "text": "нет здоровья"},
    ]
    filtered = _filter_risks_by_format(risks, "MANICURE_HOME")
    titles = [r["title"] for r in filtered]
    assert "Аренда дорогая" not in titles
    assert "Найм мастеров" not in titles
    assert "Болезнь" in titles  # не содержит ключевых слов фильтра


def test_standard_format_no_filter():
    """STANDARD-форматы не имеют фильтра — все риски проходят."""
    risks = [
        {"title": "Аренда", "text": "большая аренда"},
        {"title": "Найм", "text": "найм мастеров"},
    ]
    filtered = _filter_risks_by_format(risks, "MANICURE_STANDARD")
    assert len(filtered) == 2


def test_home_specific_risks_for_home_only():
    """HOME_SPECIFIC_RISKS содержит физсостояние, потолок, санитарию."""
    titles = [r["title"] for r in HOME_SPECIFIC_RISKS]
    assert "Зависимость от физсостояния" in titles
    assert "Потолок дохода одного мастера" in titles
    assert "Санитарные нормы без контроля" in titles


def test_generic_risks_archetype_a_has_5_items():
    """Архетип A (услуги): минимум 5 рисков для fallback."""
    assert len(GENERIC_RISKS_BY_ARCHETYPE["A"]) >= 5


def test_generic_risks_have_required_fields():
    """Каждый риск имеет title, probability, impact, text, mitigation."""
    for arch, risks in GENERIC_RISKS_BY_ARCHETYPE.items():
        for r in risks:
            assert "title" in r
            assert "probability" in r
            assert "impact" in r
            assert "text" in r
            assert "mitigation" in r


def test_format_risk_filters_have_home_only():
    """Только *_HOME форматы имеют фильтры (для STANDARD фильтр не нужен)."""
    for fmt_id in FORMAT_RISK_FILTERS:
        assert fmt_id.endswith("_HOME"), f"{fmt_id} не HOME-формат"
