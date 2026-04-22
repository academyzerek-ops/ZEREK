"""Unit tests for api/renderers/quick_check_renderer."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from renderers.quick_check_renderer import (  # noqa: E402
    LOCATION_TYPES_META,
    _entrepreneur_role_text,
    _experience_label,
    _fmt_kzt,
    _fmt_kzt_short,
    _fmt_range_kzt,
    _parse_typical_staff,
    _payroll_label,
    _split_staff_into_groups,
    fmt,
    render_for_api,
)


# ═══ Форматтеры ════════════════════════════════════════════════════════


def test_fmt_kzt_thousands():
    """1 000 ₸ → '1 тыс ₸'."""
    assert _fmt_kzt(1000) == "1 тыс ₸"
    assert _fmt_kzt(50_000) == "50 тыс ₸"


def test_fmt_kzt_millions():
    """1.5 млн → '1,5 млн ₸' (запятая разделитель)."""
    assert _fmt_kzt(1_500_000) == "1,5 млн ₸"


def test_fmt_kzt_none_returns_dash():
    """None → '—' (em dash)."""
    assert _fmt_kzt(None) == "—"


def test_fmt_kzt_short_no_currency():
    """Короткий формат без ₸."""
    assert _fmt_kzt_short(50_000) == "50 тыс"
    assert "₸" not in _fmt_kzt_short(2_000_000)


def test_fmt_range_kzt():
    """Диапазон '50 тыс–100 тыс'."""
    rng = _fmt_range_kzt(50_000, 100_000)
    assert "тыс" in rng
    assert "–" in rng


def test_fmt_range_kzt_equal_returns_single():
    """Если low==high — возвращает одно значение, не диапазон."""
    assert _fmt_range_kzt(50_000, 50_000) == _fmt_kzt(50_000)


def test_fmt_handles_thousands_with_spaces():
    """fmt(123456) → '123 456' (пробел разделитель)."""
    assert fmt(123456) == "123 456"
    assert fmt(None) == "—"


# ═══ Парсеры штата ═══════════════════════════════════════════════════════


def test_parse_typical_staff():
    """'барбер:4|админ:1' → 2 элемента."""
    out = _parse_typical_staff("барбер:4|админ:1")
    assert out == [{"role": "барбер", "count": 4}, {"role": "админ", "count": 1}]


def test_split_staff_separates_assistants():
    """Админ → assistants, барбер → masters."""
    staff = [{"role": "барбер", "count": 4}, {"role": "администратор", "count": 1}]
    groups = _split_staff_into_groups(staff)
    assert groups["masters"] == [{"role": "барбер", "count": 4}]
    assert groups["assistants"] == [{"role": "администратор", "count": 1}]


# ═══ Текстовые лейблы ═══════════════════════════════════════════════════


def test_entrepreneur_role_owner_only():
    out = _entrepreneur_role_text("owner_only", [{"role": "X", "count": 3}])
    assert out["label_rus"] == "Только владелец"
    assert "3" in out["description_rus"]


def test_entrepreneur_role_owner_plus():
    out = _entrepreneur_role_text("owner_plus_барбер", [])
    assert "Владелец + барбер" in out["label_rus"]
    assert out["subtract_role"] == "барбер"


def test_payroll_label_known_types():
    assert "Оклад" in _payroll_label("salary")
    assert "Сдельно" in _payroll_label("piece")


def test_experience_label_levels():
    assert "Нет опыта" in _experience_label("none")
    assert "1–2 года" in _experience_label("some")


# ═══ LOCATION_TYPES_META ═════════════════════════════════════════════════


def test_location_types_meta_has_home_and_street():
    assert "home" in LOCATION_TYPES_META
    assert "street" in LOCATION_TYPES_META
    assert LOCATION_TYPES_META["home"]["label"] == "Из дома"


# ═══ render_for_api ══════════════════════════════════════════════════════


def test_render_for_api_keeps_new_format_blocks():
    """render_for_api копирует block1..10 / block_season / user_inputs из calc_result."""
    calc_result = {
        "input": {"city_name": "Test", "city_id": "test", "niche_id": "X", "format_id": "X_HOME",
                  "capital": 0, "loc_type": "home", "class": "Стандарт"},
        "financials": {"check_med": 1000, "traffic_med": 5, "cogs_pct": 0.3, "loss_pct": 0.03,
                       "rent_month": 0, "marketing": 0, "utilities": 0, "consumables": 0,
                       "software": 0, "transport": 0, "sez_month": 0},
        "staff": {"fot_full_med": 0, "fot_net_med": 0, "headcount": 0, "positions": ""},
        "capex": {"total": 100, "breakdown": {}, "investment_range": {"min": 100, "max": 200}},
        "scenarios": {"pess": {}, "base": {"окупаемость": {}}, "opt": {}},
        "breakeven": {},
        "tax": {"rate_pct": 3, "regime": "УСН"},
        "verdict": {"color": "green", "text": "ok", "reasons": []},
        "products": [], "insights": [], "marketing": [],
        "alternatives": [],
        "owner_economics": {},
        "cashflow": [],
        # Новый формат от calculator
        "block1": {"color": "green", "score": 17},
        "block5": {"scenarios": {}},
        "block_season": {"coefs": [1.0] * 12},
        "user_inputs": {"specific_answers": {"experience": "none"}},
    }
    report = render_for_api(calc_result)
    # Legacy блоки от render_report_v4
    assert "block_1" in report
    assert "block_5" in report
    assert "health" in report
    # Новый формат скопирован
    assert report["block1"]["color"] == "green"
    assert report["block5"]["scenarios"] == {}
    assert "block_season" in report
    assert report["user_inputs"]["specific_answers"]["experience"] == "none"
