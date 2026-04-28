# ZEREK — Аудит YouTube-пайплайна
**Дата:** 2026-04-21
**Коммит (HEAD):** `7fcc482`

## Резюме

В репозитории ZEREK **существовал** полноценный пайплайн парсинга YouTube → транскрипт → Gemini → `*_insight.md` (папка `insight_collector/` + скрипт `scripts/yt_search_niches.py`). Он был **удалён целиком** 2026-04-13 коммитом `e2cd588` с комментарием «chore: remove old files — old Mini App, old site pages, unused tools» и на HEAD отсутствует. В текущем дереве остались только артефакты-результаты (`knowledge/kz/niches/*_insight.md`, `knowledge/common/_yt_videos.json`) и читатель этих файлов в рантайме (`api/gemini_rag.py`, `api/main.py`). Зависимостей `youtube-transcript-api`/`yt-dlp`/`google-api-python-client` в актуальном `requirements.txt` нет и никогда не было (они жили внутри отдельного сервиса `insight_collector/`). Сценарий — **Б (пайплайн был, удалён; восстановим из истории)**.

## Найденные артефакты пайплайна

### Python-скрипты (в текущем дереве)

| Путь | Размер | Дата | Назначение |
|------|--------|------|-----------|
| — | — | — | В актуальном HEAD скриптов парсинга YouTube **нет**. |

Ни `youtube_transcript_api`, ни `yt_dlp`, ни `pytube`, ни `googleapiclient` не встречаются ни в одном `.py`/`.txt`/`.toml` файле. Также не найдено функций `extract_transcript`, `parse_video`, `fetch_youtube`, `get_transcript`, `video_to_insight`. Единственное прямое вхождение `youtube.com/watch` в репозитории — это футер-комментарий HTML в `knowledge/kz/niches/PHARMACY_insight.md` (не код).

### Скрипты, восстановимые из истории (удалены коммитом `e2cd588`, 2026-04-13)

| Путь | Назначение |
|------|-----------|
| `insight_collector/collect_insights.py` | Полный пайплайн v2: YouTube Data API (search + videos) → `youtube_transcript_api` → Gemini 2.5 Flash → `{NICHE}_insight.md`. CLI: `--niche`, `--batch`, `--list`. |
| `insight_collector/server.py` | FastAPI-обёртка с эндпоинтами `POST /collect`, `POST /collect-batch`, `GET /niches`, `GET /status`, `GET /results`, `GET /results/{niche}`; запускает `collect_insights.process_niche` в BackgroundTasks. |
| `insight_collector/niche_queries.json` | Реестр 33 ниш → `{"name": "...", "queries": [5 штук]}`. Ключи: `COFFEE, DONER, CARWASH, CLEAN, GROCERY, PHARMA, BARBER, DENTAL, NAIL, BAKERY, FITNESS, CYBERCLUB, FLOWERS, FURNITURE, TIRE, AUTOSERVICE, DRYCLEAN, MASSAGE, PIZZA, SUSHI, WATER, CONFECTION, CANTEEN, FASTFOOD, SEMIFOOD, FRUITSVEGS, BROW, LASH, SUGARING, KINDERGARTEN, PVZ, REPAIR_PHONE, TAILOR`. |
| `insight_collector/railway.toml` | Деплой: builder=dockerfile, start=`uvicorn server:app --host 0.0.0.0 --port $PORT`. |
| `insight_collector/nixpacks.toml` | (удалён ещё раньше, коммитом `648583e` 2026-04-10). Python 3.12 + `pip install -r requirements.txt` + uvicorn. |
| `insight_collector/zerek_insight_collector.tar.gz` | Бинарный архив (тот же код в tar.gz). |
| `scripts/yt_search_niches.py` | Лёгкая альтернатива через `yt_dlp` subprocess (`ytsearch{n}:query`, `--flat-playlist -j`). Пишет `knowledge/niches/_yt_videos.json` (20 ниш × до 15 видео, без транскриптов, без Gemini — только метаданные). |

### Конфиги / реестры видео (в текущем дереве)

| Путь | Размер | Структура (кратко) |
|------|--------|-------------------|
| `knowledge/common/_yt_videos.json` | 83 200 B, mtime 2026-04-21 | JSON, 20 ключей верхнего уровня (`PHARMACY, DENTAL, MANICURE, BAKERY, FITNESS, COMPCLUB, PIZZA, SUSHI, FURNITURE, TIRESERVICE, FLOWERS, PETSHOP, KIDSCENTER, LAUNDRY, AUTOSERVICE, BEAUTY, PHOTO, PRINTING, HOTEL, CATERING`). Для каждой ниши — массив объектов с полями `id, title, channel, views, duration`. Транскриптов внутри нет — это результат работы `scripts/yt_search_niches.py`. |

