"""api/validators/input_validator.py — Pydantic валидация входов API.

Перенесено из main.py в Этапе 6 рефакторинга.

ВАЖНО: основная валидация `start_month` (∈ 1..12, обязательный) остаётся
в QuickCheckCalculator._validate_and_resolve_cls — она требует кастомного
HTTP 400 с конкретным текстом для UI («Укажите месяц планируемого старта…»).
Если поставить тут Field(..., ge=1, le=12), FastAPI вернёт авто-422 с
другим JSON, что сломает регрессию.

Поэтому здесь только базовые pydantic-проверки типов + минимальные:
- capital ≥ 0 если указан
- start_month: Optional[int] (calculator делает 400 если None или вне диапазона)

Контракт обратной совместимости:
    from validators.input_validator import QCReq      # backward-compat alias
    from validators.input_validator import QuickCheckRequest  # новое имя
"""
from typing import Optional

from pydantic import BaseModel, field_validator


class QuickCheckRequest(BaseModel):
    """Запрос Quick Check 5 000 ₸.

    Pydantic ловит ошибки типов на границе. Бизнес-валидации (start_month
    range, HOME/SOLO marketing калибровки) — в QuickCheckCalculator,
    они требуют кастомного HTTP 400 с UI-friendly сообщением.
    """

    # ── Основные параметры (обязательные) ──
    city_id: str
    niche_id: str
    format_id: str

    # ── Параметры формата ──
    cls: str = "Стандарт"
    area_m2: float = 0
    loc_type: str = ""

    # ── Капитал и масштаб ──
    capital: Optional[int] = 0
    qty: int = 1
    founder_works: bool = False

    # ── Аренда / старт ──
    # rent_override: переопределение арендной ставки (если пользователь знает свою)
    # start_month: НЕ ставить Field(ge=1, le=12) — calculator выдаёт кастомное
    # HTTP 400 «Укажите месяц планируемого старта…», нужное UI.
    rent_override: Optional[int] = None
    start_month: Optional[int] = None

    # ── Уровень CAPEX (анкета) ──
    capex_level: str = "стандарт"

    # ── Quick Check v2 adaptive fields (optional, не меняют расчёт) ──
    has_license: Optional[str] = None     # "yes" / "no" / "in_progress"
    staff_mode: Optional[str] = None       # "self" / "hired"
    staff_count: Optional[int] = None
    specific_answers: Optional[dict] = None  # {"experience": "none", "entrepreneur_role": "owner_plus_master", ...}

    # ── Простые валидаторы ──

    @field_validator("capital")
    @classmethod
    def _capital_non_negative(cls, v: Optional[int]) -> Optional[int]:
        """Капитал не может быть отрицательным (если указан)."""
        if v is not None and v < 0:
            raise ValueError("capital не может быть отрицательным")
        return v

    @field_validator("qty")
    @classmethod
    def _qty_positive(cls, v: int) -> int:
        """qty (количество боксов/точек) должно быть >= 1."""
        if v < 1:
            raise ValueError("qty должен быть >= 1")
        return v

    @field_validator("area_m2")
    @classmethod
    def _area_non_negative(cls, v: float) -> float:
        """Площадь не может быть отрицательной (0 = HOME без аренды)."""
        if v < 0:
            raise ValueError("area_m2 не может быть отрицательной")
        return v


# ═══════════════════════════════════════════════════════════════════════
# Backward-compat alias (для кода `from main import QCReq`)
# ═══════════════════════════════════════════════════════════════════════

QCReq = QuickCheckRequest
