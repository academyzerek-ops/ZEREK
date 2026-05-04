"""
extract_subtitles.py
====================
Скачивает субтитры YouTube через yt-dlp и парсит VTT в plain text.

Используется в pipeline 3 источников: субтитры → Gemini Flash → insight.md.

Защита от HTTP 429 (rate limit YouTube):
  • Последовательный перебор языков/режимов: ru manual → auto-ru → en manual → auto-en.
    НЕ запрашивает все варианты одним вызовом — каждая попытка отдельный запуск.
  • Между попытками — пауза `attempt_delay` секунд (по умолчанию 3).
  • Внутри yt-dlp — флаг `--sleep-requests 2` (между HTTP-запросами).
  • На HTTP 429 — exponential backoff: 60s → 5min → RateLimitStopError.
    Tracker общий на батч (передаётся снаружи), счётчик не сбрасывается между видео.

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
import time
from pathlib import Path

log = logging.getLogger("zerek.subs")


class SubtitleError(Exception):
    """Поднимается когда субтитры недоступны или неприемлемы для одного видео."""


class RateLimitError(Exception):
    """Внутренний — yt-dlp вернул HTTP 429. Не пробрасывается наверх — обрабатывается в backoff-обёртке."""


class RateLimitStopError(Exception):
    """
    Поднимается когда YouTube продолжает блокировать после 60s + 5min пауз.
    НЕ наследуется от SubtitleError специально: вызывающий код должен
    остановить весь батч, а не пропустить видео и пойти дальше.
    """


_RATE_LIMIT_MARKERS = (
    "http error 429",
    "too many requests",
    "rate limit",
    "rate-limit",
    "429: too many",
)


def _is_rate_limit(stderr: str) -> bool:
    s = (stderr or "").lower()
    return any(m in s for m in _RATE_LIMIT_MARKERS)


class RateLimitTracker:
    """
    Считает 429-удары за всю сессию. На N-ный удар (по умолчанию 3-й) —
    останавливает батч через RateLimitStopError.

    Пауз две: 60s, 300s. Третий 429 = стоп.
    """

    def __init__(self, pauses: tuple[int, ...] = (60, 300)):
        self.pauses = pauses
        self.hits = 0

    def register_hit(self) -> int:
        """Регистрирует 429. Возвращает паузу в секундах. Поднимает RateLimitStopError если квота исчерпана."""
        if self.hits >= len(self.pauses):
            raise RateLimitStopError(
                f"yt-dlp HTTP 429 повторился {self.hits + 1}-й раз — "
                f"YouTube продолжает блокировать после пауз {self.pauses}. "
                f"Батч остановлен. Подожди час и запусти снова."
            )
        wait = self.pauses[self.hits]
        self.hits += 1
        return wait


def _ensure_yt_dlp() -> list[str]:
    """Возвращает префикс команды для запуска yt-dlp."""
    binary = shutil.which("yt-dlp")
    if binary:
        return [binary]
    try:
        subprocess.run(
            [sys.executable, "-m", "yt_dlp", "--version"],
            capture_output=True, check=True, timeout=10,
        )
        return [sys.executable, "-m", "yt_dlp"]
    except Exception:
        raise SubtitleError(
            "yt-dlp не установлен. Установка: pip install yt-dlp"
        )


def _vtt_to_plain(vtt_text: str) -> str:
    """
    Парсит VTT в plain text:
      - убирает заголовок 'WEBVTT', 'Kind:', 'Language:'
      - убирает таймкоды
      - убирает inline-теги <c>...</c>, <v>...</v>
      - дедуплицирует подряд идущие одинаковые строки (типично для авто-CC)
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
        if "-->" in line:
            continue
        line = re.sub(r"<[^>]+>", "", line)
        line = re.sub(r"\s+", " ", line).strip()
        if not line or line == prev:
            continue
        out.append(line)
        prev = line

    text = " ".join(out)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _run_one_attempt(
    url: str,
    lang: str,
    mode: str,  # 'manual' | 'auto'
    timeout: int = 90,
) -> tuple[str, str]:
    """
    Один запуск yt-dlp на одну комбинацию (lang, mode).
    Возвращает (transcript_plain, video_title).

    Поднимает:
      RateLimitError — если yt-dlp вернул 429 (нужно backoff)
      SubtitleError  — если субтитров нет / транскрипт мусорный / другая ошибка
    """
    cmd = _ensure_yt_dlp()

    with tempfile.TemporaryDirectory() as tmp_root:
        tmp = Path(tmp_root)
        out_template = str(tmp / "%(id)s.%(ext)s")

        cmd_parts = list(cmd) + [
            url,
            "--sub-langs", lang,
            "--sub-format", "vtt",
            "--convert-subs", "vtt",
            "--skip-download",
            "--no-warnings",
            "--no-progress",
            "--sleep-requests", "2",  # пауза между HTTP-запросами внутри yt-dlp
            "--output", out_template,
            "--write-info-json",
        ]
        if mode == "manual":
            cmd_parts.append("--write-subs")
        elif mode == "auto":
            cmd_parts.append("--write-auto-subs")
        else:
            raise ValueError(f"unknown mode: {mode!r}")

        log.debug("yt-dlp [%s %s]: %s", lang, mode, " ".join(cmd_parts))
        try:
            res = subprocess.run(
                cmd_parts,
                capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise SubtitleError(f"yt-dlp timeout {timeout}s ({lang}/{mode})")

        if res.returncode != 0:
            stderr = res.stderr or ""
            if _is_rate_limit(stderr):
                raise RateLimitError(stderr.strip()[:300])
            raise SubtitleError(
                f"yt-dlp exit={res.returncode} ({lang}/{mode}): {stderr.strip()[:200]}"
            )

        vtt_files = list(tmp.glob("*.vtt"))
        if not vtt_files:
            raise SubtitleError(f"нет VTT в {lang}/{mode}")

        # Берём первый VTT с подходящим языком
        chosen: Path | None = None
        for f in vtt_files:
            if f".{lang}." in f.name:
                chosen = f
                break
        if not chosen:
            chosen = vtt_files[0]

        vtt_text = chosen.read_text(encoding="utf-8", errors="replace")
        transcript = _vtt_to_plain(vtt_text)
        if len(transcript) < 200:
            raise SubtitleError(
                f"транскрипт слишком короткий ({len(transcript)} симв) — мусор"
            )

        # Заголовок из info.json
        title = ""
        info_files = list(tmp.glob("*.info.json"))
        if info_files:
            try:
                import json
                info = json.loads(info_files[0].read_text(encoding="utf-8"))
                title = (info.get("title") or "").strip()
            except Exception:
                pass

        return transcript, title


def _try_with_backoff(
    url: str,
    lang: str,
    mode: str,
    tracker: "RateLimitTracker",
    timeout: int = 90,
) -> tuple[str, str]:
    """
    Запускает _run_one_attempt с обработкой 429.
    На 429 — пауза по tracker, повтор той же попытки.
    Если tracker исчерпан — RateLimitStopError всплывает наверх.
    """
    while True:
        try:
            return _run_one_attempt(url, lang, mode, timeout=timeout)
        except RateLimitError as e:
            wait = tracker.register_hit()  # raises RateLimitStopError если квота
            log.warning(
                "HTTP 429 (#%d за сессию) — пауза %ds. yt-dlp: %s",
                tracker.hits, wait, str(e)[:100],
            )
            time.sleep(wait)


def download_subtitles(
    url: str,
    tracker: "RateLimitTracker | None" = None,
    attempt_delay: float = 3.0,
    timeout: int = 90,
) -> tuple[str, str, str]:
    """
    Скачивает субтитры YouTube. Возвращает (transcript_text, lang_used, video_title).

    Перебирает по очереди с паузой `attempt_delay` между попытками:
        ru manual → auto-ru → en manual → auto-en

    Args:
        tracker: общий RateLimitTracker на батч. Если None — создаётся одноразовый.
        attempt_delay: пауза между попытками одного видео (секунд).
        timeout: timeout одной yt-dlp команды.

    Raises:
        SubtitleError: ни одна попытка не дала субтитров.
        RateLimitStopError: YouTube блокирует, batch должен остановиться.
    """
    if tracker is None:
        tracker = RateLimitTracker()

    attempts = (
        ("ru", "manual"),
        ("ru", "auto"),
        ("en", "manual"),
        ("en", "auto"),
    )
    last_err: SubtitleError | None = None

    for i, (lang, mode) in enumerate(attempts):
        if i > 0 and attempt_delay > 0:
            time.sleep(attempt_delay)
        log.debug("попытка %d/%d: %s/%s", i + 1, len(attempts), lang, mode)
        try:
            transcript, title = _try_with_backoff(url, lang, mode, tracker, timeout=timeout)
            log.info(
                "  субтитры: %s/%s, %d симв, title='%s'",
                lang, mode, len(transcript), title[:60],
            )
            return transcript, lang, title
        except SubtitleError as e:
            last_err = e
            log.debug("  ✗ %s/%s: %s", lang, mode, e)
            continue
        # RateLimitStopError всплывает наверх — НЕ ловим здесь специально

    raise SubtitleError(
        f"ни ru manual/auto, ни en manual/auto не сработали. Последняя: {last_err}"
    )


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
    except RateLimitStopError as e:
        print(f"RATE LIMIT: {e}")
        sys.exit(3)
    except SubtitleError as e:
        print(f"FAIL: {e}")
        sys.exit(2)


if __name__ == "__main__":
    main()
