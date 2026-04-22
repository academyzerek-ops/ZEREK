# ZEREK — Архитектура

> Документация слоистой архитектуры ZEREK Quick Check / FinModel / BizPlan.
> Источник истины — `ZEREK_QuickCheck_Calculation_Spec.md` (финансовые формулы).
> Рефакторинг ведётся по плану `REFACTOR_PLAN.md` (gitignore).
>
> Версия: 1.0, Этап 1 рефакторинга (2026-04-22).

---

## 1. Принципы

1. **Single source of truth** — каждая сущность (ниша, город, налог, цена) хранится в одном месте.
2. **Разделение слоёв** — данные ≠ бизнес-логика ≠ рендер ≠ платформа.
3. **Сервис-ориентированность** — общие сервисы используются всеми калькуляторами (Quick Check / FinModel / BizPlan).
4. **Калькулятор возвращает данные, не вёрстку** — рендер отдельно.
5. **Ниша описывается одним YAML-файлом** — внешние данные (БНС РК, 2GIS, аренда) парсятся отдельно.
6. **Никаких фолбэков, скрывающих баги** — валидация на входе, явная ошибка вместо 100К/мес «по умолчанию».
7. **Регрессия обязательна** — после каждого этапа API-ответ бит-в-бит совпадает с baseline.

---

## 2. Папочная структура

```
ZEREK/
├── api/
│   ├── loaders/                    # читают данные из источников
│   │   ├── niche_loader.py         # ZerekDB.niche_data + niche_config + surveys
│   │   ├── city_loader.py          # 01_cities.xlsx + legacy-id нормализация
│   │   ├── pricing_loader.py       # цены материалов (Этап 7+)
│   │   ├── rent_loader.py          # 11_rent_benchmarks.xlsx
│   │   ├── tax_loader.py           # 05_tax_regimes.xlsx
│   │   ├── competitor_loader.py    # 14_competitors.xlsx, 2GIS
│   │   └── content_loader.py       # wiki, insights, lessons, permits, failure
│   │
│   ├── services/                   # бизнес-логика
│   │   ├── pricing_service.py      # социальные платежи ИП, effective ставки
│   │   ├── market_service.py       # Block 3 (конкуренты, плотность, HOME-note)
│   │   ├── economics_service.py    # calc_cashflow, P&L, breakeven, payback,
│   │   │                           # Block 4/5/6, unit-экономика A–F,
│   │   │                           # compute_pnl_aggregates, compute_unified_payback_months
│   │   ├── seasonality_service.py  # calc_revenue_monthly, first_year_chart, Block season
│   │   ├── stress_service.py       # Block 8 (от зрелого, Шаг 8 спеки)
│   │   ├── scenario_service.py     # 3 сценария (pess/base/opt)
│   │   ├── verdict_service.py      # Block 1 (светофор), 8 скоринг-функций
│   │   ├── risk_service.py         # Block 9 (HOME-specific, filter by format)
│   │   ├── action_plan_service.py  # Block 10 (green/yellow/red план)
│   │   └── chat_service.py         # Gemini system prompt, /chat
│   │
│   ├── calculators/                # тонкие фасады продуктов
│   │   ├── quick_check.py          # Quick Check 5 000 ₸ (run_quick_check_v3)
│   │   ├── finmodel.py             # FinModel 9 000 ₸ (заглушка в Этапе 4)
│   │   └── bizplan.py              # BizPlan 15 000 ₸ (заглушка в Этапе 4)
│   │
│   ├── renderers/                  # форматирование результата
│   │   ├── quick_check_renderer.py # JSON → block1..block10 (новый формат)
│   │   ├── pdf_renderer.py         # обёртка pdf_gen, формат block_1..block_12
│   │   └── html_renderer.py        # финмодель-HTML-отчёт
│   │
│   ├── validators/                 # валидация входа
│   │   ├── input_validator.py      # QCReq/FMReq/GrantBPReq + HOME/SOLO check
│   │   └── data_validator.py       # целостность xlsx/yaml на старте
│   │
│   ├── models/                     # типы и схемы данных (pydantic)
│   │   ├── niche.py                # схема YAML ниши
│   │   ├── input.py                # схема анкеты
│   │   └── report.py               # схема API-ответа
│   │
│   ├── config.py                   # константы (MRP, МЗП, налоги, дефолты)
│   ├── file_store.py               # временное хранилище файлов (token → bytes)
│   ├── utils.py                    # clean(), _safe/int/float
│   └── main.py                     # FastAPI endpoints (тонкий, ≤300 LOC)
│
├── data/
│   ├── niches/                     # YAML по нишам (Этап 7)
│   │   ├── MANICURE_data.yaml      # первая нишa на YAML (прототип)
│   │   └── ...                     # 49 остальных
│   │
│   ├── external/                   # внешние источники (Этап 7+)
│   │   └── kz/*.xlsx               # БНС, налоги, аренда, инфляция, 2GIS
│   │
│   ├── content/                    # контент для клиента
│   │   ├── wiki/                   # HTML обзоры (50 ниш)
│   │   ├── insights/               # MD текстовые знания
│   │   ├── lessons/                # уроки академии
│   │   └── cases/                  # кейсы
│   │
│   └── kz/                         # xlsx (будут разложены по external/ и niches/)
│
├── products/                       # frontend Mini App
│   ├── quick-check.html            # анкета (редиректор → qc-v3)
│   ├── qc-v3.html                  # рендер отчёта Quick Check
│   └── app.html                    # Academy SPA
│
├── tests/
│   ├── unit/                       # 3-5 тестов на каждый service
│   ├── integration/                # тесты калькуляторов end-to-end
│   └── fixtures/                   # baseline JSON (gitignore)
│
├── docs/
│   └── refactor_history/           # архив *_NOTES.md раундов v2/v3 (gitignore)
│
├── config/                         # YAML-конфиги (constants, defaults, niches…)
├── knowledge/                      # insights, reports (для RAG и Block 9)
├── templates/                      # шаблоны документов (finmodel xlsx, bizplan docx)
├── ARCHITECTURE.md                 # этот файл
├── CLAUDE.md                       # инструкции для Claude Code
├── ZEREK_QuickCheck_Calculation_Spec.md  # спецификация расчётов (источник истины)
└── README.md
```

