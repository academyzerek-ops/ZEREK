"""api/services/verdict_service.py — Block 1: светофор + 8 пунктов скоринга.

Согласно спеке (Часть 2.10, Шаг 10): 8 компонентов × 0-3 балла → суммарный
score → цвет (зелёный ≥17, жёлтый 12-16, красный <12, пороги в defaults.yaml).

8 компонентов скоринга:
1. Капитал vs CAPEX-ориентир
2. ROI годовой (для SOLO/HOME — не применим, 3/3)
3. Точка безубыточности (окупаемость)
4. Насыщенность рынка
5. Опыт предпринимателя
6. Маркетинг (express → 2/2 «оценивается в FinModel»)
7. Устойчивость к стрессу (drop pess)
8. Соответствие формата городу

Извлечено из engine.py в Этапе 3 рефакторинга.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    BENCHMARK_COMPETITOR_DENSITY_10K,
    BLOCK1_THRESHOLDS,
    SCORING_BREAKEVEN,
    SCORING_CAPITAL,
    SCORING_CITY_POP,
    SCORING_ROI,
    SCORING_SATURATION,
    SCORING_STRESS_DROP,
    _safe_float,
    _safe_int,
)
from renderers.quick_check_renderer import _fmt_kzt  # noqa: E402
from services.economics_service import compute_unified_payback_months  # noqa: E402

_log = logging.getLogger("zerek.verdict_service")


# ═══════════════════════════════════════════════════════════════════════
# 8 компонентов скоринга
# ═══════════════════════════════════════════════════════════════════════


def _score_capital(capital_own, capex_needed):
    """Баллы за капитал vs CAPEX-бенчмарк (0-3).

    R8 H.1: фразы синхронизированы с зонами capital_service:
      ratio < 0.9        → score 0  (RED)    «критически не хватает на запуск»
      0.9 ≤ ratio < 1.1  → score 1  (AMBER)  «хватает на запуск, на разгон — нет»
      1.1 ≤ ratio < 2.0  → score 2  (YELLOW) «на запуск и часть разгона хватает»
      ratio ≥ 2.0        → score 3  (GREEN+) «комфортный запас на разгон»

    «Капитал с запасом» вне зон GREEN/GREEN+ не возвращается — это давало
    противоречие с правым блоком стр. 8 при ratio≈1.2 (попадание в AMBER).
    Слово «дефицит» — только в RED.
    """
    if not capex_needed:
        return {"score": 1, "label": "Капитал vs ориентир",
                "note": "Нет данных по ориентиру стартовых вложений"}
    if capital_own is None or capital_own == 0:
        return {"score": 2, "label": "Капитал vs ориентир",
                "note": f"Ориентир стартовых вложений: {int(capex_needed):,} ₸".replace(",", " ")}
    ratio = capital_own / capex_needed
    if ratio < 0.9:
        return {"score": 0, "label": "Капитал vs ориентир",
                "note": "Критически не хватает на минимальный запуск",
                "ratio": ratio,
                "gap_kzt": int(capex_needed - capital_own),
                "zone": "RED"}
    if ratio < 1.1:
        return {"score": 1, "label": "Капитал vs ориентир",
                "note": "Хватает на запуск, на разгон — желательно добрать",
                "ratio": ratio,
                "zone": "AMBER"}
    if ratio < 2.0:
        return {"score": 2, "label": "Капитал vs ориентир",
                "note": "Хватает на запуск и часть разгона",
                "ratio": ratio,
                "zone": "YELLOW"}
    return {"score": 3, "label": "Капитал vs ориентир",
            "note": "Комфортный запас на разгон и сезонные просадки",
            "ratio": ratio,
            "zone": "GREEN"}


def _score_roi(profit_year, total_investment, is_solo=False):
    """ROI годовой (0-3). Для SOLO/HOME — 3/3 без расчёта."""
    if is_solo:
        return {"score": 3, "label": "ROI годовой",
                "note": "Вы работаете сами — нет расходов на зарплату сотрудников"}
    if not total_investment or total_investment < 500_000:
        return {"score": 1, "label": "ROI годовой",
                "note": "Недостаточно данных о капитале"}
    roi = (profit_year or 0) / total_investment
    if roi > 3.0:
        return {"score": 1, "label": "ROI годовой",
                "note": "ROI > 300% — проверьте указанный капитал",
                "roi": 3.0,
                "roi_raw": round(roi, 2)}
    pct = int(round(roi * 100))
    t_hi, t_mid, t_lo = SCORING_ROI
    if roi >= t_hi:
        return {"score": 3, "label": "ROI годовой",
                "note": f"ROI {pct}% — выше среднего для малого бизнеса",
                "roi": roi}
    if roi >= t_mid:
        return {"score": 2, "label": "ROI годовой",
                "note": f"ROI {pct}% — нормальный",
                "roi": roi}
    if roi >= t_lo:
        return {"score": 1, "label": "ROI годовой",
                "note": f"ROI {pct}% — ниже нормы, но положительный",
                "roi": roi}
    return {"score": 0, "label": "ROI годовой",
            "note": f"ROI {pct}% — не окупает капитал",
            "roi": roi}


def _score_breakeven(breakeven_months):
    """Окупаемость в месяцах (0-3)."""
    t_fast, t_mid, t_slow = SCORING_BREAKEVEN
    if breakeven_months is None:
        return {"score": 0, "label": "Точка безубыточности", "note": f"Бизнес не окупается за {t_slow} мес"}
    if breakeven_months <= t_fast:
        return {"score": 3, "label": "Точка безубыточности", "note": f"Окупаемость {breakeven_months} мес — быстрая", "months": breakeven_months}
    if breakeven_months <= t_mid:
        return {"score": 2, "label": "Точка безубыточности", "note": f"Окупаемость {breakeven_months} мес", "months": breakeven_months}
    if breakeven_months <= t_slow:
        return {"score": 1, "label": "Точка безубыточности", "note": f"Окупаемость {breakeven_months} мес — долго", "months": breakeven_months}
    return {"score": 0, "label": "Точка безубыточности", "note": f"Окупаемость {breakeven_months} мес — слишком долго", "months": breakeven_months}


def _score_saturation(competitors_count, city_population, niche_id, density_per_10k=None):
    """Насыщенность рынка через плотность (0-3)."""
    density = None
    try:
        if density_per_10k is not None and float(density_per_10k) > 0:
            density = float(density_per_10k)
    except Exception:
        density = None
    if density is None:
        if not competitors_count or not city_population:
            return {"score": 2, "label": "Насыщенность рынка", "note": "Нет данных о конкурентах"}
        density = competitors_count / (city_population / 10000)
    benchmark = BENCHMARK_COMPETITOR_DENSITY_10K
    ratio = density / benchmark if benchmark else 0
    t_low, t_mid, t_hi = SCORING_SATURATION
    if ratio <= t_low:
        return {"score": 3, "label": "Насыщенность рынка",
                "note": f"Рынок недонасыщен: {round(density,1)} конкурентов на 10K жителей",
                "density": density}
    if ratio <= t_mid:
        return {"score": 2, "label": "Насыщенность рынка",
                "note": f"Норма: {round(density,1)} конкурентов на 10K",
                "density": density}
    if ratio <= t_hi:
        return {"score": 1, "label": "Насыщенность рынка",
                "note": f"Высокая конкуренция: {round(density,1)} конкурентов на 10K",
                "density": density}
    return {"score": 0, "label": "Насыщенность рынка",
            "note": f"Рынок перенасыщен: {round(density,1)} на 10K",
            "density": density}


def _score_experience(exp):
    """Опыт предпринимателя (0-3)."""
    if exp == "experienced":
        return {"score": 3, "label": "Опыт предпринимателя", "note": "3+ лет опыта снижает риск первого года"}
    if exp == "some":
        return {"score": 2, "label": "Опыт предпринимателя", "note": "1-2 года опыта — стандартно"}
    if exp == "none":
        return {"score": 0, "label": "Опыт предпринимателя", "note": "Нет опыта — риск первого года до 45%"}
    return {"score": 1, "label": "Опыт предпринимателя", "note": "Опыт не указан"}


def _score_marketing(tier="express"):
    """В Quick Check этот параметр не опрашивается → полный балл 2/2."""
    return {"score": 2, "label": "Маркетинговый бюджет",
            "note": "Параметр оценивается в FinModel — в экспресс-оценке полный балл",
            "max": 2}


def _score_stress(profit_base, profit_pess):
    """Устойчивость к стрессу — падение прибыли в pess (0-3)."""
    if profit_base is None or profit_pess is None:
        return {"score": 1, "label": "Устойчивость к стрессу"}
    t_stable, t_moderate = SCORING_STRESS_DROP
    if profit_pess > 0:
        drop = (profit_base - profit_pess) / profit_base if profit_base else 0
        if drop < t_stable:
            return {"score": 3, "label": "Устойчивость к стрессу", "note": "Бизнес устойчив к падению ключевого параметра на 20%"}
        if drop < t_moderate:
            return {"score": 2, "label": "Устойчивость к стрессу", "note": "Умеренно устойчив — падение выручки терпимое"}
        return {"score": 1, "label": "Устойчивость к стрессу", "note": "Хрупкая модель — небольшое падение трафика больно бьёт"}
    return {"score": 0, "label": "Устойчивость к стрессу", "note": "При падении параметра на 20% — убыток"}


def _score_format_city(format_id, format_class, city_population):
    """Формат × размер города (премиум в малом → 0)."""
    t_small, t_mid = SCORING_CITY_POP
    small = (city_population or 0) < t_small
    mid = t_small <= (city_population or 0) < t_mid
    cls = (format_class or "").lower()
    if cls == "премиум" and small:
        return {"score": 0, "label": "Соответствие формата городу", "note": "Премиум-формат в малом городе — узкая ЦА"}
    if cls == "премиум" and mid:
        return {"score": 1, "label": "Соответствие формата городу", "note": "Премиум-формат в среднем городе — ограниченная ЦА"}
    return {"score": 3, "label": "Соответствие формата городу", "note": "Формат подходит для города"}


# ═══════════════════════════════════════════════════════════════════════
# Текстовые шаблоны (вердикт, плюсы, риски)
# ═══════════════════════════════════════════════════════════════════════


def _verdict_statement_template(color, top_weak, top_strong, roi_pct, breakeven_months):
    """Шаблонный вердикт (fallback когда Gemini не подключён)."""
    strong_name = (top_strong or {}).get("label", "")
    weak_name = (top_weak or {}).get("label", "")
    weak_note = (top_weak or {}).get("note", "")

    if color == "green":
        if top_weak and top_weak.get("score", 0) <= 1:
            bm = f" Окупаемость {breakeven_months} мес — держите запас кассы." if breakeven_months else ""
            return f"Бизнес реалистичен и окупается.{bm}"
        return f"Бизнес реалистичен и окупается. Главное преимущество — {strong_name.lower()}."

    if color == "yellow":
        return f"Бизнес возможен, но требует внимания. Главный риск — {weak_name.lower()}: {weak_note.lower()}."

    return f"В текущей конфигурации бизнес не окупается в разумные сроки. Требуется пересмотр — главный слабый пункт: {weak_name.lower()}."


def _strength_text(p):
    """Тезис для плюса."""
    n = p.get("note") or ""
    return n if n else p.get("label", "")


def _risk_text(p, context):
    """Тезис для риска — с конкретной рекомендацией."""
    # R7 G.3 + R8 H.1: тон «факт + риск», без диктата и без «дефицит» вне RED.
    # Для капитала возвращаем согласованный с зоной note (см. _score_capital).
    label = p.get("label", "")
    if label == "Капитал vs ориентир":
        zone = p.get("zone")
        if zone == "RED":
            gap = p.get("gap_kzt") or 0
            return (
                f"Не хватает {_fmt_kzt(gap)} даже на минимальный "
                "запуск — без этой суммы открыться физически невозможно."
            )
        if zone == "AMBER":
            return (
                "Хватает на запуск, на разгон М1-М3 желательно добрать — "
                "иначе высокий риск кассового разрыва на 2-3 месяце."
            )
        return p.get("note") or "Бюджет не соответствует формату."
    if label == "Точка безубыточности":
        months = p.get("months")
        if months and months >= 12:
            return (
                f"Окупаемость {months} мес — это длинный горизонт "
                "ожидания возврата капитала. В первые 6-12 мес "
                "кассовый поток плотный, шаг вправо-влево чувствителен."
            )
        return p.get("note") or "Окупаемость долгая — нужен запас."
    if label == "Насыщенность рынка":
        return (p.get("note") or "") + " — без сильного УТП сложно взять долю."
    if label == "Опыт предпринимателя":
        return (
            "Отсутствие опыта в нише повышает риск первого года: "
            "типичные ошибки новичка вы будете встречать впервые "
            "и решать в реальном времени, что замедляет разгон."
        )
    if label == "Устойчивость к стрессу":
        return "Бизнес чувствителен к падению ключевого параметра. Маркетинг и удержание клиентов в первые 6 мес — приоритет."
    if label == "Соответствие формата городу":
        return "Премиум-формат в выбранном городе — узкая платёжеспособная ЦА. Рассмотрите стандартный класс."
    if label == "ROI годовой":
        return "ROI ниже среднего. Пересмотрите стартовые вложения или ожидаемую выручку."
    if label == "Маркетинговый бюджет":
        return "Маркетинг будет ключевым — не экономьте на первом старте."
    return p.get("note") or label


# ═══════════════════════════════════════════════════════════════════════
# Block 1 — оркестратор
# ═══════════════════════════════════════════════════════════════════════


def compute_block1_verdict(result, adaptive):
    """Block 1 — вердикт (светофор + 8 пунктов + плюсы/риски).

    Принимает результат run_quick_check_v3 + adaptive (specific_answers v1.0
    спеки: experience, entrepreneur_role, capital_own).
    """
    adaptive = adaptive or {}
    inp = result.get("input", {}) or {}
    fin = result.get("financials", {}) or {}
    capex_block = result.get("capex", {}) or {}
    scenarios = result.get("scenarios", {}) or {}
    payback = result.get("payback", {}) or {}
    risks_block = result.get("risks", {}) or {}

    capex_standard_08 = _safe_int(inp.get("capex_standard"), 0)
    capex_med_perniche = _safe_int(capex_block.get("capex_med")) or _safe_int(capex_block.get("capex_total"))
    capex_needed = capex_standard_08 if capex_standard_08 > 0 else capex_med_perniche
    # Добавляем обучение для новичков (training_required + experience=none/some).
    try:
        from engine import TRAINING_COSTS_BY_EXPERIENCE
        if bool(inp.get("training_required")):
            _exp = (adaptive.get("experience") or "").lower()
            _tr = TRAINING_COSTS_BY_EXPERIENCE.get(_exp, 0)
            if _tr > 0:
                capex_needed += _tr
    except Exception:
        pass
    capital_own_raw = adaptive.get("capital_own")
    if capital_own_raw is None or capital_own_raw == "":
        capital_own = None
    else:
        try:
            capital_own = int(capital_own_raw) or None
        except (TypeError, ValueError):
            capital_own = None

    total_investment = (capital_own or 0) or capex_standard_08 or _safe_int(capex_block.get("capex_total"), 0)
    if total_investment < 500_000:
        for k in ("capex_med", "capex", "total_investment", "capex_high"):
            v = _safe_int(capex_block.get(k), 0)
            if v >= 500_000:
                total_investment = v
                break
    profit_year = _safe_int(fin.get("profit_year1"), 0)
    breakeven_months = compute_unified_payback_months(result, adaptive)
    city_pop = _safe_int(inp.get("city_population"), 0)
    if not city_pop:
        city_pop = _safe_int((result.get("market", {}) or {}).get("population"), 0)
    competitors_count = 0
    density_per_10k = 0.0
    comp_block = risks_block.get("competitors") or {}
    if isinstance(comp_block, dict):
        competitors_count = _safe_int(comp_block.get("competitors_count")) or _safe_int(comp_block.get("n"))
        density_per_10k = _safe_float(comp_block.get("density_per_10k"), 0.0)
    if not density_per_10k:
        mkt_comp = (result.get("market", {}) or {}).get("competitors") or {}
        if isinstance(mkt_comp, dict):
            density_per_10k = _safe_float(mkt_comp.get("density_per_10k"), 0.0)
            if not competitors_count:
                competitors_count = _safe_int(mkt_comp.get("competitors_count"))
    exp = adaptive.get("experience") or ""

    profit_base = _safe_int((scenarios.get("base") or {}).get("прибыль_среднемес"), 0)
    profit_pess = _safe_int((scenarios.get("pess") or {}).get("прибыль_среднемес"), 0)

    format_class = inp.get("class") or inp.get("cls") or ""
    format_id = inp.get("format_id", "")

    format_id_upper = (format_id or "").upper()
    is_solo_fmt_b1 = bool(inp.get("founder_works")) and (
        format_id_upper.endswith("_HOME") or format_id_upper.endswith("_SOLO")
    )
    scoring_items = [
        _score_capital(capital_own, capex_needed),
        _score_roi(profit_year, total_investment, is_solo=is_solo_fmt_b1),
        _score_breakeven(breakeven_months),
        _score_saturation(competitors_count, city_pop, inp.get("niche_id", ""),
                          density_per_10k=density_per_10k),
        _score_experience(exp),
        _score_marketing("express"),
        _score_stress(profit_base, profit_pess),
        _score_format_city(format_id, format_class, city_pop),
    ]
    total_score = sum(it.get("score", 0) for it in scoring_items)
    max_score = sum(it.get("max", 3) for it in scoring_items)

    _t_green, _t_yellow = BLOCK1_THRESHOLDS
    if total_score >= _t_green:
        color = "green"
    elif total_score >= _t_yellow:
        color = "yellow"
    else:
        color = "red"

    sorted_desc = sorted(scoring_items, key=lambda x: -x.get("score", 0))
    sorted_asc = sorted(scoring_items, key=lambda x: x.get("score", 0))
    strengths_items = sorted_desc[:3]
    risks_pool = sorted_asc
    if is_solo_fmt_b1 or format_id_upper.endswith("_HOME"):
        risks_pool = [it for it in risks_pool if it.get("label") != "Насыщенность рынка"]
    risks_items = risks_pool[:3]

    bk_base = _safe_int(breakeven_months) if breakeven_months is not None else _safe_int(payback.get("месяц"))

    statement = _verdict_statement_template(
        color,
        risks_items[0] if risks_items else None,
        strengths_items[0] if strengths_items else None,
        None, bk_base,
    )

    strengths_texts = [_strength_text(p) for p in strengths_items if p.get("score", 0) >= 2]
    while len(strengths_texts) < 3 and strengths_items:
        p = strengths_items[len(strengths_texts) % len(strengths_items)]
        t = _strength_text(p)
        if t not in strengths_texts:
            strengths_texts.append(t)
        else:
            break
    risks_texts = [_risk_text(p, {"city": inp.get("city_name", "")}) for p in risks_items]

    return {
        "color": color,
        "score": total_score,
        "max_score": max_score,
        "verdict_statement": statement,
        "strengths": strengths_texts[:3],
        "risks": risks_texts[:3],
        "scoring": {
            "items": scoring_items,
            "strongest": strengths_items[:3],
            "weakest": risks_items[:3],
        },
    }
