# ZEREK — Архитектура

> Слоистая архитектура ZEREK Quick Check / FinModel / BizPlan.
> Источник истины формул — `specs/QC_Calculation_Spec.md`.
>
> Версия: **2.0** (финал рефакторинга, Этап 8 завершён, 2026-04-23).

---

## 1. Принципы

1. **Single source of truth** — каждая сущность хранится в одном месте.
2. **Разделение слоёв** — данные ≠ бизнес-логика ≠ рендер ≠ платформа.
3. **Сервис-ориентированность** — общие сервисы используются всеми калькуляторами.
4. **Калькулятор возвращает данные, не вёрстку** — рендер отдельно.
5. **Ниша описывается одним YAML-файлом** — внешние данные парсятся отдельно.
6. **Никаких фолбэков, скрывающих баги** — валидация на входе, явная ошибка вместо «100К/мес по умолчанию».
7. **Регрессия обязательна** — после каждого этапа API-ответ бит-в-бит совпадает с baseline.

---

## 2. Папочная структура (финал)

```
ZEREK/
├── api/
│   ├── config.py                       # 32 LOC — общие константы (LOCATION_TYPES_META)
│   ├── engine.py                       # 932 LOC — ядро (ZerekDB, run_quick_check_v3,
│   │                                   #   константы из YAML config, YAML-overlay для get_format_row)
│   ├── main.py                         # 621 LOC — FastAPI endpoints, file_store, /chat
│   ├── report.py                       # 10 LOC — re-export render_report_v4 для legacy
│   ├── pdf_gen.py                      # 10 LOC — re-export для legacy импортов
│   ├── gen_finmodel.py                 # xlsx-генератор финмодели (без изменений)
│   ├── finmodel_report.py              # HTML-отчёт финмодели (без изменений)
│   ├── grant_bp.py                     # .docx грант-БП (без изменений)
│   ├── gemini_rag.py                   # Gemini AI интеграция (без изменений)
│   │
│   ├── loaders/                        # 865 LOC — чтение данных
│   │   ├── city_loader.py              # 80 LOC — 01_cities.xlsx + city_id legacy
│   │   ├── tax_loader.py               # 64 LOC — 05_tax_regimes.xlsx
│   │   ├── rent_loader.py              # 50 LOC — 11_rent_benchmarks.xlsx
│   │   ├── competitor_loader.py        # 82 LOC — 14_competitors.xlsx
│   │   ├── content_loader.py           # 74 LOC — failure/permits/insight.md
│   │   └── niche_loader.py             # 720 LOC — niches xlsx + survey config + YAML overlay
│   │
│   ├── services/                       # 2 532 LOC — бизнес-логика
│   │   ├── pricing_service.py          # 49 LOC — соцплатежи ИП КЗ 2026
│   │   ├── seasonality_service.py      # 170 LOC — ramp+season + first_year_chart + Block season
│   │   ├── economics_service.py        # 870 LOC — P&L, payback, breakeven, Block 4/5/6
│   │   ├── stress_service.py           # 116 LOC — Block 8 от зрелого
│   │   ├── scenario_service.py         # 61 LOC — 3 сценария
│   │   ├── market_service.py           # 107 LOC — Block 3 (HOME-note, насыщенность)
│   │   ├── risk_service.py             # 229 LOC — Block 9 (insight.md, HOME-specific)
│   │   ├── action_plan_service.py      # 351 LOC — Block 10 (green/yellow/red)
│   │   └── verdict_service.py          # 388 LOC — Block 1 светофор + 8 score-ов
│   │
│   ├── calculators/                    # 702 LOC — фасады продуктов
│   │   ├── quick_check.py              # 285 LOC — Quick Check $10 (главный фасад)
│   │   ├── finmodel.py                 # 388 LOC — FinModel $20
│   │   └── bizplan.py                  # 29 LOC — заглушка (BizPlan TBD)
│   │
│   ├── renderers/                      # 1 988 LOC — UI-форматирование
│   │   ├── quick_check_renderer.py     # 618 LOC — render_for_api + Block 2 + helpers
│   │   └── pdf_renderer.py             # 1370 LOC — PDF (через ReportLab)
│   │
│   ├── validators/                     # 94 LOC — валидация входов
│   │   └── input_validator.py          # 94 LOC — QuickCheckRequest (Pydantic)
│   │
│   └── models/                         # 741 LOC — TypedDict схемы (документация)
│       ├── block.py                    # 352 LOC — TypedDict для каждого блока
│       ├── calc_result.py              # 232 LOC — CalcResult (выход calculator)
│       └── result.py                   # 110 LOC — QuickCheckResult (выход API)
│
├── data/
│   ├── niches/                         # YAML по нишам (Этап 7)
│   │   └── MANICURE_data.yaml          # 648 LOC — первая ниша на YAML (4 формата)
│   ├── kz/                             # 19 xlsx файлов (БНС, налоги, аренда, ниши)
│   ├── content/                        # placeholder (wiki, insights — пока в knowledge/)
│   └── external/                       # placeholder
│
├── tests/
│   ├── unit/                           # 96 unit-тестов
│   │   ├── test_pricing_service.py     # 5 тестов
│   │   ├── test_seasonality_service.py # 10 тестов
│   │   ├── test_economics_service.py   # 10 тестов
│   │   ├── test_stress_service.py      # 5 тестов
│   │   ├── test_scenario_service.py    # 7 тестов
│   │   ├── test_market_service.py      # 5 тестов
│   │   ├── test_risk_service.py        # 6 тестов
│   │   ├── test_action_plan_service.py # 6 тестов
│   │   ├── test_verdict_service.py     # 9 тестов
│   │   ├── test_quick_check_renderer.py # 15 тестов
│   │   ├── test_input_validator.py     # 9 тестов
│   │   └── test_yaml_loader.py         # 16 тестов
│   ├── integration/                    # 12 integration-тестов
│   │   └── test_quick_check.py         # QuickCheckCalculator end-to-end
│   ├── fixtures/                       # baseline JSON (gitignored)
│   └── local/regress.py                # локальная регрессия (TestClient)
│
├── docs/
│   ├── refactor_history/               # архив *_NOTES.md раундов v2/v3 (gitignore)
│   └── ADDING_NEW_NICHE.md             # как добавить нишу через YAML
│
├── config/                             # YAML-конфиги (constants, defaults, niches…)
├── knowledge/                          # insights для RAG и Block 9
├── templates/                          # шаблоны (finmodel xlsx, bizplan docx)
├── products/                           # frontend Mini App (qc-v3.html, app.html)
├── docs/
│   ├── ARCHITECTURE.md                 # этот файл
│   ├── DESIGN_CONTEXT.md               # users / JTBD / тон
│   ├── ADDING_NEW_NICHE.md             # как добавить нишу
│   ├── audit_history/                  # архив аудитов (2026-04-21, 2026-04-29)
│   ├── context/                        # 12 контекстных документов проекта
│   └── specs/
│       └── QC_Calculation_Spec.md      # спека расчётов
├── CLAUDE.md                           # навигатор для Claude
└── README.md
```