---

## 3. Поток выполнения Quick Check (целевой после Этапа 4)

```
1. POST /quick-check {city_id, niche_id, format_id, experience,
                       capital, start_month, specific_answers}
        ↓
2. validators/input_validator
   ├── Pydantic: QCReq (типы, границы)
   ├── start_month ∈ 1..12 (HTTP 400 если None)
   └── HOME/SOLO: marketing_med + other_opex_med обязательны (HTTP 400)
        ↓
3. calculators/quick_check.run(input, db):
   ├── normalize_input()           # HOME/SOLO → founder_works=True,
   │                               # default entrepreneur_role=owner_plus_master
   │
   ├── loaders/niche_loader        # FORMATS, FINANCIALS, STAFF, CAPEX, TAXES
   ├── loaders/city_loader         # city data + check_coef
   ├── loaders/tax_loader          # city_ud_rate
   ├── loaders/rent_loader         # rent_per_m2 для города × loc_type
   ├── loaders/competitor_loader   # 2GIS насыщенность
   ├── loaders/content_loader      # permits, failure_pattern, insight.md
   │
   ├── services/economics_service
   │   ├── compute_pnl_aggregates()     # Шаги 3–5 (зрелый + средний год)
   │   ├── calc_cashflow() × 3 сценария # Шаги 4–5 + scenario_service
   │   ├── compute_unified_payback()    # Шаг 6 (единая формула)
   │   ├── compute_block4_unit_econ()   # Шаг 7 (breakeven по архетипу)
   │   ├── compute_block5_pnl()         # P&L таблица сценариев
   │   └── compute_block6_capital()     # CAPEX структура + обучение
   │
   ├── services/seasonality_service
   │   ├── compute_first_year_chart()   # 12 мес с ramp+season
   │   └── compute_block_season()       # s01..s12
   │
   ├── services/stress_service
   │   └── compute_block8_stress_test() # Шаг 8 от зрелого режима
   │
   ├── services/market_service
   │   └── compute_block3_market()      # HOME → note
   │
   ├── services/risk_service
   │   └── compute_block9_risks()       # insight.md + HOME-specific
   │
   ├── services/verdict_service
   │   └── compute_block1_verdict()     # Шаг 10 (8 пунктов, 17/12 пороги)
   │
   └── services/action_plan_service
       └── compute_block10_next_steps() # green/yellow/red план
        ↓
4. renderers/quick_check_renderer
   ├── compute_block2_passport()        # трансформация input → паспорт
   ├── fmt helpers                      # _fmt_kzt, format_location, lables
   └── → {block1..block10, block_season, first_year_chart, user_inputs}
        ↓
5. main.py → clean(report) → клиент
        ↓
6. Mini App qc-v3.html → визуализация
```

---

## 4. Контракты между слоями

### 4.1. Loaders

- **Вход**: id/параметры (city_id, niche_id, format_id, cls, loc_type)
- **Выход**: сырые данные (dict / list of dicts), без бизнес-логики
- **Дефолты**: возвращают либо данные, либо пустой dict/list — **НЕ** падают
- **Исключения**: только если xlsx сломан (не при отсутствии строки)

### 4.2. Services

