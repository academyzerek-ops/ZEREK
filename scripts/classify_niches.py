"""
classify_niches.py
==================
Определяет код ниши (`niche_code`) для каждого video-insight в
`knowledge/youtube_kb/<topic>/yt_*/` и записывает его в `meta.yaml`.

Идемпотентно: пропускает видео, у которых `niche_code` уже задан
(если только не передан --force).

Источники:
- `data/kz/niches_registry.yaml` — список валидных кодов ниш
- `meta.yaml.video_title` — что отдаём Gemini Flash
- `scripts/niche_classifier_prompt.md` — промпт

Запуск:
    python3 scripts/classify_niches.py            # классифицировать только новые
    python3 scripts/classify_niches.py --force    # перепроверить все, перезаписать
    python3 scripts/classify_niches.py --dry-run  # ничего не писать, только показать

Логи: knowledge/logs/classify_niches_<date>.log
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KB_DIR = REPO_ROOT / "knowledge" / "youtube_kb"
REGISTRY_PATH = REPO_ROOT / "data" / "kz" / "niches_registry.yaml"
PROMPT_FILE = REPO_ROOT / "scripts" / "niche_classifier_prompt.md"
LOG_DIR = REPO_ROOT / "knowledge" / "logs"

GEMINI_MODEL = "gemini-2.5-flash"
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/"
    f"models/{GEMINI_MODEL}:generateContent"
)

log = logging.getLogger("zerek.classify_niches")


def load_dotenv():
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


def build_niches_list_for_prompt(niches: list[dict]) -> str:
    return "\n".join(f"- {n['code']} — {n.get('name_ru', '')}" for n in niches)


def call_gemini(prompt: str, api_key: str, timeout: int = 60) -> str:
    # thinkingBudget=0 отключает «размышление» 2.5 Flash — иначе модель тратит
    # output-токены на цепочку рассуждений и возвращает ответ без `parts`,
    # когда лимит достигнут (наблюдалось при первом прогоне).
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.0,
            "maxOutputTokens": 256,
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
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError) as e:
        finish = (data.get("candidates") or [{}])[0].get("finishReason")
        raise RuntimeError(f"Gemini ответ без parts (finishReason={finish}): {str(data)[:300]}") from e


def classify_one(title: str, prompt_template: str, niches_block: str,
                 valid_codes: set[str], api_key: str) -> str | None:
    prompt = (
        prompt_template
        .replace("{niches_list}", niches_block)
        .replace("{video_title}", title or "(без заголовка)")
    )
    raw = call_gemini(prompt, api_key)
    # Gemini может обернуть в кавычки или добавить пунктуацию — чистим.
    token = raw.strip().strip('"').strip("'").strip(".").strip()
    if token == "null" or not token:
        return None
    if token not in valid_codes:
        log.warning("  Gemini вернул неизвестный код '%s' — трактую как null", token)
        return None
    return token


def iter_meta_files() -> list[Path]:
    return sorted(KB_DIR.glob("*/yt_*/meta.yaml"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--force", action="store_true",
                   help="перезаписать niche_code, даже если он уже есть")
    p.add_argument("--dry-run", action="store_true",
                   help="не писать meta.yaml, только показать, что бы записал")
    p.add_argument("--limit", type=int, default=0,
                   help="ограничить число видео (0 = без лимита)")
    args = p.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = LOG_DIR / f"classify_niches_{today}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(log_file, encoding="utf-8")],
    )

    load_dotenv()
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        log.error("GEMINI_API_KEY не задан (.env или окружение)")
        sys.exit(2)

    niches = load_niches()
    valid_codes = {n["code"] for n in niches}
    niches_block = build_niches_list_for_prompt(niches)
    prompt_template = PROMPT_FILE.read_text(encoding="utf-8")

    metas = iter_meta_files()
    if args.limit:
        metas = metas[: args.limit]
    log.info("Найдено meta.yaml: %d (registry: %d ниш)", len(metas), len(valid_codes))

    stats = {"skipped_has_code": 0, "classified": 0, "null": 0, "no_insight": 0, "errors": 0}

    for meta_path in metas:
        entry_dir = meta_path.parent
        entry_id = entry_dir.name

        # Видео без insight.md классифицировать смысла нет.
        if not (entry_dir / "insight.md").exists():
            stats["no_insight"] += 1
            continue

        try:
            meta = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as e:
            log.error("  ✗ %s: невалидный YAML: %s", meta_path, e)
            stats["errors"] += 1
            continue

        if not args.force and "niche_code" in meta:
            stats["skipped_has_code"] += 1
            continue

        title = meta.get("video_title", "")
        try:
            code = classify_one(title, prompt_template, niches_block, valid_codes, api_key)
        except Exception as e:
            log.error("  ✗ %s (%s): %s", entry_id, title[:60], e)
            stats["errors"] += 1
            continue

        if code:
            stats["classified"] += 1
        else:
            stats["null"] += 1

        log.info("  %s [%s] → %s", entry_id, title[:60], code or "null")

        if args.dry_run:
            continue

        meta["niche_code"] = code  # null допустим — означает «не нишевое»
        # Сохраняем читаемый YAML с UTF-8 без излишнего флоу-стиля.
        meta_path.write_text(
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False, width=4096),
            encoding="utf-8",
        )

    log.info(
        "Готово. classified=%d null=%d skipped_has_code=%d no_insight=%d errors=%d",
        stats["classified"], stats["null"], stats["skipped_has_code"],
        stats["no_insight"], stats["errors"],
    )


if __name__ == "__main__":
    main()
