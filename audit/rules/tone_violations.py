"""Правила: тон и запрещённые шаблонные формулировки.

Происхождение списка — R7 G.3 (audit «урежьте/найдите/откладывайте»)
и R8 G.2 («откладывайте деньги» для HOME). Любое появление этих фраз
в pdf — сигнал что мы вернулись к старому диктаторскому тону.

Дополнительно — формат-зависимые запреты: HOME-формат не должен
получать совет «наймите мастера» или «команду» (для дома это бессмыслица).
"""
from __future__ import annotations

from typing import Any, Dict, List

from audit.helpers import find_phrase_context, text_contains_phrase


# Запрещённые фразы — тон/диктат.
# Формат: (фраза, причина).
BLACKLIST_GENERIC = [
    ("урежьте формат до эконом",   "shaming/диктат, для HOME не работает"),
    ("урежьте до эконом-класса",   "та же ошибка"),
    ("урежьте формат",             "диктат"),
    ("пополните резерв",           "шейминг — если бы у клиента были, он бы положил"),
    ("откладывайте деньги",        "для соло-HOME нет фикс-расходов на откладывание"),
    ("найдите ментора",            "универсальный совет вне контекста"),
    ("найдите партнёра",           "вне контекста, не наше дело"),
    ("дефицит капитала",           "тон R7 G.3 — заменили на «желательно добрать»"),
    ("капитал на грани",           "тон R7 G.3"),
    ("отлично что умеете снимать", "допущение которое в анкете не задано (R8 I.4)"),
]


def check_no_blacklist_phrases(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Любая фраза из BLACKLIST_GENERIC в PDF — high finding."""
    findings: List[Dict] = []
    full = "\n".join(pdf_text)
    for phrase, reason in BLACKLIST_GENERIC:
        if text_contains_phrase(full, phrase):
            findings.append({
                "severity": "high",
                "rule": "tone_blacklist",
                "message": f"Запрещённая фраза «{phrase}» — {reason}",
                "evidence": find_phrase_context(full, phrase, window=80),
            })
    return findings


# Для HOME-формата запрещены советы про найм/команду/проходное место.
HOME_FORBIDDEN = [
    "наймите мастера",
    "команда мастеров",
    "команду мастеров",
    "нанимайте сотрудников",
    "проходное место",
]


def check_format_specific_violations(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """HOME-формат не должен получать советы про найм/проходное место."""
    findings: List[Dict] = []
    fmt = (engine_result.get("format") or "").upper()
    if not fmt.endswith("_HOME"):
        return findings
    full = "\n".join(pdf_text)
    for phrase in HOME_FORBIDDEN:
        if text_contains_phrase(full, phrase):
            findings.append({
                "severity": "critical",
                "rule": "tone_home_violation",
                "message": f"HOME-формат: фраза «{phrase}» неприменима",
                "evidence": find_phrase_context(full, phrase, window=80),
            })
    return findings
