# ZEREK — План генеральной уборки репозитория

**Дата:** 2026-04-21
**Текущий коммит:** `784196e`
**Источник фактов:** `AUDIT_REPORT.md` (перепроверен через Read/Grep)

> **Фаза 1 — только план. Выполнение только после подтверждения владельца.**
> Никаких правок файлов, коммитов и удалений этот документ не делает.

---

## Оглавление

- [Раздел A — Удаление мёртвых файлов](#раздел-a--удаление-мёртвых-файлов)
- [Раздел B — Неиспользуемые xlsx (только инвентаризация)](#раздел-b--неиспользуемые-xlsx-только-инвентаризация)
- [Раздел C — Реструктуризация `/data/` и `/knowledge/`](#раздел-c--реструктуризация-data-и-knowledge)
- [Раздел D — Ниши и флаг `available`](#раздел-d--ниши-и-флаг-available)
- [Раздел E — Дубликаты констант](#раздел-e--дубликаты-констант)
- [Раздел F — Унификация ID городов](#раздел-f--унификация-id-городов)
- [Раздел G — Баги в `engine.py`](#раздел-g--баги-в-enginepy)
- [Раздел H — Резюме](#раздел-h--резюме)
- [Дополнительные находки](#дополнительные-находки)

---

## Раздел A — Удаление мёртвых файлов

Проверка: по каждому кандидату выполнен grep по всему репо. Статусы:
- `готов к удалению` — ссылок на файл нет либо все ссылки — в самом файле / `AUDIT_REPORT.md`.
- `ссылка в активном файле — нужна правка` — удалять можно только после правки других файлов.
- `ещё используется` — не удалять.

### A1. Каталог `/engine/` целиком

| Файл | Статус | Где найдены ссылки | Правка перед удалением |
|---|---|---|---|
| ```/engine/__init__.py``` | готов к удалению | только `AUDIT_REPORT.md` | — |
| ```/engine/gemini_rag.py``` | готов к удалению | только `AUDIT_REPORT.md` | — |
| ```/engine/run_test.py``` | готов к удалению | только `AUDIT_REPORT.md`; внутри файла — `from engine import ZerekDB, run_quick_check` (обращение к несуществующей функции; `run_quick_check_v3` живёт в `api/engine.py`) | — |

Импорты `from engine import ...` в `api/main.py:15` и `api/main.py:136` разрешаются не на корневой пакет `/engine/`, а на файл `api/engine.py` — путь добавляется через `sys.path.insert(0, BASE_DIR)` в `api/main.py:12-13`. Поэтому удаление каталога `/engine/` на работу API не повлияет.

### A2. `products/app.html`

- Статус: `ссылка в активном файле — нужна правка` (не удалять, пока не подтверждено владельцем).
- Где ссылки:
  - ```products/index.html:5``` — meta-refresh на `app.html`
  - ```products/index.html:9``` — `window.location.replace('app.html' + ...)`
  - ```academy/templates/lesson_template.html:328``` — кнопка «Содержание» → `../../../products/app.html?tab=academy`
  - ```academy/kz/junior/*.html``` и ```academy/kz/startup/*.html``` — все 52 lesson-файла академии имеют hard-coded ссылку `../../../products/app.html?tab=academy`
  - ```products/app.html:3106``` — из самого app.html есть переход `qc-v3.html?...`
  - ```CLAUDE.md:78, 100, 103``` — Mini App URL указывает на `products/index.html`, который редиректит в `app.html`
- Правка перед удалением (если всё-таки решено удалить):
  1. Обновить `products/index.html` на `qc-v3.html` (или оставить как единственную точку входа Mini App).
  2. Во всех 52 lesson-файлах `academy/kz/junior/*.html` и `academy/kz/startup/*.html` заменить `products/app.html?tab=academy` на новую точку входа академии (например, корневой `academy.html` + якорь).
  3. Обновить `CLAUDE.md` (Mini App URL, упоминания `products/app.html`).
- Вопрос к владельцу: `app.html` — это SPA, объединяющий Quick Check + landing + Academy tab. Если академия продолжает жить на `app.html`, файл остаётся. См. раздел H.5.

### A3. `products/quick-check-v2.html`

- Статус: `готов к удалению`.
- Grep показал 0 ссылок из других `.html/.py/.md`. Файл не фигурирует ни в одном редиректоре и не импортируется. Это legacy-прототип анкеты до `qc-v3.html`.
- Правка перед удалением: не требуется.

### A4. `products/quick-check.legacy.html`

- Статус: `готов к удалению`.
- Grep нашёл упоминания только в `AUDIT_REPORT.md`. Внутри самого файла (см. строки 667, 675, 879, 911, 1000, 1279, 1280) есть локальные словари `NICHE_ICONS`, `NICHE_NAMES` — но они замкнуты на сам файл.
- Правка перед удалением: не требуется.

### A5. `products/index.html` (редиректор на `app.html`)

- Статус: зависит от решения по A2.
- Содержимое (```products/index.html:1-11```): meta-refresh + JS на `app.html`.
- Варианты:
  1. **Оставить как редирект**, но перенаправить на `qc-v3.html` вместо `app.html`. Синхронизировать с `products/quick-check.html` (который уже редиректит в `qc-v3.html`).
  2. **Удалить** файл; тогда Mini App URL из BotFather надо вести напрямую на `products/qc-v3.html`, и CLAUDE.md (`:78, :100`) поправить.
- Вопрос к владельцу (см. раздел H.5): что выбрать — 1 или 2.

### A6. Файлы `.bak / .old / .tmp / *.legacy.*`

Поиск по `*.bak`, `*.old`, `*.tmp` — ни одного файла в рабочем дереве (```find /Users/adil/Documents/ZEREK -name '*.bak' -o -name '*.old' -o -name '*.tmp'``` → пусто).

Файлы с `legacy` в имени: только ```products/quick-check.legacy.html``` — обработан в A4.

Статус: `✓ ничего лишнего не найдено`.

### A7. `.DS_Store`

Файлы на диске:
```
/Users/adil/Documents/ZEREK/.DS_Store
/Users/adil/Documents/ZEREK/images/.DS_Store
/Users/adil/Documents/ZEREK/images/confection/.DS_Store
```

Статус: `готовы к удалению` (macOS-служебные, в репо не нужны).

Правка перед удалением: добавить строку `.DS_Store` в `.gitignore` (там уже какой-то контент, но явного правила не видно). Проверить текущее содержание `.gitignore` перед правкой.

### A8. Корневой `icon-192.png`

- `git status` в шапке задачи показывает `D icon-192.png` — файл **уже удалён** из рабочей копии, изменение не закоммичено.
- Статус: `коммит удаления нужен` (без дополнительных правок). В репо остаётся `icon-512.png`, а `manifest.json` проверять отдельно:
  - ```manifest.json``` ссылки на `icon-192.png` нужно проверить перед коммитом (см. раздел H.4 — риски).

---

## Раздел B — Неиспользуемые xlsx (только инвентаризация)

Файлы, чьи имена не упоминаются в активном `.py`-коде (`api/*.py`). Все остаются на месте; таблица нужна для будущих решений.

| Файл | Краткое содержание (главный лист) | Куда подключить |
|---|---|---|
| ```data/kz/02_wages_by_city.xlsx``` | Лист `Зарплаты по регионам` (27×16) — БНС РК Q3 2025 медианы по всем регионам | Подтянуть в расчёт ФОТ (fallback вместо хардкода `200_000` в `engine.py:2126` и в дефолтах финмодели) |
| ```data/kz/03_wages_by_industry.xlsx``` | Листы `Зарплаты по отраслям` (96×8), `Ключевые для ниш ZEREK` (11×6) — маппит `niche_id` → отрасль БНС | В расчёт блока 5 P&L для архетипа D/E (ФОТ по отрасли) |
| ```data/kz/04_wages_by_role.xlsx``` | Листы `Зарплаты по должностям` (24×13), `Калькулятор ФОТ` (12×12), `Схемы оплаты` (11×6) — ставки по городам | Подключить к `engine.py:2123-2130` (`role_salary_monthly`) вместо фолбэка 200K |
| ```data/kz/20_scenario_coefficients.xlsx``` | Лист `scenario_coefficients` (18×9) — `pessimistic/base/optimistic` коэффициенты трафика и чека per `format_id` | Заменить хардкод `engine.py:728`, `engine.py:594-599`, `engine.py:1777-1778` (три разных набора множителей сценариев) |
| ```data/kz/21_opex_benchmarks.xlsx``` | Лист `opex_benchmarks` (18×13) — `utilities_pct`, `utilities_fixed_kzt`, `consumables_pct`, `marketing_pct/fixed`, `software_kzt`, `transport_kzt`, `misc_pct`, `total_variable_pct` | Заменить дефолты `main.py:484-488`, `gen_finmodel.py:101-105` + `report.py` food cost/margin |
| ```data/kz/22_staff_scaling.xlsx``` | Лист `staff_scaling` (39×11) — стадии `start/growth/scale`, роли, FTE, зарплаты | Подключить к `engine.py:compute_block5_pnl` (этапы роста ФОТ) и к блоку 10 action plan |
| ```data/kz/19_inflation_by_niche.xlsx``` | Лист `Прогноз роста OPEX` (13×7) — **файл загружается в `db.inflation_niche` (```engine.py:110```), но значение нигде не читается** | Применить к годовым прогнозам в Блоке 5 P&L и к Блоку 7 scenarios (инфляция opex по нише) |

Дополнительно — **листы внутри используемых xlsx**, которые не читаются:

| Файл | Лист | Комментарий |
|---|---|---|
| `01_cities.xlsx` | `Регионы демография`, `Городское vs Сельское`, `Динамика населения` | Читается только `Города` |
| `05_tax_regimes.xlsx` | `b2b_nds_warnings`, `payroll_taxes_2026`, `key_params_2026`, `notes` | Читаются только `tax_regimes_2026` и `city_ud_rates_2026` |
| `13_macro_dynamics.xlsx` | `Индекс КЭИ`, `Динамика торговли`, `Курс и импорт`, `Параметры для Quick Check` | Читается только `Инфляция по регионам` |
| `14_competitors.xlsx` | `Сигналы для Quick Check` | Читается только `Конкуренты по городам` |
| `15_failure_cases.xlsx` | `База факапов`, `Классификатор причин`, `Как добавлять кейсы` | Читается только `Паттерны по нишам` |
| `19_inflation_by_niche.xlsx` | `Инфляция по статьям ниш` | Не читается |
| per-niche xlsx | `GROWTH`, `LAUNCH`, `SUPPLIERS`, `SURVEY`, `LOCATIONS` | Частично отдаются эндпоинтами `/survey`, `/products`, `/insights`, но в `run_quick_check_v3` не участвуют |

---

## Раздел C — Реструктуризация `/data/` и `/knowledge/`

### C.1 Текущее состояние

`/data/`:
```
/data/
├── common/
│   └── .gitkeep
├── kz/
│   ├── 01_cities.xlsx  ... 22_staff_scaling.xlsx   (17 xlsx)
│   ├── niches/
│   │   ├── gitkeep                                  ← БЕЗ точки в начале
│   │   └── niche_formats_*.xlsx                     (33 xlsx)
│   └── templates/
│       └── gitkeep                                  ← БЕЗ точки в начале
└── ru/
    └── .gitkeep
```

`/knowledge/`:
```
/knowledge/
├── kz/
│   └── .gitkeep
├── niches/
│   ├── _yt_videos.json
│   └── *_insight.md                                 (43 md)
└── ru/
    └── .gitkeep
```

### C.2 Желаемая структура (из постановки)

```
/data/
├── kz/
│   ├── (общие xlsx)
│   └── niches/
│       └── niche_formats_*.xlsx
└── ru/
    ├── .gitkeep
    └── niches/
        └── .gitkeep

/knowledge/
├── kz/
│   └── niches/
│       └── *_insight.md
└── ru/
    └── niches/
        └── .gitkeep
```

### C.3 Шаги миграции

**C.3.1. `/data/common/` → удалить**
```
rm /Users/adil/Documents/ZEREK/data/common/.gitkeep
rmdir /Users/adil/Documents/ZEREK/data/common
```
Проверить: `/data/common/` grep'ится только по `AUDIT_REPORT.md` (факт из раздела 1 аудита) — в `.py` не используется. Безопасно.

**C.3.2. Починка `gitkeep` без точки**
```
mv /Users/adil/Documents/ZEREK/data/kz/niches/gitkeep /Users/adil/Documents/ZEREK/data/kz/niches/.gitkeep
mv /Users/adil/Documents/ZEREK/data/kz/templates/gitkeep /Users/adil/Documents/ZEREK/data/kz/templates/.gitkeep
```

**C.3.3. `/data/kz/templates/` — оценить**
- Содержит только `gitkeep` (или `.gitkeep` после C.3.2). Реальный шаблон `finmodel_template.xlsx` лежит в `/templates/finmodel/` (корневой).
- `api/main.py:760-761` использует fallback путь `data/kz/templates/finmodel_template.xlsx`. Если каталог хранится на будущее — оставить `.gitkeep` и не трогать. Иначе — удалить каталог и убрать fallback из main.py.
- Пометка: решение зависит от того, продержится ли fallback-путь (см. H.5).

**C.3.4. Создать структуру под `ru/niches/`**
```
mkdir -p /Users/adil/Documents/ZEREK/data/ru/niches
touch /Users/adil/Documents/ZEREK/data/ru/niches/.gitkeep
```

**C.3.5. Перенести инсайт-файлы в `/knowledge/kz/niches/`**
```
mkdir -p /Users/adil/Documents/ZEREK/knowledge/kz/niches
git mv /Users/adil/Documents/ZEREK/knowledge/niches/*_insight.md /Users/adil/Documents/ZEREK/knowledge/kz/niches/
```
Всего перемещаются все insight-файлы (каждая ниша — один файл вида `{NICHE_ID}_insight.md`).

**C.3.6. Решить судьбу `_yt_videos.json`**
- Лежит в `/knowledge/niches/_yt_videos.json` (81.2 KB).
- В `.py` не используется (grep 0 хитов). Предположительно читается фронтом Academy/Wiki.
- Варианты:
  1. Перенести в `/knowledge/kz/niches/_yt_videos.json` (если это KZ-контент).
  2. Перенести в `/knowledge/common/` (если видео применимы для обеих локалей).
- Перед действием: grep `yt_videos|_yt_videos` по `.html`, `.js`, `.css` в `academy/`, `wiki/`, `site/`. См. раздел H.5 — открытый вопрос.

**C.3.7. Удалить пустой `/knowledge/niches/` после переноса**
```
rmdir /Users/adil/Documents/ZEREK/knowledge/niches
```
(выполняется только если `_yt_videos.json` также мигрирован).

**C.3.8. Подправить пути в коде**

Файлы, читающие из `/knowledge/niches/`:
- ```api/engine.py:1895-1896``` — `insight_path = os.path.join(repo_root, 'knowledge', 'niches', f'{niche_id}_insight.md')`
- ```api/gemini_rag.py:_read_insight_file``` — такой же путь

Правка: заменить на `os.path.join(repo_root, 'knowledge', 'kz', 'niches', ...)` (с локалью). Либо параметризовать по текущей локали.

**C.3.9. Создать структуру под `knowledge/ru/niches/`**
```
mkdir -p /Users/adil/Documents/ZEREK/knowledge/ru/niches
touch /Users/adil/Documents/ZEREK/knowledge/ru/niches/.gitkeep
```
(пустая заглушка для будущего RU-контента)

---

## Раздел D — Ниши и флаг `available`

Источник списка: `config/niches.yaml`. Проверка наличия xlsx: `glob /Users/adil/Documents/ZEREK/data/kz/niches/niche_formats_*.xlsx` + openpyxl-чтение `FINANCIALS` на каждом файле.

### D.1 Ниши с `available: true`

Условие: есть файл `data/kz/niches/niche_formats_{NICHE_ID}.xlsx` **И** лист `FINANCIALS` содержит ≥1 строку данных.

- AUTOSERVICE
- BAKERY
- BARBER
- BROW
- CANTEEN
- CARWASH
- CLEAN
- COFFEE
- CONFECTION
- DENTAL
- DONER
- DRYCLEAN
- FASTFOOD
- FITNESS
- FLOWERS
- FRUITSVEGS
- FURNITURE
- GROCERY
- KINDERGARTEN
- LASH
- MASSAGE
- PIZZA
- PVZ
- REPAIR_PHONE
- SEMIFOOD
- SUGARING
- SUSHI
- TAILOR

Отдельно — **ниши с несоответствием ID между yaml и xlsx** (xlsx присутствует, yaml использует другой ID). По факту данные есть, но для корректного `available=true` нужно унифицировать ID:

- `CYBERCLUB` (xlsx) vs `COMPCLUB` (yaml)
- `NAIL` (xlsx) vs `MANICURE` (yaml)
- `PHARMA` (xlsx) vs `PHARMACY` (yaml)
- `TIRE` (xlsx) vs `TIRESERVICE` (yaml)
- `WATER` (xlsx) vs `WATERPLANT` (yaml)

### D.2 Ниши с `available: false`

Условие: в yaml есть, но `niche_formats_{NICHE_ID}.xlsx` не существует (по каноническому yaml-ID).

- BEAUTY
- MANICURE (xlsx называется `NAIL` — см. D.1)
- COSMETOLOGY
- OPTICS
- PHOTO
- DETAILING
- NOTARY
- BUBBLETEA
- CATERING
- MEATSHOP
- AUTOPARTS
- BUILDMAT
- PETSHOP
- PHARMACY (xlsx называется `PHARMA`)
- WATERPLANT (xlsx называется `WATER`)
- YOGA
- LANGUAGES
- KIDSCENTER
- ACCOUNTING
- CROSSFIT
- MARTIAL_ARTS
- FOOTBALL_SCHOOL
- GROUP_FITNESS
- REALTOR
- EVALUATION
- LOFTFURNITURE
- PRINTING
- CARGO
- TIRESERVICE (xlsx называется `TIRE`)
- CARPETCLEAN
- LAUNDRY
- COMPCLUB (xlsx называется `CYBERCLUB`)
- DRIVING
- HOTEL

### D.3 План изменений в `config/niches.yaml`

Добавить поле `available: true/false` в каждую запись. Пример на трёх нишах:

```yaml
niches:
  BARBER:
    name_rus: "Барбершоп"
    category: beauty
    archetype: A
    icon: "💈"
    available: true           # ← xlsx есть, FINANCIALS непустой

  BEAUTY:
    name_rus: "Салон красоты"
    category: beauty
    archetype: A
    icon: "💄"
    available: false          # ← xlsx не подготовлен

  MANICURE:
    name_rus: "Маникюр"
    category: beauty
    archetype: A
    icon: "💅"
    available: false          # ← xlsx есть под другим ID (NAIL); решается через унификацию ID
```

Отдельно решить вопрос унификации ID (D.1 хвост):
- Либо переименовать файлы `niche_formats_NAIL.xlsx` → `niche_formats_MANICURE.xlsx` и т.д.
- Либо завести в yaml соответствующий niche_id ровно такой, какой в xlsx (поменять `MANICURE` → `NAIL`, `PHARMACY` → `PHARMA`, `TIRESERVICE` → `TIRE`, `WATERPLANT` → `WATER`, `COMPCLUB` → `CYBERCLUB`).
- Решение — за владельцем (см. H.5).

### D.4 Изменения в API endpoints

Эндпоинты в `api/main.py`, которые должны фильтровать по `available=true`:

| Эндпоинт | Файл / функция | Что сделать |
|---|---|---|
| `GET /niches` | ```api/main.py:111-115``` (`get_niches`) | В выдачу включать только ниши с `available=true` из `niches.yaml`, либо возвращать все, но с полем `"available": bool` — чтобы фронт мог скрывать недоступные |
| `GET /configs` | ```api/main.py:265-270``` | Отдаётся целиком `db.configs`; фронт ожидает иметь у себя список. Добавить `available` в `niches` секцию возврата |
| `GET /formats/{niche_id}` | ```api/main.py:116-121``` | Если ниша `available=false`, вернуть 404 с текстом «Ниша пока недоступна» |
| `GET /formats-v2/{niche_id}` | ```api/main.py:272-277``` | То же правило 404 |
| `GET /niche-config/{niche_id}` | ```api/main.py:239-247``` | То же |
| `GET /niche-survey/{niche_id}` | ```api/main.py:250-262``` | То же |
| `GET /quickcheck-survey/{niche_id}` | ```api/main.py:279-287``` | То же |
| `POST /quick-check` | ```api/main.py:141-237``` | В начале функции проверить `available=true`, иначе `HTTPException(400, "Ниша пока недоступна для расчёта")` |

Функции в `api/engine.py`, которые надо подстроить:
- `ZerekDB.get_available_niches()` — уже существует (упомянута в аудите, `AUDIT_REPORT.md:297`). Должна теперь читать флаг из `niches.yaml`, а не просто «есть файл».
- `get_niche_config` / `get_niche_survey` / `get_formats_v2` — поднять проверку флага до вызова данных xlsx.

---

## Раздел E — Дубликаты констант

### E.1 Таблица совпадений и расхождений

| Что | Где сейчас | Значения | Канон | Что править |
|---|---|---|---|---|
| **Сезонность** | ```api/main.py:473```; ```api/gen_finmodel.py:82```; ```api/finmodel_report.py:628``` | `main.py` и `gen_finmodel.py`: `[0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]` — совпадают. `finmodel_report.py`: `[0.85, 0.80, 0.90, 1.00, 1.05, 0.90, 0.85, 0.80, 0.95, 1.10, 1.15, 1.20]` — **отличается** (другая форма кривой) | ```config/defaults.yaml``` → ключ `finmodel.default_seasonality` (новый YAML) | `main.py`, `gen_finmodel.py`, `finmodel_report.py` — все читают из YAML; per-niche сезонность `s01…s12` из xlsx остаётся приоритетом |
| **Полный блок дефолтов финмодели (23 параметра)** | ```api/main.py:474-497```; ```api/gen_finmodel.py:85-113``` | Совпадают по именам и значениям (зеркало) | ```config/finmodel_defaults.yaml``` (новый YAML) | `main._compute_finmodel_data` и `gen_finmodel.generate_finmodel` — оба загружают из YAML; также `main.py:720-755` (`params = {...}`) использует те же дефолты как fallback |
| **МРП 2026 = 4325** | ```api/engine.py:17```; ```api/grant_bp.py:9```; ```data/kz/05_tax_regimes.xlsx:key_params_2026``` | Все совпадают | ```config/constants.yaml``` → `mrp_2026: 4325` | `engine.py:17`, `grant_bp.py:9` импортируют из yaml; xlsx-лист `key_params_2026` становится справочником для документации, код на него не опирается |
| **МЗП 2026 = 85000** | ```api/engine.py:18```; ```data/kz/05_tax_regimes.xlsx:key_params_2026``` | Совпадают | ```config/constants.yaml``` → `mzp_2026: 85000` | `engine.py:18` — импортирует из yaml |
| **Список городов и их ID** | ```data/kz/01_cities.xlsx:Города``` (`ALA/AST/SHY/AKT/SEM/URA/TAR/OSK/PAV/KOS/KZO/ATY/AKA/PET/KOK`); ```data/kz/05_tax_regimes.xlsx:city_ud_rates_2026``` (`ASTANA/ALMATY/SHYMKENT/AKTOBE/KARAGANDA/ATYRAU/AKTAU/KOSTANAY/PAVLODAR/SEMEY/USKAMAN/TARAZ/TURKESTAN/PETROPAVL/KOKSHETAU`); ```api/engine.py:40-46``` CITY_CHECK_COEF (`almaty/astana/atyrau/aktobe/karaganda/uralsk/ust_kamenogorsk/aktau/shymkent/pavlodar/kostanay/semey/taraz/petropavlovsk/kyzylorda`); ```api/grant_bp.py:16-32``` CITY_DATA (`astana/almaty/shymkent/aktobe/karaganda/atyrau/pavlodar/kostanay/aktau/semey/uralsk/taldykorgan/turkestan/kokshetau/petropavl`) | **Четыре разных набора идентификаторов.** Плюс списки городов не полностью пересекаются: `KZO`/Кызылорда есть в `01_cities.xlsx` и CITY_CHECK_COEF, но отсутствует в `05_tax_regimes.xlsx` и CITY_DATA. `TURKESTAN` есть в tax-регимах и CITY_DATA, нет в `01_cities.xlsx`. `taldykorgan` есть только в `grant_bp.py` | ```config/constants.yaml``` → `cities:` (список) + единый канонический ID вида `lower_snake_latin`. `01_cities.xlsx`, `05_tax_regimes.xlsx` нормализуются к этому ID | Подробно — раздел F |
| **Маппинг niche_id → русское имя** | ```api/engine.py:131-156``` NICHE_NAMES (33 ниши); ```api/pdf_gen.py:150-163``` NICHE_NAMES (дубль); ```config/niches.yaml``` `name_rus` (57 ниш); ```scripts/build_07_niches.py:43``` NICHE_NAMES | 33 в `engine.py` и `pdf_gen.py` совпадают между собой; yaml шире и может содержать иные имена для расхождений ID (см. раздел F) | ```config/niches.yaml``` — каноничный | Вычистить `NICHE_NAMES` из `engine.py:131-156` и `pdf_gen.py:150-163`; вместо словаря обращаться к `db.configs["niches"]["niches"][niche_id]["name_rus"]` |
| **Иконки ниш** | ```api/engine.py:157-169``` NICHE_ICONS; ```products/app.html:3027``` NICHE_ICONS; ```products/quick-check.legacy.html:667``` NICHE_ICONS; ```config/niches.yaml``` `icon` | Совпадений не проверял буквально; yaml содержит canon | ```config/niches.yaml``` | `engine.py:157-169` удалить, отдавать icon через `/niches` / `/configs`; `app.html` — получать icon с бэкенда (или оставить hardcoded как fallback) |
| **Множители сценариев трафика/чека** | ```api/engine.py:728``` (pess 0.75 / base 1.0 / opt 1.25 трафик; 0.90/1.0/1.10 чек); ```api/engine.py:594-599``` (стресс-тест: traffic_k 0.75, check_k 0.90, rent_k 1.20); ```api/engine.py:1777-1778``` (Блок 7: 0.75/1.00/1.25) | Три разных набора, частично расходятся (опт 1.20 vs 1.25, rent_k только в стресс-тесте) | ```config/defaults.yaml``` → `scenario_coefficients:` + (если подключим xlsx) фактическая priority на ```data/kz/20_scenario_coefficients.xlsx``` per format_id | `engine.py:594-599`, `:728`, `:1777-1778` — все читают единый источник |
| **Дефолтная ставка налога** | ```api/engine.py:293, 297``` (fallback 4.0% если город не найден); ```api/engine.py:2034, 2075``` (дефолт 3%); ```api/main.py:493, 728``` (3%); ```api/gen_finmodel.py:89``` (3%) | Смешение 3% и 4% | ```config/constants.yaml``` → `default_tax_rate: 0.03` (либо отдельные `tax_rate_fallback_when_city_missing: 0.04` и `tax_rate_when_city_has_no_rate: 0.03`) | все места |
| **`fot_multiplier` (налоги работодателя)** | ```api/engine.py:36``` DEFAULTS['fot_multiplier']=1.175; ```api/engine.py:387, 445, 534, 842``` — применение | Совпадают | ```config/constants.yaml``` → `fot_multiplier: 1.175` | `engine.py:36` — читать из yaml |
| **Дефолтный маркетинг** | ```api/main.py:485``` (50 000); ```api/gen_finmodel.py:102``` (50 000); ```api/engine.py:2072``` (```compute_block5_pnl``` — 100 000); ```api/report.py:125-129``` сценарии (0-15 / 30-80 / 80-150 тыс) | **Расхождение**: финмодель 50K, Block 5 100K | ```config/finmodel_defaults.yaml``` → `opex.marketing` | все места |
| **WACC** | ```api/main.py:497, 751```; ```api/gen_finmodel.py:113``` | Все 0.20 | ```config/finmodel_defaults.yaml``` → `wacc: 0.20` | — |
| **Горизонт финмодели** | ```api/main.py:474, 720+```; ```api/gen_finmodel.py:90``` | Все 36 месяцев | ```config/finmodel_defaults.yaml``` → `horizon_months: 36` | — |
| **Срок амортизации** | ```api/main.py:492```; ```api/gen_finmodel.py:109``` | Все 7 лет | ```config/finmodel_defaults.yaml``` → `amort_years: 7` | — |
| **Кредит по умолчанию** | ```api/main.py:78-79, 495-496```; ```api/gen_finmodel.py:111-112``` | Все 22% / 36 мес | ```config/finmodel_defaults.yaml``` → `credit: {rate: 0.22, term_months: 36}` | — |
| **OWNER_CLOSURE_POCKET** | ```api/engine.py:496``` | 200 000 ₸ | ```config/constants.yaml``` → `owner.closure_pocket_kzt: 200000` | `engine.py:496` |
| **OWNER_GROWTH_POCKET** | ```api/engine.py:497``` | 600 000 ₸ | ```config/constants.yaml``` → `owner.growth_pocket_kzt: 600000` | `engine.py:497` |
| **Соцплатежи ИП** | ```api/engine.py:508-510``` (`MRP_2026 * 50 * 0.22`) | Коэффициент 0.22 жёстко | ```config/constants.yaml``` → `owner.social_rate: 0.22`, `owner.social_base_mrp: 50` | `engine.py:508-510` |
| **Пороги вердикта Блок 1 (17/12)** | ```api/engine.py:1342-1344``` | green ≥17, yellow ≥12, иначе red | ```config/defaults.yaml``` → `block1_verdict_thresholds: [17, 12]` | `engine.py:1342-1344` |
| **Пороги score функций (capital/roi/breakeven/saturation/stress)** | ```api/engine.py:1154-1217``` | Разбросаны по отдельным функциям | ```config/defaults.yaml``` → `scoring_thresholds: {...}` | `engine.py:1154-1217` |
| **Прайс finmodel=9000 / bizplan=15000** | ```api/engine.py:2367-2377```; ```config/questionnaire.yaml``` `price_kzt`; ```CLAUDE.md``` | Совпадают | ```config/questionnaire.yaml``` (уже источник) | `engine.py:2367-2377` — читать из configs |

### E.2 Новые YAML-конфиги

**C1. `config/constants.yaml`** — жёсткие константы (2026)
Ключи:
```
mrp_2026: <число>
mzp_2026: <число>
subsistence_minimum_2026: <число>          # прожиточный минимум (для будущего)
nds_rate: <число>                          # 0.16
owner:
  closure_pocket_kzt: <число>
  growth_pocket_kzt: <число>
  social_rate: <число>                     # 0.22
  social_base_mrp: <число>                 # 50
  fot_multiplier: <число>                  # 1.175
taxes:
  default_tax_rate_pct: <число>            # 3
  fallback_tax_rate_pct: <число>           # 4 — когда город не найден в city_ud_rates
cities:
  - id: almaty
    name_rus: Алматы
    region_rus: "г. Алматы"
    type: megacity
    legacy_ids: [ALA, almaty]              # поддержка совместимости при миграции
  - id: astana
    ...
```

**C2. `config/defaults.yaml`** — расчётные дефолты QuickCheck
Ключи:
```
quick_check:
  default_seasonality: [12 чисел]
  scenario_coefficients:
    pessimistic: {traffic_k, check_k, rent_k}
    base:        {traffic_k, check_k, rent_k}
    optimistic:  {traffic_k, check_k, rent_k}
    stress:      {traffic_k, check_k, rent_k}    # отдельный набор для calc_stress_test
  rampup:
    months: 3
    start_pct: 0.5
  benchmarks:
    competitor_density_per_10k: 0.8              # Блок 1
    retail_density_per_10k: 0.75                 # Блок 3
  block1_verdict:
    thresholds: [17, 12]                          # green, yellow
  scoring_thresholds:
    capital:     [1.2, 0.95, 0.75]
    roi:         [0.45, 0.30, 0.15]
    breakeven_months: [6, 12, 18]
    saturation:  [0.6, 1.0, 1.5]
    stress_drop: [0.30, 0.50]
    city_population_tiers: [150000, 300000]
  work_days_in_month: 30
  work_days_unit_economics: 26
```

**C3. `config/finmodel_defaults.yaml`** — дефолты финмодели / bizplan
Ключи:
```
finmodel:
  entity_type: "ИП"
  tax_regime: "УСН"
  nds_payer: "Нет"
  horizon_months: 36
  check_med: <число>
  traffic_med: <число>
  work_days: 30
  growth:
    traffic_yr: 0.07
    check_yr: 0.08
    rent_yr: 0.10
    fot_yr: 0.08
    inflation_yr: 0.10
  cogs_pct: <число>
  loss_pct: <число>
  opex:
    rent: <число>
    utilities: <число>
    marketing: <число>
    consumables: <число>
    software: <число>
    other: <число>
  fot:
    fot_gross: <число>
    headcount: <число>
    multiplier: 1.175
  capex:
    default_kzt: <число>
    deposit_months: 2
    working_cap_kzt: <число>
    amort_years: 7
  credit:
    default_amount: 0
    rate: 0.22
    term_months: 36
  wacc: 0.20
  default_seasonality: [12 чисел]
```

---

## Раздел F — Унификация ID городов

### F.1 Найденные форматы идентификаторов

| Формат | Пример | Где встречается |
|---|---|---|
| Трёхбуквенный верхний регистр | `ALA`, `AST`, `SHY`, `AKT`, `SEM`, `URA`, `TAR`, `OSK`, `PAV`, `KOS`, `KZO`, `ATY`, `AKA`, `PET`, `KOK` | ```data/kz/01_cities.xlsx:Города``` (строки 5–19) |
| Верхний регистр латиницей, слитно | `ASTANA`, `ALMATY`, `SHYMKENT`, `AKTOBE`, `KARAGANDA`, `ATYRAU`, `AKTAU`, `KOSTANAY`, `PAVLODAR`, `SEMEY`, `USKAMAN`, `TARAZ`, `TURKESTAN`, `PETROPAVL`, `KOKSHETAU` | ```data/kz/05_tax_regimes.xlsx:city_ud_rates_2026``` |
| Нижний регистр, slug | `almaty`, `astana`, `atyrau`, `aktobe`, `karaganda`, `uralsk`, `ust_kamenogorsk`, `aktau`, `shymkent`, `pavlodar`, `kostanay`, `semey`, `taraz`, `petropavlovsk`, `kyzylorda` | ```api/engine.py:40-46``` (`CITY_CHECK_COEF`) |
| Нижний регистр, slug (другой) | `astana`, `almaty`, `shymkent`, `aktobe`, `karaganda`, `atyrau`, `pavlodar`, `kostanay`, `aktau`, `semey`, `uralsk`, `taldykorgan`, `turkestan`, `kokshetau`, `petropavl` | ```api/grant_bp.py:16-32``` (`CITY_DATA`) |
| Русское название | `"Алматы"`, `"Астана"`, … | ```api/engine.py:326``` (`get_competitors` — ключ 'кол_во' не числовой); HTML-ответ возвращает `city_name` |

### F.2 Несоответствия между наборами

| Город | `01_cities.xlsx` | `05_tax_regimes.xlsx` | `engine.py` CITY_CHECK_COEF | `grant_bp.py` CITY_DATA |
|---|---|---|---|---|
| Алматы | `ALA` | `ALMATY` | `almaty` | `almaty` |
| Астана | `AST` | `ASTANA` | `astana` | `astana` |
| Шымкент | `SHY` | `SHYMKENT` | `shymkent` | `shymkent` |
| Актобе | `AKT` | `AKTOBE` | `aktobe` | `aktobe` |
| Караганда | `KAR` нет — отсутствует | `KARAGANDA` | `karaganda` | `karaganda` |
| Атырау | `ATY` | `ATYRAU` | `atyrau` | `atyrau` |
| Актау | `AKA` | `AKTAU` | `aktau` | `aktau` |
| Костанай | `KOS` | `KOSTANAY` | `kostanay` | `kostanay` |
| Павлодар | `PAV` | `PAVLODAR` | `pavlodar` | `pavlodar` |
| Семей | `SEM` | `SEMEY` | `semey` | `semey` |
| Усть-Каменогорск | `OSK` | `USKAMAN` | `ust_kamenogorsk` | — (отсутствует) |
| Тараз | `TAR` | `TARAZ` | `taraz` | — (отсутствует) |
| Туркестан | — | `TURKESTAN` | — | `turkestan` |
| Петропавловск | `PET` | `PETROPAVL` | `petropavlovsk` | `petropavl` |
| Кокшетау | `KOK` | `KOKSHETAU` | — | `kokshetau` |
| Кызылорда | `KZO` | — | `kyzylorda` | — |
| Уральск | `URA` | — | `uralsk` | `uralsk` |
| Талдыкорган | — | — | — | `taldykorgan` |

Ни один набор не содержит все города. Город «Караганда» есть в трёх наборах, но в `01_cities.xlsx` отсутствует (в строках 5–19 нет `KAR`/`KRG`). Уральск есть в `01_cities.xlsx`, `engine.py`, `grant_bp.py`, но нет в `05_tax_regimes.xlsx`. Это значит — на запрос с city_id=`URA` `get_city_tax_rate` возвращает fallback 4%.

### F.3 Канонический формат

Формат: `lower_snake_latin` (нижний регистр латиницей, разделитель `_`). Основан на варианте из `engine.py:CITY_CHECK_COEF`, но с корректировками:

- `petropavl` (5 символов) вместо `petropavlovsk` — совместимо с `05_tax_regimes.xlsx`
- `oskemen` вместо `ust_kamenogorsk` — исторический казахский топоним, короче, совпадает с ISO-подобной формой

### F.4 Маппинг старый_ID → канонический_ID

| canonical_id | 01_cities.xlsx | 05_tax_regimes.xlsx | engine.py CITY_CHECK_COEF | grant_bp.py CITY_DATA |
|---|---|---|---|---|
| `almaty` | `ALA` | `ALMATY` | `almaty` | `almaty` |
| `astana` | `AST` | `ASTANA` | `astana` | `astana` |
| `shymkent` | `SHY` | `SHYMKENT` | `shymkent` | `shymkent` |
| `aktobe` | `AKT` | `AKTOBE` | `aktobe` | `aktobe` |
| `karaganda` | — | `KARAGANDA` | `karaganda` | `karaganda` |
| `atyrau` | `ATY` | `ATYRAU` | `atyrau` | `atyrau` |
| `aktau` | `AKA` | `AKTAU` | `aktau` | `aktau` |
| `kostanay` | `KOS` | `KOSTANAY` | `kostanay` | `kostanay` |
| `pavlodar` | `PAV` | `PAVLODAR` | `pavlodar` | `pavlodar` |
| `semey` | `SEM` | `SEMEY` | `semey` | `semey` |
| `oskemen` | `OSK` | `USKAMAN` | `ust_kamenogorsk` | — |
| `taraz` | `TAR` | `TARAZ` | `taraz` | — |
| `turkestan` | — | `TURKESTAN` | — | `turkestan` |
| `petropavl` | `PET` | `PETROPAVL` | `petropavlovsk` | `petropavl` |
| `kokshetau` | `KOK` | `KOKSHETAU` | — | `kokshetau` |
| `kyzylorda` | `KZO` | — | `kyzylorda` | — |
| `uralsk` | `URA` | — | `uralsk` | `uralsk` |
| `taldykorgan` | — | — | — | `taldykorgan` |

### F.5 Файлы, которые надо править

| Файл | Что именно править |
|---|---|
| ```config/constants.yaml``` (новый) | Создать секцию `cities:` c каноническими ID, русскими именами, демографией, `legacy_ids: [...]` |
| ```data/kz/01_cities.xlsx``` | В колонке `city_id` заменить `ALA → almaty`, `AST → astana`, `SHY → shymkent`, `AKT → aktobe`, `SEM → semey`, `URA → uralsk`, `TAR → taraz`, `OSK → oskemen`, `PAV → pavlodar`, `KOS → kostanay`, `KZO → kyzylorda`, `ATY → atyrau`, `AKA → aktau`, `PET → petropavl`, `KOK → kokshetau`. Добавить строку `karaganda` (её сейчас нет) |
| ```data/kz/05_tax_regimes.xlsx``` лист `city_ud_rates_2026` | Переименовать `ASTANA → astana`, `ALMATY → almaty` и далее. Добавить строки `uralsk`, `kyzylorda`, `taldykorgan` (их сейчас нет) |
| ```data/kz/11_rent_benchmarks.xlsx``` лист `Калькулятор для движка` | В колонке `city_id` заменить `ALA → almaty` и т.д. (использует тот же формат, что `01_cities.xlsx`) |
| ```data/kz/14_competitors.xlsx``` лист `Конкуренты по городам` | Аналогично |
| ```api/engine.py:40-46``` `CITY_CHECK_COEF` | Удалить словарь. Читать коэффициенты из `config/constants.yaml` → `cities[i].check_coef` |
| ```api/engine.py:297-312``` `get_city_tax_rate` / `get_rent_median` | Работа по каноническому ID; legacy-ID поддерживать через map в constants.yaml |
| ```api/engine.py:326``` `get_competitors` (ключ `кол_во`) | Не ID-специфично, но стоит переименовать ключи на латиницу (см. раздел G.2) |
| ```api/grant_bp.py:16-32``` `CITY_DATA` | Удалить словарь. Читать из `config/constants.yaml` → `cities[i]` |
| ```api/engine.py:131-156``` `NICHE_NAMES` | Убрать (канон — `niches.yaml`) |
| ```api/pdf_gen.py:150-163``` `NICHE_NAMES` | Убрать |
| ```products/qc-v3.html``` | В JS нет hardcoded city_id (city_id приходит с бэкенда через `GET /cities`), кроме fallback `'OTHER' → 'ALMATY'` на ```qc-v3.html:809```. Заменить на `'almaty'` после миграции |
| ```products/app.html``` | Аналогично: `city_id` идёт с `GET /cities`. Проверить внутренние fallback'ы |

### F.6 Пометка о взаимной совместимости

В `config/constants.yaml` для каждой `city` указать поле `legacy_ids: [ALA, almaty, AST, ...]` — при разборе запроса `POST /quick-check` фронт может присылать старый ID во время переходного периода. Нормализация на входе сервера: если `city_id in legacy_ids` — маппим на canonical_id перед дальнейшей работой.

---

## Раздел G — Баги в `engine.py`

### G.1 `compute_block9_risks` — regex не матчит заголовки

**Текущий regex** (```api/engine.py:1987```):
```python
m = re.search(r'#+\s*(Риски|Подводные камни|Причины провала)[\s\S]*?(?=\n#+ |\Z)', content, re.IGNORECASE)
```

Ищет заголовки `## Риски`, `## Подводные камни`, `## Причины провала`.

**Фактические заголовки H2 в insight-файлах** (выборка через grep):

```
knowledge/niches/OPTICS_insight.md:
  # Инсайты: Оптика
  ## Ключевые принципы управления
  ## Типичные ошибки новичков
  ## Экономика и юнит-экономика
  ## Операционные нюансы
  ## Маркетинг и привлечение клиентов
  ## Финансовые риски и ловушки    ← релевантно
  ## Что отличает выживших от закрывшихся
  ## Красные флаги                 ← релевантно

knowledge/niches/BUILDMAT_insight.md, CANTEEN_insight.md, WATERPLANT_insight.md,
FURNITURE_insight.md, MEATSHOP_insight.md, ACCOUNTING_insight.md, FRUITSVEGS_insight.md,
REPAIR_PHONE_insight.md, SUSHI_insight.md, SUGARING_insight.md — структура совпадает:
  ## Финансовые риски и ловушки
  ## Что отличает выживших от закрывшихся
  ## Красные флаги (когда лучше не открывать)

knowledge/niches/REALTOR_insight.md — начинается с "# Агентство недвижимости — Инсайт-файл ZEREK",
но внутренние H2 — тех же названий (не перепроверен целиком).

knowledge/niches/PVZ_insight.md — начинается с "# Пункт выдачи заказов (ПВЗ) — Отраслевой обзор" —
возможно, другая структура. Надо перепроверить перед финализацией regex.
```

Итог: реальные заголовки — `## Финансовые риски и ловушки`, `## Красные флаги`, `## Красные флаги (когда лучше не открывать)`, `## Типичные ошибки новичков`. Текущий regex не находит ни один из них.

**Предлагаемый regex:**
```python
m = re.search(
    r'#+\s*(Финансовые риски и ловушки|Красные флаги(?:\s*\([^)]*\))?|Типичные ошибки новичков|Риски|Подводные камни|Причины провала)[\s\S]*?(?=\n#+\s|\Z)',
    content,
    re.IGNORECASE,
)
```

Если найдено несколько релевантных секций — собрать из всех (отдельный `re.finditer`, не `re.search`), и из каждой взять пункты формата `- **Заголовок**: текст`, затем обрезать до 5 в сумме.

Пометка: два файла (`PVZ_insight.md`, `REALTOR_insight.md`) имеют нестандартный H1. Перед правкой стоит grep `^## ` по всем 43 файлам и зафиксировать полный перечень используемых H2 — структура скорее всего варьируется незначительно, но это надо подтвердить.

### G.2 `compute_block1_verdict._score_saturation` — ключ не тот

**Что ожидает `_score_saturation`** (```api/engine.py:1184-1194```):
- вызывается из ```api/engine.py:1332``` с первым аргументом `competitors_count` (int)
- `competitors_count` собирается на ```api/engine.py:1316-1319```:
```python
competitors_count = 0
comp_block = risks_block.get('competitors') or {}
if isinstance(comp_block, dict):
    competitors_count = _safe_int(comp_block.get('competitors_count')) or _safe_int(comp_block.get('n'))
```
Таким образом, функция ждёт в `risks_block['competitors']` один из ключей **`competitors_count`** или **`n`**.

**Что реально возвращает `get_competitors`** (```api/engine.py:314-326```):
```python
return {
    "уровень": sat,             # int 1-5
    "сигнал": signals.get(sat,""),
    "кол_во": row.get("Кол-во конкурентов (оценка)",""),   # ← строка из xlsx ("20-30", "н/д" и т.п.)
    "лидеры": row.get("Лидеры рынка",""),
}
```

Ни `competitors_count`, ни `n` не создаются. Ключ с числом конкурентов называется `кол_во`, но его значение — строка (не int), потому что в `14_competitors.xlsx` поле «Кол-во конкурентов (оценка)» — обычно диапазон типа «20-30». Отдельное числовое поле — `"Кол-во на 10 000 жителей"`, оно в выдачу `get_competitors` не попадает.

Тот же ключ ищется в `compute_block3_market` (```api/engine.py:1424, 1468```) — те же значения `competitors_count` и `n`; там оба раза возвращают 0.

**План правки**:
1. В `get_competitors` добавить числовое поле `"competitors_count"`:
```python
raw = row.get("Кол-во конкурентов (оценка)", "")
try:
    n = int(str(raw).split("-")[0]) if raw else 0   # берём нижнюю границу диапазона
except Exception:
    n = 0
return {
    "уровень": sat,
    "сигнал": signals.get(sat, ""),
    "кол_во": raw,                              # оставляем для UI
    "competitors_count": n,                     # ← добавить
    "density_per_10k": _safe_float(row.get("Кол-во на 10 000 жителей"), 0.0),
    "лидеры": row.get("Лидеры рынка", ""),
}
```
2. В `_score_saturation` / `compute_block3_market` использовать `density_per_10k` напрямую (он уже в xlsx как корректный float), без повторного деления `count / (pop/10000)`. Либо продолжать считать через `competitors_count`, но брать его как int.
3. Вернуть новое поле в результат API, обновить `render_report_v4` в `api/report.py` (проверить — там тоже может быть зависимость от ключа 'кол_во').

### G.3 Налоговые ставки УСН — `CLAUDE.md` vs `05_tax_regimes.xlsx`

**`CLAUDE.md`** (раздел «Налоги КЗ 2026»):
> Ставки УСН: Астана 3%, Алматы 3%, Шымкент 2%, Актобе 3%, Караганда 2%, Атырау 2%, Павлодар 3%, Костанай 3%, УК 2%, Уральск 3%

**`05_tax_regimes.xlsx:city_ud_rates_2026`**:

| city_id | city_name | rate |
|---|---|---|
| ASTANA | Астана | 3 |
| ALMATY | Алматы | 3 |
| SHYMKENT | Шымкент | 2 |
| AKTOBE | Актобе | 3 |
| KARAGANDA | Караганда | 3 |
| ATYRAU | Атырау | 3 |
| AKTAU | Актау | 3 |
| KOSTANAY | Костанай | 3 |
| PAVLODAR | Павлодар | 3 |
| SEMEY | Семей | 3 |
| USKAMAN | Усть-Каменогорск | 3 |
| TARAZ | Тараз | 3 |
| TURKESTAN | Туркестан | 2 |
| PETROPAVL | Петропавловск | 3 |
| KOKSHETAU | Кокшетау | 3 |

**Сравнительная таблица**:

| Город | CLAUDE.md | xlsx | Совпадает? |
|---|---|---|---|
| Астана | 3% | 3% | да |
| Алматы | 3% | 3% | да |
| Шымкент | 2% | 2% | да |
| Актобе | 3% | 3% | да |
| **Караганда** | **2%** | **3%** | **нет** |
| **Атырау** | **2%** | **3%** | **нет** |
| **УК (Усть-Каменогорск)** | **2%** | **3%** | **нет** |
| Павлодар | 3% | 3% | да |
| Костанай | 3% | 3% | да |
| Уральск | 3% | — (отсутствует) | не сравнимо |

**Опции решения** (финализирует владелец):
- (а) подтянуть `CLAUDE.md` к `xlsx` — принять Караганда/Атырау/УК = 3%. Основание: `xlsx` является каноничным источником для движка и содержит колонки `maslikhat_decision` и `decision_date` с конкретными решениями. Для Караганда/Атырау/Актау/УК/Семей/Тараз в xlsx стоит пометка «Уточнить».
- (б) подтянуть `xlsx` к `CLAUDE.md` — выставить 2% для Караганда/Атырау/УК. Основание: если эти ставки подтверждены маслихатами (нужны ссылки на решения).
- (в) дождаться уточнения ставок из официальных источников (пометки «Уточнить» в `xlsx`) перед финальным решением.

---

## Раздел H — Резюме

### H.1 Файлы и папки к удалению

| Путь | Пометка |
|---|---|
| ```/engine/__init__.py``` | сломанный пакет-заглушка |
| ```/engine/gemini_rag.py``` | дубликат `api/gemini_rag.py` |
| ```/engine/run_test.py``` | старый тестовый скрипт |
| ```/engine/``` (каталог) | после удаления трёх файлов выше |
| ```/data/common/.gitkeep``` + каталог ```/data/common/``` | по плану реструктуризации (пусто) |
| ```/knowledge/niches/``` | после переноса insight-файлов в `knowledge/kz/niches/` |
| ```products/quick-check-v2.html``` | legacy UI, ссылок нет |
| ```products/quick-check.legacy.html``` | ещё более старый legacy UI |
| ```products/app.html``` | **под вопросом** (см. раздел A2 и H.5) |
| ```products/index.html``` | **под вопросом** (см. раздел A5 и H.5) |
| ```.DS_Store``` (3 файла) | macOS мусор |

### H.2 Python-файлы, которые надо будет править

| Файл | Что изменить в одной строке |
|---|---|
| ```api/engine.py``` | Импорт констант из yaml; убрать `CITY_CHECK_COEF`, `NICHE_NAMES`, `NICHE_ICONS`, `MRP_2026`, `MZP_2026`, `DEFAULTS`; починить `get_competitors` и regex в `compute_block9_risks`; путь к insight-файлам в `compute_block9_risks:1895-1896` |
| ```api/main.py``` | Удалить дублирующийся блок дефолтов `_compute_finmodel_data:473-497`; ввести загрузку `finmodel_defaults.yaml`; добавить фильтр `available=true` в `/niches`, `/formats`, `/formats-v2`, `/niche-survey`, `/quickcheck-survey`, `/quick-check` |
| ```api/gen_finmodel.py``` | Удалить дублирующийся блок `defaults:85-113` и сезонность `:82`; читать из `finmodel_defaults.yaml` |
| ```api/report.py``` | Вычистить `cogs_pct=0.35` дефолт, `eq_notes` словарь и пороги health на `config/defaults.yaml` |
| ```api/pdf_gen.py``` | Удалить `NICHE_NAMES:150-163`, читать из `db.configs["niches"]` |
| ```api/grant_bp.py``` | Удалить `MRP_2026:9` и `CITY_DATA:16-32`; читать из `config/constants.yaml` |
| ```api/gemini_rag.py``` | Обновить путь к insight-файлам после переноса в `knowledge/kz/niches/` |

### H.3 Новые конфиги

| Файл | Назначение |
|---|---|
| ```config/constants.yaml``` | Константы 2026: МРП, МЗП, НДС, канонический список городов, параметры ИП, налоговые дефолты |
| ```config/defaults.yaml``` | Расчётные дефолты QuickCheck: сезонность, коэффициенты сценариев, скоринговые пороги, benchmarks |
| ```config/finmodel_defaults.yaml``` | Дефолты финансовой модели: горизонт, амортизация, OPEX, ФОТ, CAPEX, кредит, WACC |

### H.4 Риски — что может сломаться, что проверить

1. **Mini App из Telegram**. Если решено удалить `app.html` или перенаправить `index.html`, проверить: BotFather → `@zerekai_bot` → Web App URL, `CLAUDE.md:78, 100`. После любой миграции ID городов (раздел F) — проверить, что `qc-v3.html` и `app.html` корректно получают новый city_id в `POST /quick-check`.
2. **52 lesson-файла Academy**. Любое удаление `app.html` требует массовой правки `academy/kz/junior/*.html`, `academy/kz/startup/*.html`, `academy/templates/lesson_template.html`.
3. **Wiki-обзоры**. Все 42 `wiki/kz/ZEREK_*.html` содержат кнопку CTA на Mini App — проверить, не бьют ли на `products/app.html` и не ломаются ли ссылки.
4. **PDF-генератор** (`api/pdf_gen.py`). При выносе `NICHE_NAMES` в yaml — сгенерировать тестовый PDF на одной нише и проверить, что русское имя корректно подставляется.
5. **Финмодель xlsx**. После переноса дефолтов в yaml — сгенерировать тестовый `finmodel.xlsx` через `POST /finmodel` и сравнить значения с текущей версией (целостность PARAM_MAP в `gen_finmodel.py:15-53`).
6. **Grant BP**. После замены `CITY_DATA` в `grant_bp.py` — сгенерировать .docx по всем 15 городам, проверить подстановку `avg_wage` и `region`.
7. **Endpoint контрактов**. Фронт (и `qc-v3.html`, и `app.html`) ожидает определённые поля в ответе. Изменения в `/niches` (добавление `available`) не должны ломать текущий рендер — лучше возвращать все ниши с `available` полем, не скрывая их в массиве.
8. **manifest.json**. При удалении `icon-192.png` — убедиться, что в `manifest.json` не осталось ссылок на этот файл (проверить перед коммитом).
9. **compute_block9 новый regex**. После правки regex убедиться, что для всех 43 insight-файлов тест «есть ли хоть одна секция в матче» проходит; для ниш без insight (COFFEE — отсутствует) — используется generic.
10. **Обратная совместимость city_id**. Во время переходного периода — поддерживать легаси ID через `legacy_ids` в `constants.yaml`, чтобы кешированные в Telegram WebApp значения не сломали `POST /quick-check`.

### H.5 Открытые вопросы к владельцу

1. **Какой UI — канонический Mini App?** `qc-v3.html` или `app.html`? В `CLAUDE.md` указаны два разных URL (`:21` → `products/quick-check.html` → qc-v3; `:78, :100` → `products/index.html` → app.html). Если канон — `qc-v3.html`, удаляем `app.html` с каскадом правок в 52 lesson-файлах Academy + CLAUDE.md.
2. **Что делать с `products/index.html`?** Оставить как редирект (тогда куда — на `qc-v3.html` или `app.html`) или удалить? Выбор зависит от ответа на (1).
3. **Какой источник УСН считать каноничным?** `CLAUDE.md` (Караганда/Атырау/УК = 2%) или `05_tax_regimes.xlsx:city_ud_rates_2026` (все = 3%)? См. раздел G.3.
4. **Судьба `api/gen_finmodel.py`**. Если `app.html` удаляется — эндпоинт `POST /finmodel` остаётся (вызывается из `qc-v3.html`?). Проверить: в `qc-v3.html` в текущем виде (на момент коммита `784196e`) нет `apiPost('/finmodel')`. Значит `POST /finmodel` вызывается только из `app.html` (см. `app.html:3375` — `POST /quick-check`, но отдельно на `/finmodel` надо grep'нуть). Если `gen_finmodel.py` не вызывается из `qc-v3.html`, его можно заморозить и не рефакторить до того, как финмодель появится в `qc-v3`.
5. **Унификация niche_id между `niches.yaml` и xlsx**. Что выбрать: (а) переименовать xlsx-файлы под yaml (`niche_formats_NAIL.xlsx` → `niche_formats_MANICURE.xlsx`, `PHARMA` → `PHARMACY`, `TIRE` → `TIRESERVICE`, `WATER` → `WATERPLANT`, `CYBERCLUB` → `COMPCLUB`), или (б) наоборот, скорректировать yaml под xlsx (`MANICURE` → `NAIL` и т.д.)? Раздел D.1 и D.2 требуют выбора.
6. **Судьба `_yt_videos.json`**. Перенести в `/knowledge/kz/niches/` или в `/knowledge/common/`? И кто его потребитель — Academy, Wiki, или оба? См. раздел C.3.6.
7. **Использовать ли `20_scenario_coefficients.xlsx` / `21_opex_benchmarks.xlsx` / `22_staff_scaling.xlsx` / `19_inflation_by_niche.xlsx`?** Все четыре содержат подготовленные данные, но не подключены в движке. Подключать их в рамках этой уборки или отдельной фазой?

---

## Дополнительные находки

### N.1 Расхождение сезонности между `finmodel_report.py` и остальным кодом

`api/finmodel_report.py:628` содержит сезонность `[0.85, 0.80, 0.90, 1.00, 1.05, 0.90, 0.85, 0.80, 0.95, 1.10, 1.15, 1.20]` — это «фолбэк» для демо-рендера и он отличается от канона в `main.py`/`gen_finmodel.py`. При миграции на yaml всех трёх дефолтов привести к одному значению и использовать только в эмуляции демо.

### N.2 `api/gemini_rag.py` содержит три функции, но в плане реструктуризации упоминается только одна

Помимо `_read_insight_file`, файл содержит `extract_niche_risks` (работающий парсер с JSON-схемой Gemini) и `get_ai_interpretation` (дубликат простейшей функции из `engine/gemini_rag.py`). Первый — активно используется в `pdf_gen.py`; второй — в `chat_endpoint`. При удалении `/engine/` второй функции достаточно живёт в `api/gemini_rag.py`, дублер не нужен.

### N.3 Файл `products/quick-check.html` формально — редиректор

```products/quick-check.html``` (12 строк) — meta-refresh на `qc-v3.html`. Он не legacy, это единственная рабочая точка входа Mini App из BotFather согласно `CLAUDE.md:21`. Не удалять, не менять.

### N.4 В `api/main.py:809` и `app.html:3128` разные контракты цен

В `questionnaire.yaml` прайс Quick Check = 5000, FinModel = 9000, BizPlan = 15000. В `engine.py:2367-2377` (блок 10 up-sell) — те же цифры. При переносе на каноничный yaml (раздел E) стоит добавить явную проверку консистентности между `questionnaire.yaml` и `engine.py` через импорт.

### N.5 CLAUDE.md vs реальность — 33 ниши vs 57 yaml

CLAUDE.md утверждает «33 ниши», перечисляет конкретный набор. `config/niches.yaml` содержит 57 ниш. Список ниш «по xlsx» = 33 файла (совпадает с CLAUDE.md). После ответа на H.5.5 (унификация ID) обновить CLAUDE.md, чтобы не ссылаться на магические числа.

### N.6 `config/archetypes.yaml` содержит `finmodel_operational_questions`, которые код не читает

Секция `archetypes.{A-F}.finmodel_operational_questions` готова (по 5-6 вопросов на архетип), но `api/engine.py` её не парсит. При расширении анкеты финмодели из `questionnaire.yaml` — подключить и это поле.

### N.7 `data/2gis_competitors.csv` — файла нет в репо, но он упоминается в `questionnaire.yaml:59, 375`

Если `questionnaire.yaml` будет признан каноничным источником анкеты (раздел E), поле `source: "data/2gis_competitors.csv"` надо либо убрать, либо заменить на реальный источник (например, `14_competitors.xlsx`).

### N.8 Дублирующийся `readme` в корне

Корневой `README.md` (7 байт) — фактически пустой. При уборке можно либо удалить, либо заполнить нормальным описанием (точно не делать это в рамках текущей фазы 1).
