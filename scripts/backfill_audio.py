"""
backfill_audio.py
=================
Прогоняет audio overview (NotebookLM) + Whisper.cpp на уже-обработанных видео,
у которых ещё нет audio_transcript.md. Использует existing notebook_id из
_pipeline.yaml.

Если notebook был удалён в NotebookLM — создаёт новый, загружает source_url,
запрашивает audio overview.

Запуск:
    python3 scripts/backfill_audio.py
    python3 scripts/backfill_audio.py --limit 5
    python3 scripts/backfill_audio.py --topic marketing
    python3 scripts/backfill_audio.py --entry yt_b6bc3e98e913
    python3 scripts/backfill_audio.py --whisper-model base   # быстрее, но менее точно
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from whisper_transcribe import transcribe as whisper_transcribe, WhisperError  # noqa: E402

try:
    from notebooklm import NotebookLMClient
except ImportError:
    NotebookLMClient = None

KB_DIR = REPO_ROOT / "knowledge" / "youtube_kb"
PIPELINE_FILE = KB_DIR / "_pipeline.yaml"
AUDIO_CACHE_DIR = REPO_ROOT / "data" / "raw" / "audio"
AUDIO_VERSION = "notebooklm_audio_v1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("backfill.audio")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_pipeline() -> dict:
    return yaml.safe_load(PIPELINE_FILE.read_text(encoding="utf-8")) or {}


def save_pipeline(data: dict) -> None:
    PIPELINE_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def find_targets(pipeline: dict, args) -> list[dict]:
    targets = []
    for entry in pipeline.get("done", []):
        entry_id = entry.get("entry_id")
        topic = entry.get("primary_topic") or entry.get("target_folder") or "_inbox"
        if args.topic and topic != args.topic:
            continue
        if args.entry and entry_id != args.entry:
            continue
        entry_dir = KB_DIR / topic / entry_id
        if not entry_dir.exists():
            continue
        artifacts = entry.get("artifacts") or {}
        if "audio_transcript" in artifacts:
            continue
        if (entry_dir / "audio_transcript.md").exists():
            continue
        targets.append(entry)
    return targets


async def fetch_audio(client, notebook_id, source_url: str,
                      audio_path: Path, processing_timeout: int):
    """Стратегия:
    1. Если notebook_id есть → list_audio() — ищем уже готовое (status=completed/ready/done).
       Если есть — download_audio и вернуть 'downloaded'.
    2. Если нет готового → generate_audio (НЕ ждём долго), вернуть 'triggered'.
       Следующий backfill через ~4 часа подберёт когда NotebookLM сгенерит.
    Возвращает: 'downloaded' / 'triggered' / None.
    """
    if not notebook_id:
        log.info("  [audio] notebook_id отсутствует — создаю новый и триггерю")
        try:
            nb = await client.notebooks.create(f"ZEREK backfill audio {source_url[-11:]}")
            await client.sources.add_url(nb.id, source_url, wait=True)
            notebook_id = nb.id
            await client.artifacts.generate_audio(notebook_id, language="ru")
            log.info("  [audio] триггер отправлен — следующий backfill (4ч) подберёт")
        except Exception as e:
            log.warning(f"  [audio] не удалось создать notebook: {e}")
            return None
        return "triggered"

    # 1. Проверяем существующие audio артефакты
    try:
        existing = await client.artifacts.list_audio(notebook_id)
    except Exception as e:
        log.warning(f"  [audio] list_audio упал: {e}")
        existing = []

    ready_art = None
    for art in (existing or []):
        # NotebookLM-py: status — это число-enum, но есть удобный bool is_completed
        is_ready = bool(getattr(art, "is_completed", False))
        if not is_ready:
            # fallback на старые версии где is_completed нет
            status = str(getattr(art, "status", "") or getattr(art, "state", "")).lower()
            is_ready = status in ("completed", "ready", "done")
        if is_ready and getattr(art, "id", None):
            ready_art = art
            break

    if ready_art:
        log.info("  [audio] найден готовый артефакт — скачиваю")
        try:
            await client.artifacts.download_audio(notebook_id, output_path=str(audio_path))
            return "downloaded"
        except Exception as e:
            log.warning(f"  [audio] download упал: {e}")
            return None

    # 2. Готового нет — триггерим без ожидания
    log.info("  [audio] готового нет — отправляю триггер, следующий backfill подберёт")
    try:
        await client.artifacts.generate_audio(notebook_id, language="ru")
    except Exception as e:
        log.warning(f"  [audio] generate упал: {e}")
        return None
    return "triggered"


async def backfill_one(client, entry: dict, args) -> bool:
    entry_id = entry["entry_id"]
    url = entry.get("url")
    topic = entry.get("primary_topic") or entry.get("target_folder") or "_inbox"
    entry_dir = KB_DIR / topic / entry_id
    notebook_id = entry.get("notebook_id")

    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_CACHE_DIR / f"{entry_id}.mp3"
    transcript_path = entry_dir / "audio_transcript.md"
    meta_path = entry_dir / "meta.yaml"

    log.info(f"=== {entry_id} ({topic}) — {url} ===")
    if args.dry_run:
        log.info("  [dry-run] пропустил")
        return False

    if audio_path.exists() and audio_path.stat().st_size > 100_000 and not args.refetch:
        log.info(f"  [audio] кэш: {audio_path.name} ({audio_path.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        try:
            tag = await fetch_audio(client, notebook_id, url, audio_path,
                                    processing_timeout=args.processing_timeout)
            if tag is None:
                log.warning("  ✗ не удалось получить audio")
                return False
            if tag == "triggered":
                # триггер отправлен, аудио ещё не готово — пропускаем, в следующий запуск подберём
                return False
            log.info(f"  [audio] получено ({tag}, {audio_path.stat().st_size / 1024 / 1024:.1f} MB)")
        except Exception as e:
            log.warning(f"  ✗ NotebookLM audio: {e}")
            return False

    log.info("  [whisper] транскрибируем...")
    try:
        text = whisper_transcribe(audio_path, model=args.whisper_model, lang=args.whisper_lang)
    except WhisperError as e:
        log.warning(f"  ✗ whisper: {e}")
        return False

    if len(text) < 200:
        log.warning(f"  ✗ транскрипт слишком короткий ({len(text)} chars)")
        return False

    fm = {
        "entry_id": entry_id,
        "source_url": url,
        "audio_path": str(audio_path.relative_to(REPO_ROOT)),
        "audio_size_bytes": audio_path.stat().st_size,
        "whisper_model": args.whisper_model,
        "whisper_lang": args.whisper_lang,
        "audio_version": AUDIO_VERSION,
        "generated_at": now_iso(),
    }
    body = f"# Аудио-разбор\n\n{text}\n"
    fm_yaml = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    transcript_path.write_text(f"---\n{fm_yaml}\n---\n\n{body}", encoding="utf-8")
    log.info(f"  ✓ {transcript_path.relative_to(REPO_ROOT)} ({len(text)} chars)")

    artifact = {
        "path": str(transcript_path.relative_to(REPO_ROOT)),
        "generated_at": fm["generated_at"],
        "method": "notebooklm_audio+whisper",
        "whisper_model": args.whisper_model,
    }
    if meta_path.exists():
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    else:
        meta = {"entry_id": entry_id, "source_url": url, "primary_topic": topic, "artifacts": {}}
    meta.setdefault("artifacts", {})["audio_transcript"] = artifact
    meta_path.write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    entry.setdefault("artifacts", {})["audio_transcript"] = artifact
    return True


async def main_async(args):
    pipeline = load_pipeline()
    targets = find_targets(pipeline, args)
    log.info(f"Найдено целей: {len(targets)}")
    if args.limit:
        targets = targets[: args.limit]
        log.info(f"Ограничено до {len(targets)}")
    if not targets:
        return

    if NotebookLMClient is None:
        log.error("notebooklm-py не установлен. pip install 'notebooklm-py[browser]' && notebooklm login")
        sys.exit(1)

    counters = {"ok": 0, "skip": 0, "fail": 0}
    async with await NotebookLMClient.from_storage() as client:
        for entry in targets:
            try:
                ok = await backfill_one(client, entry, args)
                counters["ok" if ok else "skip"] += 1
            except Exception as e:
                log.error(f"  непредвиденная: {e}")
                counters["fail"] += 1
            save_pipeline(pipeline)  # инкрементально, чтобы не потерять прогресс

    log.info("=" * 60)
    log.info(f"OK: {counters['ok']}  пропущено: {counters['skip']}  ошибок: {counters['fail']}")


def main():
    parser = argparse.ArgumentParser(description="Backfill audio_transcript.md")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--topic", help="ограничить топиком")
    parser.add_argument("--entry", help="один entry_id")
    parser.add_argument("--whisper-model", default="small", choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--whisper-lang", default="ru")
    parser.add_argument("--processing-timeout", type=int, default=600,
                        help="максимум секунд ждать NotebookLM генерацию")
    parser.add_argument("--refetch", action="store_true",
                        help="игнорировать кэш аудио и запросить заново")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
