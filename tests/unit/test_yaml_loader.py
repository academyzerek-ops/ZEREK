"""Unit tests for YAML-first overlay (api/loaders/niche_loader)."""
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from loaders.niche_loader import (  # noqa: E402
    _find_yaml_format,
    _map_yaml_to_capex,
    _map_yaml_to_financials,
    _map_yaml_to_formats,
    _map_yaml_to_staff,
    _map_yaml_to_taxes,
    load_niche_yaml,
    overlay_yaml_on_xlsx,
)


# ═══ load_niche_yaml ════════════════════════════════════════════════════


def test_load_manicure_yaml_returns_dict():
    """data/niches/MANICURE_data.yaml существует и парсится."""
    data = load_niche_yaml("MANICURE")
    assert data is not None
    assert "formats" in data
    assert "seasonality" in data
    assert "risks" in data


def test_load_unknown_niche_returns_none():
    """Несуществующая ниша → None."""
    assert load_niche_yaml("NONEXISTENT_NICHE_XYZ") is None


def test_yaml_has_4_manicure_formats():
    """MANICURE YAML содержит HOME/SOLO/STANDARD/PREMIUM."""
    data = load_niche_yaml("MANICURE")
    ids = {f["id"] for f in data["formats"]}
    assert ids == {"HOME", "SOLO", "STANDARD", "PREMIUM"}


# ═══ _find_yaml_format ══════════════════════════════════════════════════


def test_find_yaml_format_by_full_id():
    """format_id 'MANICURE_HOME' → YAML format с id='HOME'."""
    data = load_niche_yaml("MANICURE")
    fmt = _find_yaml_format(data, "MANICURE_HOME", "MANICURE")
    assert fmt is not None
    assert fmt["id"] == "HOME"


def test_find_yaml_format_unknown_returns_none():
    """Unknown format_id → None."""
    data = load_niche_yaml("MANICURE")
    assert _find_yaml_format(data, "MANICURE_XYZ", "MANICURE") is None


# ═══ Mappers — структура полей ═══════════════════════════════════════════


def test_map_yaml_to_financials_home():
    """HOME mapper выдаёт совместимые с xlsx ключи."""
    data = load_niche_yaml("MANICURE")
    home = _find_yaml_format(data, "MANICURE_HOME", "MANICURE")
    fin = _map_yaml_to_financials(home, data)
    assert fin["check_min"] == 3500
    assert fin["check_med"] == 5000
    assert fin["check_max"] == 6500
    assert fin["cogs_pct"] == 0.12
    assert fin["marketing_med"] == 45000
    assert fin["other_opex_med"] == 5000
    assert fin["rampup_months"] == 3
    assert fin["rampup_start_pct"] == 0.30
    # traffic пересчитан из max_per_day × load
    assert fin["traffic_med"] == 3   # 6 × 0.50
    assert fin["traffic_min"] == 2   # 6 × 0.30 round
    assert fin["traffic_max"] == 4   # 6 × 0.75 = 4.5 → round half-to-even = 4
    # сезонность s01..s12
    assert fin["s01"] == 0.80
    assert fin["s12"] == 1.30


def test_map_yaml_to_capex_home():
    """HOME CAPEX mapper выдаёт правильные суммы."""
    data = load_niche_yaml("MANICURE")
    home = _find_yaml_format(data, "MANICURE_HOME", "MANICURE")
    cap = _map_yaml_to_capex(home)
    assert cap["capex_med"] == 330_000
    assert cap["equipment"] == 150_000
    assert cap["furniture"] == 30_000
    assert cap["first_stock"] == 60_000
    assert cap["working_cap_3m"] == 45_000
    assert cap["legal"] == 5_000


def test_map_yaml_to_staff_home():
    """HOME = ИП без ФОТ владельца."""
    data = load_niche_yaml("MANICURE")
    home = _find_yaml_format(data, "MANICURE_HOME", "MANICURE")
    staff = _map_yaml_to_staff(home)
    assert staff["fot_net_med"] == 0
    assert staff["fot_full_med"] == 0
    assert staff["headcount"] == 0


