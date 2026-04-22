"""Unit tests for api/services/pricing_service.py — соцплатежи ИП КЗ 2026."""
import os
import sys

# Включаем api/ в sys.path (как main.py делает)
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.pricing_service import calc_owner_social_payments  # noqa: E402
from engine import MRP_2026, OWNER_SOCIAL_BASE_MRP, OWNER_SOCIAL_RATE  # noqa: E402


def test_default_base_is_cap():
    """Без аргумента — используется максимум 50 МРП × 22% ≈ 47 575 ₸."""
    cap = MRP_2026 * OWNER_SOCIAL_BASE_MRP
    expected = int(cap * OWNER_SOCIAL_RATE)
    assert calc_owner_social_payments() == expected
    # Конкретное значение КЗ 2026: 4325 × 50 × 0.22 = 47 575
    assert calc_owner_social_payments() == 47_575


def test_base_below_cap():
    """Декларируемая база ниже капа → используется как есть."""
    assert calc_owner_social_payments(100_000) == int(100_000 * OWNER_SOCIAL_RATE)
    assert calc_owner_social_payments(100_000) == 22_000


def test_base_above_cap_is_clamped():
    """База выше капа (50 МРП) — капается до максимума."""
    high = MRP_2026 * OWNER_SOCIAL_BASE_MRP * 10  # 10× кап
    assert calc_owner_social_payments(high) == calc_owner_social_payments()


def test_zero_base_returns_zero():
    """База = 0 → платежи 0 (для юр. чистоты)."""
    assert calc_owner_social_payments(0) == 0


def test_returns_int():
    """Всегда int (округление к целому ₸)."""
    result = calc_owner_social_payments(12_345)
    assert isinstance(result, int)
