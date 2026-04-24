"""LLM-слоты «От консультанта» для PDF Quick Check.

4 слота, все одинакового формата (один абзац 80-120 слов, без цифр,
без брендов, без «гарантирую», без markdown). Контекст — insight.md
ниши. Модель gemini-2.5-flash-lite, T=0.3, max_tokens=800.

Slot types:
- common_mistakes    — «частые ошибки» (стр. «Главные риски»)
- first_year_reality — «как проходит первый год» (стр. «Достаточность капитала»)
- market_insight     — «особенности ниши» (стр. «Ключевые цифры»)
- real_experience    — «реальный опыт успешных» (стр. «Итоговая карточка»)

Fallback: None на любой сбой — template не рендерит блок, никаких
placeholder'ов в проде.
"""
from __future__ import annotations
import logging
import os
import re
from typing import Dict, Optional, Tuple

from gemini_rag import _read_insight_file  # reuse path constant + reader

_log = logging.getLogger("zerek.pdf_rag")


# ═══════════════════════════════════════════════════════════════════════
# Промпты по slot-типам
# ═══════════════════════════════════════════════════════════════════════


_PROMPTS = {
    "common_mistakes": (
        "Ты — отраслевой консультант ZEREK. На вход — анализ ниши из практики.\n\n"
        "Расскажи короткой прозой (80-120 слов, один абзац), какие 3-4 самые "
        "частые ошибки совершают новички в этой нише на первом году работы. "
        "Тон — заботливый, но честный: ты уже видел эти ошибки десятки раз у "
        "реальных предпринимателей и просто рассказываешь, к чему они приводят."
    ),
    "first_year_reality": (
        "Ты — отраслевой консультант ZEREK. На вход — анализ ниши из практики.\n\n"
        "Расскажи короткой прозой (80-120 слов, один абзац), как на самом деле "
        "проходит первый год работы в этой нише. Что происходит в разгоне, где "
        "типовые ямы кассы, когда возвращаются клиенты, когда становится "
        "стабильно. Тон — без драмы, практичный, как будто делишься наблюдением "
        "с партнёром, который собирается открыться."
    ),
    "market_insight": (
        "Ты — отраслевой консультант ZEREK. На вход — анализ ниши из практики.\n\n"
        "Расскажи короткой прозой (80-120 слов, один абзац), что важно понимать "
        "про эту нишу на рынке Казахстана прежде чем открыться: чем она "
        "отличается от соседних, на чём реально зарабатывают, где главный риск "
        "со стороны спроса/конкуренции/поставщиков. Без цифр, только качественно. "
        "Тон — аналитический, как короткая заметка старшего консультанта."
    ),
    "real_experience": (
        "Ты — отраслевой консультант ZEREK. На вход — анализ ниши из практики.\n\n"
        "Расскажи короткой прозой (80-120 слов, один абзац), как выглядит "
        "реальный опыт тех, кто в этой нише уже живёт несколько лет. Что они "
        "делают по-другому, какие привычки отличают устойчивых от ушедших, "
        "чему они учатся к третьему году. Тон — уважительный, без "
        "нравоучений; не даёшь советы, а показываешь картинку."
    ),
}

_GUARDRAIL_RULES = (
    "\n\nСтрогие правила (обязательные, нарушение = ответ будет отклонён):\n"
    "- Объём 80-120 слов. Не меньше, не больше.\n"
    "- Один сплошной абзац. Никаких буллетов, списков, заголовков, звёздочек или решёток.\n"
    "- Не упоминай цифры, проценты, суммы в тенге, сроки в месяцах — только качественные характеристики.\n"
    "- Не называй бренды или конкретные сервисы (Instagram, TikTok, Kaspi, 2GIS, WhatsApp, Google, Яндекс, Telegram и т.п.).\n"
    "- Не используй слова «гарантирую», «точно», «100%», «обязательно», «стопроцентно».\n"
    "- Простой русский язык, без терминов EBITDA, CAPEX, OPEX, LTV, CAC.\n\n"
    "Исходник:\n---\n{insight}\n---"
)


# ═══════════════════════════════════════════════════════════════════════
# Валидатор — общий для всех слотов
# ═══════════════════════════════════════════════════════════════════════


def _validate(text: str, format_id: str, diag: dict) -> Tuple[bool, str]:
    """Round-5 C.1: валидатор учитывает формат — для HOME/SOLO
    отклоняет упоминания найма, помещения, витрины и т.п.
    """
    from services.rag_filters import banned_words_for, find_banned
    t = (text or "").strip()
    if not t:
        return False, "empty"
    words = re.findall(r"\b[\w-]+\b", t, flags=re.UNICODE)
    wc = len(words)
    diag["word_count"] = wc
    if wc < 60 or wc > 160:
        return False, f"word_count_out_of_range:{wc}"
    if re.search(r"\d", t):
        return False, "contains_digits"
    banned = banned_words_for(format_id)
    hits = find_banned(t, banned)
    if hits:
        return False, f"banned:{hits[0]}"
    if "**" in t or "##" in t or re.search(r"^\s*[-•*]", t, re.M):
        return False, "markdown_artifacts"
    return True, "ok"


