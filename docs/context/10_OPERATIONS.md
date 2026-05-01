# 10 — OPERATIONS

> Инфраструктура: репо, vault, MCP, стек, технические правила работы.
> Обновлено: 01.05.2026

---

## Физическая инфраструктура

### Mac Адиля
- ОС: macOS
- Подписка: Claude Max (лимиты используются <50%)
- Cowork доступен и используется
- Claude Code — установлен, работает

### Папки на маке (РАЗНЫЕ корни)

| Назначение | Путь |
|---|---|
| **Git-репо проекта** | `/Users/adil/Documents/ZEREK/` |
| **Obsidian vault** | `/Users/adil/Desktop/ZEREK/` |

**Это разные сущности на разных корнях.** В репо живёт код, yaml, html, движок, CLAUDE.md. В vault — заметки и документы Obsidian. Они не одно и то же.

### Внешние системы

| Сервис | Адрес / детали |
|---|---|
| **GitHub** | `github.com/academyzerek-ops/ZEREK` (ветка main) |
| **Railway API** | `https://web-production-921a5.up.railway.app` (paid plan) |
| **GitHub Pages** | `https://academyzerek-ops.github.io/ZEREK/` |
| **Telegram Bot** | `@zerekai_bot` |
| **Mini App** | `products/quick-check.html` на GitHub Pages |
| **Domain** | `zerek.cc` (Namecheap, DNS настройки в проработке) |

## Стек технологий

| Компонент | Технология |
|---|---|
| База данных | xlsx файлы (openpyxl + pandas) — 19 файлов БНС РК, 2GIS-парсинг |
| Backend (движок расчётов) | Python 3.12 |
| API | FastAPI + uvicorn |
| Хостинг API | Railway |
| Frontend Mini App | HTML / CSS / JS чистый, без фреймворков |
| Хостинг Frontend | GitHub Pages |
| PDF-генерация | **WeasyPrint** (рекомендован поверх ReportLab — лучше работает с HTML/CSS) |
| AI / RAG | Gemini Flash (модель `gemini-2.5-flash` — НЕ deprecated 2.0). Приоритет: knowledge/ → интернет |
| Telegram Mini App | Telegram WebApp API |

## API эндпоинты

| Эндпоинт | Назначение |
|---|---|
| `GET /` | Статус сервера |
| `GET /health` | Health check + статус БД |
| `GET /debug` | JSON со списком загруженных файлов (для проверки live-статуса) |
| `GET /cities` | Города КЗ |
| `GET /niches` | Список ниш |
| `GET /formats/{niche_id}` | Форматы по нише |
| `GET /capex/{format_id}` | CAPEX по формату |
| `GET /rent/{city_id}` | Ставки аренды по городу |
| `POST /quick-check` | Главный — полный расчёт, JSON-ответ |
| `POST /quick-check/report` | Текстовый/PDF отчёт |
| `GET /competitors/{niche_id}/{city_id}` | Конкурентная среда (2GIS) |
| `GET /failure-patterns/{niche_id}` | Паттерны закрытий ниши |
| `GET /permits/{niche_id}` | Разрешения и лицензии |
| `GET /macro/{city_id}` | Макроданные региона |
| `GET /finmodel/defaults/{format_id}` | Бенчмарки для FinModel-анкеты |

`/healthz` **не реализован**. `/debug` используется как индикатор живости.

## Репо: структура

```
academyzerek-ops/ZEREK/
├── data/                      ← 19 xlsx БНС РК
│   ├── kz/
│   │   └── niches_registry.yaml   ← мета-информация ниш
│   ├── niches/
│   │   └── <CODE>_data.yaml       ← бизнес-данные, истина
│   ├── 05_tax_regimes.xlsx
│   └── ...
├── engine/                    ← Python движок
│   ├── __init__.py
│   ├── engine.py              ← главный
│   ├── report.py              ← форматирование
│   └── run_test.py
├── api/
├── products/
│   └── quick-check.html       ← Mini App
├── site/                      ← основной сайт
├── wiki/
│   ├── kz/                    ← обзоры КЗ
│   └── ru/                    ← обзоры РФ (позже)
├── knowledge/                 ← RAG база, insight-файлы
│   └── niches/
│       └── <CODE>_insight.md
├── docs/                      ← Документация и контекст
│   └── context/               ← Эта папка с 11 документами
├── main.py                    ← FastAPI сервер
├── CLAUDE.md                  ← Корневой контекст для Claude
├── Procfile
├── railway.json
└── requirements.txt
```

