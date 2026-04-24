"""LLM-слот «От консультанта» для PDF Quick Check.

MVP: единственный консультантский абзац 80-120 слов на стр. «Главные
риски». Контекст берётся из knowledge/kz/niches/{NICHE}_insight.md,
генерирует Gemini 2.5 Flash с T=0.3, max_tokens=300.

Guardrails валидатора:
- 60-160 слов (мягкий диапазон, целевой 80-120).
- Без цифр / процентов / сумм / сроков в месяцах.
- Без брендов (Instagram, TikTok, Kaspi, 2GIS, Google, Яндекс...).
- Без слов «гарантирую», «точно», «100%», «обязательно», «стопроцентно».
- Без Markdown-артефактов (буллеты, звёздочки, решётки).

Fallback: None на любой сбой (no insight / no API key / HTTP fail /
validator reject). Шаблон {% if common_mistakes %} не рендерит блок.
Никаких заглушек «[placeholder]» в проде.
"""
from __future__ import annotations
import logging
import os
import re
from typing import Optional, Tuple

from gemini_rag import _read_insight_file  # reuse path constant + reader

_log = logging.getLogger("zerek.pdf_rag")


_PROMPT_TEMPLATE = """Ты — отраслевой консультант ZEREK. На вход — анализ ниши из практики.

Расскажи короткой прозой (80-120 слов, один абзац), какие 3-4 самые частые ошибки совершают новички в этой нише на первом году работы. Тон — заботливый, но честный: ты уже видел эти ошибки десятки раз у реальных предпринимателей и просто рассказываешь, к чему они приводят.

Строгие правила:
- Объём 80-120 слов. Не меньше, не больше.
- Один сплошной абзац. Никаких буллетов, списков, заголовков, звёздочек или решёток.
- Не упоминай цифры, проценты, суммы в тенге, сроки в месяцах — только качественные характеристики.
- Не называй бренды или конкретные сервисы (Instagram, TikTok, Kaspi, 2GIS, WhatsApp, Google, Яндекс, Telegram и т.п.).
- Не используй слова «гарантирую», «точно», «100%», «обязательно», «стопроцентно».
- Простой русский язык, без терминов EBITDA, CAPEX, OPEX, LTV, CAC.

Исходник:
---
{insight}
---"""


_BANNED_WORDS = (
    "гарантирую", "гарантия", "гарантирует",
    "стопроцентно", "100%",
    "обязательно получится", "точно получится",
)

_BANNED_BRANDS = (
    "instagram", "tiktok", "whatsapp",
    "яндекс", "google",
    "kaspi", "каспи",
    "2gis", "2гис",
    "telegram", "телеграм",
    "halyk", "халык",
)


def _validate(text: str, diag: dict) -> Tuple[bool, str]:
    """True/False + reason. Пишет word_count/banned hit в diag."""
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
    low = t.lower()
    for b in _BANNED_BRANDS:
        if b in low:
            return False, f"brand:{b}"
    for w in _BANNED_WORDS:
        if w in low:
            return False, f"banned_word:{w}"
    if "**" in t or "##" in t or re.search(r"^\s*[-•*]", t, re.M):
        return False, "markdown_artifacts"
    return True, "ok"


def generate_common_mistakes(niche_id: str, diag: Optional[dict] = None) -> Optional[str]:
    """Возвращает текст 80-120 слов или None на любой сбой.

    diag (если передан) заполняется ключами:
    - niche_id, insight_len, prompt_len, http_status, raw_text, raw_len,
      word_count, validator, reason/error.
    """
    diag = diag if diag is not None else {}
    niche_id = (niche_id or "").upper()
    diag["niche_id"] = niche_id

    insight = _read_insight_file(niche_id)
    if not insight:
        diag["reason"] = "insight_missing"
        return None
    diag["insight_len"] = len(insight)

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        diag["reason"] = "no_gemini_api_key"
        return None

    import httpx

    prompt = _PROMPT_TEMPLATE.format(insight=insight)
    diag["prompt_len"] = len(prompt)

    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash:generateContent?key=" + api_key)
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.3,
            "maxOutputTokens": 300,
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
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        diag["raw_text"] = text
        diag["raw_len"] = len(text)
    except Exception as e:
        diag["reason"] = "exception"
        diag["error"] = str(e)[:200]
        return None

    ok, reason = _validate(text, diag)
    diag["validator"] = reason
    _log.info(
        "common_mistakes niche=%s ok=%s reason=%s wc=%s http=%s",
        niche_id, ok, reason, diag.get("word_count"), diag.get("http_status"),
    )
    if not ok:
        return None
    return text.strip()
