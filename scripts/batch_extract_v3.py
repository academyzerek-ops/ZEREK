"""
ZEREK Knowledge Base Extractor v3.1 — Pipeline 3 источников
============================================================
На каждое видео создаётся папка `<topic>/<entry_id>/` с тремя артефактами:

    insight.md           — структурированный insight из субтитров (yt-dlp + Gemini Flash)
    briefing.md          — NotebookLM Briefing Doc (как раньше, переименовано из yt_<id>.md)
    audio_transcript.md  — транскрипт audio overview из NotebookLM (whisper.cpp локально)

Плюс meta.yaml с общими метаданными.

Pipeline:
    YouTube URL
       ├─ yt-dlp --write-auto-sub → VTT → plain text → Gemini Flash → insight.md
       ├─ NotebookLM → briefing doc → классификация Gemini Flash → briefing.md
       └─ NotebookLM → audio overview (mp3) → whisper.cpp → audio_transcript.md

Запуск:
    python3 scripts/batch_extract_v3.py
    python3 scripts/batch_extract_v3.py --max-per-day 10 --dry-run
    python3 scripts/batch_extract_v3.py --skip-audio   # без whisper (быстрее)
    python3 scripts/batch_extract_v3.py --skip-insight # без субтитров
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml
import requests

try:
    import frontmatter
except ImportError:
    print("Установи: pip install python-frontmatter")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Установи: pip install python-dotenv")
    sys.exit(1)

try:
    from notebooklm import NotebookLMClient
except ImportError:
    NotebookLMClient = None  # позволяем импорт скрипту даже без notebooklm-py

# Локальные модули
sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_subtitles import download_subtitles, SubtitleError  # noqa: E402
from generate_insight import generate_insight, is_empty_insight, InsightError  # noqa: E402
from whisper_transcribe import transcribe as whisper_transcribe, WhisperError  # noqa: E402


# === КОНФИГ ===
REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = REPO_ROOT / "knowledge" / "youtube_kb"
PIPELINE_FILE = KB_DIR / "_pipeline.yaml"
CLASSIFIER_PROMPT_FILE = REPO_ROOT / "scripts" / "classifier_prompt.md"
AUDIO_CACHE_DIR = REPO_ROOT / "data" / "raw" / "audio"  # вне репо? нет, в data/

BRIEFING_VERSION = "notebooklm_briefing_doc_v1"
INSIGHT_VERSION = "subtitles_gemini_v1"
AUDIO_VERSION = "notebooklm_audio_v1"

VALID_TOPICS = {
    "taxes", "finance", "marketing", "management",
    "support_programs", "case_studies", "niche_reviews", "general", "cinema",
}
INBOX_TOPIC = "_inbox"

DAILY_LIMIT_DEFAULT = 30
PROCESSING_TIMEOUT_SEC = 300

# Gemini API
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent"
)
CLASSIFIER_EXCERPT_LEN = 1500

WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "small")
WHISPER_LANG = os.environ.get("WHISPER_LANG", "ru")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("zerek-v3")


# === УТИЛИТЫ ===

def url_to_entry_id(url: str) -> str:
    h = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
    return f"yt_{h}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_pipeline() -> dict:
    if not PIPELINE_FILE.exists():
        return {"pending": [], "in_progress": [], "done": [], "failed": []}
    with open(PIPELINE_FILE, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    for key in ("pending", "in_progress", "done", "failed"):
        data.setdefault(key, [])
        if data[key] is None:
            data[key] = []
    return data


def save_pipeline(data: dict):
    PIPELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PIPELINE_FILE, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def already_processed(url: str, pipeline: dict) -> bool:
    entry_id = url_to_entry_id(url)
    for entry in pipeline["done"] + pipeline["in_progress"]:
        if entry.get("entry_id") == entry_id:
            return True
    return False


# === КЛАССИФИКАЦИЯ ===

def classify_briefing(briefing_text: str) -> tuple[str, str]:
    if not GEMINI_API_KEY:
        log.warning("GEMINI_API_KEY не задан — все заметки идут в _inbox")
        return INBOX_TOPIC, "low"

    template = CLASSIFIER_PROMPT_FILE.read_text(encoding="utf-8")
    excerpt = briefing_text[:CLASSIFIER_EXCERPT_LEN]
    prompt = template.replace("{briefing_excerpt}", excerpt)

    try:
        resp = requests.post(
            GEMINI_URL,
            params={"key": GEMINI_API_KEY},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.0, "maxOutputTokens": 20},
            },
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        answer = data["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
        answer = answer.strip(".'\"\n ").split()[0] if answer else ""

        if answer in VALID_TOPICS:
            return answer, "high"
        log.warning(f"Gemini вернул '{answer}' — _inbox")
        return INBOX_TOPIC, "low"
    except Exception as e:
        log.error(f"Gemini classification failed: {e}")
        return INBOX_TOPIC, "low"


# === АРТЕФАКТЫ ===

def write_briefing_md(entry_dir: Path, briefing_text: str, meta: dict) -> Path:
    """briefing.md — Briefing Doc от NotebookLM с frontmatter."""
    out = entry_dir / "briefing.md"
    post = frontmatter.Post(content=briefing_text, **meta)
    with open(out, "wb") as f:
        frontmatter.dump(post, f)
    return out


def write_insight_md(entry_dir: Path, insight_text: str, meta: dict) -> Path:
    """insight.md — наш формат из субтитров."""
    out = entry_dir / "insight.md"
    post = frontmatter.Post(content=insight_text, **meta)
    with open(out, "wb") as f:
        frontmatter.dump(post, f)
    return out


def write_audio_transcript_md(entry_dir: Path, transcript: str, meta: dict) -> Path:
    """audio_transcript.md — Whisper транскрипт audio overview."""
    out = entry_dir / "audio_transcript.md"
    body = f"# Аудио-разбор\n\n{transcript}\n"
    post = frontmatter.Post(content=body, **meta)
    with open(out, "wb") as f:
        frontmatter.dump(post, f)
    return out


def write_meta_yaml(entry_dir: Path, meta: dict) -> Path:
    """meta.yaml — общая мета по видео (URL, заголовок, статусы артефактов)."""
    out = entry_dir / "meta.yaml"
    out.write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return out


# === ИСТОЧНИК 1: СУБТИТРЫ + GEMINI → insight.md ===

def try_generate_insight(entry_dir: Path, url: str, entry_id: str) -> dict | None:
    """
    Пытается скачать субтитры и сгенерировать insight.md.
    Возвращает artifact-дескриптор для _pipeline.yaml или None если не удалось.
    """
    log.info("  [insight] download subtitles...")
    try:
        transcript, lang, title = download_subtitles(url)
    except SubtitleError as e:
        log.warning(f"  [insight] нет субтитров: {e}")
        return None

    log.info(f"  [insight] subtitles ok: {lang}, {len(transcript)} chars, title='{title[:60]}'")

    log.info("  [insight] generating via Gemini Flash...")
    try:
        insight_text = generate_insight(transcript, title, url)
    except InsightError as e:
        log.warning(f"  [insight] Gemini failed: {e}")
        return None

    if is_empty_insight(insight_text):
        log.info("  [insight] видео без экстрагируемого опыта — пропускаю insight.md")
        return None

    meta = {
        "entry_id": entry_id,
        "source_url": url,
        "video_title": title,
        "subtitle_lang": lang,
        "transcript_length": len(transcript),
        "generator": "subtitles+gemini-2.5-flash",
        "insight_version": INSIGHT_VERSION,
        "generated_at": now_iso(),
    }
    path = write_insight_md(entry_dir, insight_text, meta)
    log.info(f"  [insight] ✓ {path.relative_to(REPO_ROOT)}")
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "generated_at": meta["generated_at"],
        "method": "subtitles+gemini",
        "subtitle_lang": lang,
    }


# === ИСТОЧНИК 2: NOTEBOOKLM → briefing.md ===

async def try_generate_briefing(client, entry_dir: Path, url: str, entry_id: str
                                ) -> tuple[dict | None, str | None, str | None, str | None]:
    """
    Создаёт notebook, запрашивает briefing doc, сохраняет briefing.md.
    Возвращает (artifact, briefing_text, notebook_id, topic) — briefing_text нужен для классификации
    и для audio overview шага.
    """
    nb = await client.notebooks.create(f"ZEREK KB {entry_id}")
    log.info(f"  [briefing] notebook {nb.id}")
    await client.sources.add_url(nb.id, url, wait=True)
    log.info(f"  [briefing] source loaded")

    log.info(f"  [briefing] generating briefing doc...")
    status = await client.artifacts.generate_report(nb.id, language="ru")
    await client.artifacts.wait_for_completion(
        nb.id, status.task_id, timeout=PROCESSING_TIMEOUT_SEC
    )

    tmp = tempfile.NamedTemporaryFile(suffix=".md", delete=False).name
    await client.artifacts.download_report(nb.id, output_path=tmp)
    briefing_text = Path(tmp).read_text(encoding="utf-8")
    Path(tmp).unlink(missing_ok=True)
    log.info(f"  [briefing] {len(briefing_text)} chars")

    topic, confidence = classify_briefing(briefing_text)
    log.info(f"  [briefing] topic={topic} ({confidence})")

    meta = {
        "entry_id": entry_id,
        "source_url": url,
        "briefing_version": BRIEFING_VERSION,
        "primary_topic": topic,
        "classification_model": GEMINI_MODEL,
        "classification_confidence": confidence,
        "generated_at": now_iso(),
        "notebook_id": nb.id,
    }
    path = write_briefing_md(entry_dir, briefing_text, meta)
    log.info(f"  [briefing] ✓ {path.relative_to(REPO_ROOT)}")
    return (
        {
            "path": str(path.relative_to(REPO_ROOT)),
            "generated_at": meta["generated_at"],
            "method": "notebooklm",
        },
        briefing_text,
        nb.id,
        topic,
    )


# === ИСТОЧНИК 3: NOTEBOOKLM AUDIO + WHISPER → audio_transcript.md ===

async def try_generate_audio_transcript(client, notebook_id: str, entry_dir: Path,
                                        entry_id: str, url: str) -> dict | None:
    """
    Запрашивает у NotebookLM audio overview, скачивает mp3, прогоняет через Whisper.
    Возвращает artifact-дескриптор или None.

    NB: API NotebookLM-py для audio может отличаться по версиям — оборачиваем в try.
    """
    AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_CACHE_DIR / f"{entry_id}.mp3"

    log.info("  [audio] requesting audio overview...")
    audio_url: str | None = None
    try:
        # API менялся: artifacts.generate_audio_overview / artifacts.generate_audio
        gen = getattr(client.artifacts, "generate_audio_overview", None) or \
              getattr(client.artifacts, "generate_audio", None)
        if gen is None:
            log.warning("  [audio] notebooklm-py не поддерживает audio overview в этой версии")
            return None
        status = await gen(notebook_id, language="ru")
        # Дожидаемся (если есть task_id) и получаем url
        wait = getattr(client.artifacts, "wait_for_completion", None)
        if wait and getattr(status, "task_id", None):
            await wait(notebook_id, status.task_id, timeout=PROCESSING_TIMEOUT_SEC * 2)

        # Получаем URL — разные версии: download_audio / get_audio_url / status.url
        dl = getattr(client.artifacts, "download_audio", None)
        if dl:
            await dl(notebook_id, output_path=str(audio_path))
        else:
            audio_url = getattr(status, "url", None) or getattr(status, "audio_url", None)
            if not audio_url:
                log.warning("  [audio] не удалось получить URL аудио")
                return None
            r = requests.get(audio_url, timeout=120)
            r.raise_for_status()
            audio_path.write_bytes(r.content)
    except Exception as e:
        log.warning(f"  [audio] notebooklm audio overview failed: {e}")
        return None

    if not audio_path.exists() or audio_path.stat().st_size < 10_000:
        log.warning("  [audio] аудио-файл пустой или не создан")
        return None

    log.info(f"  [audio] downloaded {audio_path.stat().st_size / 1024 / 1024:.1f} MB, transcribing...")
    try:
        transcript_text = whisper_transcribe(audio_path, model=WHISPER_MODEL, lang=WHISPER_LANG)
    except WhisperError as e:
        log.warning(f"  [audio] whisper failed: {e}")
        return None

    if len(transcript_text) < 200:
        log.warning(f"  [audio] транскрипт слишком короткий ({len(transcript_text)} chars)")
        return None

    meta = {
        "entry_id": entry_id,
        "source_url": url,
        "audio_path": str(audio_path.relative_to(REPO_ROOT)),
        "audio_size_bytes": audio_path.stat().st_size,
        "whisper_model": WHISPER_MODEL,
        "whisper_lang": WHISPER_LANG,
        "audio_version": AUDIO_VERSION,
        "generated_at": now_iso(),
    }
    path = write_audio_transcript_md(entry_dir, transcript_text, meta)
    log.info(f"  [audio] ✓ {path.relative_to(REPO_ROOT)} ({len(transcript_text)} chars)")
    return {
        "path": str(path.relative_to(REPO_ROOT)),
        "generated_at": meta["generated_at"],
        "method": "notebooklm_audio+whisper",
        "whisper_model": WHISPER_MODEL,
    }


# === ОСНОВНОЙ ЦИКЛ ===

async def process_one(client, url: str, args) -> tuple[str, dict]:
    entry_id = url_to_entry_id(url)
    log.info(f"=== {entry_id} — {url} ===")

    # 1. Briefing — нужен для определения topic (target folder)
    try:
        # Пока не знаем topic — кладём в timestamped temp folder, потом переносим
        tmp_dir = KB_DIR / "_inbox" / entry_id
        tmp_dir.mkdir(parents=True, exist_ok=True)
        briefing_artifact, briefing_text, notebook_id, topic = await try_generate_briefing(
            client, tmp_dir, url, entry_id,
        )
    except Exception as e:
        log.error(f"  ✗ briefing failed: {e}")
        return "failed", {
            "url": url, "entry_id": entry_id,
            "failed_at": now_iso(),
            "reason": f"briefing: {str(e)[:300]}",
        }

    # 2. Переносим в правильный topic folder
    target_folder = topic if topic in VALID_TOPICS else INBOX_TOPIC
    final_dir = KB_DIR / target_folder / entry_id
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    if final_dir.exists():
        # перетираем (повторный запуск)
        import shutil
        shutil.rmtree(final_dir)
    tmp_dir.rename(final_dir)
    # Чистим пустую _inbox/<entry_id> папку и пустую _inbox если она опустела
    inbox_root = KB_DIR / "_inbox"
    if inbox_root.exists() and not any(inbox_root.iterdir()):
        inbox_root.rmdir()
    # Перепрописываем path в artifact (после move)
    briefing_artifact["path"] = str(
        (final_dir / "briefing.md").relative_to(REPO_ROOT)
    )

    artifacts = {"briefing": briefing_artifact}

    # 3. Insight (субтитры → Gemini)
    if not args.skip_insight:
        ins = try_generate_insight(final_dir, url, entry_id)
        if ins:
            artifacts["insight"] = ins
    else:
        log.info("  [insight] пропуск (--skip-insight)")

    # 4. Audio (NotebookLM audio + Whisper)
    if not args.skip_audio:
        try:
            aud = await try_generate_audio_transcript(client, notebook_id, final_dir, entry_id, url)
            if aud:
                artifacts["audio_transcript"] = aud
        except Exception as e:
            log.warning(f"  [audio] непредвиденная ошибка: {e}")
    else:
        log.info("  [audio] пропуск (--skip-audio)")

    # 5. meta.yaml
    video_title = ""
    try:
        post = frontmatter.load(final_dir / "briefing.md")
        # title первой строкой '# ...' в briefing
        for line in (post.content or "").splitlines():
            if line.startswith("# "):
                video_title = line[2:].strip()
                break
    except Exception:
        pass

    meta = {
        "entry_id": entry_id,
        "source_url": url,
        "video_title": video_title,
        "primary_topic": target_folder,
        "completed_at": now_iso(),
        "artifacts": artifacts,
    }
    write_meta_yaml(final_dir, meta)

    payload = {
        "url": url,
        "entry_id": entry_id,
        "notebook_id": notebook_id,
        "completed_at": meta["completed_at"],
        "primary_topic": target_folder,
        "target_folder": target_folder,
        "classification_confidence": briefing_artifact.get("classification_confidence",
                                                          "high" if target_folder != INBOX_TOPIC else "low"),
        "artifacts": artifacts,
    }
    log.info(f"  ✓ done: {target_folder}/{entry_id}/ ({len(artifacts)} artifacts)")
    return "done", payload


async def main_async(args):
    pipeline = load_pipeline()

    pending = pipeline["pending"]
    if not pending:
        log.info("pending пустой. Добавь YouTube-ссылки в knowledge/youtube_kb/_pipeline.yaml")
        return

    pending = [p for p in pending if not already_processed(p["url"], pipeline)]
    batch = pending[: args.max_per_day]
    log.info(f"В обработку: {len(batch)} из {len(pending)} pending. Лимит: {args.max_per_day}/день.")

    if args.dry_run:
        log.info("DRY-RUN: только показываю.")
        for p in batch:
            log.info(f"  → {p['url']} (entry_id={url_to_entry_id(p['url'])})")
        return

    if NotebookLMClient is None:
        log.error("notebooklm-py не установлен. pip install 'notebooklm-py[browser]' && notebooklm login")
        sys.exit(1)
    if not GEMINI_API_KEY:
        log.warning("⚠ GEMINI_API_KEY не задан — briefing уйдёт в _inbox без классификации, insight пропустится")

    async with await NotebookLMClient.from_storage() as client:
        for item in batch:
            url = item["url"]

            pipeline["in_progress"].append({"url": url, "started_at": now_iso()})
            save_pipeline(pipeline)

            status, payload = await process_one(client, url, args)

            pipeline["in_progress"] = [x for x in pipeline["in_progress"] if x["url"] != url]
            pipeline["pending"] = [x for x in pipeline["pending"] if x["url"] != url]
            pipeline[status].append(payload)
            save_pipeline(pipeline)

    log.info("=" * 60)
    log.info(f"Готово. done: {len(pipeline['done'])}  failed: {len(pipeline['failed'])}")


def main():
    parser = argparse.ArgumentParser(
        description="ZEREK YouTube → 3 источника (briefing/insight/audio) v3.1"
    )
    parser.add_argument("--max-per-day", type=int, default=DAILY_LIMIT_DEFAULT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-insight", action="store_true",
                        help="не пытаться качать субтитры и генерить insight.md")
    parser.add_argument("--skip-audio", action="store_true",
                        help="не делать audio overview + whisper (быстрее)")
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