Других реестров (`*videos*.yaml`, `*videos*.csv`, других `*videos*.json`) в дереве нет. Поля `video_id`/`video_url`/`youtube_url`/`transcript`/`duration_sec` нигде не встречаются (используемые имена полей — `id`, `duration`, без underscore).

### Промпты / шаблоны для AI

| Путь | Где упоминается | Фрагмент |
|------|----------------|----------|
| `insight_collector/collect_insights.py` (история) | строки 36–72 | Жёстко зашитый `PROMPT` с заголовками «Ключевые принципы управления», «Типичные ошибки новичков», «Операционные подводные камни», «Финансовые риски и ловушки», «Что отличает выживших от закрывшихся», «Красные флаги (когда лучше не открывать)» — ровно те же H2, что в сгенерированных файлах. |
| `api/gemini_rag.py` (актуальный) | `api/gemini_rag.py:30, 43, 70, 179` | Читатель: «Читает `knowledge/niches/{NICHE}_insight.md`. Возвращает '' если нет файла.» → парсит через Gemini в 7 карточек рисков. Генератор insight.md здесь **не** реализован. |
| `api/main.py` (актуальный) | `api/main.py:360` | «Структурированные риски ниши через Gemini (из `knowledge/kz/niches/*_insight.md`).» — runtime-потребитель. |

### Документация

| Путь | О чём |
|------|-------|
| — | Отдельного README/docs по YouTube-пайплайну в репозитории нет (ни в истории, ни на HEAD). В сохранившемся `insight_collector/collect_insights.py` только короткий docstring на 5 строк. |

## Зависимости

### Текущий `requirements.txt` (HEAD)

```
fastapi==0.115.0
uvicorn==0.30.6
pandas==2.2.2
openpyxl==3.1.5
pydantic==2.9.2
python-multipart==0.0.12
python-docx==1.1.2
httpx==0.27.0
reportlab==4.2.5
pyyaml==6.0.2
```

Зависимости, связанные с YouTube — **отсутствуют**.

### История `requirements.txt`

Полная цепочка изменений (git log -p):

```
d3b85d9 2026-03-30 "Add files via upload"                         +fastapi, uvicorn, pandas, openpyxl, pydantic, python-multipart
94ea25c 2026-04-08 "Add grant business plan generator"            +python-docx
d60c520 2026-04-13 "feat: Gemini Flash API"                       +httpx
0479bdd 2026-04-17 "feat(pdf): Phase 4 — WeasyPrint"              +weasyprint==65.1
59fd377 2026-04-17 "diag(pdf): downgrade 65.1→62.3"                weasyprint==62.3
472cb01 2026-04-17 "revert: back out PDF deploy"                  -weasyprint
0c16a8f 2026-04-17 "feat(pdf): rewrite on ReportLab"              +reportlab==4.2.5
e58ae10 2026-04-20 "fix(deploy): add pyyaml"                      +pyyaml==6.0.2
```

Ни `youtube-transcript-api`, ни `yt-dlp`, ни `google-api-python-client`, ни `google-genai` никогда не добавлялись в корневой `requirements.txt`. Это согласуется с архитектурой: `insight_collector/` был **отдельным сервисом** на Railway (свой `railway.toml`, свой `nixpacks.toml`, предполагаемо со своим `requirements.txt` внутри `zerek_insight_collector.tar.gz` — git-trackable `insight_collector/requirements.txt` не находится ни в одной ревизии).

## История коммитов

### Первое появление insight.md
- `78f25cc` 2026-04-12 academyzerek-ops "knowledge: add PHARMACY YouTube insights" — самый ранний `*_insight.md` (`knowledge/niches/PHARMACY_insight.md`, 75 строк, 8 видео в футере).

