"""
whisper_transcribe.py
=====================
Транскрибирует аудиофайл через whisper.cpp локально (бесплатно, Metal на macOS).

Используется в pipeline 3 источников: NotebookLM audio overview → mp3 → Whisper → audio_transcript.md.

Установка whisper.cpp:
    brew install whisper-cpp           # бинарь whisper-cli
    # модели:
    mkdir -p ~/.whisper-models
    curl -L -o ~/.whisper-models/ggml-small.bin \
        https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin

Скорость на M1/M2:
    base  — ~0.5× реалтайм (12 мин аудио = ~6 мин обработки)
    small — ~1.0× реалтайм (12 мин аудио = ~12 мин обработки) — рекомендуется

Запуск standalone:
    python3 scripts/whisper_transcribe.py audio.mp3
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger("zerek.whisper")

DEFAULT_MODEL = "small"
DEFAULT_LANG = "ru"

# Где искать модели — переменная среды или дефолт
MODELS_DIR_DEFAULT = Path.home() / ".whisper-models"
MODELS_DIR = Path(os.environ.get("WHISPER_MODELS_DIR", MODELS_DIR_DEFAULT))


class WhisperError(Exception):
    pass


def _find_binary() -> str:
    for cand in ("whisper-cli", "whisper-cpp", "main"):
        path = shutil.which(cand)
        if path:
            return path
    raise WhisperError(
        "whisper-cpp не найден в PATH. Установка: brew install whisper-cpp"
    )


def _find_model(model: str) -> Path:
    candidate = MODELS_DIR / f"ggml-{model}.bin"
    if candidate.exists():
        return candidate
    # Иногда brew кладёт сюда:
    brew_share = Path("/opt/homebrew/share/whisper-cpp")
    if brew_share.exists():
        for f in brew_share.iterdir():
            if f.name == f"ggml-{model}.bin":
                return f
    raise WhisperError(
        f"Модель ggml-{model}.bin не найдена в {MODELS_DIR}. "
        f"Скачай: curl -L -o {candidate} "
        f"https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{model}.bin"
    )


def transcribe(
    audio_path: str | Path,
    model: str = DEFAULT_MODEL,
    lang: str = DEFAULT_LANG,
    timeout: int = 3600,  # 1 час max — длинные аудио на small модели
) -> str:
    """
    Транскрибирует аудио в plain text.

    audio_path принимает mp3, wav, m4a, flac. Whisper.cpp сам конвертит.
    Возвращает чистый текст транскрипта (без таймкодов).
    """
    audio_path = Path(audio_path).resolve()
    if not audio_path.exists():
        raise WhisperError(f"Аудио не найдено: {audio_path}")

    binary = _find_binary()
    model_path = _find_model(model)

    with tempfile.TemporaryDirectory() as tmp_root:
        tmp = Path(tmp_root)
        out_prefix = tmp / "out"

        cmd = [
            binary,
            "-m", str(model_path),
            "-f", str(audio_path),
            "-l", lang,
            "-otxt",
            "-of", str(out_prefix),
            "--no-prints",  # тише
        ]
        log.info("whisper-cpp: model=%s lang=%s file=%s", model, lang, audio_path.name)
        log.debug("cmd: %s", " ".join(cmd))

        try:
            res = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            raise WhisperError(f"whisper timeout {timeout}s")

        if res.returncode != 0:
            raise WhisperError(
                f"whisper-cpp exit={res.returncode}: {res.stderr.strip()[:500]}"
            )

        txt_file = out_prefix.with_suffix(".txt")
        if not txt_file.exists():
            raise WhisperError(f"whisper-cpp завершился, но {txt_file.name} не создан")

        text = txt_file.read_text(encoding="utf-8")

    # Базовая очистка: схлопываем множественные пустые строки
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n".join([ln for ln in lines if ln])
    return cleaned


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/whisper_transcribe.py <audio_file> [model] [lang]")
        sys.exit(1)
    audio = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MODEL
    lang = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_LANG
    text = transcribe(audio, model=model, lang=lang)
    print(text)


if __name__ == "__main__":
    main()
