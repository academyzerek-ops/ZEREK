"""Правила: качество RAG-блоков (Gemini-генерация).

R10 не покрывает RAG потому что результат недетерминирован (T=0.3).
Здесь проверяем структурные свойства которые должны быть инвариантны:
длина блока, отсутствие fallback-маркеров, отсутствие конкретных
валютных цифр (RAG должен говорить про принципы, не про числа).

Точные заголовки на стр. PDF:
  · «частые ошибки» — стр. ~14 (после блока риски)
  · «реальный опыт ниши» — удалён в R9 L.3 (его не должно быть)
  · «первый год на практике» — стр. ~7 (опционально, если first_year_reality)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from audit.helpers import extract_block, find_phrase_context, text_contains_phrase


def check_real_experience_removed(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """R9 L.3: блок «реальный опыт ниши» удалён. Если он снова появился
    в PDF — критический регресс."""
    findings: List[Dict] = []
    full = "\n".join(pdf_text)
    if text_contains_phrase(full, "реальный опыт ниши"):
        findings.append({
            "severity": "critical",
            "rule": "rag_real_experience_returned",
            "message": "Блок «реальный опыт ниши» удалён в R9 L.3, но снова в PDF",
            "evidence": find_phrase_context(full, "реальный опыт ниши", window=80),
        })
    return findings


def check_common_mistakes_present(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """RAG-блок «От консультанта · частые ошибки» должен быть в PDF.

    severity=medium (не high): RAG недетерминирован, иногда Gemini не
    отдаёт. Это диагностика «процент scenarios без блока», а не блокер
    рендера. Если RAG не отдал — отчёт всё равно валиден, просто без
    бонусного RAG-блока. Нужно мониторить долю.

    pdftotext рендерит uppercase-блок «О Т  К О Н С УЛ ЬТА Н ТА» с
    пробелами между букв из-за CSS letter-spacing — поэтому ищем
    более стабильный фрагмент в самом тексте RAG («ошибк»).
    """
    findings: List[Dict] = []
    full = "\n".join(pdf_text)
    # «частые ошибки» в заголовке uppercase + типичная фраза «ошибки»
    # в самом тексте RAG (Gemini обычно использует это слово).
    has_header = text_contains_phrase(full, "частые ошибки")
    has_text_marker = text_contains_phrase(full, "часто допускают")  # типичный фрагмент Gemini
    if not (has_header or has_text_marker):
        findings.append({
            "severity": "medium",
            "rule": "rag_common_mistakes_missing",
            "message": "В PDF нет блока «частые ошибки» (RAG не отдал — недетерминированно)",
            "evidence": "(не найдено ни в заголовке, ни в тексте)",
        })
    return findings


def check_rag_no_fallback_markers(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """В PDF не должно быть явных fallback/error-маркеров RAG-сервиса."""
    findings: List[Dict] = []
    full = "\n".join(pdf_text)
    fallback_markers = [
        "данные не найдены",
        "fallback",
        "RAG error",
        "Gemini error",
        "генерация недоступна",
    ]
    for marker in fallback_markers:
        if text_contains_phrase(full, marker):
            findings.append({
                "severity": "critical",
                "rule": "rag_fallback_leaked",
                "message": f"RAG-маркер «{marker}» утёк в PDF",
                "evidence": find_phrase_context(full, marker, window=80),
            })
    return findings


# Длина RAG-блока «частые ошибки» — 60-200 слов (валидатор pdf_rag_service).
def check_common_mistakes_length(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """Блок «частые ошибки» — 60-200 слов. Меньше — недозаполнен,
    больше — генератор сорвался в стенку текста."""
    findings: List[Dict] = []
    block_text = ""
    for page in pdf_text:
        b = extract_block(page, "частые ошибки", max_chars=2000)
        if b:
            block_text = b
            break
    if not block_text:
        return findings  # отсутствие блока ловит check_common_mistakes_present
    # Очищаем артефакты pdftotext: множественные пробелы → один.
    cleaned = re.sub(r"\s+", " ", block_text).strip()
    word_count = len(cleaned.split())
    if word_count < 40:
        findings.append({
            "severity": "medium",
            "rule": "rag_common_mistakes_too_short",
            "message": f"Блок «частые ошибки»: {word_count} слов (<40)",
            "evidence": cleaned[:200],
        })
    elif word_count > 280:
        findings.append({
            "severity": "low",
            "rule": "rag_common_mistakes_too_long",
            "message": f"Блок «частые ошибки»: {word_count} слов (>280)",
            "evidence": cleaned[:200],
        })
    return findings


_CURRENCY_NUM = re.compile(r"\b\d+\s*(?:₸|тенге|тыс)\b")


def check_rag_no_currency_in_common_mistakes(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """RAG «частые ошибки» не должен содержать конкретные валютные цифры
    (правило по словам Адиля: RAG говорит про принципы, не цифры)."""
    findings: List[Dict] = []
    block_text = ""
    for page in pdf_text:
        b = extract_block(page, "частые ошибки", max_chars=2000)
        if b:
            block_text = b
            break
    if not block_text:
        return findings
    cleaned = re.sub(r"\s+", " ", block_text)
    matches = _CURRENCY_NUM.findall(cleaned)
    if matches:
        findings.append({
            "severity": "medium",
            "rule": "rag_currency_leaked",
            "message": f"RAG «частые ошибки» содержит валютные числа: {matches[:3]}",
            "evidence": cleaned[:200],
        })
    return findings
