"""
backfill_insights.py
====================
Прогоняет subtitle-pipeline (yt-dlp + Gemini Flash) на уже-обработанных видео,
у которых ещё нет insight.md. Использует существующие entry_id и source_url
из knowledge/youtube_kb/<topic>/<entry_id>/meta.yaml.

Не трогает briefing.md и audio_transcript.md.

Запуск:
    python3 scripts/backfill_insights.py                # все done без insight.md
    python3 scripts/backfill_insights.py --limit 5      # первые 5
    python3 scripts/backfill_insights.py --dry-run
    python3 scripts/backfill_insights.py --topic marketing  # только marketing/
    python3 scripts/backfill_insights.py --entry yt_b6bc3e98e913  # одну
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from extract_subtitles import download_subtitles, SubtitleError  # noqa: E402
from generate_insight import generate_insight, is_empty_insight, InsightError  # noqa: E402

KB_DIR = REPO_ROOT / "knowledge" / "youtube_kb"
PIPELINE_FILE = KB_DIR / "_pipeline.yaml"
INSIGHT_VERSION = "subtitles_gemini_v1"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("backfill.insight")


def load_pipeline() -> dict:
    return yaml.safe_load(PIPELINE_FILE.read_text(encoding="utf-8")) or {}


def save_pipeline(data: dict) -> None:
    PIPELINE_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_targets(pipeline: dict, args) -> list[dict]:
    """Ищет entries в done без insight.md."""
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
        if "insight" in artifacts:
            continue
        if (entry_dir / "insight.md").exists():
            continue
        targets.append(entry)
    return targets


def backfill_one(entry: dict, dry_run: bool) -> bool:
    """Возвращает True если успешно сгенерил insight.md."""
    entry_id = entry["entry_id"]
    url = entry.get("url")
    topic = entry.get("primary_topic") or entry.get("target_folder") or "_inbox"
    entry_dir = KB_DIR / topic / entry_id
    insight_path = entry_dir / "insight.md"
    meta_path = entry_dir / "meta.yaml"

    log.info(f"=== {entry_id} ({topic}) — {url} ===")

    if dry_run:
        log.info("  [dry-run] пропустил")
        return False

    try:
        transcript, lang, title = download_subtitles(url)
    except SubtitleError as e:
        log.warning(f"  ✗ субтитры: {e}")
        return False
    log.info(f"  ✓ субтитры: {lang}, {len(transcript)} chars")

    try:
        insight_text = generate_insight(transcript, title or entry.get("video_title", ""), url)
    except InsightError as e:
        log.warning(f"  ✗ Gemini: {e}")
        return False

    if is_empty_insight(insight_text):
        log.info("  ~ видео без экстрагируемого опыта — пропуск")
        return False

    # Frontmatter prepend manually
    fm = {
        "entry_id": entry_id,
        "source_url": url,
        "video_title": title,
        "subtitle_lang": lang,
        "transcript_length": len(transcript),
        "generator": "subtitles+gemini-2.5-flash",
        "insight_version": INSIGHT_VERSION,
        "generated_at": now_iso(),
    }
    fm_yaml = yaml.safe_dump(fm, allow_unicode=True, sort_keys=False).strip()
    payload = f"---\n{fm_yaml}\n---\n\n{insight_text.strip()}\n"
    insight_path.write_text(payload, encoding="utf-8")
    log.info(f"  ✓ {insight_path.relative_to(REPO_ROOT)}")

    # Обновляем meta.yaml
    artifact = {
        "path": str(insight_path.relative_to(REPO_ROOT)),
        "generated_at": fm["generated_at"],
        "method": "subtitles+gemini",
        "subtitle_lang": lang,
    }
    if meta_path.exists():
        meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
    else:
        meta = {"entry_id": entry_id, "source_url": url, "primary_topic": topic, "artifacts": {}}
    artifacts = meta.setdefault("artifacts", {})
    artifacts["insight"] = artifact
    meta_path.write_text(
        yaml.safe_dump(meta, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )

    # Обновляем _pipeline.yaml
    entry_artifacts = entry.setdefault("artifacts", {})
    entry_artifacts["insight"] = artifact
    return True


def main():
    parser = argparse.ArgumentParser(description="Backfill insight.md для done-видео без него")
    parser.add_argument("--limit", type=int, default=0, help="максимум видео за прогон (0 = все)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--topic", help="ограничить определённой папкой (marketing, finance, ...)")
    parser.add_argument("--entry", help="один entry_id (yt_xxx)")
    args = parser.parse_args()

    pipeline = load_pipeline()
    targets = find_targets(pipeline, args)
    log.info(f"Найдено целей: {len(targets)}")
    if args.limit:
        targets = targets[: args.limit]
        log.info(f"Ограничено до {len(targets)}")

    counters = {"ok": 0, "skip": 0, "fail": 0}
    for entry in targets:
        try:
            ok = backfill_one(entry, args.dry_run)
            counters["ok" if ok else "skip"] += 1
        except Exception as e:
            log.error(f"  непредвиденная ошибка: {e}")
            counters["fail"] += 1

    if not args.dry_run:
        save_pipeline(pipeline)

    log.info("=" * 60)
    log.info(f"OK: {counters['ok']}  пропущено: {counters['skip']}  ошибок: {counters['fail']}")


if __name__ == "__main__":
    main()
