# ZEREK YouTube → Knowledge Base v3.1 — Pipeline 3 источников

## Что делает пайплайн

Каждое видео в `knowledge/youtube_kb/_pipeline.yaml` превращается в **папку с тремя артефактами**:

```
knowledge/youtube_kb/<topic>/<entry_id>/
├── insight.md              ← структурированный insight (8 разделов из субтитров через Gemini Flash)
├── briefing.md             ← Briefing Doc от NotebookLM (как раньше)
├── audio_transcript.md     ← транскрипт audio overview через локальный Whisper.cpp
└── meta.yaml               ← общая мета (URL, заголовок, статусы артефактов)
```

Три источника дают разную глубину контекста:
| Файл | Глубина | Сила |
|---|---|---|
| `insight.md` | средняя | структура, КЗ-локализация, готов идти в RAG для ниш |
| `briefing.md` | высокая | связное изложение, цифры, цитаты — лучший конспект |
| `audio_transcript.md` | максимальная | дословный текст подкаста, ссылки на цитаты |

## Установка (один раз)

```bash
cd /Users/adil/Documents/ZEREK/

# Базовые зависимости
pip install "notebooklm-py[browser]" pyyaml python-frontmatter python-dotenv \
            requests yt-dlp google-api-python-client google-auth
playwright install chromium
notebooklm login   # авторизация в браузере

# Whisper.cpp (локально, бесплатно, Metal на M1/M2)
brew install whisper-cpp
mkdir -p ~/.whisper-models
curl -L -o ~/.whisper-models/ggml-small.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
# Опционально base (быстрее, менее точно):
curl -L -o ~/.whisper-models/ggml-base.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin

# .env с ключами
cp scripts/.env.example .env
# Открой .env, впиши:
#   GEMINI_API_KEY=...      (https://aistudio.google.com/apikey)
#   GDOC_ID=...             (для read_gdoc_links.py)
#   WHISPER_MODEL=small     (опционально, дефолт small)
#   WHISPER_LANG=ru         (опционально)
```

## Workflow

### Когда нашёл интересное видео

Открой `knowledge/youtube_kb/_pipeline.yaml`, добавь в `pending`:

```yaml
pending:
  - url: https://youtube.com/watch?v=XXX
    note: "Что это для тебя"
```

Или вставь YouTube-ссылку в Google Doc — `read_gdoc_links.py` подхватит на следующий день.

### Когда хочешь обработать накопленное

```bash
cd /Users/adil/Documents/ZEREK/
python3 scripts/batch_extract_v3.py
```

Скрипт берёт до 30 видео за запуск. Время на видео (M1/M2):
* `briefing.md` — 5–7 мин (NotebookLM генерирует)
* `insight.md` — ~30 сек (yt-dlp субтитры + Gemini Flash)
* `audio_transcript.md` — ~12 мин на 12-минутное аудио (Whisper.cpp small + Metal)

≈ 18–20 мин на полный набор. 30 видео = ~10 часов. Запускай на ночь.

Флаги для ускорения:
```bash
python3 scripts/batch_extract_v3.py --skip-audio    # без Whisper (5–8 мин/видео)
python3 scripts/batch_extract_v3.py --skip-insight  # без субтитров
python3 scripts/batch_extract_v3.py --max-per-day 5 # лимит
python3 scripts/batch_extract_v3.py --dry-run       # без обработки
```

### Куда что попадёт

NotebookLM Briefing классифицируется через Gemini Flash на 9 категорий:
- `taxes/` — налоги, СНР, декларации
- `finance/` — юнит-экономика, кредиты
- `marketing/` — реклама, SMM, продажи
- `management/` — найм, структура, мотивация
- `support_programs/` — Даму, гранты
- `case_studies/` — конкретные истории бизнесов
- `niche_reviews/` — обзоры ниш
- `general/` — общие принципы
- `cinema/` — обзоры фильмов и культурные материалы
- `_inbox/` — Gemini не уверен в теме (твоя ручная сортировка раз в неделю)

## Backfill — добавить артефакты к уже-обработанным видео

После апгрейда v3.0 → v3.1 у уже-обработанных done-видео есть только `briefing.md`.
Чтобы догенерить `insight.md` и `audio_transcript.md`:

```bash
# insight.md — быстро (~30 сек/видео), не требует NotebookLM
python3 scripts/backfill_insights.py

# audio_transcript.md — медленно (12 мин/видео), требует NotebookLM browser session
python3 scripts/backfill_audio.py --whisper-model small

# С лимитом / для одной ниши / одного видео:
python3 scripts/backfill_insights.py --limit 5
python3 scripts/backfill_insights.py --topic marketing
python3 scripts/backfill_insights.py --entry yt_b6bc3e98e913
```

Идемпотентно: если артефакт уже есть — пропускается.

## Migration v3.0 → v3.1 (разовая)

Если в репо ещё лежат плоские файлы `<topic>/yt_<id>.md` (старая структура v3.0):

```bash
python3 scripts/migrate_to_3sources.py --dry-run    # посмотреть
python3 scripts/migrate_to_3sources.py              # с подтверждением
python3 scripts/migrate_to_3sources.py --yes        # без вопросов
```

Скрипт:
1. Создаёт `<topic>/<entry_id>/` для каждой done-записи
2. Перемещает `<topic>/yt_<id>.md` → `<topic>/<entry_id>/briefing.md`
3. Создаёт `<topic>/<entry_id>/meta.yaml`
4. Обновляет `_pipeline.yaml`: добавляет `artifacts.briefing.*`, убирает `md_path`