- **Вход**: loaded data + params
- **Выход**: вычисленные агрегаты (числа, проценты, структуры)
- **Инварианты**:
  - Окупаемость — только через `economics_service.compute_unified_payback_months`
  - Зрелый P&L — только через `economics_service.compute_pnl_aggregates`
  - Стресс-тест — база = зрелый режим (без ramp+season)
  - Сезонность и ramp — только в первом году

### 4.3. Calculators

- **Вход**: валидированный Input
- **Выход**: `result` dict для рендера — ВСЁ что нужно рендеру должно быть здесь, никаких инъекций из `main.py`
- **НЕ зовёт рендер** — это задача endpoint'а

### 4.4. Renderers

- **Вход**: `result` от калькулятора
- **Выход**: структура для UI (блоки) или bytes (PDF/xlsx)
- **Чистая трансформация** — нет бизнес-вычислений, только форматирование и лейблы

### 4.5. Validators

- **Вход**: raw request body
- **Выход**: валидированный Input (pydantic model) или HTTPException 400
- **Без side effects** — только проверка

---

## 5. Формат JSON Quick Check API

После рефакторинга API возвращает:

```jsonc
{
  "status": "ok",
  "result": {
    "input": { /* эхо параметров */ },
    "user_inputs": { /* adaptive-поля v2 */ },
    "block1": { /* светофор: color, score, strengths, risks, scoring */ },
    "block2": { /* паспорт: niche, format, city, staff, experience */ },
    "block3": { /* рынок: saturation / HOME-note */ },
    "block4": { /* юнит-экономика: breakdown чека, breakeven */ },
    "block5": {
      "pnl": { /* 3 сценария × (revenue, cogs, fot, rent, mkt, other, tax, net_profit) */ },
      "first_year_chart": { /* 12 мес с ramp+season */ },
      "payback": { /* payback_months, method */ }
    },
    "block6": { /* capex: breakdown + training + gap */ },
    "block_season": { /* s01..s12, peaks, troughs */ },
    "block8": { /* стресс-тест: sensitivities, death_points */ },
    "block9": { /* риски: 5 items */ },
    "block10": { /* план: green/yellow/red + CTA */ }
  }
}
```

Старый формат `block_1..block_12` (с подчёркиванием) остаётся для PDF-рендера (`renderers/pdf_renderer.py`).

---

## 6. Инварианты и критичные правила

1. Окупаемость считается **в одном месте** (`compute_unified_payback_months`), читается везде — светофор, Block 5, план действий. Никаких fallback'ов.
2. Все формулы подчиняются спеке (`ZEREK_QuickCheck_Calculation_Spec.md`):
   - Шаг 3: зрелый P&L (ramp=1, season=1)
   - Шаг 4: 12-мес P&L (с ramp+season)
   - Шаг 5: средние годовые (`profit_month_avg = profit_year_avg / 12`)
   - Шаг 6: `payback = ceil(capex_total / profit_month_avg)`
   - Шаг 7: `breakeven = ceil(fixed_monthly / (avg_check − var_per_service))`
   - Шаг 8: стресс от зрелого (revenue × (1-X%), materials пропорционально для трафика / без изменений для чека)
3. HOME/SOLO: `marketing_med` и `other_opex_med` обязательны в xlsx (HTTP 400 если пусто).
4. `ceil` для консервативности (окупаемость, breakeven), не `round`.
5. Сравнение с `avg_salary_2025` — только для HOME/SOLO, для STANDARD/PREMIUM не показывать.
6. Обучение (`training_cost`) — только если `training_required=True` для ниши и `experience ∈ {none, some}`.
7. ИП не платит себе зарплату: `fot_monthly = 0`, доход = вся прибыль.

---

## 7. Коммит-стратегия рефакторинга

- Один этап = серия атомарных коммитов (Conventional Commits).
- Префиксы: `refactor:` (перенос без изменения логики), `chore:` (структура, документация), `feat:` (новая функциональность), `fix:` (баг), `test:` (тесты).
- После каждого коммита — регрессия 4 baseline JSON. Отклонение > 0 = откат.
- Документация обновляется в Этапе 8 (финальный проход).

---

## 8. История

- **Этап 0** (2026-04-22): Baseline + REFACTOR_PLAN.md + аудит 5171 LOC.
- **Этап 1** (2026-04-22): Структура папок, ARCHITECTURE.md, перенос *_NOTES.md в docs/refactor_history/.
- **Этап 2**: Loaders (TBD).
- **Этап 3**: Services (TBD).
- **Этап 4**: Calculators (TBD).
- **Этап 5**: Renderers (TBD).
- **Этап 6**: Validators + Models (TBD).
- **Этап 7**: YAML-first для MANICURE (TBD).
- **Этап 8**: Cleanup + документация (TBD).
