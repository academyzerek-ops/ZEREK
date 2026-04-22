"""Unit tests for api/services/seasonality_service.py — ramp + сезонность."""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(_ROOT, "api"))

from services.seasonality_service import (  # noqa: E402
    calc_revenue_monthly,
    compute_block_season,
    compute_first_year_chart,
)


# ─── MANICURE_HOME realistic fin (из baseline) ─────────────────────────
MANICURE_HOME_FIN = {
    "check_med": 5250,   # после city_coef Астана 1.05 × 5000
    "traffic_med": 3,
    "rampup_months": 3,
    "rampup_start_pct": 0.30,
    "s01": 0.80, "s02": 0.85, "s03": 1.15, "s04": 0.75,
    "s05": 1.10, "s06": 1.10, "s07": 1.00, "s08": 1.00,
    "s09": 1.00, "s10": 0.95, "s11": 0.85, "s12": 1.30,
}


# ═══ calc_revenue_monthly ════════════════════════════════════════════════


def test_ramp_month_1_is_start_pct():
    """Месяц 1 ramp-up: выручка = base × start_pct × season."""
    # Месяц 1, cal_month=1 (январь, s01=0.80)
    # ramp = 0.30 + (1-0.30) × (1/3) = 0.30 + 0.233 = 0.533
    # rev = 5250 × 3 × 30 × 0.80 × 0.533 ≈ 201 348
    rev = calc_revenue_monthly(MANICURE_HOME_FIN, cal_month=1, razgon_month=1)
    assert 200_000 <= rev <= 203_000, f"got {rev}"


def test_ramp_after_rampup_months_is_1():
    """Месяц > rampup_months ramp = 1.0, применяется только сезонность."""
    # Месяц 4 работы, cal_month=7 (июль, s07=1.00)
    # rev = 5250 × 3 × 30 × 1.00 × 1.00 = 472_500
    rev = calc_revenue_monthly(MANICURE_HOME_FIN, cal_month=7, razgon_month=4)
    assert rev == 472_500


def test_seasonality_applied_by_cal_month():
    """Сезонность читается по cal_month, независимо от razgon_month."""
    # cal_month=12 (декабрь, s12=1.30), razgon=5 (ramp=1.0)
    # rev = 472500 × 1.30 = 614_250
    rev = calc_revenue_monthly(MANICURE_HOME_FIN, cal_month=12, razgon_month=5)
    assert rev == 614_250


def test_ramp_at_rampup_months_is_1():
    """В точности на месяце rampup_months ramp становится 1.0."""
    # Месяц 3 работы, cal_month=7 (s=1.00) → rev = 472_500 × 1.0 × 1.0
    rev = calc_revenue_monthly(MANICURE_HOME_FIN, cal_month=7, razgon_month=3)
    assert rev == 472_500


# ═══ compute_first_year_chart ═════════════════════════════════════════════


def test_narrative_january_start_is_slump():
    """Старт в январе (s01=0.80, s02=0.85) → avg=0.825 ≤ 0.90 → просадка."""
    result = {
        "input": {"start_month": 1},
        "financials": MANICURE_HOME_FIN,
        "pnl_aggregates": {"mature": {"revenue_monthly": 472_500}},
    }
    chart = compute_first_year_chart(result)
    assert "просадку" in chart["narrative"], chart["narrative"]


def test_narrative_may_start_is_peak():
    """Старт в мае (s05=1.10, s06=1.10) → avg=1.10 ≥ 1.05 → пик."""
    result = {
        "input": {"start_month": 5},
        "financials": MANICURE_HOME_FIN,
        "pnl_aggregates": {"mature": {"revenue_monthly": 472_500}},
    }
    chart = compute_first_year_chart(result)
    assert "удачно попадает на сезонный пик" in chart["narrative"], chart["narrative"]


def test_first_year_chart_has_12_months():
    """Выходная структура: 12 месяцев с калерндарными лейблами и цветами."""
    result = {
        "input": {"start_month": 4},  # апрель
        "financials": MANICURE_HOME_FIN,
        "pnl_aggregates": {"mature": {"revenue_monthly": 472_500}},
    }
    chart = compute_first_year_chart(result)
    assert len(chart["months"]) == 12
    assert chart["months"][0]["calendar_label"] == "Апр"
    assert chart["months"][0]["color"] == "ramp"  # первый месяц — всегда ramp
    assert chart["start_month_label"] == "Апрель"


# ═══ compute_block_season ════════════════════════════════════════════════


def test_block_season_uses_niche_coefs():
    """Если s01..s12 заполнены — используются они, source=niche."""
    raw_fin = MANICURE_HOME_FIN  # со всеми s01..s12
    block = compute_block_season(raw_fin)
    assert block["source"] == "niche"
    assert block["coefs"][0] == 0.80  # s01
    assert block["coefs"][11] == 1.30  # s12


def test_block_season_falls_back_to_default():
    """Пустой raw_fin → DEFAULT_SEASONALITY, source=default."""
    block = compute_block_season({})
    assert block["source"] == "default"
    assert len(block["coefs"]) == 12


def test_block_season_peaks_and_troughs():
    """Пики > 1.05, просадки < 0.95."""
    block = compute_block_season(MANICURE_HOME_FIN)
    # MANICURE: декабрь 1.30, март 1.15, май 1.10, июн 1.10 — пики
    assert "дек" in block["peaks"]
    assert "мар" in block["peaks"]
    # янв 0.80, фев 0.85, апр 0.75, ноя 0.85 — просадки
    assert "янв" in block["troughs"]
    assert "апр" in block["troughs"]
