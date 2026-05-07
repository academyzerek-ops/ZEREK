"""
aggregate_niche_insights.py
===========================
Синтезирует обновлённый сводный insight по нише, объединяя:
- Старый `knowledge/kz/niches/<NICHE>_insight.md` (база ~5-7 видео, апрель 2026)
- Все `knowledge/youtube_kb/<topic>/yt_*/insight.md`, у которых
  `meta.yaml.niche_code == <NICHE>` (выставляется `classify_niches.py`).

Старая версия бэкапится в `knowledge/kz/niches/_archive/<NICHE>_insight.<ts>.md`.
В обновлённой версии добавляется YAML-frontmatter с источниками.

Запуск:
    python3 scripts/aggregate_niche_insights.py --niche=COFFEE
    python3 scripts/aggregate_niche_insights.py --all          # все ниши с >= MIN_VIDEOS
    python3 scripts/aggregate_niche_insights.py --niche=COFFEE --dry-run

Логи: knowledge/logs/aggregate_<date>.log
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = REPO_ROOT / "knowledge" / "youtube_kb"
NICHES_DIR = REPO_ROOT / "knowledge" / "kz" / "niches"
ARCHIVE_DIR = NICHES_DIR / "_archive"
REGISTRY_PATH = REPO_ROOT / "data" / "kz" / "niches_registry.yaml"
PROMPT_FILE = REPO_ROOT / "scripts" / "aggregate_prompt.md"
LOG_DIR = REPO_ROOT / "knowledge" / "logs"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent"
)

GENERATOR_TAG = "aggregate-gemini-2.5-flash-v1"
DEFAULT_MIN_VIDEOS = 2
NEW_INSIGHT_HARD_LIMIT = 30_000  # символов из одного нового insight (страховка от выбросов)

log = logging.getLogger("zerek.aggregate")


# ---------- helpers ----------

def load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


def load_niches() -> list[dict]:
    data = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    return data.get("niches", [])


def split_frontmatter(text: str) -> tuple[dict, str]:
    """Возвращает (frontmatter_dict, body). Если frontmatter'а нет — ({}, text)."""
    if not text.startswith("---"):
        return {}, text
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        fm = {}
    return fm, m.group(2)


def find_videos_for_niche(niche_code: str) -> list[Path]:
    """Возвращает список путей к insight.md для всех видео с niche_code == niche_code."""
    out: list[Path] = []
    for meta_path in sorted(KB_DIR.glob("*/yt_*/meta.yaml")):
        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        if meta.get("niche_code") != niche_code:
            continue
        insight = meta_path.parent / "insight.md"
        if insight.exists():
            out.append(insight)
    return out


def read_video_insight(path: Path) -> str:
    """Читает insight.md, отбрасывает frontmatter, возвращает только тело."""
    text = path.read_text(encoding="utf-8")
    _, body = split_frontmatter(text)
    body = body.strip()
    if len(body) > NEW_INSIGHT_HARD_LIMIT:
        body = body[:NEW_INSIGHT_HARD_LIMIT]
    return body


def call_gemini(prompt: str, api_key: str, timeout: int = 180) -> str:
    # thinkingBudget=0 — отключаем «размышление» 2.5 Flash, чтобы output-токены
    # не тратились на цепочку рассуждений (см. classify_niches.py).
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": 8192,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }
    resp = requests.post(
        GEMINI_URL, params={"key": api_key},
        json=payload, timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError) as e:
        finish = (data.get("candidates") or [{}])[0].get("finishReason")
        raise RuntimeError(f"Gemini ответ без parts (finishReason={finish}): {str(data)[:300]}") from e
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def build_prompt(niche_code: str, niche_name: str, old_text: str,
                 video_insights: list[tuple[Path, str]]) -> str:
    template = PROMPT_FILE.read_text(encoding="utf-8")

    parts = []
    for i, (p, body) in enumerate(video_insights, start=1):
        rel = p.relative_to(REPO_ROOT)
        parts.append(f"#### Видео {i} — {rel}\n\n{body}\n")
    new_concat = "\n---\n\n".join(parts)

    niche_label = f"{niche_code} ({niche_name})" if niche_name else niche_code
    return (
        template
        .replace("{niche}", niche_label)
        .replace("{old_insight_text}", old_text or "(старого insight'а нет)")
        .replace("{n_videos}", str(len(video_insights)))
        .replace("{new_insights_concatenated}", new_concat)
    )


