"""
read_gdoc_links.py
==================
Читает Google Doc ZEREK_links через Service Account, извлекает YouTube-ссылки,
добавляет новые в knowledge/youtube_kb/_pipeline.yaml.

Дубликаты (URL уже в pending/in_progress/done) пропускаются автоматически.
Скрипт идемпотентный — можно запускать сколько угодно раз без побочных эффектов.

Запуск:
    python scripts/read_gdoc_links.py

Требует:
    - secrets/google_service_account.json (ключ робота)
    - .env с GDOC_ID=<id документа>
    - Google Doc должен быть расшарен на email робота с правами Viewer
"""

import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    print("Установи Google API: pip install google-api-python-client google-auth")
    sys.exit(1)

# === КОНФИГ ===
REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(REPO_ROOT / ".env")

SERVICE_ACCOUNT_FILE = REPO_ROOT / "secrets" / "google_service_account.json"
PIPELINE_FILE = REPO_ROOT / "knowledge" / "youtube_kb" / "_pipeline.yaml"
GDOC_ID = os.environ.get("GDOC_ID", "").strip()

SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]

# Регулярка для YouTube-ссылок (ловит youtu.be/ID и youtube.com/watch?v=ID)
YOUTUBE_REGEX = re.compile(
    r"https?://(?:www\.)?(?:youtu\.be/|youtube\.com/(?:watch\?v=|shorts/|embed/))"
    r"([A-Za-z0-9_-]{11})",
    re.IGNORECASE,
)


def fail(msg: str, code: int = 1):
    print(f"✗ {msg}")
    sys.exit(code)


def extract_doc_text(doc: dict) -> str:
    """Вытягивает весь plain-text из Google Doc структуры."""
    parts = []
    for element in doc.get("body", {}).get("content", []):
        para = element.get("paragraph")
        if not para:
            continue
        for run in para.get("elements", []):
            text_run = run.get("textRun")
            if text_run:
                parts.append(text_run.get("content", ""))
    return "".join(parts)


def find_youtube_urls(text: str) -> list[str]:
    """Возвращает уникальные канонические YouTube-URL'ы из текста."""
    seen = set()
    urls = []
    for match in YOUTUBE_REGEX.finditer(text):
        video_id = match.group(1)
        canonical = f"https://youtu.be/{video_id}"
        if canonical not in seen:
            seen.add(canonical)
            urls.append(canonical)
    return urls


def load_pipeline() -> dict:
    if not PIPELINE_FILE.exists():
        return {"pending": [], "in_progress": [], "done": [], "failed": []}
    data = yaml.safe_load(PIPELINE_FILE.read_text(encoding="utf-8")) or {}
    for key in ("pending", "in_progress", "done", "failed"):
        data.setdefault(key, [])
        if data[key] is None:
            data[key] = []
    return data


def save_pipeline(data: dict):
    PIPELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    PIPELINE_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def known_urls(pipeline: dict) -> set[str]:
    """URL'ы которые уже где-то были — чтобы не дублировать."""
    s = set()
    for bucket in ("pending", "in_progress", "done", "failed"):
        for entry in pipeline[bucket]:
            if isinstance(entry, dict) and "url" in entry:
                # Нормализуем youtu.be и youtube.com к одному виду
                url = entry["url"]
                m = YOUTUBE_REGEX.search(url)
                if m:
                    s.add(f"https://youtu.be/{m.group(1)}")
                else:
                    s.add(url)
    return s


def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Чтение Google Doc...")

    # Проверки
    if not GDOC_ID:
        fail("GDOC_ID не задан в .env. Добавь строку: GDOC_ID=...")
    if not SERVICE_ACCOUNT_FILE.exists():
        fail(f"Не найден ключ {SERVICE_ACCOUNT_FILE}")

    # Авторизация через service account
    try:
        credentials = service_account.Credentials.from_service_account_file(
            str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
        )
        service = build("docs", "v1", credentials=credentials, cache_discovery=False)
    except Exception as e:
        fail(f"Ошибка авторизации: {e}")

    # Чтение документа
    try:
        doc = service.documents().get(documentId=GDOC_ID).execute()
    except HttpError as e:
        if e.resp.status == 403:
            fail(
                f"Доступ запрещён (403). Проверь что документ расшарен на робота:\n"
                f"  email робота: {credentials.service_account_email}\n"
                f"  права: Viewer\n"
                f"  ID документа: {GDOC_ID}"
            )
        elif e.resp.status == 404:
            fail(f"Документ не найден (404). Проверь GDOC_ID в .env: {GDOC_ID}")
        else:
            fail(f"Google API error: {e}")
    except Exception as e:
        fail(f"Ошибка чтения документа: {e}")

    title = doc.get("title", "<без заголовка>")
    text = extract_doc_text(doc)
    print(f"  ✓ документ '{title}' прочитан, {len(text)} символов")

    # Поиск YouTube-ссылок
    urls_in_doc = find_youtube_urls(text)
    print(f"  ✓ найдено YouTube-ссылок: {len(urls_in_doc)}")

    if not urls_in_doc:
        print("[i] В документе нет YouTube-ссылок. Нечего добавлять.")
        return

    # Загружаем pipeline и фильтруем дубликаты
    pipeline = load_pipeline()
    already = known_urls(pipeline)

    new_urls = [u for u in urls_in_doc if u not in already]
    skipped = len(urls_in_doc) - len(new_urls)

    print(f"  ↳ новых: {len(new_urls)}")
    print(f"  ↳ уже было: {skipped}")

    if not new_urls:
        print("[✓] Все ссылки из документа уже в очереди или обработаны.")
        return

    # Добавляем
    now = datetime.now(timezone.utc).isoformat()
    for url in new_urls:
        pipeline["pending"].append({
            "url": url,
            "added_at": now,
            "source": "gdoc",
        })

    save_pipeline(pipeline)

    print(f"\n[✓] Добавлено {len(new_urls)} новых URL в очередь:")
    for u in new_urls:
        print(f"    + {u}")
    print(f"\nВсего в pending: {len(pipeline['pending'])}")


if __name__ == "__main__":
    main()