**Total api/ code: ~7 200 LOC** (vs 5 171 LOC до Этапа 0).

---

## 3. Поток выполнения Quick Check

```
1. POST /quick-check {city_id, niche_id, format_id, capital, start_month, …}
        ↓
2. validators/input_validator.QuickCheckRequest
   - Pydantic типы
   - capital >= 0, qty >= 1, area_m2 >= 0
        ↓
3. calculators/quick_check.QuickCheckCalculator(db).run(req):
   ├── _validate_and_resolve_cls (start_month, niche_available, HOME marketing)
   ├── _normalize_params (HOME/SOLO → founder_works=True, ent_role default)
   ├── _compute_base → engine.run_quick_check_v3(...) — главный движок
   │     ├── loaders.city_loader (city, check_coef, normalize)
   │     ├── loaders.tax_loader (city_tax_rate)
   │     ├── loaders.rent_loader (rent_median)
   │     ├── loaders.competitor_loader (get_competitors)
   │     ├── loaders.content_loader (failure_pattern, permits)
   │     ├── loaders.niche_loader (_get_canonical_format_meta + YAML overlay)
   │     ├── services.economics_service (calc_cashflow, calc_breakeven,
   │     │     calc_payback, calc_owner_economics, calc_closure_growth_points)
   │     └── services.scenario_service.compute_3_scenarios
   ├── pnl_aggregates ← services.economics_service.compute_pnl_aggregates
   └── _overlay_blocks (block1..10):
       ├── services.verdict_service.compute_block1_verdict
       ├── renderers.quick_check_renderer.compute_block2_passport
       ├── services.market_service.compute_block3_market
       ├── services.economics_service.compute_block4_unit_economics
       ├── services.economics_service.compute_block5_pnl
       │     + services.seasonality_service.compute_first_year_chart
       ├── services.economics_service.compute_block6_capital
       ├── services.seasonality_service.compute_block_season
       ├── services.stress_service.compute_block8_stress_test
       ├── services.risk_service.compute_block9_risks
       └── services.action_plan_service.compute_block10_next_steps
        ↓
4. renderers/quick_check_renderer.render_for_api(calc_result):
   ├── render_report_v4 → legacy block_1..block_12 (для PDF)
   └── копирует block1..block10 + block_season + user_inputs из calc_result
        ↓
5. main.py: clean(report) → JSON → клиент
        ↓
6. Mini App qc-v3.html → визуализация
```

