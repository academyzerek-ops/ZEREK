"""Правила: числовая согласованность между страницами PDF.

R9 L.1 закрыл рассинхрон 323 vs 324K между стр. 3 и 9. Здесь правило
ловит **новые** появления похожих рассинхронов: если рядом с «На мощности»
на любой странице оказалось число которое отличается от engine.mature_profit
больше чем на 1K — finding.

Также правило `check_no_orphan_numbers` ищет крупные числа в PDF без пары
в engine_result — это потенциальные «забытые» хардкоды или ошибки рендера.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from audit.helpers import collect_all_engine_numbers, extract_numbers_after, parse_number


# Константы которые могут встречаться в PDF без пары в engine — пропускаем.
# Расширены под фактический контент R10/R11 (соцплатежи округлённо, фазы
# маркетинга, типичные диапазоны цен в RAG-блоках, население городов).
KNOWN_CONSTANTS = {
    # Налоги/соцплатежи 2026
    4_325, 85_000, 21_500, 21_675, 260_100,
    # Цены продуктов ZEREK
    5_000, 9_000, 15_000,
    # Маркетинговые фазы и типичные RAG-числа
    10_000, 16_000, 20_000, 30_000, 40_000, 50_000,
    52_000, 54_000, 60_000, 80_000, 100_000, 130_000,
    150_000, 152_000, 160_000, 175_000, 715_000,
    # Население городов (тыс) — в RAG могут упоминаться
    1_640, 2_350,
    # Прочие round-числа и пороги
    25_000, 35_000, 45_000, 65_000, 75_000, 90_000, 200_000, 250_000, 300_000,
    500_000, 1_000_000,
    # Год
    2_026, 2_025,
}


def check_mature_profit_consistent(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """На каждой странице, где встречается «На мощности», числа ПОСЛЕ
    фразы должны быть равны engine.mature_profit (±1K — допуск round).

    Используем extract_numbers_after (не near) чтобы не ловить ЗП слева
    от фразы — она может быть рядом в строке «Прогнозная прибыль на
    мощности: 281 000 ₸ — около 87% от ЗП [где ЗП впереди в той же
    строке]».
    """
    findings: List[Dict] = []
    expected = int(engine_result.get("mature_profit") or 0)
    if expected <= 0:
        return findings
    for idx, page in enumerate(pdf_text):
        if not page:
            continue
        nums = extract_numbers_after(page, "На мощности", window=80)
        # Отфильтруем мелочь — нас интересуют только числа в порядке прибыли.
        nums = [n for n in nums if 50_000 < n < 5_000_000]
        for n in nums:
            if abs(n - expected) <= 1000:
                continue  # совпало в пределах округления
            if abs(n - expected) < 50_000:
                findings.append({
                    "severity": "medium",
                    "rule": "mature_profit_inconsistent",
                    "message": (
                        f"Стр. {idx+1}: после «На мощности» число {n}, "
                        f"engine.mature_profit={expected}, разница {abs(n - expected)}"
                    ),
                    "evidence": f"page={idx+1} found={n} expected={expected}",
                })
    return findings


def check_avg_y1_within_range(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Около фразы «В среднем за месяц» число должно отличаться от
    engine.avg_y1 не более чем на 5%. Если хотя бы одно близкое — ок,
    иначе high finding."""
    findings: List[Dict] = []
    expected = int(engine_result.get("avg_y1") or 0)
    if expected <= 0:
        return findings
    full = "\n".join(pdf_text)
    nums = extract_numbers_after(full, "В среднем за месяц", window=150)
    nums = [n for n in nums if 50_000 < n < 5_000_000]
    if not nums:
        return findings  # нет упоминания фразы — не проблема правила
    for n in nums:
        if expected * 0.95 <= n <= expected * 1.05:
            return findings  # хотя бы одно совпало — ок
    findings.append({
        "severity": "high",
        "rule": "avg_y1_mismatch",
        "message": (
            f"После «В среднем за месяц» в PDF: {nums}, "
            f"engine.avg_y1={expected} (отклонение >5%)"
        ),
        "evidence": f"found={nums} expected={expected}",
    })
    return findings


_BIG_NUM_PAT = re.compile(r"\b\d{1,3}(?:[ \xa0 ]\d{3})+\b")


def check_no_orphan_numbers(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Все большие числа (>10K) в PDF должны быть в engine_result или в
    KNOWN_CONSTANTS (с допуском ±2%). Иначе — `low` finding (потенциально
    «откуда взялась цифра»).

    Допуск 2% покрывает округление money_round (max шаг 10K на >1M).
    Не считаем `low` критичным — это just diagnostic.
    """
    findings: List[Dict] = []
    full = "\n".join(pdf_text)
    pdf_numbers = set()
    for m in _BIG_NUM_PAT.finditer(full):
        v = parse_number(m.group())
        if v >= 10_000:
            pdf_numbers.add(v)

    eng_numbers = [v for v in collect_all_engine_numbers(engine_result) if v >= 10_000]

    def has_match(pdf_num: int) -> bool:
        if pdf_num in KNOWN_CONSTANTS:
            return True
        for en in eng_numbers:
            if en > 0 and abs(pdf_num - en) / en <= 0.02:
                return True
        return False

    orphans = sorted(p for p in pdf_numbers if not has_match(p))
    if orphans:
        findings.append({
            "severity": "low",
            "rule": "orphan_numbers",
            "message": f"PDF содержит {len(orphans)} крупных чисел без пары в engine",
            "evidence": f"first_5={orphans[:5]}",
        })
    return findings