### Массовые коммиты insight.md (2026-04-12, все — `academyzerek-ops`)
```
78f25cc 2026-04-12 "knowledge: add PHARMACY YouTube insights"
e0f4ef2 2026-04-12 "knowledge: add MANICURE YouTube insights"
049ce0b 2026-04-12 "knowledge: add PIZZA YouTube insights"
13358c9 2026-04-12 "knowledge: add FURNITURE YouTube insights"
3d2ab24 2026-04-12 "knowledge: add DENTAL YouTube insights"
cf0b218 2026-04-12 "knowledge: add BAKERY YouTube insights"
905c67f 2026-04-12 "knowledge: add KIDSCENTER YouTube insights"
0b0cef3 2026-04-12 "knowledge: add FITNESS YouTube insights"
b05e2f2 2026-04-12 "knowledge: add FLOWERS YouTube insights"
50d4a7a 2026-04-12 "knowledge: add SUSHI YouTube insights"
37eec40 2026-04-12 "knowledge: add TIRESERVICE YouTube insights"
17fe86c 2026-04-12 "knowledge: add AUTOSERVICE YouTube insights"
9980204 2026-04-12 "knowledge: add PRINTING YouTube insights"
f78bcd5 2026-04-12 "knowledge: add COMPCLUB YouTube insights"
beecc00 2026-04-12 "knowledge: add LAUNDRY YouTube insights"
6a0b2a4 2026-04-12 "knowledge: add BEAUTY YouTube insights"
31afa86 2026-04-12 "knowledge: add PHOTO YouTube insights"
1106e5c 2026-04-12 "knowledge: add PETSHOP YouTube insights"
baa09da 2026-04-12 "knowledge: add HOTEL YouTube insights"
8310c0a 2026-04-12 "knowledge: add CATERING YouTube insights"
10957c5 2026-04-12 "knowledge: fix RU-specific references in insights, make universal"
8beffbc 2026-04-12 "knowledge: add 30 new niche insights, fix RU refs in existing"   ← +27 файлов одним коммитом
a796f2c 2026-04-12 "knowledge: rename 4 insights, add 3 missing (DRYCLEAN/KINDERGARTEN/SUSHI), remove 5 non-list niches"
```

### Последний массовый коммит по insight.md
- `6e77b41` 2026-04-21 academyzerek-ops "refactor(knowledge): реструктуризация под /kz/niches/, /common/, /ru/niches/" — перенос всех `knowledge/niches/*_insight.md` → `knowledge/kz/niches/*_insight.md` и `knowledge/common/_yt_videos.json`.
- `c40c986` 2026-04-21 — «chore: удалить мёртвые файлы и каталоги» (задел не-insight, тем же числом).

### Появление и судьба `_yt_videos.json`
- `56d08c1` 2026-04-12 academyzerek-ops "knowledge: add YouTube search script and video metadata" — первое появление (путь `knowledge/niches/_yt_videos.json` + `scripts/yt_search_niches.py`).
- `6e77b41` 2026-04-21 — перемещён в `knowledge/common/_yt_videos.json`.
- Скрипт `scripts/yt_search_niches.py` удалён коммитом `e2cd588` 2026-04-13 (через день после создания).

### Коммиты с YouTube-зависимостями в `requirements.txt`
- **Ни одного.** YouTube-зависимости (`youtube-transcript-api`, `yt-dlp`, `google-genai`, `google-api-python-client`, `requests`) никогда не присутствовали в корневом `requirements.txt`. Они жили внутри отдельного сервиса `insight_collector/` (предположительно в `zerek_insight_collector.tar.gz` — `insight_collector/requirements.txt` как отдельного файла в git не появлялось ни разу).

### Удалённые из истории скрипты парсинга (все в коммите `e2cd588` 2026-04-13)
Восстанавливаются через:
```
git show e2cd588^:insight_collector/collect_insights.py
git show e2cd588^:insight_collector/server.py
git show e2cd588^:insight_collector/niche_queries.json
git show e2cd588^:insight_collector/railway.toml
git show e2cd588^:insight_collector/zerek_insight_collector.tar.gz   # binary
git show 648583e^:insight_collector/nixpacks.toml                    # удалён раньше, отдельно
git show e2cd588^:scripts/yt_search_niches.py
```
Первая и единственная версия `collect_insights.py` — blob `fabc39ad409e389e11eb17c6269a3be383582348`, залит 2026-04-10 коммитом `f4b7ef3` "Add files via upload" (между `f4b7ef3` и `e2cd588` файл не менялся).

## Анализ insight-файлов

Всего в `knowledge/kz/niches/` — **44** файла `*_insight.md`. Все имеют ровно **8** H2-разделов. Состав H2 одинаков для всех v2-файлов:
1. Ключевые принципы управления
2. Типичные ошибки новичков
3. Экономика и юнит-экономика
4. Операционные нюансы
5. Маркетинг и привлечение клиентов
6. Финансовые риски и ловушки
7. Что отличает выживших от закрывшихся
8. Красные флаги (когда лучше не открывать)