---

## 4. Граф зависимостей

```
endpoint (main.py)
    ↓
validator → calculator → renderer
                ↓
              services → loaders
                ↓
              config (константы)
```

Правила:
- Loaders НЕ знают про services/calculators/renderers/main.
- Services используют loaders + другие services (через explicit imports).
- Calculator оркестрирует всё. Не знает про renderer (renderer вызывает endpoint).
- Renderer берёт calc_result, ничего не считает (кроме форматирования и compute_block2_passport — паспорт это трансформация, не расчёт).
- main.py — тонкий слой эндпоинтов. Бизнес-логики нет.

---

## 5. YAML-first для ниш (Этап 7)

`data/niches/{NICHE}_data.yaml` — источник правды для нишевых данных.

Подключение через `loaders.niche_loader.overlay_yaml_on_xlsx`:
- Не-MANICURE → xlsx без изменений.
- MANICURE_HOME → xlsx (калиброван за 7 раундов, baseline).
- MANICURE_SOLO/STANDARD/PREMIUM → YAML overlay (xlsx был некалиброван).

Подробности добавления новой ниши — `docs/ADDING_NEW_NICHE.md`.

---

## 6. Контракты слоёв

### Loaders
- Вход: id/параметры (city_id, niche_id, format_id, cls, loc_type)
- Выход: сырые данные (dict / list of dicts)
- Дефолты: НЕ падают, возвращают пустой dict/list

### Services
- Вход: loaded data + params
- Выход: вычисленные числа/структуры
- Инварианты:
  - Окупаемость — только через `economics_service.compute_unified_payback_months`
  - Зрелый P&L — только через `economics_service.compute_pnl_aggregates`
  - Стресс-тест — база = зрелый режим (без ramp+season)
  - Сезонность и ramp — только в первом году

### Calculators
- Вход: валидированный Input (QuickCheckRequest)
- Выход: `calc_result` dict (raw + block1..10 overlay), без legacy block_1..block_12

### Renderers
- Вход: `calc_result` от калькулятора
- Выход: финальный отчёт для UI (через `render_for_api`) или PDF/xlsx
- Чистая трансформация — никаких бизнес-вычислений

### Validators
- Вход: raw request body
- Выход: валидированный Input или HTTPException 400

---

## 7. Точки входа (FastAPI endpoints)

| Endpoint | Метод | Назначение |
|---|---|---|
| `/` | GET | Service info |
| `/health` | GET | Health check + список ниш |
| `/cities` | GET | Список городов КЗ |
| `/niches` | GET | Список ниш с флагом available |
| `/formats/{niche_id}` | GET | Форматы ниши |
| `/locations/{niche_id}` | GET | Типы локаций для ниши |
| `/classes/{niche_id}/{format_id}` | GET | Доступные классы (Эконом/Стандарт/...) |
| `/tax-rate/{city_id}` | GET | Налоговая ставка УСН по городу |
| `/configs` | GET | YAML-конфиги (niches/archetypes/locations/questionnaire) |
| `/formats-v2/{niche_id}` | GET | Форматы с расширенными полями (v1.0) |
| `/quickcheck-survey/{niche_id}` | GET | Полная анкета Quick Check |
| `/niche-config/{niche_id}` | GET | Адаптивная анкета v2 |
| `/niche-survey/{niche_id}` | GET | Survey по tier (express/finmodel) |
| `/products/{niche_id}/{format_id}` | GET | Продукты ниши |
| `/marketing/{niche_id}/{format_id}` | GET | Маркетинговые рекомендации |
| `/insights/{niche_id}/{format_id}` | GET | Инсайты |
| `/survey/{niche_id}` | GET | Анкета v3 (legacy) |
| `/niche-risks/{niche_id}` | GET | Структурированные риски через Gemini |
| **`/quick-check`** | POST | **Quick Check $10 — главный расчёт** |
| `/quick-check/pdf` | POST | PDF отчёт Quick Check |
| `/pdf-health` | GET | Диагностика PDF-генератора |
| **`/finmodel`** | POST | **FinModel $20 — генерация xlsx + HTML** |
| `/finmodel/report` | POST | HTML-отчёт по финмодели |
| `/grant-bp` | POST | Бизнес-план на грант 400 МРП (.docx) |
| `/download/{token}` | GET | Скачать сгенерированный файл |
| `/ai-chat`, `/test-gemini`, `/chat` | POST/GET | Gemini AI чат |