## Архитектура данных по нишам (3 слоя)

```
data/kz/niches_registry.yaml          ← мета (название, статус, архетип)
data/niches/<CODE>_data.yaml          ← БИЗНЕС-ДАННЫЕ (источник истины)
niche_formats_<CODE>.xlsx             ← runtime cache (yaml побеждает)
knowledge/niches/<CODE>_insight.md    ← текст для RAG и Wiki
```

Лоадер сливает md+yaml. Excel — runtime-кэш для скорости загрузки на Railway, **не источник истины**. При конфликте YAML побеждает.

## Source of Truth и протокол изменений

Каждой теме принадлежит ОДИН источник истины (см. таблицу ниже). Все остальные слои — описывают, ссылаются, но не дублируют значения.

### Иерархия SoT

| Тема | Источник истины | Что ссылается |
|---|---|---|
| Налоги КЗ 2026 | `data/external/kz_tax_constants_2026.yaml` | `knowledge/taxes/`, `docs/context/09`, Wiki |
| Ниши и форматы | `data/kz/niches_registry.yaml` | `CLAUDE.md`, `docs/context/04` |
| Архитектура движка | `docs/ARCHITECTURE.md` | `CLAUDE.md`, `docs/context/10` |
| Цены продуктов | `data/products.yaml` | Wiki, CTA, `docs/context/02` |
| Архетипы (A1 и др.) | `knowledge/archetypes/*.md` | `docs/context/04` |

### Протокол изменений

При изменении любого параметра, относящегося к одной из тем выше:

1. **СНАЧАЛА** меняется YAML / источник истины
2. **ПОТОМ** прогоняются тесты / loader / код, который читает источник
3. **ПОСЛЕ** — обновляются текстовые описания (`docs/context/`, `CLAUDE.md`, `knowledge/`), так чтобы они **ссылались** на изменение, не дублировали значение

### Запреты

- **В `docs/context/` запрещены конкретные цифры** (ставки, счётчики, лимиты). Конкретика — в `data/`. В `docs/context/` — методология.
- **В `CLAUDE.md` запрещены конкретные счётчики ниш и счётчики проектов** (число production_ready / wiki_only / research). Они могут устареть за день.
- **В `knowledge/` — допустимы пересказы YAML** с явной пометкой про источник и датой последней синхронизации.

### Триггер ревизии

Раз в 2 недели или после серьёзного изменения — пройтись по таблице SoT и сверить, что текстовые слои не разошлись с источником.

## Obsidian vault — single source of truth для контента

**Vault:** `/Users/adil/Desktop/ZEREK/`

**Подключение:** Claude Desktop через MCP (jacksteamdev plugin). Бинарь: `[vault-path]/.obsidian/plugins/mcp-tools/bin/mcp-server`.

**Доступные MCP-tools:**
- `obsidian:list_vault_files`
- `obsidian:get_vault_file`
- `obsidian:search_vault`
- `obsidian:create_vault_file`
- `obsidian:append_to_vault_file`
- `obsidian:patch_vault_file`

**Правило:** Ноа вызывает MCP-tools напрямую, **не дёргает Адиля за пути / скрины / листинги**. Веб claude.ai — MCP недоступен. MCP активен только в Claude Desktop в новой сессии после полного Cmd+Q-перезапуска.

**PARA-структура vault:** INBOX / NICHES / PRODUCTS / BUGS / ACADEMY / FUNNEL / BUSINESS / BLOCK2_SAAS / KNOWLEDGE.

## Knowledge base — RAG-источник

**Папка:** `knowledge/` в репо.