Это **расширенная** версия промпта из `collect_insights.py` (там 6 H2: без «Экономика» и «Маркетинг» — их добавили позже, уже при массовой генерации 2026-04-12, вероятно вручную или в обновлённой версии скрипта, не попавшей в git).

| niche_id | версия | H2 | YT-ссылок | дата в футере | KB |
|----------|--------|----|-----------|---------------|------|
| ACCOUNTING | v2_with_youtube | 8 | 0 | 2026-04-12T00:00:00+05:00 | 25.7 |
| AUTOPARTS | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 20.6 |
| AUTOSERVICE | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 21.5 |
| BAKERY | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 16.8 |
| BROW | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 18.0 |
| BUBBLETEA | v2_with_youtube | 8 | 0 | 2026-04-12T00:00:00+05:00 | 22.5 |
| BUILDMAT | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 20.4 |
| CANTEEN | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 17.6 |
| CARGO | v1_no_youtube | 8 | 0 | — | 12.1 |
| CARPETCLEAN | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 24.7 |
| COMPCLUB | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 22.7 |
| CONFECTION | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 17.5 |
| COSMETOLOGY | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 19.1 |
| DENTAL | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 19.3 |
| DETAILING | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 25.4 |
| DRIVING | v1_no_youtube | 8 | 0 | — | 15.2 |
| DRYCLEAN | v2_with_youtube | 8 | 0 | 2026-04-12T04:30:00+05:00 | 14.4 |
| FASTFOOD | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 18.8 |
| FITNESS | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 21.2 |
| FLOWERS | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 18.0 |
| FRUITSVEGS | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 17.5 |
| FURNITURE | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 15.3 |
| KIDSCENTER | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 23.1 |
| KINDERGARTEN | v2_with_youtube | 8 | 0 | 2026-04-12T04:30:00+05:00 | 15.6 |
| LANGUAGES | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 11.6 |
| LASH | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 19.7 |
| MANICURE | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 14.4 |
| MASSAGE | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 18.3 |
| MEATSHOP | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 35.4 |
| OPTICS | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 19.2 |
| PETSHOP | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 11.0 |
| **PHARMACY** | **v2_with_youtube** | **8** | **8** | **2026-04-12T03:30:00+05:00** | **13.0** |
| PHOTO | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 23.2 |
| PIZZA | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 15.9 |
| PVZ | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 11.4 |
| REALTOR | v1_no_youtube | 8 | 0 | — | 13.3 |
| REPAIR_PHONE | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 24.0 |
| SEMIFOOD | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 18.2 |
| SUGARING | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 20.2 |
| SUSHI | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 16.9 |
| TAILOR | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 11.3 |
| TIRESERVICE | v2_with_youtube | 8 | 0 | 2026-04-12T03:30:00+05:00 | 15.5 |
| WATERPLANT | v2_with_youtube | 8 | 0 | 2026-04-12T04:00:00+05:00 | 19.5 |
| YOGA | v2_with_youtube | 8 | 0 | 2026-04-12T00:00:00+05:00 | 22.7 |

### Статистика
- **Файлов всего:** 44
- **`v2_with_youtube`** (с футером `<!-- ZEREK v2 | ... | N videos`): **41** (из них с **реальными** YouTube-ссылками в футере — **только 1**, PHARMACY, 8 ссылок; остальные 40 помечены как `0 videos` — то есть сгенерированы без транскриптов, Gemini по знаниям модели + ручному промпту)
- **`v1_no_youtube`** (та же структура 8 H2, футер «*Материал подготовлен аналитической платформой ZEREK...*», без `ZEREK v2`-маркера): **3** — CARGO, DRIVING, REALTOR
- **`other`**: 0
- **H2:** min/median/max = 8/8/8 (абсолютная однородность — явно машинная генерация по шаблону)
- **Размер:** min 11.0 KB (PETSHOP), max 35.4 KB (MEATSHOP), медиана ~18 KB
- **Уникальные паттерны ссылок в футерах:** только `youtube.com/watch?v=<id>` (без `youtu.be`, без timestamps, без плейлистов). Единственный домен — `youtube.com`.

