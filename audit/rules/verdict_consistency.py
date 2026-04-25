"""Правила: согласованность вердикта по капиталу между страницами.

Проверки:
  · check_no_zone_contradiction — для зон AMBER/RED/YELLOW в PDF не должно
    быть «капитал с запасом» / «капитала достаточно» (это противоречие).
  · check_capital_label_present — заголовок-лейбл капитала должен звучать
    в PDF (мы уже проверяем согласованность стр. 3 ↔ 8 в R10 регрессии).

Намеренно не дублируем R10: там engine.capital_zone уже проверен. Здесь
ловим «текст соврал относительно зоны».
"""
from __future__ import annotations

from typing import Any, Dict, List

from audit.helpers import find_phrase_context, text_contains_phrase


# Лейблы для каждой зоны должны быть в PDF минимум 1 раз (на стр. 8 callout).
ZONE_LABEL = {
    "RED":        "Критически не хватает",
    "AMBER":      "На запуск, на разгон — нет",
    "YELLOW":     "На запуск и часть разгона хватает",
    "GREEN":      "Комфортный запас на разгон",
    "GREEN_PLUS": "Безопасный запас с подушкой",
}


def check_capital_label_present(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Лейбл зоны должен встречаться в PDF (стр. 8 callout).

    Ищем по частичному фрагменту лейбла а не целиком: callout-title
    может быть разорван layout-ом из-за переноса строки между
    «разгона» и «хватает». Берём первые 4 слова — это устойчивая
    часть, переносу не подвергается.
    """
    findings: List[Dict] = []
    zone = engine_result.get("capital_zone") or "UNKNOWN"
    if zone in ("UNKNOWN",):
        return findings
    label = ZONE_LABEL.get(zone)
    if not label:
        return findings
    # Берём первые 4 слова лейбла как устойчивый фрагмент.
    label_prefix = " ".join(label.split()[:4])
    full = "\n".join(pdf_text)
    if not text_contains_phrase(full, label_prefix):
        findings.append({
            "severity": "high",
            "rule": "verdict_capital_label_missing",
            "message": f"Зона={zone}, в PDF нет лейбла «{label_prefix}…»",
            "evidence": f"zone={zone} expected_prefix={label_prefix!r}",
        })
    return findings


# Запрещённые фразы для зон где капитал недостаточен.
NON_GREEN_FORBIDDEN = [
    "Капитал с запасом",
    "Капитала достаточно",
    "Капитал достаточен",
    "Безопасный запас с подушкой",  # не должно быть на AMBER/RED/YELLOW
]


def check_no_zone_contradiction(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Если зона AMBER/RED/YELLOW — нигде не должно быть «капитал с запасом»."""
    findings: List[Dict] = []
    zone = engine_result.get("capital_zone") or "UNKNOWN"
    if zone not in ("RED", "AMBER", "YELLOW"):
        return findings
    full = "\n".join(pdf_text)
    for phrase in NON_GREEN_FORBIDDEN:
        if text_contains_phrase(full, phrase):
            findings.append({
                "severity": "critical",
                "rule": "verdict_zone_contradiction",
                "message": f"Зона={zone}, в PDF фраза «{phrase}» (противоречие)",
                "evidence": find_phrase_context(full, phrase, window=80),
            })
    return findings


# Для GREEN/GREEN_PLUS не должно быть «критически» / «дефицит».
GREEN_FORBIDDEN = [
    "Критически не хватает",
    "критически мало",
    "Дефицит капитала",
]


def check_no_green_contradiction(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Если зона GREEN/GREEN_PLUS — никаких «критически»/«дефицит» в PDF."""
    findings: List[Dict] = []
    zone = engine_result.get("capital_zone") or "UNKNOWN"
    if zone not in ("GREEN", "GREEN_PLUS"):
        return findings
    full = "\n".join(pdf_text)
    for phrase in GREEN_FORBIDDEN:
        if text_contains_phrase(full, phrase):
            findings.append({
                "severity": "critical",
                "rule": "verdict_green_contradiction",
                "message": f"Зона={zone}, в PDF фраза «{phrase}»",
                "evidence": find_phrase_context(full, phrase, window=80),
            })
    return findings