**Что сюда складывает Адиль:** все найденные отчёты, аналитику, статьи, кодексы — без жёсткой систематизации. Имена файлов — описательные.

**Приоритет в RAG:** Gemini Flash сначала ищет в `knowledge/`, потом в интернете. Чем больше документов — тем точнее продукт.

## Технические правила работы (как Ноа строит код и контент)

### Создание файлов

- **По одному с проверкой**, не пачкой. Большие пачки = риск ошибок и потери времени на откаты.
- **Большие файлы** (>200–300 строк) — через части (p1.py, p2.py, ..., p4.py) + `cat` для сборки. Уменьшает риск таймаута.
- **Сложные правки существующих файлов** — лучше создать новый, чем латать старый.
- Build-скрипты через `create_file` → исполнение через `bash_tool`.

### Работа с изображениями

- PNG → JPEG quality 55 перед base64
- Hero ~800×533 px
- Замена изображения = поменять, какая b64-переменная грузится — не inline search/replace

### Wiki-обзоры

- Hero: 80vh, full-width (вне `.wrapper`), `::before` base64 + blur(2px) + brightness(.35) + saturate(1.3), z-index правильный
- Nav: sticky, всегда **под** hero-фото, ZEREK-лого слева
- Шрифты: Playfair Display + Source Sans 3 + JetBrains Mono
- Мобильные таблицы: 9.5px + nowrap + 5px padding
- Уникальная цветовая палитра под нишу

### Скрипты для Claude Code

Адиль работает с Claude Code из папки репо. Команды для Claude Code:
- Одна большая инструкция вместо мелких шагов
- Явные команды git: `git add -A && git commit -m "..." && git push origin main`
- Без подтверждений (Адиль это пишет в инструкции)

## CLAUDE.md в корне репо

`CLAUDE.md` — **короткий навигатор** в корне репо. Не содержит всего, ссылается на эту папку (`docs/context/`).

Правило: при существенном изменении проекта — **немедленно обновляется** CLAUDE.md и/или соответствующий документ в `docs/context/`. Не накапливать «обновлю позже».

## Команды Адиля для базовых операций

**Проверить, что Railway-сервер живой:**
- Открыть `https://web-production-921a5.up.railway.app/debug`
- Если возвращает JSON со списком файлов → живой
- Если 502 / timeout → сервер заснул (на free plan) или упал

**Запушить локальные изменения в репо:**
```bash
cd /Users/adil/Documents/ZEREK
git add -A
git commit -m "описание"
git push origin main
```

**Запустить Claude Code в репо:**
```bash
cd /Users/adil/Documents/ZEREK
claude
```

**Дать Cowork доступ к репо:** через интерфейс Claude Desktop → Cowork → выбрать папку `/Users/adil/Documents/ZEREK/`.

## Что НЕ инфраструктура и куда НЕ ходить

- **Вход в Notion** — Notion исключён, контент только в Obsidian + Claude Desktop с MCP
- **Прямые правки на Railway** — нет, всё через GitHub push → автодеплой
- **Локальные xlsx-файлы** — не править руками, источник истины — YAML

## Полезные внешние сервисы

| Сервис | Назначение | Цена |
|---|---|---|
| Kling AI Pro | AI-видео для контента (TikTok/Reels) | ~13 000 ₸/мес |
| NotebookLM | Обработка видео-разборов в insight | бесплатно |
| Namecheap | Домен `zerek.cc` | ~$15/год |
| Railway | API-хостинг | $5/мес (paid plan) |
| Gemini API | RAG-слой | по тарифу Google |
| Claude Max | основной AI-ассистент | по подписке |

## Безопасность и резервные копии

- Репо в GitHub — основной источник истины кода
- Vault — Obsidian Git plugin синхронизирует в репо ~раз в 30 минут
- xlsx-данные — версионированы в репо
- Telegram Bot Token — в Railway Variables, не в репо
- API-ключи внешних сервисов — в Railway Variables / .env (не в репо)
- Регулярная резервная копия Obsidian vault — пока вручную; рассмотреть iCloud-бэкап автоматически
