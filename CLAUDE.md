# ZEREK — Контекст проекта для Claude Code

## Что такое ZEREK
AI-платформа финансовой аналитики для предпринимателей Казахстана. Telegram Mini App (@zerekai_bot).

## Основатель
Адиль — финансист из Актобе. Не разработчик. Техническую часть ведёт Claude.

## Продуктовая линейка (Блок 1 — через Telegram Mini App)
1. Wiki-обзоры — бесплатно (лид-магнит)
2. Экспресс-оценка — 5 000 ₸ (оценка бизнес-идеи за 2 минуты, MVP запущен)
3. Финансовая модель — 9 000 ₸ (Excel 36 мес)
4. Бизнес-план — 15 000 ₸
5. Pitch Deck — цена TBD

## Стек
- Backend: Python 3.12, FastAPI, Railway (https://web-production-921a5.up.railway.app)
- Frontend: чистый HTML/CSS/JS, GitHub Pages
- Данные: xlsx-файлы в /data/kz/ (БНС РК, рыночные данные КЗ 2026)
- Бот: @zerekai_bot
  - Quick Check Mini App: https://academyzerek-ops.github.io/ZEREK/products/quick-check.html (редиректор на `qc-v3.html`)
  - Academy Mini App: https://academyzerek-ops.github.io/ZEREK/products/app.html (SPA с учебными уроками)

## Структура репозитория
```
ZEREK/
index.html, about.html, privacy.html, wiki.html — сайт (GitHub Pages root)
products/
  quick-check.html      — редиректор на qc-v3.html (Mini App Экспресс-оценка)
  qc-v3.html            — канон Quick Check Mini App
  app.html              — SPA Academy (tabs, уроки)
  index.html            — редиректор на app.html
wiki/
  kz/                   — обзоры ниш Казахстан
  ru/                   — обзоры ниш Россия (на будущее)
api/                    — бэкенд (Railway деплоит отсюда)
  main.py, engine.py, report.py, gen_finmodel.py, pdf_gen.py, grant_bp.py,
  gemini_rag.py, finmodel_report.py
config/                 — YAML-конфиги (источники истины, см. раздел ниже)
  constants.yaml, defaults.yaml, finmodel_defaults.yaml,
  niches.yaml, archetypes.yaml, locations.yaml, questionnaire.yaml
data/
  kz/                   — xlsx-файлы по КЗ + niches/ + templates/
  ru/                   — пустые зеркала под RU (niches/, templates/)
  niches/               — legacy-YAML по 53 нишам (для не-A1 + не-мигрированных в R12.6)
  archetypes/           — legacy-YAML архетипов (a1_beauty_solo.yaml — пилот R12.6 ушёл в knowledge/)
knowledge/              — R12.6 единый источник истины (бизнес-данные, frontmatter+md)
  niches/               — структурированные данные ниш (R12.6 пилот = MANICURE; остальные через fallback на data/niches/*.yaml)
  archetypes/           — A1_BEAUTY_SOLO.md и т.п.
  regions/              — 18 городов КЗ (frontmatter: ЗП, население, check_coef)
  taxes/                — KZ_2026.md (МРП, НДС, УД-ставки по городам)
  changelog/            — история изменений + Obsidian setup guide
  _schemas/             — JSON Schema для валидации frontmatter
  _templates/           — болванки для новых ниш / регионов
  kz/niches/            — *_insight.md по нишам (RAG, ОТДЕЛЬНЫЙ контур от R12.6)
  ru/niches/            — пустое зеркало под RU
  common/               — общие ресурсы (например, _yt_videos.json)
templates/
  finmodel/, bizplan/, pitchdeck/ — шаблоны документов
app/                    — Блок 2 Flutter SaaS (на будущее)
Procfile, railway.json, requirements.txt
```

## API эндпоинты
- GET /cities — список городов КЗ
- GET /niches — все ниши из реестра с флагом `available: true|false` (производный: True ⇔ `status == 'production_ready'`; фронт решает, скрывать ли недоступные)
- GET /formats/{niche_id} — форматы по нише (400 если ниша недоступна)
- POST /quick-check — главный расчёт (city_id, niche_id, format_id, area_m2, loc_type, capital, start_month, capex_level)
- POST /quick-check/report — текстовый отчёт
- POST /finmodel — генерация xlsx финмодели
- POST /grant-bp — генерация .docx бизнес-плана на грант 400 МРП (Бастау Бизнес)

Все эндпоинты принимают city_id в любой форме (ALA / ALMATY / almaty) — нормализация идёт через `normalize_city_id()` на входе.

## Ниши — архитектура данных (post-migration 2026-04-29)

**Три слоя, все остаются:**

1. **`data/kz/niches_registry.yaml`** — ЕДИНСТВЕННЫЙ источник правды по списку и статусам ниш. Поля: `code`, `name_ru`, `status` (production_ready / wiki_only / research / idea), `archetype`, `category`, `icon`, `aliases`, флаги наличия и пути артефактов (`has_*`, `*_path`).
2. **`data/niches/<CODE>_data.yaml`** — бизнес-данные ниши (`formats`, `seasonality`, `risks`, `growth_scenarios`). Per-niche.
3. **`data/kz/niches/niche_formats_<CODE>.xlsx`** — расчётные параметры калибровки (FORMATS, FINANCIALS, STAFF, CAPEX, …). Per-niche.

**Правила добавления новой ниши:**
1. Запись в registry со `status: idea`.
2. Insight-материал в `knowledge/kz/niches/<CODE>_insight.md` → `status: research`.
3. `data/niches/<CODE>_data.yaml` + `wiki/kz/ZEREK_<CODE>.html` → `status: wiki_only` (CTA «Скоро» неактивна).
4. Калибровка xlsx → `status: production_ready` (CTA Quick Check активна за 5 000 ₸).

**Правила удаления / переименования:**
- В registry — добавлять `aliases` при переименовании, не удалять старый код пока живут ссылки в обзорах/коде.
- При слиянии ниш — добавить алиас удаляемой в той, что остаётся (пример: `BROW.aliases: [LASH]`).
- При разделении одной ниши на две — старый код становится алиасом одной из новых.

**Убрано из архитектуры в миграции 2026-04-29:**
- `config/niches.yaml` — удалён. Был дублирующим реестром.
- Поле `available` — заменено на проверку `status == 'production_ready'` в коде.
- Поле `name_rus` — переименовано в `name_ru` везде (legacy alias `name_rus` ещё живёт в синтез-shape `db.configs["niches"]` для backwards-compat в течение transition).

**Состав на 2026-04-29:**
- 49 утверждённых ниш из roadmap (было 50, минус LASH — слита с BROW «Брови и ресницы», alias сохранён).
- HOTEL осталась одной записью; разделение на HOSTEL/MINIHOTEL отложено до калибровки (см. `docs/niches_todo.md`).
- Полный реестр (включая wiki-only сироты из аудита): 63 записи.

**Архетипы** (A–F) определены в `config/archetypes.yaml` (отдельный реестр, не мигрирован).

---

### Архитектура бизнес-данных внутри ниши (post-cleanup 2026-04-30)

- **`data/niches/<CODE>_data.yaml`** — ИСТОЧНИК ИСТИНЫ для всех структурированных бизнес-данных ниши: форматы (`formats`, `formats_r12`), экономика (`marketing_min/med/max`, `other_opex_min/med/max`), сезонность (`seasonality`), риски (`risks`), сценарии роста (`growth_scenarios`), info-блоки (`info_blocks_r12`), upsells, action_plan.
- **`data/kz/niches/niche_formats_<CODE>.xlsx`** (лист FINANCIALS и др.) — производный от YAML, является runtime-cache для движка. При изменении YAML — xlsx синхронизируется **вручную**. Расхождение YAML vs xlsx = баг, чинится в пользу YAML.
- **`knowledge/kz/niches/<CODE>_insight.md`** (для большинства ниш) или **`knowledge/niches/<CODE>.md`** (R12.6 пилот, MANICURE) — текстовый материал: insight, исследование, паттерны. **Без структурированных данных по форматам.** Frontmatter содержит только meta (id, name_ru, icon, archetype) + опциональные текстовые поля; формат-блок `formats:` запрещён (живёт в YAML).

**Загрузчик** (`api/loaders/niche_loader.py::load_niche_yaml`) делает **merge**: knowledge md как база (для insight + meta), `data/niches/<CODE>_data.yaml` перезаписывает все совпадающие ключи. Если yaml отсутствует — используется только knowledge; если knowledge отсутствует — только yaml.

**Правило добавления / изменения**: всегда сначала YAML, потом ручная синхронизация xlsx. **Никогда не вписывать бизнес-данные напрямую в xlsx минуя YAML** — это создаёт рассинхрон.

## Налоги КЗ 2026
- МРП = 4 325 ₸
- Патент ОТМЕНЁН с 01.01.2026 → заменён на «Самозанятый»
- УСН порог = 600 000 МРП ≈ 2,595 млрд ₸
- НДС = 16%, ОПВР = 3.5%
- Ставки УСН (канон — `data/kz/05_tax_regimes.xlsx`, лист `city_ud_rates_2026`):
  - Астана, Алматы, Актобе, Атырау, Актау, Караганда, Семей, Усть-Каменогорск, Тараз, Кокшетау, Павлодар, Костанай, Петропавловск — 3%
  - Шымкент, Туркестан — 2%
  - Города с пометкой «Уточнить» в xlsx — значение подтверждается решениями маслихатов.

## Источники истины (канон)
Когда правишь значения — сверяйся только с каноническим источником.

**R12.6 разделение:** бизнес-данные (то, что Адиль правит) → `knowledge/`. Технические дефолты + структуры анкет → `config/`.

| Что | Канон | Тип |
|---|---|---|
| **Бизнес-данные ниш** (формат, чек, аренда, риски) — пилот R12.6 = MANICURE | `knowledge/niches/{NICHE}.md` (frontmatter + markdown) | бизнес |
| **Архетипы** (опыт, стратегии маркетинга, антипаттерны) — A1 пилот | `knowledge/archetypes/{ID}.md` | бизнес |
| **Регионы** (ЗП, население, check_coef) | `knowledge/regions/{city}.md` | бизнес |
| **Налоги КЗ** (МРП, МЗП, НДС, УД-ставки по городам) | `knowledge/taxes/KZ_{year}.md` | бизнес |
| Список ниш + статус + иконки + категории + aliases | `data/kz/niches_registry.yaml` | единый реестр (post-migration 2026-04-29) |
| Расчётные дефолты Quick Check (скоринг, бенчмарки) | `config/defaults.yaml` | техдеф |
| Дефолты финмодели (горизонт, OPEX, кредит, WACC) | `config/finmodel_defaults.yaml` | техдеф |
| Канонические ID городов + legacy_ids + check_coef | `config/constants.yaml` (секция cities) | технический реестр |
| ФОТ-множитель, соцплатежи ИП (расчётные коэф.) | `config/constants.yaml` | техдеф |
| Архетипы и операционные вопросы финмодели | `config/archetypes.yaml` | техдеф |
| Типы локаций | `config/locations.yaml` | техдеф |
| Вопросы анкеты (Quick Check / FinModel / BizPlan) | `config/questionnaire.yaml` | техдеф |
| **Не-A1 / не-мигрированные ниши** (53 ниши) | `data/niches/{NICHE}_data.yaml` | legacy YAML, fallback после knowledge |
| Инсайты по нишам (RAG для PDF) | `knowledge/kz/niches/{NICHE_ID}_insight.md` | RAG (отдельный контур) |

**R12.6 backward-compat:** для мигрированных ниш есть парный `knowledge/niches/{NICHE}.legacy.yaml` — машинный файл с legacy `formats:` блоком (не редактировать). Будет удалён в R12.7+ когда engine целиком перейдёт на `formats_r12`.

**Workflow редактирования бизнес-данных:** Адиль открывает `knowledge/` в Obsidian → правит markdown frontmatter → плагин Obsidian Git авто-коммитит каждые 30 мин → Railway пересобирает. См. `knowledge/changelog/2026-04-26_R12.6_obsidian_setup.md`.

## Правила работы
- Все тексты пользователю — на русском языке
- Все ID в коде — на английском (COFFEE, BAKERY и тд)
- Названия в интерфейсе — всегда на русском через маппинг
- Экспресс-оценка стоит 5 000 ₸ (НЕ бесплатно)
- GitHub Pages настроен на / (root), НЕ на /docs
- При любых изменениях — git add, commit, push
- Тон ZEREK: практичный консультант, не мотиватор. Акцент на рисках.

## Telegram-бот (@zerekai_bot)
- Бот без кода — настраивается через BotFather
- Mini App URL (кнопка меню): https://academyzerek-ops.github.io/ZEREK/products/index.html
  - `index.html` редиректит в `app.html` (Academy SPA). Внутри — переход на `qc-v3.html` по клику на Quick Check.
- Приветственное сообщение настраивается через BotFather → /setdescription
- Текст /start (description):

```
Привет! На связи ZEREK 👋

Открыть бизнес — это риск. 70% новых бизнесов в Казахстане закрываются в первые 2 года. Главная причина — не считали до старта.

Мы это исправляем. ZEREK — AI-аналитик, который за минуты покажет реальную картину вашей бизнес-идеи: сколько вложить, когда окупится, какие риски подстерегают и какой налоговый режим выбрать.

Честные цифры. Без иллюзий. На данных по вашему городу.

📊 Обзор ниши — бесплатно
⚡ Экспресс-оценка — 5 000 ₸
📈 Финансовая модель — 9 000 ₸
📋 Бизнес-план + Презентация — 15 000 ₸

Нажмите кнопку меню ↓ и проверьте свою идею.
```

- Как настроить: BotFather → @zerekai_bot → /setdescription → вставить текст выше
- Кнопка меню: BotFather → /setmenubutton → Web App URL → https://academyzerek-ops.github.io/ZEREK/products/index.html

## Дизайн
- Mini App Quick Check (`products/qc-v3.html`) — светлая тема: --bg #FFFFFF, --accent #7C6CFF, --green #10B981, --amber #F59E0B, --red #EF4444
- Academy SPA (`products/app.html` + `academy/kz/**`) — warm beige editorial: #FAF8F5, акцент #6C5CE7
- Wiki-обзоры — светлая тема
- Шрифты Mini App: Geist (UI), Geist Mono (цифры)
- Шрифты Академии: Playfair Display + Nunito + JetBrains Mono
- PDF Quick Check использует editorial-палитру (navy #1F3864 + gold #C9A961, Source Sans 3, JetBrains Mono) намеренно. Это не Mini App-стиль (#7C6CFF, Geist) — разные контексты потребления.
- Mobile-first, max-width 480px (Mini App), 460px (академия)
- Полный дизайн-контекст: `.impeccable.md` (users, brand personality, aesthetic direction, 5 design principles)
