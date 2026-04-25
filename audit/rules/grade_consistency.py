"""Правила: согласованность income_grade с заголовком на стр. 3.

R9 K.2 ввёл 6-градационную шкалу. Если engine посчитал DECENT — заголовок
«Характер направления» должен быть «Достойный доход…», и наоборот: при
DECENT/HIGH в заголовке не должно быть «Невысокий» или «Низкий».
"""
from __future__ import annotations

from typing import Any, Dict, List

from audit.helpers import find_phrase_context, text_contains_phrase


# grade → ожидаемый префикс заголовка стр. 3 (из _direction_character)
EXPECTED_TITLE_PREFIX = {
    "LOW":       "Низкий доход",
    "MODEST":    "Невысокий доход",
    "MIDDLE":    "Средний доход",
    "DECENT":    "Достойный доход",
    "HIGH":      "Высокий доход",
    "VERY_HIGH": "Очень высокий доход",
}


def check_grade_title_match(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Заголовок «Характер направления» на стр. 3 должен начинаться
    с фразы соответствующей grade."""
    findings: List[Dict] = []
    grade = engine_result.get("income_grade") or "?"
    expected = EXPECTED_TITLE_PREFIX.get(grade)
    if not expected:
        return findings
    # Стр. 3 (индекс 2) — где «Итог»/«Характер направления». Если страниц
    # меньше 3 — значит PDF битый, отдельная критическая ошибка.
    if len(pdf_text) < 3:
        findings.append({
            "severity": "critical",
            "rule": "grade_pdf_too_short",
            "message": f"PDF содержит {len(pdf_text)} страниц (<3) — стр. 3 нет",
            "evidence": f"pages={len(pdf_text)}",
        })
        return findings
    page3 = pdf_text[2]
    if not text_contains_phrase(page3, expected):
        findings.append({
            "severity": "critical",
            "rule": "grade_title_mismatch",
            "message": f"Grade={grade}, на стр. 3 нет «{expected}»",
            "evidence": page3[:300],
        })
    return findings


# Несовместимые пары: высокая градация с фразой про низкий доход и наоборот.
HIGH_GRADES = ("DECENT", "HIGH", "VERY_HIGH")
LOW_GRADES = ("LOW", "MODEST")


def check_grade_no_contradiction(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """На стр. 3 не должно одновременно быть «Достойный доход» и
    «Невысокий доход» / «Низкий доход».
    """
    findings: List[Dict] = []
    grade = engine_result.get("income_grade") or "?"
    if len(pdf_text) < 3:
        return findings
    page3 = pdf_text[2]
    if grade in HIGH_GRADES:
        for bad in ("Невысокий доход", "Низкий доход для соло-формата"):
            if text_contains_phrase(page3, bad):
                findings.append({
                    "severity": "critical",
                    "rule": "grade_high_with_low_text",
                    "message": f"Grade={grade}, но на стр. 3 фраза «{bad}»",
                    "evidence": find_phrase_context(page3, bad),
                })
    if grade in LOW_GRADES:
        for bad in ("Достойный доход", "Высокий доход — выше"):
            if text_contains_phrase(page3, bad):
                findings.append({
                    "severity": "critical",
                    "rule": "grade_low_with_high_text",
                    "message": f"Grade={grade}, но на стр. 3 фраза «{bad}»",
                    "evidence": find_phrase_context(page3, bad),
                })
    return findings


def check_grade_ratio_consistent(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """`income_ratio_pct` должен соответствовать grade по таблице
    R9 K.2:
      <45 LOW · 45-65 MODEST · 65-85 MIDDLE · 85-105 DECENT
      105-130 HIGH · ≥130 VERY_HIGH

    Если engine выдал grade=DECENT при ratio=48% — серьёзный
    рассинхрон в самом движке.
    """
    findings: List[Dict] = []
    grade = engine_result.get("income_grade") or "?"
    pct = engine_result.get("income_ratio_pct") or 0
    EXPECTED = (
        ("LOW",       0,   45),
        ("MODEST",    45,  65),
        ("MIDDLE",    65,  85),
        ("DECENT",    85,  105),
        ("HIGH",      105, 130),
        ("VERY_HIGH", 130, 1_000),
    )
    bucket = next((g for g, lo, hi in EXPECTED if lo <= pct < hi), None)
    if bucket and grade != bucket and grade not in ("?", "BAD"):
        findings.append({
            "severity": "critical",
            "rule": "grade_ratio_mismatch",
            "message": f"ratio={pct}% попадает в {bucket}, но engine выдал {grade}",
            "evidence": f"pct={pct} grade={grade}",
        })
    return findings
