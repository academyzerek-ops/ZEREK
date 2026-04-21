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
knowledge/
  kz/niches/            — *_insight.md по нишам (RAG)
  ru/niches/            — пустое зеркало под RU
  common/               — общие ресурсы (например, _yt_videos.json)
templates/
  finmodel/, bizplan/, pitchdeck/ — шаблоны документов
app/                    — Блок 2 Flutter SaaS (на будущее)
Procfile, railway.json, requirements.txt
```

## API эндпоинты
- GET /cities — список городов КЗ
- GET /niches — все ниши с флагом `available: true|false` (фронт решает, скрывать ли недоступные)
- GET /formats/{niche_id} — форматы по нише (400 если ниша недоступна)
- POST /quick-check — главный расчёт (city_id, niche_id, format_id, area_m2, loc_type, capital, start_month, capex_level)
- POST /quick-check/report — текстовый отчёт
- POST /finmodel — генерация xlsx финмодели
- POST /grant-bp — генерация .docx бизнес-плана на грант 400 МРП (Бастау Бизнес)

Все эндпоинты принимают city_id в любой форме (ALA / ALMATY / almaty) — нормализация идёт через `normalize_city_id()` на входе.

## Ниши
Канонический список — в `config/niches.yaml`. Каждая ниша имеет поле `available`:
- `available: true` — есть `data/kz/niches/niche_formats_{ID}.xlsx` с непустым листом FINANCIALS.
- `available: false` — xlsx нет (заготовка на будущее; фронт может показать с пометкой «скоро»).

Каждая ниша отнесена к одному из архетипов A–F (см. `config/archetypes.yaml`).

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

| Что | Канон |
|---|---|
| Список ниш, иконки, имена, архетип, флаг `available` | `config/niches.yaml` |
| Налоги УСН по городам | `data/kz/05_tax_regimes.xlsx` (лист `city_ud_rates_2026`) |
| Константы 2026 (МРП, МЗП, НДС, ФОТ-множитель, соцплатежи ИП) | `config/constants.yaml` |
| Расчётные дефолты Quick Check (сезонность, сценарные коэффициенты, скоринг, бенчмарки) | `config/defaults.yaml` |
| Дефолты финмодели (горизонт, OPEX, ФОТ, CAPEX, кредит, WACC) | `config/finmodel_defaults.yaml` |
| Канонические ID городов (+ legacy_ids для совместимости) | `config/constants.yaml`, секция `cities` |
| Архетипы и операционные вопросы финмодели | `config/archetypes.yaml` |
| Типы локаций | `config/locations.yaml` |
| Вопросы анкеты (Quick Check / FinModel / BizPlan) | `config/questionnaire.yaml` |
| Инсайты по нишам (риски, красные флаги) | `knowledge/kz/niches/{NICHE_ID}_insight.md` |

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
- Mobile-first, max-width 480px (Mini App), 460px (академия)
- Полный дизайн-контекст: `.impeccable.md` (users, brand personality, aesthetic direction, 5 design principles)
