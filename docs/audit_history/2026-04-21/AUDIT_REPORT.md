# ZEREK — Инвентаризационный отчёт Quick Check

**Дата:** 2026-04-21
**Commit:** `784196e`
**Назначение:** фактическая инвентаризация перед решением о перестройке расчётов Quick Check. Только факты, без оценок.

---

## Оглавление

1. [Структура репозитория](#раздел-1--структура-репозитория)
2. [Python-файлы в расчётах Quick Check](#раздел-2--python-файлы-в-расчётах-quick-check)
3. [XLSX/CSV файлы](#раздел-3--xlsxcsv-файлы)
4. [YAML/JSON конфиги](#раздел-4--yamljson-конфиги)
5. [Инсайт-файлы по нишам](#раздел-5--инсайт-файлы-по-нишам)
6. [HTML/JS для Quick Check](#раздел-6--htmljs-для-quick-check)
7. [Текущий flow Quick Check](#раздел-7--текущий-flow-quick-check)
8. [Источники цифр](#раздел-8--источники-цифр-самое-важное)
9. [Мёртвые файлы](#раздел-9--мёртвые-файлы)
10. [Резюме и открытые вопросы](#раздел-10--резюме-и-открытые-вопросы)

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 1 — СТРУКТУРА РЕПОЗИТОРИЯ
═══════════════════════════════════════════════════════════════════════

### Корень
```
./.gitignore                                                   0.0 KB  2026-04-17
./.impeccable.md                                               5.8 KB  2026-04-17
./.nojekyll                                                    0.0 KB  2026-04-17
./CLAUDE.md                                                    7.1 KB  2026-04-17
./CNAME                                                        0.0 KB  2026-04-17
./Procfile                                                     0.1 KB  2026-04-17
./README.md                                                    0.0 KB  2026-04-17
./about.html                                                   0.4 KB  2026-04-17
./academy.html                                                 0.4 KB  2026-04-17
./cases.html                                                   0.4 KB  2026-04-17
./icon-512.png                                                11.2 KB  2026-04-17
./index.html                                                  19.2 KB  2026-04-17
./manifest.json                                                0.6 KB  2026-04-17
./privacy.html                                                 0.4 KB  2026-04-17
./products.html                                                0.4 KB  2026-04-17
./railway.json                                                 0.2 KB  2026-04-17
./requirements.txt                                             0.2 KB  2026-04-20
./sw.js                                                        1.1 KB  2026-04-20
./wiki.html                                                    0.4 KB  2026-04-17
```

### /config/
```
./config/archetypes.yaml                                      10.9 KB  2026-04-20
./config/locations.yaml                                        6.5 KB  2026-04-20
./config/niches.yaml                                           9.7 KB  2026-04-20
./config/questionnaire.yaml                                   18.1 KB  2026-04-20
```

### /data/
```
./data/common/.gitkeep                                         0.0 KB  2026-04-17
./data/ru/.gitkeep                                             0.0 KB  2026-04-17
./data/kz/01_cities.xlsx                                      15.8 KB  2026-04-17
./data/kz/02_wages_by_city.xlsx                               11.0 KB  2026-04-17
./data/kz/03_wages_by_industry.xlsx                           13.9 KB  2026-04-17
./data/kz/04_wages_by_role.xlsx                               11.0 KB  2026-04-17
./data/kz/05_tax_regimes.xlsx                                 14.1 KB  2026-04-17
./data/kz/07_niches.xlsx                                      13.6 KB  2026-04-20
./data/kz/08_niche_formats.xlsx                               14.2 KB  2026-04-20
./data/kz/09_surveys.xlsx                                     63.4 KB  2026-04-20
./data/kz/11_rent_benchmarks.xlsx                             15.7 KB  2026-04-17
./data/kz/13_macro_dynamics.xlsx                              15.5 KB  2026-04-17
./data/kz/14_competitors.xlsx                                  9.3 KB  2026-04-17
./data/kz/15_failure_cases.xlsx                               16.3 KB  2026-04-17
./data/kz/17_permits.xlsx                                      8.5 KB  2026-04-17
./data/kz/19_inflation_by_niche.xlsx                           9.9 KB  2026-04-17
./data/kz/20_scenario_coefficients.xlsx                        7.6 KB  2026-04-17
./data/kz/21_opex_benchmarks.xlsx                              8.3 KB  2026-04-17
./data/kz/22_staff_scaling.xlsx                                9.2 KB  2026-04-17
./data/kz/templates/gitkeep                                    0.0 KB  2026-04-17
./data/kz/niches/gitkeep                                       0.0 KB  2026-04-17
./data/kz/niches/niche_formats_AUTOSERVICE.xlsx               21.7 KB  2026-04-17
./data/kz/niches/niche_formats_BAKERY.xlsx                    53.3 KB  2026-04-17
./data/kz/niches/niche_formats_BARBER.xlsx                    21.3 KB  2026-04-17
./data/kz/niches/niche_formats_BROW.xlsx                      19.3 KB  2026-04-17
./data/kz/niches/niche_formats_CANTEEN.xlsx                   24.6 KB  2026-04-17
./data/kz/niches/niche_formats_CARWASH.xlsx                   49.7 KB  2026-04-17
./data/kz/niches/niche_formats_CLEAN.xlsx                     20.0 KB  2026-04-17
./data/kz/niches/niche_formats_COFFEE.xlsx                    69.9 KB  2026-04-17
./data/kz/niches/niche_formats_CONFECTION.xlsx                20.1 KB  2026-04-17
./data/kz/niches/niche_formats_CYBERCLUB.xlsx                 20.4 KB  2026-04-17
./data/kz/niches/niche_formats_DENTAL.xlsx                    20.7 KB  2026-04-17
./data/kz/niches/niche_formats_DONER.xlsx                     28.4 KB  2026-04-17
./data/kz/niches/niche_formats_DRYCLEAN.xlsx                  20.2 KB  2026-04-17
./data/kz/niches/niche_formats_FASTFOOD.xlsx                  24.4 KB  2026-04-17
./data/kz/niches/niche_formats_FITNESS.xlsx                   22.2 KB  2026-04-17
./data/kz/niches/niche_formats_FLOWERS.xlsx                   19.7 KB  2026-04-17
./data/kz/niches/niche_formats_FRUITSVEGS.xlsx                20.1 KB  2026-04-17
./data/kz/niches/niche_formats_FURNITURE.xlsx                 20.7 KB  2026-04-17
./data/kz/niches/niche_formats_GROCERY.xlsx                   19.5 KB  2026-04-17
./data/kz/niches/niche_formats_KINDERGARTEN.xlsx              20.3 KB  2026-04-17
./data/kz/niches/niche_formats_LASH.xlsx                      19.4 KB  2026-04-17
./data/kz/niches/niche_formats_MASSAGE.xlsx                   19.6 KB  2026-04-17
./data/kz/niches/niche_formats_NAIL.xlsx                      21.2 KB  2026-04-17
./data/kz/niches/niche_formats_PHARMA.xlsx                    18.9 KB  2026-04-17
./data/kz/niches/niche_formats_PIZZA.xlsx                     27.1 KB  2026-04-17
./data/kz/niches/niche_formats_PVZ.xlsx                       18.7 KB  2026-04-17
./data/kz/niches/niche_formats_REPAIR_PHONE.xlsx              19.6 KB  2026-04-17
./data/kz/niches/niche_formats_SEMIFOOD.xlsx                  20.0 KB  2026-04-17
./data/kz/niches/niche_formats_SUGARING.xlsx                  19.5 KB  2026-04-17
./data/kz/niches/niche_formats_SUSHI.xlsx                     24.9 KB  2026-04-17
./data/kz/niches/niche_formats_TAILOR.xlsx                    19.6 KB  2026-04-17
./data/kz/niches/niche_formats_TIRE.xlsx                      20.6 KB  2026-04-17
./data/kz/niches/niche_formats_WATER.xlsx                     19.5 KB  2026-04-17
```

### /knowledge/
```
./knowledge/kz/.gitkeep                                        0.0 KB  2026-04-17
./knowledge/ru/.gitkeep                                        0.0 KB  2026-04-17
./knowledge/niches/_yt_videos.json                            81.2 KB  2026-04-17
./knowledge/niches/ACCOUNTING_insight.md                      25.7 KB  2026-04-17
./knowledge/niches/AUTOPARTS_insight.md                       20.6 KB  2026-04-17
./knowledge/niches/AUTOSERVICE_insight.md                     21.5 KB  2026-04-17
./knowledge/niches/BAKERY_insight.md                          16.8 KB  2026-04-17
./knowledge/niches/BROW_insight.md                            18.0 KB  2026-04-17
./knowledge/niches/BUBBLETEA_insight.md                       22.5 KB  2026-04-17
./knowledge/niches/BUILDMAT_insight.md                        20.4 KB  2026-04-17
./knowledge/niches/CANTEEN_insight.md                         17.6 KB  2026-04-17
./knowledge/niches/CARGO_insight.md                           12.1 KB  2026-04-17
./knowledge/niches/CARPETCLEAN_insight.md                     24.7 KB  2026-04-17
./knowledge/niches/CONFECTION_insight.md                      17.5 KB  2026-04-17
./knowledge/niches/COSMETOLOGY_insight.md                     19.1 KB  2026-04-17
./knowledge/niches/CYBERCLUB_insight.md                       22.7 KB  2026-04-17
./knowledge/niches/DENTAL_insight.md                          19.3 KB  2026-04-17
./knowledge/niches/DETAILING_insight.md                       25.4 KB  2026-04-17
./knowledge/niches/DRIVING_insight.md                         15.2 KB  2026-04-17
./knowledge/niches/DRYCLEAN_insight.md                        14.4 KB  2026-04-17
./knowledge/niches/FASTFOOD_insight.md                        18.8 KB  2026-04-17
./knowledge/niches/FITNESS_insight.md                         21.2 KB  2026-04-17
./knowledge/niches/FLOWERS_insight.md                         18.0 KB  2026-04-17
./knowledge/niches/FRUITSVEGS_insight.md                      17.5 KB  2026-04-17
./knowledge/niches/FURNITURE_insight.md                       15.3 KB  2026-04-17
./knowledge/niches/KIDSCENTER_insight.md                      23.1 KB  2026-04-17
./knowledge/niches/KINDERGARTEN_insight.md                    15.6 KB  2026-04-17
./knowledge/niches/LANGUAGES_insight.md                       11.6 KB  2026-04-17
./knowledge/niches/LASH_insight.md                            19.7 KB  2026-04-17
./knowledge/niches/MASSAGE_insight.md                         18.3 KB  2026-04-17
./knowledge/niches/MEATSHOP_insight.md                        35.4 KB  2026-04-17
./knowledge/niches/NAIL_insight.md                            14.4 KB  2026-04-17
./knowledge/niches/OPTICS_insight.md                          19.2 KB  2026-04-17
./knowledge/niches/PETSHOP_insight.md                         11.0 KB  2026-04-17
./knowledge/niches/PHARMA_insight.md                          13.0 KB  2026-04-17
./knowledge/niches/PHOTO_insight.md                           23.2 KB  2026-04-17
./knowledge/niches/PIZZA_insight.md                           15.9 KB  2026-04-17
./knowledge/niches/PVZ_insight.md                             11.4 KB  2026-04-17
./knowledge/niches/REALTOR_insight.md                         13.3 KB  2026-04-17
./knowledge/niches/REPAIR_PHONE_insight.md                    24.0 KB  2026-04-17
./knowledge/niches/SEMIFOOD_insight.md                        18.2 KB  2026-04-17
./knowledge/niches/SUGARING_insight.md                        20.2 KB  2026-04-17
./knowledge/niches/SUSHI_insight.md                           16.9 KB  2026-04-17
./knowledge/niches/TAILOR_insight.md                          11.3 KB  2026-04-17
./knowledge/niches/TIRE_insight.md                            15.5 KB  2026-04-17
./knowledge/niches/WATERPLANT_insight.md                      19.5 KB  2026-04-17
./knowledge/niches/YOGA_insight.md                            22.7 KB  2026-04-17
```

> ⚠️ замечено: для ниши `COFFEE` инсайт-файла нет (`knowledge/niches/COFFEE_insight.md` отсутствует), хотя COFFEE — основная ниша и в `data/kz/niches/niche_formats_COFFEE.xlsx` есть все 14 листов.

### /products/
```
./products/.gitkeep                                            0.0 KB  2026-04-17
./products/app.html                                          145.1 KB  2026-04-21
./products/index.html                                          0.3 KB  2026-04-17
./products/qc-v3.html                                         78.4 KB  2026-04-20
./products/quick-check-v2.html                                54.8 KB  2026-04-20
./products/quick-check.html                                    0.4 KB  2026-04-20
./products/quick-check.legacy.html                            85.9 KB  2026-04-20
./products/assets/logo.png                                   365.1 KB  2026-04-17
./products/assets/splash.mp4                                  98.1 KB  2026-04-17
```

### /api/ (бэкенд)
```
./api/.gitkeep                                                 0.0 KB  2026-04-17
./api/engine.py                                              150.2 KB  2026-04-20
./api/finmodel_report.py                                      41.9 KB  2026-04-17
./api/gemini_rag.py                                            9.2 KB  2026-04-17
./api/gen_finmodel.py                                          8.8 KB  2026-04-17
./api/grant_bp.py                                             38.8 KB  2026-04-17
./api/main.py                                                 42.1 KB  2026-04-20
./api/pdf_gen.py                                              63.7 KB  2026-04-17
./api/report.py                                               16.5 KB  2026-04-17
./api/fonts/DejaVuSans-Bold.ttf                              689.1 KB  2026-04-17
./api/fonts/DejaVuSans.ttf                                   739.3 KB  2026-04-17
./api/fonts/DejaVuSansMono-Bold.ttf                          324.2 KB  2026-04-17
./api/fonts/DejaVuSansMono.ttf                               332.4 KB  2026-04-17
```

### /engine/ (отдельный модуль в корне)
```
./engine/__init__.py                                           0.2 KB  2026-04-17
./engine/gemini_rag.py                                         2.1 KB  2026-04-17
./engine/run_test.py                                           1.7 KB  2026-04-17
```

> ⚠️ замечено: корневая директория `/engine/` и каталог `/api/` содержат файлы с одинаковыми именами (`gemini_rag.py`). Корневой `engine/__init__.py` импортирует `.engine` и `.report`, но таких файлов внутри `/engine/` нет — модуль поломан в момент импорта.

### /scripts/ (генераторы xlsx)
```
./scripts/build_07_niches.py                                  24.4 KB  2026-04-20
./scripts/build_08_niche_formats.py                           29.1 KB  2026-04-20
./scripts/build_09_surveys.py                                 42.5 KB  2026-04-20
```

### /templates/
```
./templates/bizplan/grant_400mrp_template.docx                30.7 KB  2026-04-17
./templates/finmodel/finmodel_template.xlsx                   88.1 KB  2026-04-17
./templates/bizplan/.gitkeep                                   0.0 KB  2026-04-17
./templates/finmodel/.gitkeep                                  0.0 KB  2026-04-17
./templates/pitchdeck/.gitkeep                                 0.0 KB  2026-04-17
```

### /docs/
```
./docs/ADAPTIVE_SURVEY.md                                      8.9 KB  2026-04-20
./docs/SURVEY_DRAFT.md                                        28.9 KB  2026-04-20
```

### Прочие каталоги (не участвуют в расчётах Quick Check)
- `/academy/` — 52 html-файла уроков (Junior + Startup), не связаны с движком
- `/wiki/kz/` — 42 html wiki-обзора ниш (статические)
- `/cases/` — 5 html-кейсов
- `/site/` — 8 статических файлов лендинга (копии из корня)
- `/design-system/` — 1 файл `threads.css`
- `/images/` — папка с изображениями (confection подкаталог)
- `/.github/workflows/wiki-inject.yml` — CI workflow
- `/.claude/settings.local.json` — локальные настройки Claude Code

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 2 — PYTHON-ФАЙЛЫ В РАСЧЁТАХ QUICK CHECK
═══════════════════════════════════════════════════════════════════════

### 2.1 `api/main.py` (918 строк, 42.1 KB)

**Что делает.** FastAPI-сервер ZEREK API v3.1. Регистрирует все HTTP-эндпоинты, инициализирует `ZerekDB` при старте, оркеструет вызовы движка Quick Check, финмодели, генерации PDF и бизнес-плана. Обрабатывает интеграцию с Gemini Flash для AI-чата и интерпретации отчётов.

**Экспортируемые функции/классы:**
- `class QCReq(BaseModel)` — модель запроса на `/quick-check`
- `class FMReq(BaseModel)` — модель запроса на `/finmodel`
- `class GrantBPReq(BaseModel)` — модель запроса на `/grant-bp`
- `def clean(obj)` — рекурсивная нормализация numpy-типов в native JSON
- `def _store_file(content, filename, media_type, disposition='attachment') -> str`
- `def _compute_finmodel_data(params: dict) -> dict`
- `def _parse_pct(val)`, `def _parse_int(val)`
- `def _apply_adaptive_answers(req: FMReq) -> FMReq`
- Эндпоинты FastAPI: `root`, `health`, `debug`, `get_cities`, `get_niches`, `get_formats`, `get_locations`, `get_classes`, `get_tax_rate`, `quick_check` (POST), `niche_config`, `niche_survey`, `configs`, `formats_v2`, `quickcheck_survey`, `get_products`, `get_marketing`, `get_insights`, `get_survey`, `get_niche_risks`, `pdf_health`, `generate_pdf` (POST), `download_file`, `grant_bp_endpoint` (POST), `generate_finmodel_endpoint` (POST), `finmodel_html_report` (POST), `ai_chat` (POST), `test_gemini`, `chat_endpoint` (POST)

**Читает файлов:** напрямую — нет. Через `ZerekDB` (из `engine`). Поднимает конфиги/шаблоны только путевые:
- `templates/finmodel/finmodel_template.xlsx` (fallback `data/kz/templates/finmodel_template.xlsx`)
- `templates/bizplan/grant_400mrp_template.docx` (fallback `data/kz/templates/grant_400mrp_template.docx`)

**Магические числа / жёсткие константы:**
- `main.py:139` — `CAPEX_TO_CLS = {"эконом":"Эконом","стандарт":"Стандарт","бизнес":"Бизнес","премиум":"Премиум"}`
- `main.py:393` — `_FILE_TTL_SECONDS = 7 * 24 * 3600`
- `main.py:436` — дефолт `grant_amount: int = 1730000`
- `main.py:473` — сезонность `[0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]`
- `main.py:474-497` — `horizon=36`, `check0=1400`, `traffic0=70`, `work_days=30`, `tg=0.07`, `cg=0.08`, `cogs_pct=0.35`, `loss_pct=0.03`, `rent=70000`, `fot=200000*2`, `utilities=15000`, `marketing=50000`, `consumables=3500`, `software=5000`, `other=10000`, `capex=1500000`, `deposit_months=2`, `working_cap=1000000`, `amort_years=7`, `tax_rate=0.03`, `credit_rate=0.22`, `credit_term=36`, `wacc=0.20`
- `main.py:70` — поле `fot_gross: int = 200000`, `headcount: int = 2`
- `main.py:74-79` — `cogs_pct: float = 0.35`, `credit_rate: float = 0.22`, `credit_term: int = 36`, `working_cap: int = 1000000`
- `main.py:832` — URL Gemini Flash, API key из env `GEMINI_API_KEY`
- `main.py:903` — `temperature=0.7`, `maxOutputTokens=1024`, `topP=0.9`
- `main.py:637-690` — `_FM_FIELD_MAP`: карта `qid` анкеты на поля `FMReq` (около 35 пар)

**Внутренние импорты:**
- `from engine import (ZerekDB, run_quick_check_v3, get_niche_config, get_niche_survey, get_formats_v2, get_quickcheck_survey, get_entrepreneur_roles, compute_block1_verdict, compute_block2_passport, compute_block3_market, compute_block4_unit_economics, compute_block5_pnl, compute_block6_capital, compute_block7_scenarios, compute_block8_stress_test, compute_block9_risks, compute_block10_next_steps)`
- `from report import render_report_v4`
- `from engine import get_city_tax_rate` (динамически в `get_tax_rate`)
- `from pdf_gen import generate_quick_check_pdf, _register_fonts_once` (динамически)
- `from gemini_rag import extract_niche_risks, get_ai_interpretation, clean_markdown`
- `from grant_bp import generate_grant_bp`
- `from gen_finmodel import generate_finmodel`
- `from finmodel_report import render_finmodel_report`

> ⚠️ замечено: импорты `from engine`, `from report`, `from gemini_rag`, `from gen_finmodel`, `from pdf_gen`, `from grant_bp`, `from finmodel_report` — это файлы внутри `/api/`, а не из `/engine/` каталога. Путь добавляется через `sys.path.insert(0, BASE_DIR)` в `main.py:12-13`.

---

### 2.2 `api/engine.py` (2861 строка, 150.2 KB) — **главный расчётный модуль**

**Что делает.** Читает 19 xlsx-файлов из `data/kz/` (общие) + 33 `niche_formats_{NICHE}.xlsx` из `data/kz/niches/`. Строит `ZerekDB` — in-memory БД. Содержит всю расчётную логику Quick Check v3: выручка, cashflow на 12 месяцев, точка безубыточности, окупаемость, экономика собственника, стресс-тест, 3 сценария. А также 10 функций `compute_blockN_*` для отчёта Quick Check v1.0 (блоки 1, 2, 3, 4, 5, 6, 7, 8, 9, 10). Всего ~70 функций в одном файле.

**Экспортируемые функции/классы:**
- `class ZerekDB:` — загрузчик БД. Методы: `__init__(data_dir)`, `_xl(filename, sheet, header)`, `_load_common()`, `_load_niches()`, `_load_yaml_configs()`, `get_niche_sheet(niche_id, sheet)`, `get_format_row(niche_id, sheet, format_id, cls)`, `get_format_all_rows(...)`, `get_available_niches()`, `get_formats_for_niche(niche_id)`, `get_survey(niche_id)`, `get_locations(niche_id)`, `get_classes_for_format(niche_id, format_id)`
- `def get_city_check_coef(city_id: str) -> float`
- `def _safe(val, default=0)`, `_safe_int`, `_safe_float`
- `def get_city(db, city_id) -> dict`
- `def get_city_tax_rate(db, city_id) -> float`
- `def get_rent_median(db, city_id, loc_type) -> tuple`
- `def get_competitors(db, niche_id, city_id) -> dict`
- `def get_failure_pattern(db, niche_id) -> dict`
- `def get_permits(db, niche_id) -> list`
- `def calc_revenue_monthly(fin, cal_month, razgon_month) -> int`
- `def calc_cashflow(fin, staff, capex_total, tax_rate, start_month=1, months=12, qty=1) -> list`
- `def calc_breakeven(fin, staff, tax_rate, qty=1) -> dict`
- `def calc_payback(capex_total, cashflow) -> dict`
- `def calc_owner_social_payments(declared_monthly_base=None) -> int`
- `def calc_owner_economics(fin, staff, tax_rate, rent_month_total, qty=1, traffic_k=1.0, check_k=1.0, rent_k=1.0, social=None) -> dict`
- `def calc_closure_growth_points(owner_eco) -> dict`
- `def calc_stress_test(fin, staff, tax_rate, rent_month_total, qty=1) -> list`
- `def run_quick_check_v3(db, city_id, niche_id, format_id, cls, area_m2, loc_type, capital=0, qty=1, founder_works=False, rent_override=None, start_month=4) -> dict`
- `def get_inflation_region(db, city_id)` — заглушка, всегда возвращает 10.0
- `def render_report(result)` — заглушка, возвращает `str(result)`
- `def get_niche_config(db, niche_id) -> dict`
- `def _question_to_dict(row) -> dict`, `_dependencies_for(deps_df, qid)`
- `def _fmt_range_kzt(low, high)`, `_fmt_kzt(v)`, `_fmt_kzt_short(v)`
- Скоринг-функции Блока 1: `_score_capital`, `_score_roi`, `_score_breakeven`, `_score_saturation`, `_score_experience`, `_score_marketing`, `_score_stress`, `_score_format_city`
- `def _verdict_statement_template(color, top_weak, top_strong, roi_pct, breakeven_months)`
- `def _strength_text(p)`, `def _risk_text(p, context)`
- `def compute_block1_verdict(result, adaptive) -> dict`
- `def compute_block3_market(db, result, adaptive) -> dict`
- `def _archetype_of(db, niche_id)`
- `def compute_block4_unit_economics(db, result, adaptive, block2=None) -> dict`
- `def compute_block6_capital(db, result, adaptive, block2=None) -> dict`
- `def compute_block7_scenarios(db, result, adaptive) -> dict`
- `def compute_block8_stress_test(db, result, adaptive) -> dict`
- `def compute_block9_risks(db, result, adaptive) -> dict`
- `def _cogs_label_by_archetype(archetype)`, `_scenario_pnl_row(...)`
- `def compute_block5_pnl(db, result, adaptive) -> dict`
- Helpers Блока 10: `_green_action_plan(block2, block1)`, `_yellow_conditions(block1, block2)`, `_red_alternatives(block1, block2, result, db)`, `_upsell_block(color, block1, block2)`, `_final_farewell(color, block2)`
- `def compute_block10_next_steps(db, result, adaptive, block1=None, block2=None) -> dict`
- Helpers Блока 2: `_parse_typical_staff`, `_split_staff_into_groups`, `_subtract_entrepreneur_role`, `_entrepreneur_role_text`, `_payroll_label`, `_experience_label`, `_format_location`
- `def compute_block2_passport(db, result, adaptive) -> dict`
- `def _load_yaml_configs_on(self)` (bind-ается как метод `ZerekDB._load_yaml_configs`)
- `def get_formats_v2(db, niche_id) -> list`
- `def get_entrepreneur_roles(typical_staff: list) -> list`
- `def get_quickcheck_survey(db, niche_id, format_id=None) -> dict`
- `def get_niche_survey(db, niche_id, tier='express') -> dict`

**Читает файлов:**
- `data/kz/01_cities.xlsx` лист `Города` header=4
- `data/kz/05_tax_regimes.xlsx` листы `tax_regimes_2026`, `city_ud_rates_2026`
- `data/kz/07_niches.xlsx` листы `Ниши` header=5, `Специфичные вопросы` header=5
- `data/kz/08_niche_formats.xlsx` лист `Форматы` header=5
- `data/kz/09_surveys.xlsx` листы `Вопросы`, `Применимость`, `Зависимости` header=5
- `data/kz/11_rent_benchmarks.xlsx` лист `Калькулятор для движка` header=5
- `data/kz/13_macro_dynamics.xlsx` лист `Инфляция по регионам` header=5
- `data/kz/14_competitors.xlsx` лист `Конкуренты по городам` header=5
- `data/kz/15_failure_cases.xlsx` лист `Паттерны по нишам` header=5
- `data/kz/17_permits.xlsx` лист `Разрешения и лицензии` header=5
- `data/kz/19_inflation_by_niche.xlsx` лист `Прогноз роста OPEX` header=5
- `data/kz/niches/niche_formats_{NICHE}.xlsx` — 33 файла по glob, по 14 листов каждый: `FORMATS`, `STAFF`, `FINANCIALS`, `CAPEX`, `GROWTH`, `TAXES`, `MARKET`, `LAUNCH`, `INSIGHTS`, `PRODUCTS`, `MARKETING`, `SUPPLIERS`, `SURVEY`, `LOCATIONS`
- `config/niches.yaml`, `config/archetypes.yaml`, `config/locations.yaml`, `config/questionnaire.yaml` через `_load_yaml_configs_on`
- `knowledge/niches/{niche_id}_insight.md` — для Block 9 (компания через regex)

**Магические числа / жёсткие константы (ключевые):**
- `engine.py:17` — `MRP_2026 = 4325`
- `engine.py:18` — `MZP_2026 = 85000`
- `engine.py:21-37` — `DEFAULTS`: `cogs_pct=0.30`, `margin_pct=0.70`, `deposit_months=2`, `loss_pct=0.02`, `sez_month=0`, `rampup_months=3`, `rampup_start_pct=0.50`, `repeat_pct=0.40`, `traffic_growth_yr=0.07`, `check_growth_yr=0.08`, `rent_growth_yr=0.10`, `fot_growth_yr=0.08`, `inflation_yr=0.10`, `deprec_years=7`, `fot_multiplier=1.175`
- `engine.py:40-46` — `CITY_CHECK_COEF`: чек-коэффициент по 15 городам (Алматы/Астана 1.05; Актобе/Караганда/Уральск/УКГ/Актау 1.00; Шымкент/Павлодар/Костанай 0.97; Семей/Тараз/Петропавловск/Кызылорда 0.95; Атырау 1.03)
- `engine.py:297` — fallback tax rate 4.0% если город не в таблице
- `engine.py:300-301` — fallback аренда `(3000, 500)` (₸/м²/мес, коммуналка/м²)
- `engine.py:316, 322` — fallback уровень конкуренции = 3
- `engine.py:358` — `base_rev = check * traffic * 30` (30 — жёстко захардкоженное количество рабочих дней)
- `engine.py:365-369` — разгон: start=0.5, 3 месяца линейно до 1.0
- `engine.py:496-497` — `OWNER_CLOSURE_POCKET = 200_000`, `OWNER_GROWTH_POCKET = 600_000`
- `engine.py:508-510` — соцплатежи собственника ИП: `MRP_2026 * 50 * 0.22` (≈22% от 50 МРП ≈ 47 575 ₸/мес)
- `engine.py:594-599` — стресс-тест: плохо `(traffic_k=0.75, check_k=0.90, rent_k=1.20)`, база `(1.00,1.00,1.00)`, хорошо `(1.20,1.10,1.00)`
- `engine.py:727-728` — 3 сценария: `pess=(0.75,0.90)`, `base=(1.0,1.0)`, `opt=(1.25,1.10)`
- `engine.py:766-770` — пороги вердикта по score: 5+ green, 2+ yellow, иначе red
- `engine.py:1189, 1429` — benchmark плотности конкурентов `0.8` (blk1), `0.75` (blk3) на 10 000 жителей
- `engine.py:1154-1157` — пороги `_score_capital`: 1.2 / 0.95 / 0.75
- `engine.py:1169-1172` — пороги `_score_roi`: 0.45 / 0.30 / 0.15 (годовой ROI)
- `engine.py:1178-1181` — пороги `_score_breakeven` мес: 6 / 12 / 18
- `engine.py:1191-1194` — пороги `_score_saturation`: 0.6 / 1.0 / 1.5 ratio
- `engine.py:1214-1217` — пороги `_score_stress`: 0.30 / 0.50 drop
- `engine.py:1222` — `small = city_pop < 150_000`, `mid = 150K-300K`
- `engine.py:1302, 2105` — валидация `total_investment < 500_000` → 1 балл / None ROI
- `engine.py:1342-1344` — пороги color Блок 1: 17 / 12
- `engine.py:1433-1440` — насыщение Блок 3: 60/110/150% benchmark
- `engine.py:1514` — `work_days = 26` (для Блока 4 юнит-эко)
- `engine.py:1521-1522, 1543, 1557-1561, 1585-1593, 1613-1618, 1644, 1660-1668` — захардкоженные коэффициенты unit-эко по архетипам (piece_rate=0.40, materials=0.12, load=0.80 для A; markup=50% для C; churn=0.08 для D; и т.п.)
- `engine.py:1708-1716` — синтетическая структура CAPEX: equipment=32%, renovation=22%, first_stock=15%, marketing=10%, working_cap=12%, deposit=4%, legal=5%
- `engine.py:1731` — `credit_monthly = int(gap * 0.035)` — аннуитет приближённо 22%/36мес
- `engine.py:1777-1778` — множители сценариев P&L Блок 7: pess 0.75, base 1.0, opt 1.25
- `engine.py:1835-1840` — импакты стресс-теста Блок 8: трафик/чек -20%, ФОТ +20%, аренда +30%, маркетинг -100% (выручка -10%), налог +50%
- `engine.py:2034` — дефолт tax_rate 0.03
- `engine.py:2092` — оптимист ФОТ `× 1.15`
- `engine.py:2126-2130` — фолбэк зарплата роли 200_000 ₸/мес; владелец на нескольких позициях — `fot_monthly * 0.35` минимум 300_000
- `engine.py:2172-2174` — CAPEX-доли в Green-плане: equipment=40%, inventory=15%, rent_setup=22%
- `engine.py:2261` — `monthly_credit = gap * 0.035`
- `engine.py:2272-2273` — резерв оборотки: `capex * 0.12 * months`, минимум 1_000_000
- `engine.py:2367-2377` — прайс Блок 10: finmodel 9000, bizplan 15000, заполнено 60%/45%
- `engine.py:2618-2626` — пороги capital_diff_status в Блоке 2: ≥5% surplus / ±5% match / ≤-30% critical_deficit

**Внутренние зависимости:**
- нет импортов из других файлов проекта (кроме внешних `pandas`, `os`, `glob`, `yaml`, `re`)

---

### 2.3 `api/report.py` (233 строки, 16.5 KB)

**Что делает.** Принимает dict из `run_quick_check_v3` и возвращает dict 12 блоков (block_1…block_12_checklist) для фронтенда. Не ведёт расчётов — только переформатирует данные и добавляет шаблонные тексты (дисклеймеры, health-indicators, сценарии, список оборудования).

**Экспортируемые функции:**
- `def fmt(n) -> str` — форматирование числа
- `def render_report_v4(result: dict) -> dict`

**Читает файлов:** нет.

**Магические числа / жёсткие константы:**
- `report.py:33` — дефолт `cogs_pct=0.35`
- `report.py:71-105` — захардкоженный словарь `eq_notes` — список типового оборудования для 33 ниш (COFFEE, BAKERY, DONER, PIZZA и т.д.)
- `report.py:125-129` — маркетинговые бюджеты сценариев: pess `0-15 тыс`, base `30-80 тыс`, opt `80-150 тыс`
- `report.py:153-159` — пороги health: payback 18/30 мес, gm 60/40, конкуренция 2/3, запас прочности 30/10

**Внутренние зависимости:** нет.

---

### 2.4 `api/gen_finmodel.py` (227 строк, 8.8 KB)

**Что делает.** Загружает шаблон `finmodel_template.xlsx` через openpyxl, подставляет параметры в лист `⚙️ ПАРАМЕТРЫ` и сезонность в `📊 ДОПУЩЕНИЯ`. Обновляет заголовки в merged cells. Сохраняет заполненную xlsx.

**Экспортируемые функции:**
- `def safe_write(ws, row, col, value)` — безопасная запись (пропускает MergedCell)
- `def safe_write_addr(ws, addr, value)`
- `def generate_finmodel(template_path, params, seasonality=None, output_path=None, eq_note='') -> str`
- `def generate_from_quickcheck(template_path, qc_result, output_path=None) -> str`

**Читает файлов:**
- Шаблон `templates/finmodel/finmodel_template.xlsx`

**Магические числа / жёсткие константы:**
- `gen_finmodel.py:13-53` — `PARAM_MAP`: жёстко захардкоженная карта «row→параметр» для листа `⚙️ ПАРАМЕТРЫ` (20 ячеек)
- `gen_finmodel.py:82` — дефолтная сезонность `[0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]`
- `gen_finmodel.py:84-114` — `defaults`: полный набор дефолтов (те же 23 параметра что в `main._compute_finmodel_data`, зеркалят друг друга)

**Внутренние зависимости:** нет.

> ⚠️ замечено: ТЕ ЖЕ дефолты параметров фин-модели фигурируют в `api/main.py:474-497` (`_compute_finmodel_data`) и в `api/gen_finmodel.py:85-113` (`generate_finmodel`) — две разные функции с одинаковыми жёстко зашитыми значениями.

---

### 2.5 `api/finmodel_report.py` (639 строк, 41.9 KB)

**Что делает.** Рендерит HTML-отчёт по финансовой модели (GeoSafe advisory style). Серверные SVG-графики без JS-библиотек.

**Экспортируемые функции:**
- `def fmt(n)`, `fmtM(n)`, `fmtPct(n)`, `safe(d, *keys, default=None)`, `color_for(value, thresholds)`
- `def svg_bar_chart(data, width=560, height=260, show_values=True) -> str`
- `def svg_line_chart(series, labels, width=560, height=280) -> str`
- (по логике файла: `render_finmodel_report(data) -> str` — вызывается из `main.py:776, 797`)

**Читает файлов:** нет.

**Магические числа:** стили/размеры графиков, цвета темы — не цифры расчёта.

**Внутренние зависимости:** нет.

---

### 2.6 `api/pdf_gen.py` (1365 строк, 63.7 KB)

**Что делает.** Генерирует 11-страничный A4 PDF-отчёт Quick Check через ReportLab. Регистрирует шрифты DejaVu, строит `BaseDocTemplate` с несколькими `PageTemplate`.

**Экспортируемые функции:**
- `def _register_fonts_once()`
- `def generate_quick_check_pdf(rendered_report, niche_id, ai_risks=None) -> tuple[bytes, str, str]` (вызывается из `main.py:370`)
- много внутренних `_draw_*`, форматтеров, `Flowable` классов

**Читает файлов:**
- `api/fonts/DejaVuSans.ttf`, `DejaVuSans-Bold.ttf`, `DejaVuSansMono.ttf`, `DejaVuSansMono-Bold.ttf`

**Магические числа:**
- `pdf_gen.py:60-96` — палитра цветов (ink/text/card/accent/green/amber/red)
- жёстко заданные brand-токены (#7C6CFF, #10B981, #F59E0B, #EF4444) — соответствуют CLAUDE.md

**Внутренние зависимости:** `from reportlab.*` — внешний; внутренних импортов проекта нет.

---

### 2.7 `api/grant_bp.py` (632 строки, 38.8 KB)

**Что делает.** Генерирует заполненный .docx-шаблон бизнес-плана на грант 400 МРП (Бастау Бизнес). Содержит свой справочник городов со среднимой зарплатой и мэппинг `FORMAT_NAMES` (имена форматов для документа).

**Экспортируемые функции:**
- `def generate_grant_bp(template_path, fio, iin, phone, address, legal_status, legal_address, experience_years, family_status, city_id, niche_id, format_id, project_name, location_description, loc_type, own_funds, grant_amount, start_month) -> bytes`

**Читает файлов:**
- Шаблон `templates/bizplan/grant_400mrp_template.docx`

**Магические числа / жёсткие константы:**
- `grant_bp.py:9-10` — `MRP_2026 = 4325`, `GRANT_400MRP = 400 * MRP_2026 = 1_730_000`
- `grant_bp.py:16-32` — `CITY_DATA`: справочник 15 городов с `avg_wage` (захардкоженные ₸)
- `grant_bp.py:34-80+` — `FORMAT_NAMES`: перевод format_id → русское имя, список шире чем 33 ниши движка (включает варианты типа COFFEE_VENDING, COFFEE_MOBILE)
- Файл содержит значительный объём текстовых шаблонов для каждой ниши (не прочитано полностью, виден только первый блок констант)

**Внутренние зависимости:** нет (только `python-docx`).

> ⚠️ замечено: `grant_bp.py` использует ключи городов в нижнем регистре (`"astana"`, `"almaty"`, …), тогда как `engine.py` работает с `city_id` в верхнем (`"ALA"`, `"ASTANA"`, `"SHYMKENT"`, `"AKTOBE"`, `"KARAGANDA"`, `"URA"` и т.п., видно в `01_cities.xlsx` и `05_tax_regimes.xlsx`). Маппинга между ними нет.

---

### 2.8 `api/gemini_rag.py` (210 строк, 9.2 KB)

**Что делает.** Читает `knowledge/niches/{NICHE}_insight.md` и запрашивает у Gemini 2.5 Flash структурированный JSON из 7 карточек рисков. Кеширует результат в памяти процесса. Также содержит `get_ai_interpretation` для AI-текста под отчётом и `clean_markdown`.

**Экспортируемые функции:**
- `def clean_markdown(text: str) -> str`
- `def _read_insight_file(niche_id: str) -> str`
- `def extract_niche_risks(niche_id: str, diag: dict = None) -> list[dict]`
- `def clear_risk_cache(niche_id: str = None) -> None`
- `def get_ai_interpretation(report_data: dict, knowledge_context: str = '') -> str`

**Читает файлов:**
- `knowledge/niches/{NICHE}_insight.md` (динамический путь)

**Магические числа:**
- `gemini_rag.py:119` — `temperature=0.4`, `maxOutputTokens=4096`
- `gemini_rag.py:141` — срезает результат до первых 7 карточек

**Внутренние зависимости:** нет.

---

### 2.9 `/engine/__init__.py` (4 строки, 0.2 KB)

**Что делает.** Объявляет пакет `engine` и пытается импортировать `from .engine import ZerekDB, run_quick_check, get_inflation_region` и `from .report import render_report`.

> ⚠️ замечено: в каталоге `/engine/` **нет** файлов `engine.py` или `report.py`. Этот пакет при импорте сломается. На деле `from engine import ...` в `api/main.py` резолвится на `/api/engine.py` через `sys.path.insert(0, BASE_DIR)`, где `BASE_DIR = api/`.

**Внутренние зависимости:** ломаны (не удаётся импортировать).

---

### 2.10 `/engine/gemini_rag.py` (40 строк, 2.1 KB)

**Что делает.** Очень короткий дубликат/предок `api/gemini_rag.py:get_ai_interpretation` — минимальная версия без кеша и без `extract_niche_risks`.

**Экспортируемые функции:**
- `def get_ai_interpretation(report_data: dict, knowledge_context: str = '') -> str`

**Читает файлов:** нет.

**Внутренние зависимости:** нет.

> ⚠️ замечено: дубликат функции из `api/gemini_rag.py`. Не импортируется нигде в проекте — grep по `from engine.gemini_rag`, `import engine.gemini_rag` даёт 0 хитов.

---

### 2.11 `/engine/run_test.py` (62 строки, 1.7 KB)

**Что делает.** Скрипт-тест: запускает `run_quick_check` (v1, уже не существует) на трёх сценариях (кофейня Актобе, барбершоп Алматы, автомойка Уральск) и печатает через `render_report`.

**Экспортируемые функции:** нет (top-level script).

**Читает файлов:** вызывает `ZerekDB(data_dir="/home/claude/zerek_data")`.

**Магические числа:** город-коды `"AKT"`, `"ALA"`, `"URA"` (НЕ совпадают с `"AKTOBE"`, `"ALMATY"`, `"URALSK"` из 05_tax_regimes / 01_cities).

**Внутренние зависимости:** `from engine import ZerekDB, run_quick_check` — ссылается на несуществующую функцию `run_quick_check` (в `api/engine.py` функция теперь называется `run_quick_check_v3`). `from report import render_report` — в `api/engine.py` есть `def render_report(result)` в виде заглушки, но каталог `/engine/` никаким `report.py` не содержит.

> ⚠️ замечено: скрипт сломан (обращается к старым API + к директории `/home/claude/zerek_data`, которой нет в репо). Нигде в коде не импортируется.

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 3 — XLSX/CSV ФАЙЛЫ
═══════════════════════════════════════════════════════════════════════

Всего xlsx: 17 файлов в `data/kz/` + 33 файла в `data/kz/niches/` + 1 шаблон в `templates/finmodel/` = **51 xlsx**. CSV-файлов в репо — **ноль** (упоминаемый в спеках `2gis_competitors.csv` не существует).

> ⚠️ замечено: `config/questionnaire.yaml:59` и `:375` ссылаются на источник `"data/2gis_competitors.csv"` — файла нет в репо.

### 3.1 Общие xlsx из `data/kz/`

#### `data/kz/01_cities.xlsx` — 15.8 KB
- Листы: `Города`, `Регионы демография`, `Городское vs Сельское`, `Динамика населения`
- `Города`: 20 строк × 16 колонок. Заголовки на строке 5 (header=4 для pandas): `city_id`, `Город`, `Регион`, `Тип города`, `Население всего (чел.)`, `Мужчины (чел.)`, `Женщины (чел.)`, `Доля городского нас. %`, `Дети 0-15 (чел.)`, `Трудоспособные 16-62 (чел.)` и др. Пример данных: `ALA` / `Алматы` / `г.Алматы` / `Мегаполис` / `2 348 103`.
- `Регионы демография`: 26 строк × 13 колонок, `Регион/Всего/Муж/Жен/0-15/…/16-62/…`
- `Городское vs Сельское`: 25 × 12
- `Динамика населения`: 28 × 8
- Используется в `api/engine.py:94` (`Города`, header=4)

#### `data/kz/02_wages_by_city.xlsx` — 11.0 KB
- Листы: `Зарплаты по регионам` (27×16), `Полная динамика (все годы)` (26×19)
- Источник: БНС РК Q3 2025 по всем регионам
- **НЕ используется** ни в `api/engine.py`, ни в других `.py` (grep по `02_wages` — 0 хитов)

#### `data/kz/03_wages_by_industry.xlsx` — 13.9 KB
- Листы: `Зарплаты по отраслям` (96×8), `Ключевые для ниш ZEREK` (11×6)
- Маппит `niche_id` ZEREK → отрасль БНС и выдаёт Q3 2025 зарплату
- **НЕ используется** (grep по `03_wages` — 0 хитов в `.py`)

#### `data/kz/04_wages_by_role.xlsx` — 11.0 KB
- Листы: `Зарплаты по должностям` (24×13), `Калькулятор ФОТ` (12×12), `Схемы оплаты` (11×6)
- Содержит ставки по городам Алматы/Астана/Актобе/Шымкент/Уральск/Тараз
- **НЕ используется** (grep по `04_wages` — 0 хитов в `.py`)

#### `data/kz/05_tax_regimes.xlsx` — 14.1 KB
- Листы: `tax_regimes_2026` (5×11), `city_ud_rates_2026` (16×8), `b2b_nds_warnings` (10×5), `payroll_taxes_2026` (8×6), `key_params_2026` (13×5), `notes` (24×2)
- `tax_regimes_2026`: UD (Упрощённая) 4% базовая (маслихат ±50%: 2-6%), SELF (Самозанятый) 0%, OUR (ОУР) 20%, KFH
- `city_ud_rates_2026`: 15 городов с ставкой УД (ASTANA=3, ALMATY=3, SHYMKENT=2, AKTOBE=3, KARAGANDA=3, ATYRAU=3, AKTAU=3, KOSTANAY=3, PAVLODAR=3, SEMEY=3, USKAMAN=3, TARAZ=3, TURKESTAN=2, PETROPAVL=3, KOKSHETAU=3)
- `key_params_2026`: МРП 2026 = 4325, МЗП 2026 = 85000, НДС = 16%, прожиточный минимум = 50851
- `payroll_taxes_2026`: ОПВ 10%, ОПВР 3.5%, ВОСМС 2%, ООСМС 3%
- Используется в `api/engine.py:113-114` (листы `tax_regimes_2026` header=0, `city_ud_rates_2026` header=0)
- Листы `b2b_nds_warnings`, `payroll_taxes_2026`, `key_params_2026`, `notes` — **НЕ используются в коде**

> ⚠️ замечено: `CLAUDE.md` утверждает УСН Караганда 2% / Атырау 2% / УК 2%. В `05_tax_regimes.xlsx:city_ud_rates_2026` стоит 3%/3%/3%. Расхождение между документацией и источником данных.

> ⚠️ замечено: в `05_tax_regimes.xlsx:city_ud_rates_2026` нет city_id "OSKEMEN"/"URALSK" — есть `USKAMAN` (Усть-Каменогорск). При этом `engine.py:CITY_CHECK_COEF` использует ключ `ust_kamenogorsk`. Ключи не стыкуются.

#### `data/kz/07_niches.xlsx` — 13.6 KB (2026-04-20)
- Листы: `Ниши` (64×12), `Специфичные вопросы` (23×4), `Типы локации` (16×3)
- Построен `scripts/build_07_niches.py`. 58 ниш (TARGET_NICHES)
- `Ниши` header на строке 6 (pandas header=5): `niche_id`, `niche_name`, `requires_license`, `license_description`, `self_operation_possible`, `class_grades_applicable`, `allowed_location_types`, `default_location_type`, `area_question_mode`, `staff_question_mode`, …
- Используется в `api/engine.py:96-97`

#### `data/kz/08_niche_formats.xlsx` — 14.2 KB (2026-04-20)
- Лист: `Форматы` (135×9). Header строка 6 (pandas header=5): `niche_id`, `format_id`, `format_name`, `area_m2`, `capex_standard`, `class`, `format_type`, `allowed_locations`, `typical_staff`
- Пример данных: `BARBER / BARBER_SOLO / Барбер-одиночка / 15 / 1800000 / эконом / SOLO / rent_in_salon / (пусто)`; `BARBER / BARBER_STANDARD / Барбершоп 3-5 кресел / 45 / 7500000 / стандарт / STANDARD / city_center,residential,residential_complex,mall_standard / барбер:4|администратор:1`
- Построен `scripts/build_08_niche_formats.py`
- Используется в `api/engine.py:98`, в функциях `_formats_from_fallback_xlsx`, `get_formats_v2`, `compute_block2_passport`, `_red_alternatives`

#### `data/kz/09_surveys.xlsx` — 63.4 KB (2026-04-20)
- Листы: `Вопросы` (169×10), `Применимость` (1918×5), `Зависимости` (13×4)
- `Вопросы` header row 6: `qid`, `question_text`, `input_type`, `options`, `placeholder`, `min`, `max`, `step`, `unit`, `help`. 163 вопроса каталога.
- `Применимость`: qid × niche_id × tier (express|finmodel) × order × required. ~1914 строк применимости.
- `Зависимости`: qid × depends_on × condition × action
- Построен `scripts/build_09_surveys.py`
- Используется в `api/engine.py:100-102`; отдаётся фронту через `/niche-survey/{niche_id}`

#### `data/kz/11_rent_benchmarks.xlsx` — 15.7 KB
- Листы: `Аренда по городам` (58×15), `Калькулятор для движка` (36×9), `Советы по локации` (13×5)
- `Калькулятор для движка` header row 6: `city_id`, `Город`, `Тип локации`, `Площадь`, `Медиана (₸/м²/мес)`, `Коммуналка (₸/м²/мес)`, `Пример 30/50/80 м²`
- Пример: `ALA / Алматы / Центр стрит 1 лин / до 20 м² / 16 000 / 900`
- Источник: Krisha.kz, OLX, опросы предпринимателей Q1 2026
- Используется в `api/engine.py:105` (лист `Калькулятор для движка`, header=5)

#### `data/kz/13_macro_dynamics.xlsx` — 15.5 KB
- Листы: `Инфляция по регионам` (27×8), `Индекс КЭИ` (26×7), `Динамика торговли` (20×4), `Курс и импорт` (21×4), `Параметры для Quick Check` (16×5)
- Используется в `api/engine.py:106` только лист `Инфляция по регионам` (header=5). Другие листы не читаются.

#### `data/kz/14_competitors.xlsx` — 9.3 KB
- Листы: `Конкуренты по городам` (39×11), `Сигналы для Quick Check` (10×4)
- `Конкуренты по городам` header row 6: `comp_id`, `niche_id`, `city_id`, `Город`, `Тип локации`, `Кол-во конкурентов (оценка)`, `Кол-во на 10 000 жителей`, `Уровень насыщения (1-5)`, `Лидеры рынка`, `Дата проверки`
- Используется в `api/engine.py:107` (лист `Конкуренты по городам`, header=5)
- Лист `Сигналы для Quick Check` — **не используется в коде**

#### `data/kz/15_failure_cases.xlsx` — 16.3 KB
- Листы: `База факапов` (16×15), `Классификатор причин` (14×6), `Паттерны по нишам` (13×7), `Как добавлять кейсы` (19×3)
- `Паттерны по нишам` header row 6: `niche_id`, `Ниша`, `Медиана месяца закрытия`, `Топ-1 причина`, `Топ-2 причина`, `Доля закрытых до 6 мес. (%)`, `Фраза для отчёта Quick Check`
- Используется в `api/engine.py:108` только лист `Паттерны по нишам`

#### `data/kz/17_permits.xlsx` — 8.5 KB
- Лист `Разрешения и лицензии` (25×10). Header row 6.
- Используется в `api/engine.py:109`

#### `data/kz/19_inflation_by_niche.xlsx` — 9.9 KB
- Листы: `Инфляция по статьям ниш` (36×10), `Прогноз роста OPEX` (13×7)
- Используется в `api/engine.py:110` — лист `Прогноз роста OPEX` **загружается в `db.inflation_niche`, но НИГДЕ в коде не читается дальше** (нет обращений к `self.inflation_niche` / `db.inflation_niche` в расчётах)

#### `data/kz/20_scenario_coefficients.xlsx` — 7.6 KB
- Листы: `scenario_coefficients` (18×9), `notes` (12×2)
- Содержит `pessimistic_traffic_coef` / `base` / `optimistic` и аналогично по чеку. Данные по `format_id` (COFFEE_KIOSK, COFFEE_ISLAND, DONER_KIOSK и т.п.)
- **НЕ используется** в коде (grep по `20_scenario` — 0 хитов в `.py`). Вместо него в `engine.py` коэффициенты жёстко захардкожены в строке 728 (0.75/1.0/1.25 для трафика, 0.90/1.0/1.10 для чека).

#### `data/kz/21_opex_benchmarks.xlsx` — 8.3 KB
- Листы: `opex_benchmarks` (18×13), `notes` (16×2)
- Содержит `utilities_pct`, `utilities_fixed_kzt`, `consumables_pct`, `marketing_pct`, `marketing_fixed_kzt`, `packaging_pct`, `software_kzt`, `transport_kzt`, `misc_pct`, `total_variable_pct` по `format_id`
- **НЕ используется** в коде (grep по `21_opex` — 0 хитов в `.py`)

#### `data/kz/22_staff_scaling.xlsx` — 9.2 KB
- Листы: `staff_scaling` (39×11), `notes` (14×2)
- Содержит стадии `start/growth/scale` с `revenue_from/to`, `role`, `headcount`, `salary_kzt`, `is_owner_role`
- **НЕ используется** в коде (grep по `22_staff` — 0 хитов в `.py`)

---

### 3.2 Per-niche xlsx из `data/kz/niches/` (33 файла)

Все файлы имеют одинаковую структуру 14 листов:
`FORMATS`, `STAFF`, `FINANCIALS`, `CAPEX`, `GROWTH`, `TAXES`, `MARKET`, `LAUNCH`, `INSIGHTS`, `PRODUCTS`, `MARKETING`, `SUPPLIERS`, `SURVEY`, `LOCATIONS`.

Header — на строке 3 (pandas header=2). Каждая строка = один формат × класс.

Пример полей листа `FORMATS` (из `niche_formats_COFFEE.xlsx`): `num`, `format_name`, `format_id`, `class`, `class_desc`, `area_min`, `area_med`, `area_max`, `seats_min`, `seats_max`, `qty_points`, `size_desc`, `loc_type`, `loc_dependency`, `classes_available`.

Пример полей `FINANCIALS`: `format_id`, `class`, `check_min`, `check_med`, `check_max`, `traffic_min`, `traffic_med`, `traffic_max`, `cogs_pct`, `margin_pct`, `rent_min`, `rent_med`, `rent_max`, `deposit_months`, `utilities`, `marketing`, `consumables`, `software`, `transport`, `sez_month`, `loss_pct`, `rampup_*`, `s01…s12` (сезонность), `opex_min`, `opex_med`, `opex_max`, `revenue_med` и т.д.

Пример полей `CAPEX`: `format_id`, `class`, `capex_min`, `capex_med`, `capex_max`, `equipment`, `renovation`, `furniture`, `first_stock`, `permits_sez`, `working_cap_3m`, `deprec_years`, `notes`.

Пример полей `STAFF`: `format_id`, `class`, `positions`, `headcount`, `founder_role`, `schedule`, `backup_needed`, `fot_net_min`, `fot_net_med`, `fot_net_max`, `fot_full_min`, `fot_full_med`, `fot_full_max`, `hire_m3`, `hire_m6`, `hire_m12`.

Пример полей `TAXES`: `format_id`, `class`, `tax_regime`, `selfemployed_ok`, `simplified_ok`, `b2b`, `oked`, `nds_risk`, `threshold_simplified`, `notes`.

**Пример данных** (`niche_formats_COFFEE.xlsx`, лист `FINANCIALS`, первые 3 data-row):
- `COFFEE_VENDING / Эконом / 394 / 500 / 592 / 20 / 35 / 50 / 0.25 / 0.75 / 20 000 / 30 000 …`
- `COFFEE_VENDING / Стандарт / 400 / 500 / 600 / 30 / 55 / 80 / 0.28 / 0.72 / 30 000 / 45 000 …`
- `COFFEE_VENDING / Бизнес / 384 / 500 / 615 / 40 / 70 / 100 / 0.3 / 0.7 / 50 000 / 65 000 …`

Пример `CAPEX` COFFEE_VENDING: Эконом 800K/1M/1.2M ₸, Стандарт 1.5M/2M/2.5M ₸, Бизнес 2.5M/3M/3.5M ₸.

Пример `TAXES` COFFEE_VENDING: Эконом — Самозанятый, Стандарт/Бизнес — Упрощёнка, ОКЭД 56.10, порог 82 931 200 (по мрп).

Все 33 файла загружаются **динамически** через `glob(data/kz/niches/niche_formats_*.xlsx)` в `api/engine.py:124-125` → `ZerekDB._load_niches()`. Файлы НЕ помечаются по именам в коде.

Размеры файлов варьируют от 18 KB (WATER, LASH) до 70 KB (COFFEE) — больше форматов/классов → больше строк.

---

### 3.3 Шаблон `templates/finmodel/finmodel_template.xlsx` — 88.1 KB
- Заполняется функцией `api/gen_finmodel.generate_finmodel`
- Имеет листы `📋 НАВИГАЦИЯ`, `⚙️ ПАРАМЕТРЫ`, `📊 ДОПУЩЕНИЯ`, `🎯 ДАШБОРД`, `📈 P&L`, `💰 CASH FLOW`, `📑 БАЛАНС` (из `gen_finmodel.py:153-160`)
- Адреса ячеек для подстановки параметров — `gen_finmodel.py:15-53` (row 5, 6, 7, 8, 9, 12, 13, 14, 15, 16, 19, 20, 23, 25, 26, 27, 28, 29, 30, 31, 37, 38, 39, 40, 46, 47, 48, 52 в колонке C)

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 4 — YAML/JSON КОНФИГИ
═══════════════════════════════════════════════════════════════════════

### 4.1 `config/niches.yaml` — 9.7 KB
- Ключи верхнего уровня: `niches:`, `categories:`
- Под `niches:` — 57 ниш, каждая как `NICHE_ID: {name_rus, category, archetype (A-F), icon}`. Примеры подключей: `BARBER`, `BEAUTY`, `MANICURE`, `COFFEE`, `BAKERY`, `FITNESS`, `PVZ`, `AUTOSERVICE` и др.
- Под `categories:` — 12 категорий для UI-группировки (`beauty`, `food`, `retail`, `health`, `services`, `auto`, `sport`, `education`, `production`, `b2b`, `hospitality`, `entertainment`), каждая как `{label_rus, order}`
- Используется: загружается в `ZerekDB.configs["niches"]` через `_load_yaml_configs_on`; читается в `compute_block2_passport`, `compute_block4_unit_economics`, `compute_block5_pnl`, `get_quickcheck_survey`

> ⚠️ замечено: имена ниш в `niches.yaml` и в `data/kz/niches/niche_formats_*.xlsx` расходятся. В yaml: `MANICURE`, `PHARMACY`, `TIRESERVICE`, `COMPCLUB`, `MARTIAL_ARTS`, `FOOTBALL_SCHOOL`, `GROUP_FITNESS`, `CROSSFIT`. В файлах xlsx: `NAIL`, `PHARMA`, `TIRE`, `CYBERCLUB`. Часть ниш из yaml вообще отсутствует в xlsx (BEAUTY, YOGA, LANGUAGES, ACCOUNTING, KIDSCENTER, MEATSHOP, AUTOPARTS, BUILDMAT, PETSHOP, CATERING, BUBBLETEA, HOTEL, LAUNDRY, DRIVING, PRINTING, LOFTFURNITURE, CARGO, REALTOR, EVALUATION, NOTARY, COSMETOLOGY, OPTICS, PHOTO, DETAILING, CARPETCLEAN, MARTIAL_ARTS, FOOTBALL_SCHOOL, GROUP_FITNESS, CROSSFIT), но есть в `knowledge/niches/*_insight.md`.

### 4.2 `config/archetypes.yaml` — 10.9 KB
- Ключи верхнего уровня: `archetypes:`
- Под `archetypes:` — 6 архетипов A/B/C/D/E/F. Каждый содержит: `name_rus`, `description_rus`, `revenue_formula`, `key_metrics`, `niches:` (список), `finmodel_operational_questions:` (список из 5-6 вопросов)
- Архетипы: A — Услуги с мастерами, B — Общепит, C — Розничная торговля, D — Абонементы, E — Проектный, F — Мощность
- Используется: в `engine._archetype_of` (через `configs["niches"]["niches"][niche_id]["archetype"]`). Поле `finmodel_operational_questions` **НЕ читается** в коде — его нет в движке.

### 4.3 `config/locations.yaml` — 6.5 KB
- Ключи верхнего уровня: `locations:`, `line_modifier:`, `format_type_rules:`
- Под `locations:` — 12 типов + `rent_in_salon`. Поля: `label_rus`, `description_rus`, `supports_line_modifier`, `rent_coefficient`, `traffic_level`, иногда `rent_flat_monthly_kzt` (для rent_in_salon = 80000).
- Под `line_modifier:` — `enabled_for_locations`, `not_applied_to_locations`, `lines: {line_1, line_2}` с множителями `rent_multiplier` (1.0 / 0.7) и `traffic_multiplier` (1.0 / 0.5).
- Под `format_type_rules:` — 7 типов (`SOLO`, `HOME`, `MOBILE`, `KIOSK`, `HIGHWAY`, `PRODUCTION`, `STANDARD`) с описанием видимости полей.
- Используется: `configs["locations"]["locations"]` — читается в `compute_block2_passport._format_location` (только для label_rus) и в `get_quickcheck_survey` (передаётся фронту целиком). **Коэффициенты `rent_coefficient` и `traffic_multiplier` в расчётах НЕ используются** — аренда берётся из `11_rent_benchmarks.xlsx`.

### 4.4 `config/questionnaire.yaml` — 18.1 KB
- Ключи верхнего уровня: `questionnaire:`
- Под `questionnaire:` — `quickcheck:` (8 вопросов, price_kzt: 5000), `finmodel:` (наследуется, +13-15 вопросов, 9000), `bizplan:` (+7 вопросов, 15000)
- Каждый вопрос: `id`, `order`, `required`, `type`, `label_rus`, `help_rus`, `source` / `options` / `visibility_logic` / `triggers`
- Упоминает источники: `data/08_niche_formats.xlsx`, `data/2gis_competitors.csv` (нет в репо), `config/niches.yaml`, `niche_risks from insight file`
- Используется: `configs["questionnaire"]["questionnaire"]["quickcheck"]` → `get_quickcheck_survey` → отдаётся на `/quickcheck-survey/{niche_id}`. FinModel/BizPlan блоки из yaml в коде движка не парсятся.

### 4.5 JSON-файлы
- `manifest.json` (0.6 KB) — PWA manifest, не связан с Quick Check
- `railway.json` (0.2 KB) — конфиг Railway деплоя
- `knowledge/niches/_yt_videos.json` (81.2 KB) — JSON массив YouTube-видео по нишам; **не используется** в Python-коде расчёта (grep по `_yt_videos` / `yt_videos` — 0 хитов в `.py`; скорее всего потребляется фронтом Academy или wiki)
- `.claude/settings.local.json` (5.2 KB) — локальные настройки Claude Code

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 5 — ИНСАЙТ-ФАЙЛЫ ПО НИШАМ
═══════════════════════════════════════════════════════════════════════

Расположение: `knowledge/niches/*_insight.md`. Всего файлов — **43** (+ 1 json `_yt_videos.json`). Отсутствует только `COFFEE_insight.md`.

**Типовая структура** (на примере `BAKERY_insight.md`, 16.8 KB):
- `# Инсайты: Пекарня`
- `## Ключевые принципы управления`
- `## Типичные ошибки новичков`
- `## Экономика и юнит-экономика` — **здесь конкретные цифры**
- `## Операционные нюансы`
- `## Маркетинг и привлечение клиентов`
- `## Финансовые риски и ловушки`
- `## Что отличает выживших от закрывшихся`

**Секции с цифрами**. Пример из `BAKERY_insight.md` раздел «Экономика и юнит-экономика»:
> Food cost: 28-38% от выручки — оптимум; выше 40% — бизнес в зоне риска.
> Маржинальность до аренды и зарплат: 60-72% при правильном управлении себестоимостью.
> Аренда: Не выше 12-15% от выручки. Для проходных точек в ТЦ — до 18% при высоком среднем чеке.
> Оборудование (стартовые вложения): Печь, расстойка, тестомес, холодильник, витрина — суммарно от 30 до 80% общих стартовых инвестиций в зависимости от формата и мощности.
> Окупаемость: 10-18 месяцев при стабильном потоке. Кафе-пекарня с посадкой — 14-24 месяца из-за более высоких вложений.
> Потери на остатках: Допустимо не более 5-8% от выпуска. Превышение 15% — системная проблема с планированием.
> Точка безубыточности по выручке: Обычно достигается при загрузке 55-65% от расчётной производственной мощности.

**Полный список инсайт-файлов** (размер KB):
- ACCOUNTING_insight.md — 25.7
- AUTOPARTS_insight.md — 20.6
- AUTOSERVICE_insight.md — 21.5
- BAKERY_insight.md — 16.8
- BROW_insight.md — 18.0
- BUBBLETEA_insight.md — 22.5
- BUILDMAT_insight.md — 20.4
- CANTEEN_insight.md — 17.6
- CARGO_insight.md — 12.1
- CARPETCLEAN_insight.md — 24.7
- CONFECTION_insight.md — 17.5
- COSMETOLOGY_insight.md — 19.1
- CYBERCLUB_insight.md — 22.7
- DENTAL_insight.md — 19.3
- DETAILING_insight.md — 25.4
- DRIVING_insight.md — 15.2
- DRYCLEAN_insight.md — 14.4
- FASTFOOD_insight.md — 18.8
- FITNESS_insight.md — 21.2
- FLOWERS_insight.md — 18.0
- FRUITSVEGS_insight.md — 17.5
- FURNITURE_insight.md — 15.3
- KIDSCENTER_insight.md — 23.1
- KINDERGARTEN_insight.md — 15.6
- LANGUAGES_insight.md — 11.6
- LASH_insight.md — 19.7
- MASSAGE_insight.md — 18.3
- MEATSHOP_insight.md — 35.4 (самый большой)
- NAIL_insight.md — 14.4
- OPTICS_insight.md — 19.2
- PETSHOP_insight.md — 11.0
- PHARMA_insight.md — 13.0
- PHOTO_insight.md — 23.2
- PIZZA_insight.md — 15.9
- PVZ_insight.md — 11.4
- REALTOR_insight.md — 13.3
- REPAIR_PHONE_insight.md — 24.0
- SEMIFOOD_insight.md — 18.2
- SUGARING_insight.md — 20.2
- SUSHI_insight.md — 16.9
- TAILOR_insight.md — 11.3
- TIRE_insight.md — 15.5
- WATERPLANT_insight.md — 19.5
- YOGA_insight.md — 22.7

**Использование в коде:**
- `api/gemini_rag.py:_read_insight_file` — читает `knowledge/niches/{NICHE}_insight.md`. Вызывается из `extract_niche_risks` (7 карточек рисков через Gemini 2.5 Flash)
- `api/engine.py:1895-1999` — `compute_block9_risks` пытается regex-парсить секции «Риски | Подводные камни | Причины провала» (таких секций в файлах нет — секции названы «Финансовые риски и ловушки» и «Типичные ошибки новичков»)

> ⚠️ замечено: `compute_block9_risks` ищет заголовки `## Риски | ## Подводные камни | ## Причины провала` в insight-файлах. В реальных файлах таких заголовков нет — значит regex всегда промахивается, и код выпадает на `generic_risks[arch]` (жёстко захардкоженные тексты для 6 архетипов в `engine.py:1900-1979`).

> ⚠️ замечено: отсутствует `COFFEE_insight.md` — при запросе Quick Check по кофейне `extract_niche_risks` вернёт пустой список; `compute_block9_risks` тоже использует generic.

> ⚠️ замечено: инсайт-файлы существуют для ниш, для которых **нет** `niche_formats_*.xlsx` и, соответственно, движок не может посчитать Quick Check: ACCOUNTING, AUTOPARTS, BUBBLETEA, BUILDMAT, CARGO, CARPETCLEAN, COSMETOLOGY, DETAILING, DRIVING, KIDSCENTER, LANGUAGES, MEATSHOP, OPTICS, PETSHOP, PHOTO, REALTOR, YOGA.

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 6 — HTML/JS для QUICK CHECK
═══════════════════════════════════════════════════════════════════════

В `/products/` лежат несколько версий точки входа Quick Check — одна активная, остальные legacy/дубли/редиректы.

### 6.1 `products/quick-check.html` — 0.4 KB — редиректор
- Содержимое: meta-refresh на `qc-v3.html` + JS `window.location.replace('qc-v3.html' + window.location.search)`
- Файл — точка входа Mini App из Telegram (URL из BotFather должен открывать именно этот файл). Сейчас он перенаправляет на `qc-v3.html`.

### 6.2 `products/qc-v3.html` — 78.4 KB, 1449 строк — **активный UI анкеты Quick Check**
- Тёмная тема (`--bg:#0F0F0F`). Использует Telegram WebApp JS (`telegram-web-app.js`)
- API: `var API = 'https://web-production-921a5.up.railway.app';` (qc-v3.html:328)
- XHR-клиенты `apiGet`, `apiPost` (не fetch — просто XHR)
- Последовательность вызовов к API:
  - `GET /configs` (строка 367)
  - `GET /cities` (371)
  - `GET /formats-v2/{niche_id}` (527)
  - `POST /quick-check` (825) — отправляет собранное `QC {niche_id, format_id, city_id, loc_type, location_line, experience, payroll_type, entrepreneur_role, capital_own, capital_needed, …}`
- Рендер экрана результата — `showResultError` на `qc-v3.html:836` и далее
- Источник данных: API (`web-production-921a5.up.railway.app`)
- Сохранение результатов: отсутствует (ничего в localStorage не пишет в момент результата; данные хранит только в in-memory `QC`)

### 6.3 `products/index.html` — 0.3 KB — редиректор
- meta-refresh на `app.html`
- По `CLAUDE.md` Mini App URL на этот файл: `https://academyzerek-ops.github.io/ZEREK/products/index.html` — открывает старый лендинг продуктов.

### 6.4 `products/app.html` — 145.1 KB, 3737 строк — большой комбайн
- Та же тёмная тема
- API endpoint (`app.html:2113`): `var API = 'https://web-production-921a5.up.railway.app';`
- Эндпоинты к которым ходит:
  - `GET /cities` (3128)
  - `GET /niches` (3136)
  - `GET /formats/{niche_id}` (3241)
  - `POST /quick-check` (3375)
- Объединяет несколько экранов: лендинг продуктов, анкета Quick Check, HTML-отчёт
- Работает как отдельная SPA (Single Page App) внутри Telegram Mini App

### 6.5 `products/quick-check-v2.html` — 54.8 KB, 1162 строки — legacy-вариант анкеты (версия до qc-v3)
- Не упоминается ни в одном редиректе (кроме legacy.html → quick-check-v2.html возможных кросс-ссылок)
- Grep показывает, что файл существует сам по себе

### 6.6 `products/quick-check.legacy.html` — 85.9 KB, 1582 строки — ещё более старая версия
- Строка 956: `// Back from report to wizard`
- По коммитам (`d7428fd`) видно, что имя `quick-check.html` переименовывалось для обхода кэша Telegram

### 6.7 Активный рендер-поток
Между `qc-v3.html` и `app.html` — два независимых UI, обращающихся к одному и тому же API `/quick-check`. Какой из них «канонический Mini App» зависит от того, что стоит в BotFather как Web App URL.

> ⚠️ замечено: `CLAUDE.md:21` и `:60` дают разные Mini App URL: один `products/quick-check.html` (редиректит на qc-v3), другой `products/index.html` (редиректит на app.html). В репо есть оба активных UI — qc-v3.html и app.html — с разными фронтовыми контрактами (в app.html идут `/niches` и `/formats`, в qc-v3.html — `/configs` и `/formats-v2`).

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 7 — ТЕКУЩИЙ FLOW QUICK CHECK
═══════════════════════════════════════════════════════════════════════

### 7.1 Endpoint
- Путь: `/quick-check`
- Метод: POST
- Реализация: `api/main.py:141-237` (`def quick_check(req: QCReq)`)

### 7.2 Входные параметры (`class QCReq`, `main.py:48-58`)
```
city_id: str
niche_id: str
format_id: str
cls: str = "Стандарт"
area_m2: float = 0
loc_type: str = ""
capital: Optional[int] = 0
qty: int = 1
founder_works: bool = False
rent_override: Optional[int] = None
start_month: int = 4
capex_level: str = "стандарт"
has_license: Optional[str] = None
staff_mode: Optional[str] = None
staff_count: Optional[int] = None
specific_answers: Optional[dict] = None
```

### 7.3 Последовательность вызовов
1. Маппинг `capex_level` на `cls` через `CAPEX_TO_CLS` (`main.py:145`)
2. `result = run_quick_check_v3(db, city_id, niche_id, format_id, cls, area_m2, loc_type, capital, qty, founder_works, rent_override, start_month)` — главный расчёт, `engine.py:620-893`. Возвращает dict с ключами: `input`, `market`, `capex`, `staff`, `financials`, `breakeven`, `scenarios`, `payback`, `owner_economics`, `tax`, `verdict`, `alternatives`, `risks`, `products`, `insights`, `marketing`, `cashflow`. Внутри:
   - `db.get_format_row(...)` для листов FORMATS / FINANCIALS / STAFF / CAPEX / TAXES / MARKET
   - `db.get_format_all_rows(...)` для PRODUCTS / INSIGHTS / MARKETING
   - `get_city`, `get_competitors`, `get_failure_pattern`, `get_permits`
   - `get_city_tax_rate` → `tax_rate`
   - `get_city_check_coef` → масштабирует check_med/check_min/check_max/revenue_med
   - `get_rent_median` (+ `rent_override` если задан)
   - `calc_cashflow` на 12 месяцев, `calc_breakeven`, `calc_payback`
   - `calc_owner_economics` → `calc_closure_growth_points`, `calc_stress_test`
   - 3 сценария pess/base/opt (локальный цикл)
   - Скоринг → `verdict` (`green/yellow/red` по score 5+/2+)
   - `alternatives` — текстовые подсказки, если red
3. `report = render_report_v4(result)` — `api/report.py:13-233`. Превращает result в 12 блоков (`block_1`…`block_12_checklist`) + `health`.
4. Блоки Quick Check v1.0 spec (7 try/except блоков, `main.py:161-229`):
   - `compute_block1_verdict(result, block1_inputs)` — вердикт / scoring / main_metrics
   - `compute_block2_passport(db, result, block2_inputs)` — паспорт
   - `compute_block3_market(db, result, block1_inputs)`
   - `compute_block4_unit_economics(db, result, block1_inputs, block2=block2_obj)`
   - `compute_block5_pnl(db, result, block1_inputs)`
   - `compute_block6_capital(db, result, block1_inputs, block2=block2_obj)`
   - `compute_block7_scenarios(db, result, block1_inputs)`
   - `compute_block8_stress_test(db, result, block1_inputs)`
   - `compute_block9_risks(db, result, block1_inputs)`
   - `compute_block10_next_steps(db, result, block1_inputs, block1=block1_obj, block2=block2_obj)`
5. Если есть adaptive-поля — в `report["user_inputs"]` впихиваются `has_license/staff_mode/staff_count/specific_answers`
6. `return {"status":"ok","result":clean(report)}` — JSON

### 7.4 Формат ответа клиенту
- JSON с ключом `status` и полем `result` (весь отчёт)
- Клиент (`qc-v3.html` / `app.html`) рендерит HTML прямо на странице (Mini App) из полученного JSON

### 7.5 Где сохраняются результаты
- В рамках `/quick-check` **нигде не сохраняются**. БД/хранилища нет
- Для `/quick-check/pdf` и `/finmodel` и `/grant-bp` — есть in-memory store `_file_store` в `main.py:391-406`, TTL 7 дней. Токен → bytes + filename + media_type
- Никакой базы данных, никакого кеша результатов Quick Check

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 8 — ИСТОЧНИКИ ЦИФР (САМОЕ ВАЖНОЕ!)
═══════════════════════════════════════════════════════════════════════

### 8.1 Средний чек по нишам

| Источник | Тип | Детали |
|---|---|---|
| `data/kz/niches/niche_formats_{NICHE}.xlsx` лист `FINANCIALS` колонки `check_min/check_med/check_max` | xlsx | **основной источник** — считывается в `engine.py:640-641, 665-670`. Потом домножается на `get_city_check_coef` |
| `engine.py:40-46` `CITY_CHECK_COEF` | жёстко в .py | Ценовой коэффициент по 15 городам (0.95-1.05) |
| `engine.py:1499` `avg_check = _safe_int(fin.get('check_med'), 0) or 3000` | жёстко в .py | Фолбэк 3000 ₸ в `compute_block4_unit_economics` |
| `engine.py:1815` `avg_check = ... or 3000` | жёстко в .py | Фолбэк 3000 ₸ в `compute_block8_stress_test` |
| `main.py:476, 729` `check_med: 1400` | жёстко в .py | Дефолт в финмодели |
| `gen_finmodel.py:91` `check_med: 1400` | жёстко в .py | Тот же дефолт (дублируется) |
| `report.py:33` `check_med = fin.get("check_med", 0)` | из QC | Передаётся из engine |

### 8.2 Маржа / food cost / COGS

| Источник | Тип | Детали |
|---|---|---|
| `niche_formats_{NICHE}.xlsx` лист `FINANCIALS` колонки `cogs_pct`, `margin_pct` | xlsx | Основной источник |
| `engine.py:22-23` `DEFAULTS['cogs_pct']=0.30`, `DEFAULTS['margin_pct']=0.70` | жёстко в .py | Фолбэк |
| `engine.py:1501, 2074` `cogs_pct = _safe_float(fin.get('cogs_pct'), 0.30)` | жёстко в .py | Дефолт 0.30 в блоках 4, 5 |
| `engine.py:1558-1568` food cost breakdown для архетипа B | жёстко в .py | food_cost = check × cogs_pct |
| `main.py:480, 734` `cogs_pct: 0.35` | жёстко в .py | Дефолт финмодели |
| `gen_finmodel.py:96` `cogs_pct: 0.35` | жёстко в .py | Дубль дефолта |
| `report.py:32, 156` `cogs_pct = fin.get("cogs_pct", 0.35)` | из QC + фолбэк | margin в отчёте = `(1 - cogs_pct) × 100` |
| `data/kz/21_opex_benchmarks.xlsx` `total_variable_pct` | xlsx | **Есть, но не используется** |
| `engine.py:2029` `cogs_y = int(revenue_y * (cogs_pct or 0.30))` | жёстко | Block 5 |
| `engine.py:1524` `piece_rate = int(avg_check * 0.40)` (архетип A) | жёстко | Доля мастеру |
| `engine.py:1524` `materials = int(avg_check * 0.12)` (архетип A) | жёстко | Материалы на услугу |
| `engine.py:1586-1593` архетип C: `markup_pct=50`, `cogs≈67`, `c_fot=10`, `c_rent=12`, `c_over=8`, `c_loss=5` | жёстко | Структура ритейла |

### 8.3 Ставки аренды по городам

| Источник | Тип | Детали |
|---|---|---|
| `data/kz/11_rent_benchmarks.xlsx` лист `Калькулятор для движка` | xlsx | **основной источник** — `rent_per_m2_median`, `utilities_per_m2` |
| `engine.py:300-312` `get_rent_median` — поиск по `city_id + loc_type` | читает xlsx | Фолбэк: `(3000, 500)` если нет строки |
| `niche_formats_{NICHE}.xlsx` лист `FINANCIALS` колонки `rent_min/rent_med/rent_max` | xlsx | Альтернативный путь — если движок решает использовать benchmark из ниши |
| `engine.py:681` `rent_month = rent_override if rent_override else _safe_int(fin.get('rent_med'), int(area_m2 * rent_median_m2))` | логика | rent_med ниши приоритетнее area × city |
| `engine.py:1503` `rent_month = _safe_int(fin.get('rent_month'), 0)` | из QC | Block 4 |
| `engine.py:1817` `rent = ... or 150_000` | жёстко | Фолбэк 150K ₸ в Block 8 |
| `main.py:482, 736` `rent: 70000` | жёстко | Дефолт финмодели |
| `gen_finmodel.py:98` `rent: 70000` | жёстко | Дубль |
| `locations.yaml:*.rent_coefficient` | yaml | **Есть, но не применяется** в расчёте |
| `locations.yaml:line_modifier.lines.line_2.rent_multiplier=0.7` | yaml | **Не применяется** |

### 8.4 Зарплаты / ФОТ

| Источник | Тип | Детали |
|---|---|---|
| `niche_formats_{NICHE}.xlsx` лист `STAFF` колонки `fot_net_min/med/max`, `fot_full_min/med/max` | xlsx | **основной источник** |
| `engine.py:37` `DEFAULTS['fot_multiplier']=1.175` | жёстко | Налоги работодателя 17.5% — когда `fot_full_med` пустой |
| `engine.py:383-388` применение multiplier | логика | `fot_full = int(fot_net × 1.175)` |
| `engine.py:1818` `fot = ... or 300_000` | жёстко | Фолбэк 300K ₸ в Block 8 |
| `engine.py:2123-2126` `role_salary_monthly = int(fot_monthly / headcount)`, иначе 200_000 | жёстко | Block 5 зарплата роли |
| `engine.py:2129` `role_salary_monthly = max(int(fot_monthly * 0.35), 300_000)` | жёстко | Для multi-role |
| `main.py:70, 482` `fot_gross: 200000`, `headcount: 2` | жёстко | Дефолты финмодели |
| `gen_finmodel.py:99-100` то же | жёстко | Дубль |
| `grant_bp.py:16-32` `CITY_DATA[*].avg_wage` (15 городов, 250K-420K) | жёстко в .py | Средняя зарплата для бизнес-плана гранта — **своя система, не связана с engine** |
| `data/kz/04_wages_by_role.xlsx` лист `Зарплаты по должностям` (по городам) | xlsx | **Есть, но не используется** |
| `data/kz/02_wages_by_city.xlsx` | xlsx | **Есть, но не используется** |
| `data/kz/03_wages_by_industry.xlsx` | xlsx | **Есть, но не используется** |

### 8.5 Налоговые ставки

| Параметр | Источник | Детали |
|---|---|---|
| УСН (УД) базовая | `05_tax_regimes.xlsx` лист `tax_regimes_2026` строка UD → 4% | — |
| УСН по городу | `05_tax_regimes.xlsx` лист `city_ud_rates_2026` колонка `ud_rate_pct` | 15 городов, значения 2-3%. Читается в `engine.py:114, 291-297` |
| МРП 2026 = 4325 | `engine.py:17` + `grant_bp.py:9` + `05_tax_regimes.xlsx:key_params_2026` | В 3 местах дублируется |
| МЗП 2026 = 85000 | `engine.py:18` + `05_tax_regimes.xlsx:key_params_2026` | В 2 местах |
| ОПВ 10% / ОПВР 3.5% / ВОСМС 2% / ООСМС 3% | `05_tax_regimes.xlsx:payroll_taxes_2026` | **Лист НЕ используется в коде**. Вместо него — `engine.py:37` `fot_multiplier=1.175` (≈17.5% нагрузки работодателя, приблизительно = ОПВР+ООСМС+СО) |
| Ставка социальных платежей ИП = 22% от базы (50 МРП) | `engine.py:510` `int(base * 0.22)` | Жёстко захардкожено |
| Соцналог (СН), ОПВР = 3.5% (2026) | `CLAUDE.md` + `05_tax_regimes.xlsx:payroll_taxes_2026` | В коде не применяется явно |
| НДС = 16% | `05_tax_regimes.xlsx:key_params_2026` + `CLAUDE.md` | В `engine.py` — не используется (УСН не-плательщик) |
| Fallback tax rate | `engine.py:293, 297` — 4.0% если город не найден | — |

> ⚠️ замечено: `CLAUDE.md` гласит «Караганда 2%, Атырау 2%, УК 2%», а `05_tax_regimes.xlsx:city_ud_rates_2026` — 3%/3%/3%.

### 8.6 Загрузка / заполняемость / churn

| Параметр | Источник | Детали |
|---|---|---|
| Разгон: start=50%, 3 мес до 100% | `engine.py:28-30` `DEFAULTS['rampup_months']=3, 'rampup_start_pct']=0.50` | По умолчанию, переопределяется полями xlsx |
| Архетип A: `load_pct = 0.80` | `engine.py:1521` | Жёстко в `compute_block4_unit_economics` |
| Архетип D (абонементы): `churn_pct = 0.08` | `engine.py:1613` | Жёстко |
| Архетип F (мощность): `occupancy = 0.65` | `engine.py:1659` | Жёстко; безубыточность при ≥35% |
| Стресс-тест Quick Check: traffic_k = 0.75/1.00/1.20 | `engine.py:594-599` | Жёстко |
| Три сценария Quick Check: traffic_k = 0.75/1.00/1.25 | `engine.py:728` | Жёстко (расходится со стресс-тестом выше!) |
| Блок 7 scenarios: `scale = 0.75/1.00/1.25` | `engine.py:1777-1778` | Жёстко |
| `20_scenario_coefficients.xlsx` per format_id | xlsx | **Есть, но не используется** |

### 8.7 CAPEX

| Параметр | Источник | Детали |
|---|---|---|
| CAPEX min/med/max по формату/классу | `niche_formats_{NICHE}.xlsx` лист `CAPEX` | Основной источник — `engine.py:643, 675-677` |
| Разбивка equipment/renovation/furniture/first_stock/permits_sez/working_cap_3m | `CAPEX` лист | `engine.py:823-828` |
| `capex_standard` | `08_niche_formats.xlsx` | Альтернатива — используется в `_formats_from_fallback_xlsx`, `compute_block2_passport` (fallback), `_red_alternatives` |
| Синтетика при отсутствии breakdown: equipment=32%, renovation=22%, first_stock=15%, marketing=10%, working_cap=12%, deposit=4%, legal=5% | `engine.py:1708-1716` | Жёстко в `compute_block6_capital` |
| Green action_plan: equipment=40%, inventory=15%, rent_setup=22% | `engine.py:2172-2174` | Жёстко, расходится с 1708-1716 |
| `main.py:489, 744` `capex: 1500000` | жёстко | Дефолт финмодели |
| `gen_finmodel.py:106` `capex: 1500000` | жёстко | Дубль |
| Депозит аренды | `fin.deposit_months × rent_month_total` (default `DEFAULTS['deposit_months']=2`) | `engine.py:678, 683` |

### 8.8 Сезонность

| Источник | Тип | Детали |
|---|---|---|
| `niche_formats_{NICHE}.xlsx` лист `FINANCIALS` колонки `s01…s12` | xlsx | Основной источник — `engine.py:361-362` читает `fin[f"s{cal_month:02d}"]` |
| `main.py:473` сезонность `[0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]` | жёстко | Дефолт в `_compute_finmodel_data` |
| `gen_finmodel.py:82` тот же массив | жёстко | Дубль |
| `main.py:484` `sez_month = _safe_int(fin.get('sez_month'), 0)` | из xlsx | Дополнительный ежемесячный расход (СЭЗ) |

### 8.9 Прочие магические числа

| Что | Где |
|---|---|
| `OWNER_CLOSURE_POCKET = 200 000 ₸` (точка закрытия) | `engine.py:496` |
| `OWNER_GROWTH_POCKET = 600 000 ₸` (точка масштабирования) | `engine.py:497` |
| WACC = 0.20 | `main.py:497, 751`, `gen_finmodel.py:113` |
| Горизонт финмодели = 36 мес | `main.py:474`, `gen_finmodel.py:90` |
| Амортизация = 7 лет | `main.py:492`, `gen_finmodel.py:109` |
| Кредит дефолт: 22% / 36 мес | `main.py:78-79, 495-496`, `gen_finmodel.py:111-112` |
| Прайс finmodel=9000 / bizplan=15000 | `engine.py:2367, 2373` + `questionnaire.yaml` + `CLAUDE.md` |
| Дефолтный `marketing_monthly = 100 000` | `engine.py:2072` |
| Дефолтный `other_opex_monthly = 100 000` | `engine.py:2073` |

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 9 — МЁРТВЫЕ ФАЙЛЫ
═══════════════════════════════════════════════════════════════════════

### 9.1 Точно мёртвые / сломанные

1. `/engine/__init__.py` + `/engine/gemini_rag.py` + `/engine/run_test.py` — каталог в корне, **НЕ `/api/engine.py`**. `__init__.py` импортирует `.engine` и `.report`, которых нет. Нигде в проекте нет `from engine.gemini_rag import` или `from engine.run_test import`. Вероятно — устаревший первый вариант движка до переноса в `/api/`.

2. `data/kz/02_wages_by_city.xlsx` — не упоминается в `.py`. В коде расчёта не используется.
3. `data/kz/03_wages_by_industry.xlsx` — не упоминается в `.py`.
4. `data/kz/04_wages_by_role.xlsx` — не упоминается в `.py`.
5. `data/kz/20_scenario_coefficients.xlsx` — не упоминается в `.py`. Захардкоженные коэффициенты в `engine.py:728` игнорируют этот файл.
6. `data/kz/21_opex_benchmarks.xlsx` — не упоминается в `.py`. OPEX-бенчмарки берутся из `FINANCIALS` листа per-niche xlsx.
7. `data/kz/22_staff_scaling.xlsx` — не упоминается в `.py`. Этапы start/growth/scale не применяются в движке.
8. `data/kz/19_inflation_by_niche.xlsx` — загружается в `db.inflation_niche` (`engine.py:110`), но значение никогда не читается в расчётах.
9. `knowledge/niches/_yt_videos.json` — не используется в Python (вероятно, потребляется фронтом wiki/academy).

### 9.2 Возможно мёртвые (не подтверждено)
- `products/quick-check-v2.html` — отдельный legacy UI, прямых ссылок в HTML-дереве нет
- `products/quick-check.legacy.html` — ещё один legacy UI
- Листы внутри xlsx (подсписки):
  - `01_cities.xlsx`: `Регионы демография`, `Городское vs Сельское`, `Динамика населения` — читается только лист `Города`
  - `05_tax_regimes.xlsx`: `b2b_nds_warnings`, `payroll_taxes_2026`, `key_params_2026`, `notes` — читаются только `tax_regimes_2026` и `city_ud_rates_2026`
  - `13_macro_dynamics.xlsx`: `Индекс КЭИ`, `Динамика торговли`, `Курс и импорт`, `Параметры для Quick Check` — читается только `Инфляция по регионам`
  - `14_competitors.xlsx`: `Сигналы для Quick Check` — читается только `Конкуренты по городам`
  - `15_failure_cases.xlsx`: `База факапов`, `Классификатор причин`, `Как добавлять кейсы` — читается только `Паттерны по нишам`
  - `19_inflation_by_niche.xlsx`: лист `Инфляция по статьям ниш` — не читается
  - Листы per-niche xlsx: `GROWTH`, `LAUNCH`, `SUPPLIERS`, `SURVEY`, `LOCATIONS` — загружаются в `niche_data`, но использование в расчётах Quick Check v3 ограничено. `LAUNCH`, `SUPPLIERS`, `SURVEY`, `LOCATIONS` отдаются через отдельные эндпоинты (`/survey`, `/products`, `/insights` и т.п.), в `run_quick_check_v3` прямо не вызываются.

### 9.3 Возможно используются динамически
- Все 33 `niche_formats_*.xlsx` — **используются** через `glob` в `engine.py:124-125` (`_load_niches`). Не грепаются по имени, но читаются динамически.
- `config/*.yaml` — **используются** через `_load_yaml_configs_on`, читаются по `niches/archetypes/locations/questionnaire`.

---

═══════════════════════════════════════════════════════════════════════
## РАЗДЕЛ 10 — РЕЗЮМЕ И ОТКРЫТЫЕ ВОПРОСЫ
═══════════════════════════════════════════════════════════════════════

### 10.1 Ключевые факты о репо

1. **Весь расчёт Quick Check — в одном файле `api/engine.py` (2861 строка, 150 KB).** Туда же втянуты: загрузка БД, 4 yaml-конфига, функции форматирования, 10 блоков отчёта Quick Check v1.0 и адаптивная анкета.

2. **Источник исходных цифр Quick Check — per-niche xlsx.** 33 файла `niche_formats_{NICHE}.xlsx` загружаются через `glob` в `_load_niches`. Каждый файл — 14 листов, самый важный — `FINANCIALS` (check_med, traffic_med, cogs_pct, rent_med, opex, сезонность s01-s12) и `CAPEX` / `STAFF` / `TAXES`.

3. **Список ниш в коде = список файлов в каталоге.** Нет реестра ниш в коде — если файл `niche_formats_X.xlsx` отсутствует, движок просто не будет знать про нишу X, даже если она есть в `config/niches.yaml` или `knowledge/niches/`.

4. **Параллельно существуют два источника форматов.** Per-niche (`niche_formats_*.xlsx` лист `FORMATS`, 14 колонок включая `num`, `class_desc`, `area_min/med/max`, `seats`, `qty_points`, `loc_type`, `loc_dependency`, `classes_available`) и fallback (`08_niche_formats.xlsx` лист `Форматы`, 9 колонок: `niche_id`, `format_id`, `format_name`, `area_m2`, `capex_standard`, `class`, `format_type`, `allowed_locations`, `typical_staff`). Их поля пересекаются только частично. Block 2 «Паспорт бизнеса» берёт `format_type`, `typical_staff`, `allowed_locations` только из fallback; остальное — из per-niche.

5. **Клиенты `/quick-check` разные — два разных фронта.** `qc-v3.html` и `app.html` — независимые UI, работают с одним API. Первый использует `/configs`, `/formats-v2`; второй — `/niches`, `/formats`.

6. **Сезонность, коэффициенты сценариев, fot_multiplier, WACC, горизонт, дефолты финмодели и MRP — задублированы в 2-4 местах.** Например, сезонность `[0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]` — в `main.py:473` и `gen_finmodel.py:82`. MRP 4325 — в `engine.py:17`, `grant_bp.py:9`, `05_tax_regimes.xlsx:key_params_2026`.

7. **7 из 17 общих xlsx-файлов не читаются движком.** `02_wages_by_city`, `03_wages_by_industry`, `04_wages_by_role`, `20_scenario_coefficients`, `21_opex_benchmarks`, `22_staff_scaling` не упомянуты в `.py`. `19_inflation_by_niche` загружается, но значение никогда не используется.

8. **Results Quick Check не сохраняются.** Нет БД, нет кеша. Только in-memory словарь `_file_store` для PDF/xlsx/docx с TTL 7 дней.

9. **Block 9 (риски) в 99% случаев срабатывает через generic fallback.** Regex ищет `## Риски` / `## Подводные камни` / `## Причины провала` в insight-файлах, но реальные заголовки — `## Финансовые риски и ловушки`, `## Типичные ошибки новичков`. Параллельно есть `gemini_rag.extract_niche_risks` с нормальным парсингом через Gemini 2.5 Flash + JSON-схема — это работает, но используется только в PDF-генерации, не в основном Block 9.

10. **Конфиги yaml перекрываются с per-niche xlsx.** `config/niches.yaml` содержит 57 ниш, из них 33 имеют per-niche xlsx, 24 — только insight и/или wiki. `config/archetypes.yaml` хранит поле `finmodel_operational_questions` (по 5-6 вопросов на архетип), которое движком не читается.

### 10.2 Открытые вопросы

1. **Какой UI — канонический Mini App?** `qc-v3.html` или `app.html`? CLAUDE.md указывает два разных URL. Они используют разные эндпоинты (`/configs`+`/formats-v2` vs `/niches`+`/formats`) и разный объём данных.

2. **Какой источник истины для списка ниш: yaml или xlsx?** `niches.yaml` — 57 ниш; per-niche xlsx — 33; insight-файлы — 43. Реестр движка = 33.

3. **Какие xlsx «готовы к использованию, но забыты», а какие «готовились, но не дошли до интеграции»?** `20_scenario_coefficients`, `21_opex_benchmarks`, `22_staff_scaling` — имеют структурированные данные по формату, но движок их не читает.

4. **Что значит Block 1 `_score_saturation` с `competitors_count=0`?** Через `result['risks']['competitors']` движок передаёт только уровень 1-5 и число строкой («н/д» / «оценка»). Числовое поле `competitors_count` берётся в `compute_block1_verdict:1319` из `comp.get('competitors_count') or comp.get('n')` — но ни тот, ни другой ключ в `get_competitors` не создаются. Саттурация почти всегда 0 → score 2 по фолбэку.

5. **Почему 3-сценарийный множитель трафика в разных местах отличается?** `run_quick_check_v3` использует 0.75/1.0/1.25, `calc_stress_test` — 0.75/1.0/1.20, `compute_block7_scenarios` — 0.75/1.0/1.25. Какой «правильный»?

### 10.3 Что ТОЧНО дублируется (факт-основанный список)

- Сезонность `[0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]` — в `api/main.py:473` и `api/gen_finmodel.py:82`
- Полный блок из 23 дефолтов финмодели — в `api/main.py:474-497` (функция `_compute_finmodel_data`) и `api/gen_finmodel.py:85-113` (функция `generate_finmodel`)
- MRP 4325 — в `api/engine.py:17`, `api/grant_bp.py:9`, `data/kz/05_tax_regimes.xlsx:key_params_2026`
- Список 15 городов — в `data/kz/01_cities.xlsx`, `data/kz/05_tax_regimes.xlsx:city_ud_rates_2026`, `api/engine.py:40-46` (CITY_CHECK_COEF), `api/grant_bp.py:16-32` (CITY_DATA) — с разными идентификаторами (`ALA`/`ASTANA`/`SHYMKENT` vs `almaty`/`astana`/`shymkent` vs `aktobe`/…)
- Разбивка CAPEX — в `engine.py:1708-1716` (Block 6: 32/22/15/10/12/4/5) и в `engine.py:2172-2174` (Green plan: 40/15/22) — разные проценты
- Структура форматов — в `niche_formats_{NICHE}.xlsx:FORMATS` и в `08_niche_formats.xlsx:Форматы` — разные наборы полей
- Маппинг niche_id → русское имя — в `api/engine.py:131-156` (NICHE_NAMES) и в `config/niches.yaml` (name_rus) — оба пути используются
- Иконки ниш — в `api/engine.py:157-169` (NICHE_ICONS) и в `config/niches.yaml` (icon)
- Сценарные множители трафика — в `engine.py:594-599` (0.75/1.00/1.20), `engine.py:728` (0.75/1.0/1.25), `engine.py:1777-1778` (0.75/1.00/1.25)
- `gemini_rag.py` существует в `/api/gemini_rag.py` (210 строк) и `/engine/gemini_rag.py` (40 строк, сокращённая копия)
- Tax rate fallback 4.0% — в `engine.py:293, 297`; дефолт 3% — в `engine.py:2034, 2075`, `main.py:493, 728`
- Дефолт маркетинга 50 000 — в `main.py:485, 740`, `gen_finmodel.py:102`; 100 000 — в `engine.py:2072` (`compute_block5_pnl`)

### 10.4 Что МОЖНО переиспользовать как есть

- `data/kz/01_cities.xlsx` лист `Города` — источник городов/населения, структура корректна для движка
- `data/kz/05_tax_regimes.xlsx` листы `tax_regimes_2026` и `city_ud_rates_2026` — актуальные ставки 2026
- `data/kz/11_rent_benchmarks.xlsx` лист `Калькулятор для движка` — ставки аренды по городам и типам локации
- `data/kz/14_competitors.xlsx` лист `Конкуренты по городам` — для Block 3
- `data/kz/17_permits.xlsx` — список разрешений/лицензий
- `config/niches.yaml`, `config/archetypes.yaml`, `config/locations.yaml` — каноничные справочники (при условии, что их ID-ы станут единственным источником истины)
- `knowledge/niches/*_insight.md` — 43 инсайт-файла, пригодны для Gemini RAG (парсинг через схему работает)
- `api/pdf_gen.py` — рендер PDF, независим от изменений расчётного движка
- `api/finmodel_report.py` — HTML-отчёт финмодели, независим
- `templates/finmodel/finmodel_template.xlsx` + `templates/bizplan/grant_400mrp_template.docx` — шаблоны
- `api/gemini_rag.py:extract_niche_risks` — работающий парсер рисков из Gemini с JSON-схемой и кешем

### 10.5 Что МОЖНО переиспользовать с правками

- `data/kz/niches/niche_formats_*.xlsx` — основной источник цифр, но содержит специфику старой схемы (14 листов). Правка: унификация с `08_niche_formats.xlsx`
- `data/kz/09_surveys.xlsx` — 163 вопроса каталога + применимость на 33 ниши × 2 tier. Правка: синхронизация с yaml-спекой анкеты
- `api/engine.py` — содержит правильную логику `run_quick_check_v3` (cashflow, breakeven, payback, owner_economics). Правка: выделить в отдельные модули, убрать дубликаты с main.py, подключить неиспользуемые xlsx (20/21/22)
- `api/report.py` — структура 12 блоков разумна, но дублирует компетенции с `compute_block*_*` в engine.py. Правка: выбрать одну схему отчёта
- `data/kz/20_scenario_coefficients.xlsx` — можно заменить захардкоженные 0.75/1.0/1.25
- `data/kz/21_opex_benchmarks.xlsx` — можно подставить вместо дефолтов main.py/gen_finmodel.py
- `data/kz/22_staff_scaling.xlsx` — можно подключить к Block 5 (этапы роста)
- `data/kz/04_wages_by_role.xlsx` — можно использовать вместо `role_salary_monthly = 200_000` fallback
- `config/questionnaire.yaml` блок `finmodel` и `bizplan` — структура вопросов готова, но не парсится движком
- `config/archetypes.yaml` поле `finmodel_operational_questions` — 33 вопроса по 6 архетипам, готовы, но не читаются