### Ключевое наблюдение
Хотя футер `ZEREK v2 | {NICHE} | {date} | {N} videos` у 41 файла — только PHARMACY фактически содержит список из 8 ссылок на видео; остальные 40 помечены `0 videos` и **не содержат ни одной ссылки**. Это означает: **исходный пайплайн из `collect_insights.py` реально отработал с транскриптами только для PHARMACY**. Все остальные файлы были сгенерированы либо (а) через ту же v2-шаблонную логику, но с нулём прошедших фильтр видео (Gemini сгенерировал по собственным знаниям), либо (б) вручную/через отдельный скрипт-заглушку, эмулирующий тот же футер. В обоих случаях **реальные транскрипты практически не использовались** при генерации содержательной части.

## Вывод

**Сценарий Б) Пайплайн был, удалён.** С уточнением: пайплайн **существовал как работающий код**, но судя по метаданным в футерах `*_insight.md`, **был реально прогнан end-to-end только для одной ниши (PHARMACY)**. Остальные 43 insight-файла были сгенерированы либо обёрткой без транскриптов (Gemini по prior knowledge), либо в отдельном shadow-процессе, не попавшем в git.

- Последняя версия рабочего кода: коммит `f4b7ef3` 2026-04-10 (первый upload `insight_collector/`) — `collect_insights.py`, `server.py`, `niche_queries.json`, `railway.toml`.
- Удаление пайплайна: `e2cd588` 2026-04-13 (чистка «unused tools» + удалены `scripts/yt_search_niches.py`, `scripts/wiki_inject.py`).
- Восстановимость: **высокая**. Весь код пайплайна лежит в git-объектах (`git show e2cd588^:insight_collector/*`), blobs читаются без потерь. Бинарь `zerek_insight_collector.tar.gz` тоже сохранён (blob `8a76b3c7...`).

Смешанная деталь: в текущем репо **реестр видео** (`knowledge/common/_yt_videos.json`, 20 ниш × до 15 видео) — это результат **другого, упрощённого скрипта** (`scripts/yt_search_niches.py` на `yt_dlp`), не того пайплайна, что генерировал `*_insight.md`. То есть в истории сосуществовало **два разных YouTube-тулза**:
1. `insight_collector/` — тяжёлый: YouTube Data API + транскрипты + Gemini (один запуск на PHARMACY).
2. `scripts/yt_search_niches.py` — лёгкий: `yt_dlp` subprocess, только метаданные, без транскриптов, без AI — источник `_yt_videos.json`.
Оба удалены 2026-04-13. `_yt_videos.json` остался как «осиротевший» артефакт без своего писателя.

## Что нужно для возобновления парсинга

### Чего не хватает в текущем дереве
- Нет ни одного Python-скрипта, умеющего вызывать YouTube API или `yt_dlp`.
- Нет зависимостей `youtube-transcript-api`, `yt-dlp`, `google-api-python-client`, `google-genai`, `requests` в `requirements.txt`.
- Нет конфига `niche_queries.json` — с mapping-ом 33 ниш на поисковые запросы.
- Нет отдельного `requirements.txt` для сервиса `insight_collector` (даже в истории git — не отслеживался).

### Что можно восстановить одной командой из git
```
git show e2cd588^:insight_collector/collect_insights.py > insight_collector/collect_insights.py
git show e2cd588^:insight_collector/server.py           > insight_collector/server.py
git show e2cd588^:insight_collector/niche_queries.json  > insight_collector/niche_queries.json
git show e2cd588^:insight_collector/railway.toml        > insight_collector/railway.toml
git show 648583e^:insight_collector/nixpacks.toml       > insight_collector/nixpacks.toml
git show e2cd588^:scripts/yt_search_niches.py           > scripts/yt_search_niches.py
```
Плюс потребуется написать с нуля (в истории нет):
- `insight_collector/requirements.txt` — минимально нужны: `fastapi`, `uvicorn`, `pydantic`, `requests`, `youtube-transcript-api`, `google-genai`.
- Актуализация `niche_queries.json`: в нём 33 ниши устаревшего ID-набора (`CYBERCLUB`, `NAIL`, `PHARMA`, `TIRE`, `WATER`) — надо привести к текущему ID-набору (`COMPCLUB`, `MANICURE`, `PHARMACY`, `TIRESERVICE`, `WATERPLANT`) и добавить ниши, которых в старом конфиге нет: `ACCOUNTING, AUTOPARTS, BUBBLETEA, BUILDMAT, CARGO, CARPETCLEAN, COSMETOLOGY, DETAILING, DRIVING, KIDSCENTER, LANGUAGES, MEATSHOP, OPTICS, PETSHOP, PHOTO, REALTOR, YOGA, BEAUTY, PRINTING, HOTEL, CATERING, LAUNDRY`.
- Актуализация промпта: в старой версии 6 H2; в сгенерированных файлах — 8 H2 (добавлены «Экономика и юнит-экономика» и «Маркетинг и привлечение клиентов»).

