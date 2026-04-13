"""Gemini Flash RAG — AI-интерпретация отчётов Quick Check."""

import os
import json


def get_ai_interpretation(report_data: dict, knowledge_context: str = "") -> str:
    """Генерирует AI-интерпретацию отчёта Quick Check на простом русском языке."""
    import httpx

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return "AI-интерпретация временно недоступна."

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"

    prompt = f"""Ты — финансовый консультант ZEREK. Проанализируй результаты Quick Check и дай интерпретацию на простом русском языке.

Тон: заботливый но честный. Предупреждай о рисках. Не мотиватор — практичный советник.
Формат: 3-5 абзацев, без списков, простым языком для человека без финансового образования.

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
            return data["candidates"][0]["content"]["parts"][0]["text"]
        return "AI-интерпретация временно недоступна: " + json.dumps(data.get("error", {}), ensure_ascii=False)[:200]
    except Exception as e:
        return f"AI-интерпретация временно недоступна: {str(e)}"