---

## 8. Метрики рефакторинга (Этап 0 → Этап 8)

### До рефакторинга (Этап 0)
| Файл | LOC |
|---|---|
| `api/engine.py` | 3 913 |
| `api/main.py` | 1 025 |
| `api/report.py` | 233 |
| **Total монолит** | **5 171** |

### После рефакторинга (Этап 8)
| Файл / папка | LOC |
|---|---|
| `api/engine.py` | 932 (−76%) |
| `api/main.py` | 621 (−39%) |
| `api/report.py` | 10 (−96%, re-export) |
| `api/pdf_gen.py` | 10 (−99%, re-export) |
| `api/config.py` | 32 (новый) |
| `api/loaders/` (6 файлов) | 865 |
| `api/services/` (10 файлов) | 2 532 |
| `api/calculators/` (3 файла) | 702 |
| `api/renderers/` (3 файла) | 1 988 |
| `api/validators/` (1 файл) | 94 |
| `api/models/` (4 файла) | 741 |
| **Total api/** | **~7 500 LOC** |

### Тесты
| Слой | Тестов |
|---|---|
| Unit (services/loaders/renderers/validators) | 96 |
| Integration (calculators) | 12 |
| Локальная регрессия (4 baseline) | 4/4 бит-в-бит |
| **Total** | **115 + 4 = 119 проверок** |

### Коммиты
- 46 refactor-коммитов (Этап 1 — Этап 8)
- + предыдущие коммиты репо

---

## 9. История этапов

- **Этап 0** (2026-04-22): Baseline + REFACTOR_PLAN.md + аудит 5 171 LOC.
- **Этап 1**: Структура папок, ARCHITECTURE.md, *_NOTES.md → docs/.
- **Этап 2**: 6 loaders (city/tax/rent/competitor/content/niche).
- **Этап 3**: 9 services (pricing/seasonality/economics/stress/scenario/market/risk/action_plan/verdict).
- **Этап 4**: 3 calculators (quick_check фасад, finmodel/bizplan stubs).
- **Этап 5**: 2 renderers (quick_check_renderer, pdf_renderer wrapper).
- **Этап 6**: validators (Pydantic) + models (TypedDict).
- **Этап 7**: YAML-first для MANICURE (overlay для SOLO/STANDARD/PREMIUM).
- **Этап 8** (2026-04-23): Cleanup — death_points, calc_stress_test, 71 wrapper, finmodel в calculator, pdf_gen в renderer, config.py, документация.

---

## 10. Технический долг (после Этапа 8)

Что осталось (в порядке приоритета):

1. **Бизнес-цена YAML risks integration**: YAML.risks секция для MANICURE есть, но `risk_service` пока не читает её. См. OQ-S Этапа 7.
2. **Расхождение profit_year_avg ~4%** (спека Р-9): ручной расчёт даёт 3.91 млн, движок 3.76 млн. Нужно проверить calc_cashflow на двойной учёт. Не критично, но стоит разобрать.
3. **Константы → config.py**: MRP_2026, DEFAULTS, SCORING_*, BLOCK1_THRESHOLDS, TRAINING_COSTS_BY_EXPERIENCE, CAPEX_BREAKDOWN_LABELS_RUS — пока в engine.py. Постепенно мигрировать в config.py для чистоты.
4. **engine.py содержит 932 LOC**: основное — `run_quick_check_v3` (380 LOC), ZerekDB class (200 LOC), constants (140 LOC). Дальнейшая чистка через extract YAML-овер для всего DB, переход на `loaders.NicheLoader` singleton — Этап 9+ (если понадобится).
5. **calc_owner_economics dual-purpose** — используется только для owner_payback_m в run_quick_check_v3. Можно удалить, заменить на простой расчёт (`capex_total / monthly_net_income`).

---

## 11. Что проект готов к

- ✅ Добавить новую нишу через YAML (см. `docs/ADDING_NEW_NICHE.md`).
- ✅ Развивать FinModel: фасад `FinModelCalculator` готов, реальная логика расчёта внутри.
- 🔄 Реализовать BizPlan: stub в `calculators/bizplan.py` ждёт реализации (есть `grant_bp.py` для гранта 400 МРП — отдельный flow).
- ✅ Тестировать новые фичи: 119 регрессионных проверок ловят поломки до прода.
- ✅ Расширять unit-тесты для каждого нового сервиса по паттерну.