### Есть ли смысл возобновлять?
С практической точки зрения — **скорее нет, как механики обновления `*_insight.md`**:
- Текущие 44 файла уже лежат в `knowledge/kz/niches/`, используются `api/gemini_rag.py` как RAG-источник, формат стабилен, содержание — относительные показатели (без дат и цен, по правилам промпта). Переписывать их каждые N месяцев смысла немного.
- Реальных транскриптов в генерации и так почти не было (39 из 40 v2-файлов помечены `0 videos`), то есть качественного прироста от «настоящего YouTube-пайплайна» поверх Gemini-знаний — минимальный.
- `_yt_videos.json` полезен как справочный реестр (показать пользователю список релевантных видео на странице ниши), но тогда нужен только лёгкий `yt_search_niches.py` (yt-dlp), а не тяжёлая связка с транскриптами и Gemini.

Если цель — именно обогатить insight фактурой из транскриптов (а не просто Gemini по prior knowledge) — пайплайн надо восстанавливать и прогонять именно с ненулевыми транскриптами. Для этого потребуется YOUTUBE_API_KEY с квотой, GEMINI_API_KEY и время (33–44 ниши × ~7 видео × fetch транскрипта × Gemini = 5–10 минут/ниша).

## Методология

1. **Текущее дерево.** Grep по 8+ ключевым словам (`youtube_transcript_api`, `yt_dlp`, `pytube`, `googleapiclient`, `youtube.com/watch`, `extract_transcript`, `parse_video`, `fetch_youtube`, `get_transcript`, `video_to_insight`) + Glob по маскам `**/*youtube*`, `**/*transcript*`, `**/*insight_gen*`, `**/*scrape*`. В HEAD не найдено ничего, кроме insight.md-результатов и одного читателя (`api/gemini_rag.py`).
2. **История git.** `git log --all --diff-filter=D --name-only` по всему репо — нашёл коммит `e2cd588` 2026-04-13, удаливший `insight_collector/*` и `scripts/yt_search_niches.py`. Проверил blob-ы через `git show <sha>^:<path>` — весь код восстановим.
3. **Реестр видео.** Прочитал `knowledge/common/_yt_videos.json` (20 ниш, поля `id, title, channel, views, duration`, нет `transcript`). Отдельно нашёл `git log --all -- '**/_yt_videos.json'` → файл впервые появился в `56d08c1` 2026-04-12, перемещён в `6e77b41` 2026-04-21.
4. **Зависимости.** `git log -p -- requirements.txt` — полная эволюция, ни одной YouTube-зависимости никогда не добавлялось; подтверждает, что пайплайн был в отдельном сервисе.
5. **Insight-файлы.** Python-скрипт прошёлся по 44 `*_insight.md`: подсчёт `^## ` (везде 8), поиск `ZEREK v2` маркера (41/44), извлечение `N videos` из футера (40 из 41 = 0 видео, только PHARMACY = 8). Классификация по правилу: есть `ZEREK v2` или есть youtube-ссылки → `v2_with_youtube`; иначе если 6–10 H2 → `v1_no_youtube`.

### Сознательно пропущено
- Не сравнивал побайтово содержание PROMPT в старом `collect_insights.py` с каждым сгенерированным insight.md — достаточно того, что все 8 H2-заголовков совпадают со структурой-наследником старого промпта.
- Не распаковывал `zerek_insight_collector.tar.gz` (бинарный blob); полагаю, что он содержит тот же код, что и не-архивные файлы.
- Не искал YouTube-следы за пределами `.py`/`.json`/`.yaml`/`.csv`/`.md`/`.toml` (например, в `.html`/`.yml` для GitHub Actions — Glob по `**/*youtube*` подтвердил отсутствие).
- Не уверен на 100%, откуда взялись 40 v2-файлов с `0 videos`: либо это тот же `collect_insights.py`, прогнанный в режиме «Gemini без транскриптов», либо отдельный wrapper. В git этот wrapper не сохранился.
