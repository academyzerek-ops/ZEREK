"""
migrate_to_3sources.py
======================
Разовая миграция структуры knowledge/youtube_kb/ от плоских файлов
к папкам с тремя источниками.

Было:
    knowledge/youtube_kb/<topic>/yt_<id>.md

Стало:
    knowledge/youtube_kb/<topic>/yt_<id>/
        ├── briefing.md   (бывший yt_<id>.md, без изменений контента)
        ├── meta.yaml     (общие метаданные)
        ├── insight.md             ← backfill отдельным скриптом
        └── audio_transcript.md    ← backfill отдельным скриптом

Также обновляет _pipeline.yaml: для каждой done-записи добавляет
artifacts.briefing.* и убирает md_path/target_folder в пользу нового формата.

Запуск:
    python3 scripts/migrate_to_3sources.py            # с подтверждением
    python3 scripts/migrate_to_3sources.py --dry-run  # только показать
    python3 scripts/migrate_to_3sources.py --yes      # без подтверждения
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import frontmatter
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = REPO_ROOT / "knowledge" / "youtube_kb"
PIPELINE_FILE = KB_DIR / "_pipeline.yaml"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("migrate")


def load_pipeline() -> dict:
    data = yaml.safe_load(PIPELINE_FILE.read_text(encoding="utf-8")) or {}
    for k in ("pending", "in_progress", "done", "failed"):
        data.setdefault(k, [])
        if data[k] is None:
            data[k] = []
    return data


def save_pipeline(data: dict) -> None:
    PIPELINE_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def extract_title(briefing_text: str) -> str:
    for line in briefing_text.splitlines()[:30]:
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def migrate_one_done(entry: dict, dry_run: bool) -> tuple[str, dict]:
    """
    Возвращает (status, обновлённая-запись).
    status ∈ {migrated, already, missing, error}
    """
    entry_id = entry.get("entry_id")
    if not entry_id:
        return "error", entry

    target_folder = entry.get("target_folder") or entry.get("primary_topic") or "_inbox"
    md_path = entry.get("md_path")

    # Возможные источники: явный md_path или дефолтный <topic>/<entry_id>.md
    src_candidates: list[Path] = []
    if md_path:
        src_candidates.append(REPO_ROOT / md_path)
    src_candidates.append(KB_DIR / target_folder / f"{entry_id}.md")

    src = next((p for p in src_candidates if p.exists() and p.is_file()), None)

    final_dir = KB_DIR / target_folder / entry_id
    briefing_target = final_dir / "briefing.md"
    meta_target = final_dir / "meta.yaml"

    if briefing_target.exists() and meta_target.exists():
        log.info(f"  ~ {entry_id}: уже мигрирован")
        return "already", _reshape_entry(entry, final_dir, briefing_target)

    if src is None:
        log.warning(f"  ✗ {entry_id}: исходный md не найден ({target_folder}/{entry_id}.md)")
        return "missing", entry

    if dry_run:
        log.info(f"  → {entry_id}: {src.relative_to(REPO_ROOT)} → {briefing_target.relative_to(REPO_ROOT)}")
        return "migrated", entry  # не трогаем запись

    # Делаем папку
    final_dir.mkdir(parents=True, exist_ok=True)

    # Перемещаем yt_<id>.md → briefing.md
    src.rename(briefing_target)
    log.info(f"  ✓ {entry_id}: {src.relative_to(REPO_ROOT)} → {briefing_target.relative_to(REPO_ROOT)}")

    # Парсим frontmatter из briefing.md чтобы извлечь данные
    try:
        post = frontmatter.load(briefing_target)
        briefing_meta = dict(post.metadata)
        briefing_text = post.content or ""
    except Exception as e:
        log.warning(f"    frontmatter parse failed: {e}")
        briefing_meta = {}
        briefing_text = briefing_target.read_text(encoding="utf-8")

    title = extract_title(briefing_text)

    # Собираем meta.yaml
    completed_at = entry.get("completed_at") or briefing_meta.get("extracted_at") \
        or datetime.now(timezone.utc).isoformat()

    artifact_briefing = {
        "path": str(briefing_target.relative_to(REPO_ROOT)),
        "generated_at": briefing_meta.get("extracted_at") or completed_at,
        "method": "notebooklm",
    }

    meta_yaml = {
        "entry_id": entry_id,
        "source_url": entry.get("url") or briefing_meta.get("source_url"),
        "video_title": title,
        "primary_topic": target_folder,
        "completed_at": completed_at,
        "notebook_id": entry.get("notebook_id"),
        "classification_confidence": entry.get("classification_confidence")
            or briefing_meta.get("classification_confidence"),
        "artifacts": {"briefing": artifact_briefing},
    }
    # reclassification данные если были
    for k in ("reclassified_at", "reclassified_by", "reclassification_note"):
        if entry.get(k):
            meta_yaml[k] = entry[k]

    meta_target.write_text(
        yaml.safe_dump(meta_yaml, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    log.info(f"    + meta.yaml")

    return "migrated", _reshape_entry(entry, final_dir, briefing_target, title=title)


def _reshape_entry(entry: dict, final_dir: Path, briefing_target: Path, title: str = "") -> dict:
    """Перепрописывает запись из старого формата в новый."""
    out = dict(entry)
    out.pop("md_path", None)
    out["primary_topic"] = entry.get("primary_topic") or entry.get("target_folder")
    out["target_folder"] = entry.get("target_folder") or entry.get("primary_topic")
    out.setdefault("video_title", title)
    artifacts = out.setdefault("artifacts", {})
    artifacts.setdefault("briefing", {
        "path": str(briefing_target.relative_to(REPO_ROOT)),
        "generated_at": entry.get("completed_at"),
        "method": "notebooklm",
    })
    return out


def main():
    parser = argparse.ArgumentParser(description="Миграция knowledge/youtube_kb/ к структуре 3-х источников")
    parser.add_argument("--dry-run", action="store_true", help="только показать что будет сделано")
    parser.add_argument("--yes", action="store_true", help="без подтверждения")
    args = parser.parse_args()

    if not PIPELINE_FILE.exists():
        log.error(f"Не найден {PIPELINE_FILE}")
        sys.exit(1)

    pipeline = load_pipeline()
    done = pipeline["done"]
    log.info(f"В done: {len(done)} видео")

    if not args.yes and not args.dry_run:
        ans = input(f"Мигрировать {len(done)} видео? (yes/no) ").strip().lower()
        if ans not in ("yes", "y", "да", "д"):
            log.info("Отменено.")
            return

    counters = {"migrated": 0, "already": 0, "missing": 0, "error": 0}
    new_done: list[dict] = []

    for entry in done:
        status, new_entry = migrate_one_done(entry, dry_run=args.dry_run)
        counters[status] = counters.get(status, 0) + 1
        new_done.append(new_entry)

    if not args.dry_run:
        pipeline["done"] = new_done
        save_pipeline(pipeline)
        log.info(f"_pipeline.yaml обновлён.")

    log.info("=" * 60)
    log.info(f"Мигрировано: {counters['migrated']}  "
             f"уже было: {counters['already']}  "
             f"без файла: {counters['missing']}  "
             f"ошибок: {counters['error']}")


if __name__ == "__main__":
    main()
