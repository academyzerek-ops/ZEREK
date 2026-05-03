"""
mirror_to_vault.py
==================
Зеркалирует базы знаний из репо в Obsidian Vault. Заменяет старый mirror_to_vault.sh.

Раздел A — youtube_kb (структура 3-х источников):
    knowledge/youtube_kb/<topic>/<entry_id>/   →   Vault/KNOWLEDGE/YouTube/<topic>/<readable-title>/

Раздел B — kz/niches (insights):
    knowledge/kz/niches/<NICHE>_insight.md     →   Vault/01_NICHES/<NICHE>/insight.md

Особенности:
  • State-файл `~/.zerek_mirror_state.json` запоминает entry_id → vault_path.
  • Идемпотентно: SHA256 каждого файла; повторный прогон пропускает неизменённое.
  • Безопасно: никогда не удаляет файлы из Vault. Только копирует/переименовывает.
  • Cleanup (--cleanup): архивирует в KNOWLEDGE/YouTube/_archive/ те видео,
    которых больше нет в репо. Не удаляет.

Запуск:
    python3 scripts/mirror_to_vault.py
    python3 scripts/mirror_to_vault.py --dry-run
    python3 scripts/mirror_to_vault.py --cleanup
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_YOUTUBE_KB = REPO_ROOT / "knowledge" / "youtube_kb"
REPO_NICHES = REPO_ROOT / "knowledge" / "kz" / "niches"

VAULT_ROOT = Path(os.environ.get("ZEREK_VAULT_ROOT", "/Users/adil/Desktop/ZEREK"))
VAULT_YOUTUBE = VAULT_ROOT / "KNOWLEDGE" / "YouTube"
VAULT_NICHES = VAULT_ROOT / "01_NICHES"
VAULT_YT_ARCHIVE = VAULT_YOUTUBE / "_archive"

STATE_FILE = Path(os.environ.get(
    "ZEREK_MIRROR_STATE", str(Path.home() / ".zerek_mirror_state.json")
))

YOUTUBE_FILES = ("insight.md", "briefing.md", "audio_transcript.md")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("mirror")


# === STATE ===

def load_state() -> dict:
    if not STATE_FILE.exists():
        return {"version": 1, "youtube": {}, "niches": {}}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        data.setdefault("version", 1)
        data.setdefault("youtube", {})
        data.setdefault("niches", {})
        return data
    except Exception as e:
        log.warning(f"State-файл повреждён ({e}) — создаю заново")
        return {"version": 1, "youtube": {}, "niches": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


# === TITLE CLEANUP ===

_TITLE_PREFIX_RE = re.compile(
    r"^(Аналитический (брифинг|бриф|отчет|обзор)|Брифинг по итогам анализа)[: ]+",
    re.IGNORECASE,
)
_FORBIDDEN_FS_CHARS = re.compile(r'[\\/:*?"<>|]')
_WHITESPACE = re.compile(r"\s+")


def clean_title(raw: str) -> str:
    """Применяет правила очистки заголовков для имён в Vault."""
    title = _TITLE_PREFIX_RE.sub("", raw or "")
    title = _FORBIDDEN_FS_CHARS.sub("-", title)
    title = title.replace("«", '"').replace("»", '"')
    title = _WHITESPACE.sub(" ", title).strip()
    title = title[:100].rstrip(" -")
    return title or "Без названия"


def extract_title_from_md(md_path: Path) -> str:
    """Ищет первый '# ...' в первых 30 строках файла."""
    try:
        with open(md_path, "r", encoding="utf-8", errors="replace") as f:
            for _ in range(30):
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                # frontmatter — пропускаем
                if line in ("---",):
                    continue
                if line.startswith("# "):
                    return line[2:].strip()
    except Exception:
        pass
    return ""


# === РАЗДЕЛ A: YOUTUBE ===

def collect_repo_youtube_entries() -> dict[str, dict]:
    """
    Возвращает {entry_id: {topic, dir_path}} для всех валидных entry-папок.
    """
    out: dict[str, dict] = {}
    if not REPO_YOUTUBE_KB.exists():
        return out
    for topic_dir in sorted(REPO_YOUTUBE_KB.iterdir()):
        if not topic_dir.is_dir() or topic_dir.name.startswith("_"):
            # _inbox валиден как topic, _archive нет — но поскольку мы зеркалим только репо в vault,
            # _inbox разрешим (это валидный topic).
            if topic_dir.name != "_inbox":
                continue
        for entry_dir in sorted(topic_dir.iterdir()):
            if not entry_dir.is_dir():
                continue
            if not entry_dir.name.startswith("yt_"):
                continue
            # Убедиться что внутри есть хоть один из YOUTUBE_FILES
            if not any((entry_dir / f).exists() for f in YOUTUBE_FILES):
                continue
            out[entry_dir.name] = {"topic": topic_dir.name, "dir": entry_dir}
    return out


def resolve_vault_path(topic: str, title_seed_path: Path,
                      taken: set[str]) -> tuple[Path, str]:
    """
    Возвращает (полный путь к папке в Vault, относительный vault_path для state).
    Разрешает конфликты имён через -2, -3 ... суффикс.
    """
    title = clean_title(extract_title_from_md(title_seed_path)) if title_seed_path.exists() else ""
    if not title:
        title = "Без названия"
    base = title
    for i in range(1, 100):
        candidate_name = base if i == 1 else f"{base}-{i}"
        rel = Path("KNOWLEDGE") / "YouTube" / topic / candidate_name
        if str(rel) not in taken and not (VAULT_ROOT / rel).exists():
            taken.add(str(rel))
            return (VAULT_ROOT / rel, str(rel))
    # Совсем уж край — entry_id вместо имени
    fallback = Path("KNOWLEDGE") / "YouTube" / topic / title_seed_path.parent.name
    return (VAULT_ROOT / fallback, str(fallback))


def sync_youtube_entry(entry_id: str, info: dict, state: dict, dry_run: bool,
                       taken_paths: set[str]) -> str:
    """
    Возвращает статус: 'new', 'updated', 'skipped', 'renamed'
    """
    topic = info["topic"]
    src_dir: Path = info["dir"]

    src_files: dict[str, Path] = {
        f: src_dir / f for f in YOUTUBE_FILES if (src_dir / f).exists()
    }
    if not src_files:
        return "skipped"

    src_hashes = {f: file_sha256(p) for f, p in src_files.items()}

    yt_state = state["youtube"]
    prev = yt_state.get(entry_id)

    # ---- НОВОЕ ВИДЕО ----
    if not prev:
        # Заголовок берём из briefing.md → insight.md → audio_transcript.md
        title_seed = (
            src_files.get("briefing.md")
            or src_files.get("insight.md")
            or src_files.get("audio_transcript.md")
        )
        vault_dir, vault_rel = resolve_vault_path(topic, title_seed, taken_paths)

        if dry_run:
            log.info(f"  [+] {entry_id} → {vault_rel}/ ({len(src_files)} файлов)")
            return "new"

        vault_dir.mkdir(parents=True, exist_ok=True)
        for fname, src in src_files.items():
            shutil.copy2(src, vault_dir / fname)
        yt_state[entry_id] = {
            "vault_path": vault_rel,
            "topic": topic,
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "source_hashes": src_hashes,
        }
        log.info(f"  [+] {entry_id} → {vault_rel}/ ({len(src_files)} файлов)")
        return "new"

    # ---- УЖЕ ЕСТЬ В STATE ----
    vault_rel = prev.get("vault_path") or ""
    vault_dir = VAULT_ROOT / vault_rel
    taken_paths.add(vault_rel)

    # Если topic поменялся (например, запись пере-классифицировали) — переносим в Vault
    if prev.get("topic") != topic:
        # Новый таргет
        title_seed = (
            src_files.get("briefing.md")
            or src_files.get("insight.md")
            or src_files.get("audio_transcript.md")
        )
        new_vault_dir, new_rel = resolve_vault_path(topic, title_seed, taken_paths)
        if dry_run:
            log.info(f"  [→] {entry_id} перенос topic: {prev.get('topic')} → {topic} ({new_rel})")
            return "renamed"
        if vault_dir.exists():
            new_vault_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(vault_dir), str(new_vault_dir))
            log.info(f"  [→] {entry_id} перенос {prev.get('topic')} → {topic}")
        else:
            new_vault_dir.mkdir(parents=True, exist_ok=True)
        vault_dir = new_vault_dir
        prev["vault_path"] = new_rel
        prev["topic"] = topic

    # Поэлементная сверка хешей
    prev_hashes = prev.get("source_hashes", {})
    changed = [f for f, h in src_hashes.items() if prev_hashes.get(f) != h]

    if not changed:
        return "skipped"

    if dry_run:
        log.info(f"  [^] {entry_id} обновить: {', '.join(changed)}")
        return "updated"

    vault_dir.mkdir(parents=True, exist_ok=True)
    for fname in changed:
        shutil.copy2(src_files[fname], vault_dir / fname)
    prev["source_hashes"] = src_hashes
    prev["last_synced"] = datetime.now(timezone.utc).isoformat()
    log.info(f"  [^] {entry_id} обновлено: {', '.join(changed)}")
    return "updated"


def cleanup_youtube(repo_entries: dict[str, dict], state: dict, dry_run: bool) -> int:
    """
    Видео которых нет в репо, но есть в state — переносим в _archive/.
    Возвращает количество архивированных.
    """
    archived = 0
    yt_state = state["youtube"]
    for entry_id in list(yt_state.keys()):
        if entry_id in repo_entries:
            continue
        prev = yt_state[entry_id]
        vault_rel = prev.get("vault_path")
        if not vault_rel:
            continue
        src = VAULT_ROOT / vault_rel
        if not src.exists():
            # уже нет в Vault — просто чистим state
            log.info(f"  [-] {entry_id} нет ни в репо, ни в Vault — чищу state")
            if not dry_run:
                yt_state.pop(entry_id, None)
            continue
        dst = VAULT_YT_ARCHIVE / src.name
        # Имя коллизии — добавляем timestamp
        if dst.exists():
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            dst = VAULT_YT_ARCHIVE / f"{src.name}_{ts}"
        if dry_run:
            log.info(f"  [a] {entry_id} → _archive/{dst.name}")
        else:
            VAULT_YT_ARCHIVE.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            yt_state.pop(entry_id, None)
            log.info(f"  [a] {entry_id} → _archive/{dst.name}")
        archived += 1
    return archived


# === РАЗДЕЛ B: NICHES ===

def sync_niches(state: dict, dry_run: bool) -> dict[str, int]:
    counters = {"new": 0, "updated": 0, "skipped": 0}
    if not REPO_NICHES.exists():
        return counters

    niches_state = state["niches"]
    for src in sorted(REPO_NICHES.glob("*_insight.md")):
        niche_code = src.name.replace("_insight.md", "")
        if not niche_code:
            continue

        sha = file_sha256(src)
        prev = niches_state.get(niche_code) or {}
        prev_sha = prev.get("source_hash")

        rel = Path("01_NICHES") / niche_code / "insight.md"
        dst = VAULT_ROOT / rel

        if prev_sha == sha and dst.exists():
            counters["skipped"] += 1
            continue

        if dry_run:
            tag = "+" if not dst.exists() else "^"
            log.info(f"  [{tag}] {niche_code} → {rel}")
            counters["new" if not dst.exists() else "updated"] += 1
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        niches_state[niche_code] = {
            "vault_path": str(rel),
            "last_synced": datetime.now(timezone.utc).isoformat(),
            "source_hash": sha,
        }
        if not prev:
            log.info(f"  [+] {niche_code} → {rel}")
            counters["new"] += 1
        else:
            log.info(f"  [^] {niche_code} обновлён")
            counters["updated"] += 1

    return counters


# === MAIN ===

def main():
    parser = argparse.ArgumentParser(description="ZEREK mirror_to_vault — knowledge репо → Obsidian Vault")
    parser.add_argument("--dry-run", action="store_true", help="не копировать, только показать")
    parser.add_argument("--cleanup", action="store_true", help="архивировать в Vault/_archive то, чего больше нет в репо")
    args = parser.parse_args()

    if not VAULT_ROOT.exists():
        log.error(f"Vault не найден: {VAULT_ROOT}. Установи ZEREK_VAULT_ROOT или создай папку.")
        sys.exit(1)

    state = load_state()

    # ---- A. YouTube ----
    log.info("=== A. youtube_kb ===")
    repo_entries = collect_repo_youtube_entries()
    log.info(f"В репо: {len(repo_entries)} entry-папок")

    counters_yt = {"new": 0, "updated": 0, "skipped": 0, "renamed": 0}
    taken: set[str] = set()
    # сначала маркируем уже-известные пути как занятые
    for v in state["youtube"].values():
        if "vault_path" in v:
            taken.add(v["vault_path"])

    for entry_id, info in repo_entries.items():
        st = sync_youtube_entry(entry_id, info, state, args.dry_run, taken)
        counters_yt[st] = counters_yt.get(st, 0) + 1

    archived = 0
    if args.cleanup:
        log.info("--- cleanup ---")
        archived = cleanup_youtube(repo_entries, state, args.dry_run)

    # ---- B. Niches ----
    log.info("=== B. kz/niches ===")
    counters_n = sync_niches(state, args.dry_run)

    if not args.dry_run:
        save_state(state)

    log.info("=" * 60)
    log.info(
        f"YouTube: новых {counters_yt['new']}, обновлено {counters_yt['updated']}, "
        f"пропущено {counters_yt['skipped']}, перенесено {counters_yt.get('renamed', 0)}, "
        f"архивировано {archived}"
    )
    log.info(
        f"Niches:  новых {counters_n['new']}, обновлено {counters_n['updated']}, "
        f"пропущено {counters_n['skipped']}"
    )
    log.info(f"State: {STATE_FILE}")


if __name__ == "__main__":
    main()
