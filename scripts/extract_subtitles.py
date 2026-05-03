"""
extract_subtitles.py
====================
Скачивает авто-субтитры YouTube через yt-dlp и парсит VTT в plain text.

Используется в pipeline 3 источников: субтитры → Gemini Flash → insight.md
(параллельно с briefing.md от NotebookLM).

Запуск standalone (для теста):
    python3 scripts/extract_subtitles.py https://youtu.be/XXX
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("zerek.subs")


class SubtitleError(Exception):
    """Поднимается когда субтитры недоступны или неприемлемы."""


def _ensure_yt_dlp() -> str:
    """Возвращает путь к yt-dlp или поднимает SubtitleError."""
    binary = shutil.which("yt-dlp")
    if binary:
        return binary
    # Fallback на python -m yt_dlp
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, check=True, timeout=10,
        )
        return f"{sys.executable} -m yt_dlp"
    except Exception:
        raise SubtitleError(
            "yt-dlp не установлен. Установка: pip install yt-dlp"
        )


def _vtt_to_plain(vtt_text: str) -> str:
    """
    Парсит VTT в plain text:
      - убирает заголовок 'WEBVTT', 'Kind:', 'Language:'
      - убирает таймкоды '00:00:00.000 --> 00:00:05.000'
      - убирает inline-теги <c>...</c>, <v>...</v>
      - дедуплицирует подряд идущие одинаковые строки (типично для авто-CC)
      - схлопывает пустые строки
    """
    lines = vtt_text.splitlines()
    out: list[str] = []
    prev = ""
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("WEBVTT") or line.startswith("Kind:") or line.startswith("Language:"):
            continue
        if line.startswith("NOTE"):
            continue
        # Таймкод-строки: '00:00:01.500 --> 00:00:04.000' или '00:01.500 --> 00:04.000'
        if "-->" in line:
            continue
        # Убираем inline-теги
        line = re.sub(r"<[^>]+>", "", line)
        # Лишние пробелы
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == prev:
            continue
        out.append(line)
        prev = line

    text = " ".join(out)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def download_subtitles(
    url: str,
    lang_priority: list[str] | None = None,
    timeout: int = 90,
) -> tuple[str, str, str]:
    """
    Скачивает субтитры YouTube. Возвращает (transcript_text, lang_used, video_title).

    Логика:
      1. Пытается скачать **manual** субтитры (точнее авто) на одном из языков из priority.
      2. Если manual не нашёл — пробует **auto** субтитры.
      3. Если ничего нет — поднимает SubtitleError.

    Сохраняет файлы во временный каталог, удаляет после парсинга.
    """
    lang_priority = lang_priority or ["ru", "en"]
    binary = _ensure_yt_dlp()

    with tempfile.TemporaryDirectory() as tmp_root:
        tmp = Path(tmp_root)
        out_template = str(tmp / "%(id)s.%(ext)s")

        sub_langs = ",".join(lang_priority)
        # Один прогон с обоими флагами: yt-dlp выберет manual если есть, иначе auto
        cmd_parts = binary.split() + [
            url,
            "--write-subs",
            "--write-auto-subs",
            "--sub-langs", sub_langs,
            "--sub-format", "vtt",
            "--convert-subs", "vtt",
            "--skip-download",
            "--no-warnings",
            "--no-progress",
            "--output", out_template,
            # Дать заголовок видео в info.json
            "--write-info-json",
        ]

        log.debug("yt-dlp: %s", " ".join(cmd_parts))
        try:
            res = subprocess.run(
                cmd_parts,
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise SubtitleError(f"yt-dlp timeout {timeout}s")

        if res.returncode != 0:
            raise SubtitleError(
                f"yt-dlp exit={res.returncode}: {res.stderr.strip()[:300]}"
            )

        # Ищем VTT файл — приоритет manual (без .auto в имени)
        vtt_files = list(tmp.glob("*.vtt"))
        if not vtt_files:
            raise SubtitleError("yt-dlp скачал, но VTT не найден (видимо нет субтитров)")

        chosen: Path | None = None
        chosen_lang: str | None = None
        # 1) manual subs (по приоритету языков)
        for lang in lang_priority:
            for f in vtt_files:
                # manual: file.LANG.vtt  (без точки auto)
                # auto:   file.LANG.auto.vtt — yt-dlp по факту использует .LANG.vtt всё равно;
                #         но с --write-auto-subs тоже создаёт файл — отличаем по содержимому/Kind.
                if f.name.endswith(f".{lang}.vtt"):
                    chosen = f
                    chosen_lang = lang
                    break
            if chosen:
                break

        if not chosen:
            # fallback — берём любой первый
            chosen = vtt_files[0]
            # Пытаемся вычислить язык из имени
            m = re.search(r"\.([a-z]{2,3})(?:\.auto)?\.vtt$", chosen.name)
            chosen_lang = m.group(1) if m else "unknown"

        vtt_text = chosen.read_text(encoding="utf-8", errors="replace")
        transcript = _vtt_to_plain(vtt_text)

        if len(transcript) < 200:
            raise SubtitleError(
                f"Транскрипт слишком короткий ({len(transcript)} симв) — субтитры мусорные"
            )

        # Заголовок из info.json
        title = ""
        info_files = list(tmp.glob("*.info.json"))
        if info_files:
            try:
                import json
                info = json.loads(info_files[0].read_text(encoding="utf-8"))
                title = (info.get("title") or "").strip()
            except Exception as e:
                log.warning("info.json read failed: %s", e)

        return transcript, chosen_lang or "unknown", title


def main():
    """CLI для тестирования."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/extract_subtitles.py <youtube_url>")
        sys.exit(1)
    url = sys.argv[1]
    try:
        transcript, lang, title = download_subtitles(url)
        print(f"=== Title: {title} ===")
        print(f"=== Lang: {lang} ===")
        print(f"=== Length: {len(transcript)} chars ===")
        print()
        print(transcript[:2000])
        if len(transcript) > 2000:
            print(f"\n... ({len(transcript) - 2000} more chars)")
    except SubtitleError as e:
        print(f"FAIL: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
