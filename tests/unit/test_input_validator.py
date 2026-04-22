"""Unit tests for api/validators/input_validator.py."""
import os
import sys

import pytest
from pydantic import ValidationError

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from validators.input_validator import QCReq, QuickCheckRequest  # noqa: E402


def _valid_payload(**overrides):
    """Минимальный валидный payload."""
    base = {
        "city_id": "astana",
        "niche_id": "MANICURE",
        "format_id": "MANICURE_HOME",
        "start_month": 5,
    }
    base.update(overrides)
    return base


def test_valid_request_passes():
    """Минимальный payload проходит валидацию."""
    req = QuickCheckRequest(**_valid_payload())
    assert req.city_id == "astana"
    assert req.niche_id == "MANICURE"
    assert req.format_id == "MANICURE_HOME"
    assert req.start_month == 5
    # Дефолты
    assert req.cls == "Стандарт"
    assert req.qty == 1
    assert req.area_m2 == 0
    assert req.capital == 0
    assert req.founder_works is False
    assert req.capex_level == "стандарт"


def test_qcreq_alias_matches():
    """QCReq — обратная совместимость с QuickCheckRequest."""
    assert QCReq is QuickCheckRequest


def test_negative_capital_fails():
    """capital < 0 → ValidationError."""
    with pytest.raises(ValidationError) as exc:
        QuickCheckRequest(**_valid_payload(capital=-100))
    assert "capital" in str(exc.value)


def test_zero_qty_fails():
    """qty < 1 → ValidationError."""
    with pytest.raises(ValidationError):
        QuickCheckRequest(**_valid_payload(qty=0))


def test_negative_area_fails():
    """area_m2 < 0 → ValidationError."""
    with pytest.raises(ValidationError):
        QuickCheckRequest(**_valid_payload(area_m2=-10))


def test_missing_required_field_fails():
    """Отсутствие city_id / niche_id / format_id → ValidationError."""
    payload = _valid_payload()
    payload.pop("city_id")
    with pytest.raises(ValidationError) as exc:
        QuickCheckRequest(**payload)
    assert "city_id" in str(exc.value)


def test_start_month_none_allowed():
    """start_month=None разрешён в Pydantic — calculator выдаёт кастомное 400.

    Нельзя ставить Field(ge=1, le=12) — иначе Pydantic вернёт авто-422
    с другим текстом, что сломает baseline_no_start_month.
    """
    req = QuickCheckRequest(**_valid_payload(start_month=None))
    assert req.start_month is None


def test_specific_answers_dict():
    """specific_answers как dict сохраняется."""
    sa = {"experience": "none", "entrepreneur_role": "owner_plus_master"}
    req = QuickCheckRequest(**_valid_payload(specific_answers=sa))
    assert req.specific_answers == sa


def test_capital_zero_allowed():
    """capital=0 проходит (анкета без указания капитала)."""
    req = QuickCheckRequest(**_valid_payload(capital=0))
    assert req.capital == 0
