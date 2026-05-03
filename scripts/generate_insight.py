"""
generate_insight.py
===================
Превращает транскрипт YouTube-видео в insight.md формата
knowledge/kz/niches/<NICHE>_insight.md (8 разделов).

Используется в pipeline 3 источников: subtitles → Gemini Flash → insight.md.

Запуск standalone:
    python3 scripts/generate_insight.py <transcript.txt> "<title>" <url>
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = REPO_ROOT / "scripts" / "insight_prompt.md"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent"
)

# Чтобы транскрипт точно влез в окно Flash — обрезаем агрессивно.
# 1.0M-context Flash спокойно ест 200k+ tokens, но 80k симв ≈ 25k tokens,
# чего хватает для 1-1.5 ч видео и оставляет место под ответ.
TRANSCRIPT_HARD_LIMIT = 80_000

NO_CONTENT_MARKER = "## Видео не содержит экстрагируемого опыта"

log = logging.getLogger("zerek.insight")


class InsightError(Exception):
    pass


def _build_prompt(transcript: str, title: str, url: str) -> str:
    template = PROMPT_FILE.read_text(encoding="utf-8")
    excerpt = transcript[:TRANSCRIPT_HARD_LIMIT]
    return (
        template
        .replace("{title}", title or "(без заголовка)")
        .replace("{url}", url)
        .replace("{transcript}", excerpt)
    )


def generate_insight(transcript: str, title: str, url: str, api_key: str | None = None,
                     timeout: int = 120) -> str:
    """
    Вызывает Gemini Flash. Возвращает markdown текст.
    Если видео пустое (мотивация без содержания) — возвращает строку-маркер.
    """
    api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise InsightError("GEMINI_API_KEY не задан")

    if not transcript or len(transcript) < 200:
        raise InsightError(f"transcript пустой/короткий ({len(transcript)} симв)")

    prompt = _build_prompt(transcript, title, url)

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
        },
    }

    log.debug("Gemini request: prompt=%d chars", len(prompt))
    try:
        resp = requests.post(
            GEMINI_URL, params={"key": api_key},
            json=payload, timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.HTTPError as e:
        raise InsightError(f"Gemini HTTP {resp.status_code}: {resp.text[:300]}") from e
    except Exception as e:
        raise InsightError(f"Gemini request failed: {e}") from e

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        raise InsightError(f"Gemini ответ без candidates: {data}") from e

    text = text.strip()
    if not text:
        raise InsightError("Gemini вернул пустой ответ")

    # Очищаем от случайной обёртки в кодблок
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return text


def is_empty_insight(text: str) -> bool:
    """True если Gemini сказал что видео без содержания."""
    return NO_CONTENT_MARKER in text


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if len(sys.argv) < 4:
        print("Usage: python3 scripts/generate_insight.py <transcript_file> <title> <url>")
        sys.exit(1)
    transcript_path = Path(sys.argv[1])
    title = sys.argv[2]
    url = sys.argv[3]
    transcript = transcript_path.read_text(encoding="utf-8")
    out = generate_insight(transcript, title, url)
    print(out)


if __name__ == "__main__":
    main()