## Mirror to Obsidian Vault

```bash
python3 scripts/mirror_to_vault.py            # обычный прогон
python3 scripts/mirror_to_vault.py --dry-run  # без копирования
python3 scripts/mirror_to_vault.py --cleanup  # архивирует в _archive/ то, чего нет в репо
```

State-файл: `~/.zerek_mirror_state.json` (вне репо). Хранит SHA256 каждого
файла и читаемое имя папки в Vault — повторный прогон пропускает неизменённое.

Структура в Vault:
```
~/Desktop/ZEREK/
├── KNOWLEDGE/YouTube/<topic>/<readable-title>/
│   ├── insight.md
│   ├── briefing.md
│   └── audio_transcript.md
└── 01_NICHES/<NICHE>/insight.md   ← из knowledge/kz/niches/<NICHE>_insight.md
```

### Разовая чистка Vault при первом запуске v3.1

Если в Vault уже лежат **плоские** файлы (после `rename_vault_yt.py` Адиля),
их нужно либо:

**Вариант А (мягкий) — оставить, новые папки появятся рядом:**
Просто запусти `mirror_to_vault.py`. Старые `<title>.md` останутся, новые
создадутся как `<title>/{insight,briefing,audio_transcript}.md`. После
проверки удалишь старые вручную.

**Вариант Б (жёсткий) — удалить старые перед прогоном:**
```bash
# В Vault, после backup:
find /Users/adil/Desktop/ZEREK/KNOWLEDGE/YouTube -maxdepth 3 -type f -name "*.md" \
    -not -name "insight.md" -not -name "briefing.md" -not -name "audio_transcript.md" \
    -delete
python3 scripts/mirror_to_vault.py
```

Дальше работает идемпотентно.

## Что нового по сравнению с v3.0

| | v3.0 (briefing only) | v3.1 (3 источника) |
|---|---|---|
| Файл на видео | один `yt_<id>.md` (briefing) | папка `<entry_id>/` с 3 файлами + meta.yaml |
| Источник briefing | NotebookLM | NotebookLM (без изменений) |
| Источник insight | — | yt-dlp субтитры + Gemini 2.5 Flash |
| Источник audio | — | NotebookLM audio overview + Whisper.cpp локально |
| Стоимость | $0 (Gemini free tier) | $0 (Whisper тоже бесплатно, локально) |
| Время на видео | 5–7 мин | 18–20 мин (или 5–8 мин с `--skip-audio`) |

## Архитектурные решения (зафиксированы 2026-05-03)

1. **Whisper локально, не через OpenAI API.** $0 vs ~$72/1000 видео. Медленнее, но Адиль выбрал бесплатный путь.
2. **Gemini 2.5 Flash для insight, не Pro.** Free tier 1500/день, качество для нашего промпта достаточно.
3. **Структура `<entry_id>/<3 файла>` + meta.yaml.** Папка вместо плоского файла — растёт без изменений схемы.
4. **Сразу на всём** (миграция всех done без тестового набора). Адиль уверен в подходе.

## Лимиты и скорость

| Этап | Лимит | На что обращать внимание |
|---|---|---|
| `read_gdoc_links.py` | Google Docs API лимит 300 RPM, не нагружаем | Дубликаты автоматически пропускаются |
| NotebookLM briefing | ~5 видео/час на одного юзера | Браузер не должен заснуть |
| NotebookLM audio | те же лимиты + квоты на audio overview | Может быть отключено для некоторых аккаунтов |
| Gemini Flash classifier | 1500/день (free tier) | На 30 видео/день — с большим запасом |
| Gemini Flash insight | те же 1500/день | Хватит на ~1500 видео/день |
| yt-dlp субтитры | ~5 секунд на видео | Авто-CC доступны не всегда (короткие видео, маленькие каналы) |
| Whisper.cpp small | ~1× реалтайм | 12 мин аудио → 12 мин обработки. На M1 с Metal |

## Структура `_pipeline.yaml`

```yaml
pending:
  - url: https://youtu.be/...
    added_at: '2026-05-03T...'
    source: gdoc

in_progress:
  - url: https://...
    started_at: '...'

done:
  - url: https://youtu.be/BB39qYx_Fho
    entry_id: yt_b6bc3e98e913
    notebook_id: f3a65d9b-9e2a-4de5-ab2f-714bdb4799c2
    completed_at: '2026-05-01T23:28:45+00:00'
    primary_topic: marketing
    target_folder: marketing
    classification_confidence: high
    artifacts:
      briefing:
        path: knowledge/youtube_kb/marketing/yt_b6bc3e98e913/briefing.md
        generated_at: '2026-05-01T23:28:45+00:00'
        method: notebooklm
      insight:
        path: knowledge/youtube_kb/marketing/yt_b6bc3e98e913/insight.md
        generated_at: '2026-05-03T20:00:00+00:00'
        method: subtitles+gemini
        subtitle_lang: ru
      audio_transcript:
        path: knowledge/youtube_kb/marketing/yt_b6bc3e98e913/audio_transcript.md
        generated_at: '2026-05-03T22:00:00+00:00'
        method: notebooklm_audio+whisper
        whisper_model: small

failed:
  - url: https://...
    entry_id: yt_...
    failed_at: '...'
    reason: 'briefing: timeout'
```
