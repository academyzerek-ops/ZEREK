"""Gemini Flash RAG — AI-интерпретация отчётов Quick Check."""

import os
import json
import re

KNOWLEDGE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "knowledge", "niches"
)

# In-memory cache: niche_id → list[{title, body, protect}]
_RISK_CACHE: dict[str, list[dict]] = {}


def clean_markdown(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'#{1,6}\s*', '', text)
    text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ═══════════════════════════════════════════════
# Phase 3 — Niche risks parser
# ═══════════════════════════════════════════════

def _read_insight_file(niche_id: str) -> str:
    """Читает knowledge/niches/{NICHE}_insight.md. Возвращает '' если нет файла."""
    path = os.path.join(KNOWLEDGE_DIR, f"{niche_id}_insight.md")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""


def extract_niche_risks(niche_id: str, diag: dict = None) -> list[dict]:
    """
    Структурирует риски ниши из knowledge/niches/{NICHE}_insight.md в 7 карточек
    формата {title, body, protect} через Gemini 2.5 Flash с JSON-схемой.
    Кешируется в памяти процесса.
    Возвращает пустой список, если insight.md или GEMINI_API_KEY отсутствуют.
    Если передан dict `diag`, в него пишется стадия и причина пустого ответа.
    """
    if diag is not None:
        diag["knowledge_dir"] = KNOWLEDGE_DIR
    if niche_id in _RISK_CACHE:
        if diag is not None: diag["source"] = "cache"
        return _RISK_CACHE[niche_id]

    insight_text = _read_insight_file(niche_id)
    if not insight_text:
        if diag is not None:
            diag["reason"] = "insight_file_missing"
            diag["expected_path"] = os.path.join(KNOWLEDGE_DIR, f"{niche_id}_insight.md")
            diag["dir_exists"] = os.path.isdir(KNOWLEDGE_DIR)
            try:
                diag["dir_listing"] = os.listdir(KNOWLEDGE_DIR)[:10] if diag["dir_exists"] else []
            except Exception as e:
                diag["dir_listing_error"] = str(e)
        return []

    if diag is not None:
        diag["insight_len"] = len(insight_text)

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        if diag is not None: diag["reason"] = "no_gemini_api_key"
        return []

    import httpx

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.5-flash:generateContent?key=" + api_key
    )

    prompt = f"""Ты — отраслевой консультант ZEREK. На вход — анализ ниши из практики.

Твоя задача: выделить 7 самых важных РИСКОВ для предпринимателя, открывающего бизнес в этой нише.

Для каждого риска верни ровно:
- title: короткий заголовок-вывод 4-8 слов (не вопрос, а утверждение). Примеры: «Списание цветов 15-25%», «Сезонность: 50% года в пиках», «Зависимость от одного поставщика»
- body: 2-3 предложения, что это за риск и чем он опасен. Конкретные цифры если есть в исходнике.
- protect: 1-2 предложения практического действия, как защититься. Начинай с глагола.

Требования:
- Простой русский язык для самозанятых без финобразования.
- Никаких терминов EBITDA, CAPEX, OPEX, LTV, CAC — только человеческие слова.
- Отбирай самые денежно-критичные риски (то что убивает бизнес), не косметические.
- Не дублируй смысл между карточками.
- Только 7 карточек, ни больше ни меньше.

Исходник:
---
{insight_text}
---"""

    schema = {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "title":   {"type": "string"},
                "body":    {"type": "string"},
                "protect": {"type": "string"},
            },
            "required": ["title", "body", "protect"],
        },
    }

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 2048,
            "response_mime_type": "application/json",
            "response_schema": schema,
        },
    }

    try:
        resp = httpx.post(url, json=payload, timeout=45.0)
        data = resp.json()
        if diag is not None: diag["http_status"] = resp.status_code
        if "candidates" not in data or not data["candidates"]:
            if diag is not None:
                diag["reason"] = "no_candidates"
                diag["api_response"] = str(data)[:500]
            return []
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            if diag is not None: diag["reason"] = "not_a_list"
            return []
        risks = []
        for item in parsed[:7]:
            if not isinstance(item, dict):
                continue
            t = (item.get("title") or "").strip()
            b = (item.get("body") or "").strip()
            p = (item.get("protect") or "").strip()
            if t and b:
                risks.append({"title": t, "body": b, "protect": p})
        if risks:
            _RISK_CACHE[niche_id] = risks
        elif diag is not None:
            diag["reason"] = "parsed_empty"
            diag["parsed_items"] = len(parsed)
        return risks
    except Exception as e:
        if diag is not None:
            diag["reason"] = "exception"
            diag["error"] = str(e)[:300]
        return []


def clear_risk_cache(niche_id: str = None) -> None:
    """Очистить кеш. Без аргумента — весь; с niche_id — только конкретную нишу."""
    if niche_id is None:
        _RISK_CACHE.clear()
    elif niche_id in _RISK_CACHE:
        del _RISK_CACHE[niche_id]


def get_ai_interpretation(report_data: dict, knowledge_context: str = "") -> str:
    """Генерирует AI-интерпретацию отчёта Quick Check на простом русском языке."""
    import httpx

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return "AI-интерпретация временно недоступна."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    prompt = f"""Ты — финансовый консультант ZEREK. Проанализируй результаты Quick Check и дай интерпретацию на простом русском языке.

Тон: заботливый но честный. Предупреждай о рисках. Не мотиватор — практичный советник.
Формат: 3-5 абзацев, только абзацы с обычным текстом.
Отвечай чистым текстом без Markdown-разметки. Не используй звёздочки, решётки, списки с дефисами.

Данные отчёта:
{json.dumps(report_data, ensure_ascii=False, default=str)}

{f"Контекст по нише: {knowledge_context}" if knowledge_context else ""}

Дай оценку: стоит ли входить в этот бизнес с такими параметрами? Главные риски? На что обратить внимание?"""

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024, "topP": 0.9}
    }

    try:
        resp = httpx.post(url, json=payload, timeout=30.0)
        data = resp.json()
        if "candidates" in data and len(data["candidates"]) > 0:
            return clean_markdown(data["candidates"][0]["content"]["parts"][0]["text"])
        return "AI-интерпретация временно недоступна: " + json.dumps(data.get("error", {}), ensure_ascii=False)[:200]
    except Exception as e:
        return f"AI-интерпретация временно недоступна: {str(e)}"