# ═══════════════════════════════════════════════════════════════════════
# Общий генератор для всех слотов
# ═══════════════════════════════════════════════════════════════════════


def _gemini_call(prompt: str, diag: dict) -> Optional[str]:
    """Один HTTP-вызов Gemini. Возвращает raw text или None."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        diag["reason"] = "no_gemini_api_key"
        return None
    import httpx
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash-lite:generateContent?key=" + api_key)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 800,
            "topP": 0.9,
        },
    }
    try:
        resp = httpx.post(url, json=payload, timeout=20.0)
        diag["http_status"] = resp.status_code
        data = resp.json()
        if "candidates" not in data or not data["candidates"]:
            diag["reason"] = "no_candidates"
            diag["api_response_preview"] = str(data)[:300]
            return None
        cand = data["candidates"][0]
        diag["finish_reason"] = cand.get("finishReason")
        diag["usage"] = data.get("usageMetadata") or {}
        text = cand["content"]["parts"][0]["text"]
        diag["raw_text"] = text
        diag["raw_len"] = len(text)
        return text
    except Exception as e:
        diag["reason"] = "exception"
        diag["error"] = str(e)[:200]
        return None


def generate_slot(
    slot_type: str,
    niche_id: str,
    diag: Optional[dict] = None,
    format_id: str = "",
    max_retries: int = 3,
) -> Optional[str]:
    """Возвращает текст 80-120 слов или None.

    Round-5 C.1: добавили format_id — попадает в system-prompt как
    «КРИТИЧЕСКИ ВАЖНО О ФОРМАТЕ» секция, а валидатор отклоняет тексты
    с найм/помещение/бренды для HOME/SOLO. До max_retries попыток
    с разными температурами.
    """
    diag = diag if diag is not None else {}
    niche_id = (niche_id or "").upper()
    diag["niche_id"] = niche_id
    diag["slot_type"] = slot_type
    diag["format_id"] = format_id
    diag["attempts"] = []

    if slot_type not in _PROMPTS:
        diag["reason"] = f"unknown_slot:{slot_type}"
        return None

    insight = _read_insight_file(niche_id)
    if not insight:
        diag["reason"] = "insight_missing"
        return None
    diag["insight_len"] = len(insight)

    from services.rag_filters import get_format_context
    fmt_ctx = get_format_context(format_id)
    fmt_block = ""
    if fmt_ctx:
        fmt_block = (
            "\n\nФОРМАТ: " + (format_id or "") +
            "\nКРИТИЧЕСКИ ВАЖНО О ФОРМАТЕ:\n" + fmt_ctx
        )

    base_prompt = _PROMPTS[slot_type] + fmt_block + _GUARDRAIL_RULES.format(insight=insight)
    diag["prompt_len"] = len(base_prompt)

    accepted_text: Optional[str] = None
    for attempt in range(max_retries):
        attempt_diag: Dict[str, object] = {"attempt": attempt + 1}
        text = _gemini_call(base_prompt, attempt_diag)
        if text:
            ok, reason = _validate(text, format_id, attempt_diag)
            attempt_diag["validator"] = reason
            if ok:
                accepted_text = text.strip()
                diag["attempts"].append(attempt_diag)
                diag["validator"] = reason
                break
        diag["attempts"].append(attempt_diag)

    final_ok = accepted_text is not None
    _log.info(
        "pdf-rag slot=%s niche=%s fmt=%s ok=%s attempts=%s",
        slot_type, niche_id, format_id, final_ok, len(diag["attempts"]),
    )
    if not final_ok:
        diag["reason"] = "all_attempts_failed"
        return None
    return accepted_text


# ═══════════════════════════════════════════════════════════════════════
# Обратная совместимость — старое имя (+ именованные обёртки)
# ═══════════════════════════════════════════════════════════════════════


def generate_common_mistakes(niche_id: str, diag: Optional[dict] = None, format_id: str = "") -> Optional[str]:
    return generate_slot("common_mistakes", niche_id, diag, format_id=format_id)


def generate_first_year_reality(niche_id: str, diag: Optional[dict] = None, format_id: str = "") -> Optional[str]:
    return generate_slot("first_year_reality", niche_id, diag, format_id=format_id)


def generate_market_insight(niche_id: str, diag: Optional[dict] = None, format_id: str = "") -> Optional[str]:
    return generate_slot("market_insight", niche_id, diag, format_id=format_id)


def generate_real_experience(niche_id: str, diag: Optional[dict] = None, format_id: str = "") -> Optional[str]:
    return generate_slot("real_experience", niche_id, diag, format_id=format_id)