def make_frontmatter(niche_code: str, sources: list[Path]) -> str:
    rels = [str(p.relative_to(REPO_ROOT)) for p in sources]
    fm = {
        "niche_code": niche_code,
        "aggregated_at": datetime.now(timezone.utc).isoformat(),
        "sources_count": len(rels),
        "sources": rels,
        "generator": GENERATOR_TAG,
    }
    return "---\n" + yaml.safe_dump(fm, allow_unicode=True, sort_keys=False, width=4096) + "---\n\n"


# ---------- main aggregation ----------

def aggregate_niche(niche: dict, min_videos: int, dry_run: bool, api_key: str) -> str:
    """
    Возвращает короткий статус: 'ok', 'skip_no_videos', 'skip_below_threshold', 'error'.
    """
    code = niche["code"]
    name = niche.get("name_ru", "")
    log.info("→ ниша %s (%s)", code, name)

    old_path = NICHES_DIR / f"{code}_insight.md"
    old_text = ""
    if old_path.exists():
        raw = old_path.read_text(encoding="utf-8")
        # Если старый файл уже агрегированный — снимаем frontmatter, передаём только тело.
        _, old_body = split_frontmatter(raw)
        old_text = old_body.strip() or raw.strip()

    video_insights_paths = find_videos_for_niche(code)
    log.info("  старый insight: %s | новых видео: %d",
             "есть" if old_text else "нет", len(video_insights_paths))

    if len(video_insights_paths) == 0:
        log.info("  нет новых видео — пропуск")
        return "skip_no_videos"

    if len(video_insights_paths) < min_videos:
        log.info("  ниже порога MIN_VIDEOS=%d — пропуск", min_videos)
        return "skip_below_threshold"

    video_bodies = [(p, read_video_insight(p)) for p in video_insights_paths]
    prompt = build_prompt(code, name, old_text, video_bodies)
    log.info("  prompt: %d символов", len(prompt))

    if dry_run:
        log.info("  [dry-run] ничего не пишем")
        return "ok"

    try:
        new_body = call_gemini(prompt, api_key)
    except Exception as e:
        log.error("  ✗ Gemini: %s", e)
        return "error"

    if not new_body.strip():
        log.error("  ✗ Gemini вернул пустой ответ")
        return "error"

    # Бэкап старой версии (только если она была).
    sources_for_fm: list[Path] = []
    if old_path.exists():
        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = ARCHIVE_DIR / f"{code}_insight.{ts}.md"
        backup.write_text(old_path.read_text(encoding="utf-8"), encoding="utf-8")
        sources_for_fm.append(backup)
        log.info("  backup: %s", backup.relative_to(REPO_ROOT))

    sources_for_fm.extend(video_insights_paths)

    final_text = make_frontmatter(code, sources_for_fm) + new_body.strip() + "\n"
    old_path.write_text(final_text, encoding="utf-8")
    log.info("  ✓ записан %s (%d строк)",
             old_path.relative_to(REPO_ROOT), final_text.count("\n"))
    return "ok"


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--niche", help="код ниши, например COFFEE")
    g.add_argument("--all", action="store_true", help="все ниши с >= MIN_VIDEOS видео")
    p.add_argument("--min-videos", type=int, default=DEFAULT_MIN_VIDEOS,
                   help=f"минимум новых видео для агрегации (default {DEFAULT_MIN_VIDEOS})")
    p.add_argument("--dry-run", action="store_true",
                   help="не вызывать Gemini, не писать файлы")
    args = p.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"aggregate_{today}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding="utf-8")],
    )

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        log.error("GEMINI_API_KEY не задан (.env или окружение)")
        sys.exit(2)

    niches = load_niches()
    by_code = {n["code"]: n for n in niches}

    if args.niche:
        if args.niche not in by_code:
            log.error("ниша %s не найдена в registry", args.niche)
            sys.exit(2)
        targets = [by_code[args.niche]]
    else:
        targets = niches

    counts = {"ok": 0, "skip_no_videos": 0, "skip_below_threshold": 0, "error": 0}
    for niche in targets:
        status = aggregate_niche(niche, args.min_videos, args.dry_run, api_key)
        counts[status] = counts.get(status, 0) + 1

    log.info(
        "Готово. ok=%d skip_no_videos=%d skip_below_threshold=%d error=%d",
        counts["ok"], counts["skip_no_videos"],
        counts["skip_below_threshold"], counts["error"],
    )
    if counts["error"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