def test_map_yaml_to_staff_standard():
    """STANDARD: 5 человек, ФОТ 1.2 млн брутто."""
    data = load_niche_yaml("MANICURE")
    std = _find_yaml_format(data, "MANICURE_STANDARD", "MANICURE")
    staff = _map_yaml_to_staff(std)
    assert staff["headcount"] == 5
    assert staff["fot_net_med"] == 1_200_000
    # fot_full = monthly × (1 + employer_taxes_pct=0.115)
    assert staff["fot_full_med"] == int(1_200_000 * 1.115)


def test_map_yaml_to_taxes_premium():
    """PREMIUM на ОУР ТОО."""
    data = load_niche_yaml("MANICURE")
    prem = _find_yaml_format(data, "MANICURE_PREMIUM", "MANICURE")
    tax = _map_yaml_to_taxes(prem)
    assert tax["tax_regime"] == "ОУР ТОО"


def test_map_yaml_to_formats_training_required_home():
    """HOME требует обучение (training_required=True)."""
    data = load_niche_yaml("MANICURE")
    home = _find_yaml_format(data, "MANICURE_HOME", "MANICURE")
    fmt = _map_yaml_to_formats(home)
    assert fmt["format_name"] == "Мастер на дому"
    assert fmt["training_required"] is True


# ═══ overlay_yaml_on_xlsx ════════════════════════════════════════════════


def test_overlay_skips_non_manicure():
    """Для не-MANICURE — xlsx_row возвращается без изменений."""
    xlsx_row = {"check_med": 1000, "fake_field": "xlsx"}
    out = overlay_yaml_on_xlsx(xlsx_row, "BARBER", "FINANCIALS", "BARBER_STANDARD", "Стандарт")
    assert out == xlsx_row


def test_overlay_skips_manicure_home():
    """MANICURE_HOME — xlsx канон, YAML НЕ применяется (защита baseline)."""
    xlsx_row = {"check_med": 5000, "marketing_med": 45000}
    out = overlay_yaml_on_xlsx(xlsx_row, "MANICURE", "FINANCIALS", "MANICURE_HOME", "Стандарт")
    assert out is xlsx_row  # тот же объект, не мутирует


def test_overlay_applies_to_manicure_solo():
    """MANICURE_SOLO — YAML overlay даёт правильный marketing_med (xlsx NaN)."""
    import math
    xlsx_row = {
        "format_id": "MANICURE_SOLO",
        "class": "стандарт",
        "check_med": 6000,  # старое xlsx значение
        "marketing_med": math.nan,  # NaN — YAML должен заполнить
    }
    out = overlay_yaml_on_xlsx(xlsx_row, "MANICURE", "FINANCIALS", "MANICURE_SOLO", "Стандарт")
    # YAML overrides:
    assert out["check_med"] == 7000   # YAML SOLO med
    assert out["marketing_med"] == 70_000  # YAML SOLO marketing
    assert out["other_opex_med"] == 25_000
    # format_id сохранён
    assert out["format_id"] == "MANICURE_SOLO"


def test_overlay_applies_to_manicure_standard_capex():
    """MANICURE_STANDARD CAPEX overlay даёт 4.5М (vs 600K xlsx)."""
    xlsx_row = {"format_id": "MANICURE_STANDARD", "capex_med": 600_000}
    out = overlay_yaml_on_xlsx(xlsx_row, "MANICURE", "CAPEX", "MANICURE_STANDARD", "Стандарт")
    assert out["capex_med"] == 4_500_000
    assert out["equipment"] == 1_200_000


def test_overlay_unknown_sheet_passes_through():
    """Sheet не в _SHEET_MAPPERS (например, MARKETING) → xlsx без изменений."""
    xlsx_row = {"some": "data"}
    out = overlay_yaml_on_xlsx(xlsx_row, "MANICURE", "MARKETING", "MANICURE_SOLO", "Стандарт")
    assert out == xlsx_row
