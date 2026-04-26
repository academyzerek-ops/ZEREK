"""api/services/seasonality_service.py — Ramp-up + сезонность + first-year chart.

Извлечено из engine.py в Этапе 3 рефакторинга.

Согласно спеке (п. 2.3, 2.4, Шаг 4):
- Ramp-up: линейная интерполяция от rampup_start_pct до 1.0 за rampup_months.
- Сезонность: s01..s12 из FINANCIALS или DEFAULT_SEASONALITY (из config).
- Применяется в первом году (месячные графики, средний P&L за год).
- НЕ применяется к зрелому режиму и стресс-тесту (там ramp=1, season=1).

Сервисы возвращают чистые числа/структуры — никакого UI-форматирования.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    DEFAULTS,
    DEFAULT_SEASONALITY,
    _safe_float,
    _safe_int,
)

_log = logging.getLogger("zerek.seasonality_service")


_MONTH_NAMES_RUS_FULL = ["Янв", "Фев", "Мар", "Апр", "Май", "Июн",
                          "Июл", "Авг", "Сен", "Окт", "Ноя", "Дек"]
_MONTH_NAMES_RUS_LONG = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
                          "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"]
_MONTH_NAMES_RUS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн",
                           "июл", "авг", "сен", "окт", "ноя", "дек"]


# R8 I.1: явный ramp curve для первых 3 месяцев соло-старта.
# Старая линейная интерполяция (start=0.50, 3 мес) давала 67/83/100% —
# это слишком оптимистично. Реальный соло-старт без раскрученного
# бренда: M1 = 40% (только реклама, нет ещё ни сарафана, ни возвратов),
# M2 = 65% (первые сарафанные клиенты), M3 = 85% (сарафан работает
# на 20-30% потока), M4+ = 100% (выход на мощность).
# Согласовано с моделью Адиля в R8 ТЗ. Применяется глобально через
# calc_revenue_monthly → calc_cashflow → pnl_base.прибыль_среднемес.
RAMP_CURVE_DEFAULT = [0.40, 0.65, 0.85]


def calc_revenue_monthly(fin, cal_month, razgon_month):
    """Выручка за 1 месяц (₸) с учётом сезонности и ramp-up.

    fin: dict с ключами check_med, traffic_med, s01..s12, rampup_months.
    cal_month: календарный месяц 1..12 (для сезонности).
    razgon_month: месяц с начала работы 1..N (для ramp-up).

    R8 I.1: ramp_coef берётся из явного RAMP_CURVE_DEFAULT (40/65/85),
    поле fin.rampup_start_pct больше не используется. Старая линейная
    модель оставляется как fallback для не-3-месячного rampup_months.
    """
    check = _safe_int(fin.get("check_med"), 1000)
    traffic = _safe_int(fin.get("traffic_med"), 50)
    # R12.5 Сессия 2: × working_days_per_month вместо хардкода × 30.
    # Если поле не задано (legacy ниши до R12.5) — fallback на 30 для
    # обратной совместимости. Маникюр R12.5: HOME=26, STUDIO=22,
    # SALON_RENT=24, MALL_SOLO=26 — приходит через _apply_r12_5_overrides.
    working_days = _safe_int(fin.get("working_days_per_month"), 30)
    base_rev = check * traffic * working_days

    s_key = f"s{cal_month:02d}"
    season_coef = _safe_float(fin.get(s_key), 1.0)

    rampup_months = _safe_int(fin.get("rampup_months"), DEFAULTS["rampup_months"])

    # R12.5 S2 хвост: ramp_curve по стратегии из A1 archetype, если
    # стратегия задана в fin. Conservative — медленная (выход на М11),
    # middle — стандарт (М4), aggressive — быстрая (М3).
    strategy = (fin.get("strategy") or "middle").lower()
    a1_ramp = None
    try:
        from loaders.niche_loader import load_archetype_yaml  # noqa: WPS433
        a1 = load_archetype_yaml('A1') or {}
        strats = a1.get('marketing_strategies') or {}
        strat_data = strats.get(strategy) or strats.get('middle') or {}
        rc = strat_data.get('ramp_curve')
        if rc and isinstance(rc, list) and len(rc) >= 12:
            a1_ramp = [float(v) for v in rc[:12]]
    except Exception:  # noqa: BLE001
        a1_ramp = None

    if a1_ramp and 1 <= razgon_month <= 12:
        razgon_coef = min(a1_ramp[razgon_month - 1], 1.0)
    elif rampup_months == 3 and razgon_month <= 3:
        razgon_coef = RAMP_CURVE_DEFAULT[razgon_month - 1]
    elif razgon_month <= rampup_months:
        # Fallback на линейную интерполяцию для нестандартных rampup_months.
        rampup_start = _safe_float(fin.get("rampup_start_pct"), DEFAULTS["rampup_start_pct"])
        progress = rampup_start + (1.0 - rampup_start) * (razgon_month / rampup_months)
        razgon_coef = min(progress, 1.0)
    else:
        razgon_coef = 1.0

    return int(base_rev * season_coef * razgon_coef)


def compute_first_year_chart(result):
    """Персонализированный прогноз первых 12 месяцев работы.

    Показывает помесячную выручку с учётом ramp-up + сезонности +
    календарной привязки (месяц 1 = start_month).

    Возвращает dict с полями start_month, start_month_label, months[12],
    narrative.

    Для каждого месяца: n (1..12), calendar_label (Янв-Дек), revenue,
    color ∈ {ramp, mature, mature_high, season_low}.
    """
    inp = result.get("input", {}) or {}
    fin = result.get("financials", {}) or {}
    mature = (result.get("pnl_aggregates") or {}).get("mature") or {}

    start_month = _safe_int(inp.get("start_month"), 4)
    rev_mature_m = _safe_int(mature.get("revenue_monthly"), 0)
    if rev_mature_m <= 0:
        # Фолбэк: revenue из финансов (если pnl_aggregates не собран).
        avg_check = _safe_int(fin.get("check_med"), 0) or 3000
        traffic = _safe_int(fin.get("traffic_med"), 0) or 30
        rev_mature_m = avg_check * traffic * 30

    rampup_months = _safe_int(fin.get("rampup_months"), 3) or 3
    rampup_start_pct = _safe_float(fin.get("rampup_start_pct"), 0.50) or 0.50

    # Сезонность: per-niche s01..s12 если заполнены, иначе DEFAULT_SEASONALITY.
    season = []
    for m in range(1, 13):
        v = _safe_float(fin.get(f"s{m:02d}"), 0.0)
        season.append(v if v > 0 else DEFAULT_SEASONALITY[m - 1])

    def ramp_coef(m):
        # R8 I.1: единая ramp curve с calc_revenue_monthly выше.
        if rampup_months == 3 and m <= 3:
            return RAMP_CURVE_DEFAULT[m - 1]
        if m <= rampup_months:
            return rampup_start_pct + (1.0 - rampup_start_pct) * m / rampup_months
        return 1.0

    def month_color(m, season_coef):
        if m <= rampup_months:
            return "ramp"
        if season_coef > 1.05:
            return "mature_high"
        if season_coef < 0.95:
            return "season_low"
        return "mature"

    months = []
    for m in range(1, 13):
        cal_m = ((start_month - 1 + m - 1) % 12) + 1
        s_coef = season[cal_m - 1]
        r_coef = ramp_coef(m)
        rev = int(rev_mature_m * r_coef * s_coef)
        months.append({
            "n": m,
            "calendar_label": _MONTH_NAMES_RUS_FULL[cal_m - 1],
            "revenue": rev,
            "color": month_color(m, s_coef),
        })

    # Narrative: разгон + «ваш старт попадает на…»
    parts = [f"Первые {rampup_months} месяца — разгон. С {rampup_months + 1}-го месяца — выход на полную мощность."]
    window_size = min(2, 12)
    start_window_cal = [((start_month - 1 + i) % 12) + 1 for i in range(window_size)]
    start_season_avg = sum(season[c - 1] for c in start_window_cal) / window_size
    if start_season_avg >= 1.05:
        parts.append("Ваш старт удачно попадает на сезонный пик — это ускорит выход на стабильный доход.")
    elif start_season_avg <= 0.90:
        parts.append("Ваш старт попадает на сезонную просадку — первые месяцы будут особенно тихими. Закладывайте подушку безопасности.")
    elif start_season_avg <= 0.95:
        parts.append("Ваш старт попадает на нейтральный/слабый сезон. Без дополнительных усилий по маркетингу разгон может затянуться.")
    else:
        parts.append("Ваш старт попадает на средний сезонный период — стандартный сценарий.")

    return {
        "start_month": start_month,
        "start_month_label": _MONTH_NAMES_RUS_LONG[start_month - 1],
        "months": months,
        "narrative": " ".join(parts),
    }


def compute_block_season(raw_fin):
    """12 коэффициентов сезонности + пики/просадки.

    raw_fin: полная строка FINANCIALS из xlsx (не отфильтрованная).
    Источник: s01..s12 (если любой > 0) или DEFAULT_SEASONALITY.
    """
    coefs = []
    for m in range(1, 13):
        v = _safe_float((raw_fin or {}).get(f"s{m:02d}"), 0.0)
        coefs.append(v)
    if not any(c > 0 for c in coefs):
        coefs = list(DEFAULT_SEASONALITY)
    peak_idx = [i for i, c in enumerate(coefs) if c > 1.05]
    trough_idx = [i for i, c in enumerate(coefs) if c < 0.95]
    peaks = [_MONTH_NAMES_RUS_SHORT[i] for i in peak_idx]
    troughs = [_MONTH_NAMES_RUS_SHORT[i] for i in trough_idx]
    return {
        "coefs":   [round(c, 2) for c in coefs],
        "months":  list(_MONTH_NAMES_RUS_SHORT),
        "peaks":   peaks,
        "troughs": troughs,
        "source":  "niche" if any((raw_fin or {}).get(f"s{m:02d}") for m in range(1, 13)) else "default",
    }
