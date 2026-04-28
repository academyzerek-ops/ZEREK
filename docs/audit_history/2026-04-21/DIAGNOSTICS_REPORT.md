# ZEREK — Диагностика 7 багов Quick Check

**Дата:** 2026-04-22
**Базовый запрос:** BARBER / BARBER_STANDARD / aktobe / capital=6 000 000 / cls=Стандарт / area_m2=0 / loc_type=residential
**Ветка/коммит:** main, HEAD = `7fcc482` (merge «генеральная уборка репо, Фаза 2»)
**Пре-уборочный SHA:** `784196e`
**Сохранённый JSON-ответ:** `/tmp/qc_diag.json`

---

## Критическое открытие (ключевое для 5 из 7 багов)

Между двумя источниками данных о форматах BARBER существует **структурный рассинхрон**:

| Источник | Файл | Листы | format_id для BARBER |
|---|---|---|---|
| Per-niche (движок v3) | `data/kz/niches/niche_formats_BARBER.xlsx` | FORMATS, FINANCIALS, STAFF, CAPEX, … | `BARBER_SOLO`, `BARBER_MINI`, `BARBER_FULL` |
| Fallback / v1 spec (Block 2) | `data/kz/08_niche_formats.xlsx` | Форматы | `BARBER_SOLO`, `BARBER_STANDARD`, `BARBER_PREMIUM` |

Тест отправляет `format_id=BARBER_STANDARD`. В per-niche xlsx такого format_id **нет** → `db.get_format_row(...)` возвращает `{}` для FORMATS / FINANCIALS / STAFF / CAPEX / TAXES → движок считает всё на пустых дефолтах (нули).

Воспроизведено напрямую:
```
>>> db.get_format_row('BARBER','FINANCIALS','BARBER_STANDARD','Стандарт')
{}
>>> db.get_format_row('BARBER','STAFF','BARBER_STANDARD','Стандарт')
{}
>>> db.get_format_row('BARBER','CAPEX','BARBER_STANDARD','Стандарт')
{}
```

Рассинхрон существовал **ДО уборки** (`git show 784196e:data/kz/08_niche_formats.xlsx` тоже содержит `BARBER_STANDARD`, а `git show 784196e:data/kz/niches/niche_formats_BARBER.xlsx` — `BARBER_SOLO/MINI/FULL`). То есть это долг датасета, который уборка не устранила.

---

## Сводка

| # | Баг | Корневая причина (1 фраза) | Где чинить | ДО/ПОСЛЕ |
|---|---|---|---|---|
| 1 | `area_m2=0` не подтягивается из FORMATS.area_med | В `fin.get('rent_med')=None` → выражение `int(area_m2 * rent_median_m2)=0`; + при `BARBER_STANDARD` `fmt={}`, fallback на `area_med` не выполняется | `api/engine.py:826-828` | ДО уборки (идентичный код) |
| 2 | ФОТ=0 во всех блоках расходов | `staff = db.get_format_row(niche,'STAFF','BARBER_STANDARD','Стандарт') → {}` из-за несуществующего format_id | `api/engine.py:788` + рассинхрон xlsx | ДО уборки |
| 3 | `block_1.check_med/traffic_med/revenue_monthly=0` | `fin={}` → `result['financials']['check_med']=0` → report_v4 видит 0 | `api/engine.py:997-1008` + рассинхрон xlsx | ДО уборки |
| 4 | `block_4.total=0` vs `block6.capex_needed=7 500 000` | `block_4` (report v4) читает `result.capex.total` (из per-niche, пусто=0); `block6` (новый compute) делает fallback на block2→08_niche_formats (`capex_standard=7.5M`) | `api/engine.py:820-830` + `api/report.py:67` + рассинхрон xlsx | ДО уборки |
| 5 | `block3.affordability.city_coef=1.0` для Актобе | Не баг — Актобе по CLAUDE.md база коэф = 1.00. yaml содержит `check_coef: 1.00` | `config/constants.yaml:59` — корректно | не баг (by design) |
| 6 | `block9.source="generic"` для BARBER | `knowledge/kz/niches/BARBER_insight.md` не существует (и не существовал в `knowledge/niches/` до уборки тоже) | отсутствие файла, не код | ДО уборки (нет исходника) |
| 7 | Сезонность плоская 1.5 млн | В `FINANCIALS` листе BARBER нет колонок `s01..s12`; `calc_revenue_monthly` фолбэк на 1.0 вместо `defaults.yaml.default_seasonality` | `api/engine.py:486-487` | ДО уборки (но `default_seasonality` в yaml добавлен уборкой и не подключён к движку) |

---

## Баг 1 — `area_m2=0` → нули в аренде

### Текущее поведение
- `input.area_m2 = 0` (передано юзером)
- `block_3.items[name=Аренда].amount = 0`
- `block_3.items[name=Коммунальные].amount = 0`
- `block_3.total = 0`
- В xlsx `FORMATS.area_med` для `BARBER_STANDARD` в per-niche файле **не существует** (только в 08_niche_formats.xlsx: `area_m2=45`)

Пруф из xlsx:
```
# data/kz/niches/niche_formats_BARBER.xlsx, лист FORMATS
('num','format_name','format_id','class','class_desc','area_min','area_med','area_max', ...)
(1,'Аренда кресла','BARBER_SOLO','Эконом',...,0,3,5,...)
(2,'Мини-барбершоп','BARBER_MINI','Эконом',...,15,20,25,...)
(3,'Полный барбершоп','BARBER_FULL','Стандарт',...,30,45,60,...)
# BARBER_STANDARD здесь ОТСУТСТВУЕТ
```

Для блока 2 paspport читается из 08_niche_formats.xlsx, поэтому там корректно `area_m2=45`:
```
# data/kz/08_niche_formats.xlsx
('BARBER','BARBER_STANDARD','Барбершоп 3-5 кресел',45,7500000,'стандарт','STANDARD',...)
```

### Корневая причина
```python
# api/engine.py:826-827
rent_median_m2, _ = get_rent_median(db, city_id, loc_type)
rent_month = rent_override if rent_override else _safe_int(fin.get('rent_med'), int(area_m2 * rent_median_m2))
```

При `area_m2=0` и при пустом `fin={}` (так как `BARBER_STANDARD` не найден в per-niche FORMATS):
- `fin.get('rent_med')` → `None` → `_safe_int(None, default=int(0 * rent_median_m2))` = **0**
- `rent_month = 0`

Нет fallback на `fmt.get('area_med')` (из FORMATS). Даже если он был бы, `fmt={}` в этом тесте.

### Минимальный fix (описание)
1. В `api/engine.py:826-828` перед расчётом ренты вставить нормализацию площади:
   ```
   area_m2 = area_m2 or _safe_int(fmt.get('area_med'), 0)
   ```
2. Но глубинно проблема — `fmt={}`. Реальный fix: устранить рассинхрон format_id между `niche_formats_BARBER.xlsx` и `08_niche_formats.xlsx`, или добавить в `get_format_row` фолбэк «ищи в 08_niche_formats если в per-niche пусто».

### Связь с другими багами
Блокирует корректность block_3 (аренда + коммуналка), block5.rent, block6 breakdown, блок здоровья, тд.

### ДО/ПОСЛЕ
Идентичный код в `git show 784196e:api/engine.py:681`:
```
rent_month = rent_override if rent_override else _safe_int(fin.get('rent_med'), int(area_m2 * rent_median_m2))
```
→ **баг существовал ДО уборки**.

---

## Баг 2 — ФОТ = 0 во всех блоках расходов

### Текущее поведение
- `block_3.items[name=ФОТ].amount = 0, note = ""`
- `block5.scenarios.*.fot = 0` (наблюдаемо)
- `block_1.disclaimer` (из report_v4 через `sf.get('positions','')`): штат пустой

### Корневая причина
В xlsx `STAFF` для BARBER **есть** строки `fot_net_med`/`fot_full_med`:
```
# niche_formats_BARBER.xlsx, лист STAFF
('format_id','class','positions','headcount','founder_role','schedule','backup_needed',
 'fot_net_min','fot_net_med','fot_net_max','fot_full_min','fot_full_med','fot_full_max','hire_m3','hire_m6')
('BARBER_SOLO','Эконом','Барбер (сам)',1,'Сам работает','10ч 6/1','Нет',0,0,0,0,0,0,0,0)
('BARBER_MINI','Эконом','Барбер × 2',2,...,180000,240000,300000,211500,282000,352500,0,0)
('BARBER_MINI','Стандарт','Барбер × 3',3,...,300000,400000,500000,352500,470000,587500,0,1)
('BARBER_FULL','Стандарт','Барбер × 4, Админ',5,...,500000,680000,850000,587500,799000,998750,1,2)
('BARBER_FULL','Бизнес','Барбер × 6, Админ × 2',8,...,700000,950000,1200000,822500,1116250,1410000,2,3)
# BARBER_STANDARD ОТСУТСТВУЕТ
```

В `api/engine.py:788`:
```
staff = db.get_format_row(niche_id, 'STAFF', format_id, cls)  # BARBER_STANDARD/Стандарт → {}
```

`get_format_row` (engine.py:271) ищет строки по `format_id`. Для `BARBER_STANDARD` их нет → fallback по «только format_id» тоже пустой → `{}`. Далее `_safe_int(staff.get('fot_net_med'),0) = 0`, `fot_full_med = 0`, `headcount = 0`, `positions = ''`.

### Минимальный fix
Устранить рассинхрон xlsx (см. Баг 1). Альтернатива: передавать из блока 2 (08_niche_formats — там есть `typical_staff: "барбер:4|администратор:1"`) рассчитанный ФОТ как fallback — но это переделка архитектуры.

### Связь с багами 1, 3, 4
Один и тот же корень — несуществующий format_id → пустые dict на 4 листах (FINANCIALS / STAFF / CAPEX / FORMATS / TAXES).

### Переименование ниш (вторичная гипотеза)
Проверено grep'ом по `report.py` и `engine.py`: в обновлённом коде NAIL→MANICURE, TIRE→TIRESERVICE, PHARMA→PHARMACY, WATER→WATERPLANT, CYBERCLUB→COMPCLUB. Для BARBER ничего не переименовывалось. BARBER_STANDARD — это не legacy-ID ниши, а существующий но несогласованный format_id.

### ДО/ПОСЛЕ
`git show 784196e:api/engine.py:642`:
```
staff = db.get_format_row(niche_id, 'STAFF', format_id, cls)
```
Идентично. Данные xlsx тоже идентичны. → **ДО уборки**.

---

## Баг 3 — `block_1` (report v4): check_med=0, traffic_med=0, revenue_monthly=0

### Текущее поведение
```json
"block_1": {
  "check_med": 0, "traffic_med": 0, "revenue_monthly": 0,
  "revenue_structure": [],
  "disclaimer": "Средний чек 0 ₸ — типовая корзина для класса «Стандарт» в г. Актобе. ..."
}
```

### Корневая причина
`api/report.py:13-40`:
```
def render_report_v4(result: dict) -> dict:
    fin = result.get("financials", {})
    ...
    check_med = fin.get("check_med", 0)
    traffic_med = fin.get("traffic_med", 0)
    ...
    revenue_med = check_med * traffic_med * 30
```

`result["financials"]` формируется в `api/engine.py:997-1008`:
```
"financials": {
    "check_med": _safe_int(fin.get('check_med')),
    "traffic_med": _safe_int(fin.get('traffic_med')),
    ...
}
```

Здесь локальная переменная `fin` = пустой dict (см. Баг 2) → всё сваливается в 0.

`revenue_structure` пустой потому, что `pr = result.get("products", [])` (строка 22), а `products` в `run_quick_check_v3:793` — `db.get_format_all_rows('BARBER','PRODUCTS','BARBER_STANDARD','Стандарт')`. В PRODUCTS листе есть только `BARBER_FULL/Стандарт` — `BARBER_STANDARD` нет → пустой DataFrame.

### Минимальный fix
Тот же, что для багов 1 и 2: устранить рассинхрон format_id. Ни `run_quick_check_v3`, ни `render_report_v4` логически не сломаны — они работают с пустыми данными корректно.

### ДО/ПОСЛЕ
`git show 784196e:api/report.py` диффается с текущим только по niche-ID-ключам в словаре `eq_notes` (NAIL→MANICURE итд). Основная логика `render_report_v4` идентична. → **ДО уборки**.

---

## Баг 4 — `block_4.total=0` vs `block6.capex_needed=7 500 000`

### Текущее поведение
`block_4` (из report_v4):
```json
"block_4": { "items": [], "total": 0, "budget": 6000000, "investment_min": 0, "investment_max": 0 }
```
`block6` (из compute_block6_capital):
```json
"block6": { "capex_needed": 7500000, "capex_structure": [...], ... }
```

### Корневая причина

`block_4` (report_v4) в `api/report.py:66-67,114-116,204-208`:
```
bk = cap.get("breakdown", {})       # cap = result['capex'] (из engine.py:973-986 — всё из capex_data с форматом BARBER_STANDARD → нули)
...
capex_total = cap.get("total", 0)
...
"block_4": { "items": capex_items, "total": capex_total, ...,
             "investment_min": inv_min, "investment_max": inv_max }
```

`result["capex"]` собирается в `api/engine.py:820-830,963-986`:
```
capex_med = _safe_int(capex_data.get('capex_med'), 0) * qty   # 0
...
capex_total = capex_med + deposit                             # 0 + 0
```
(поскольку `capex_data = db.get_format_row('BARBER','CAPEX','BARBER_STANDARD','Стандарт') = {}`).

`block6` (новый путь) в `api/engine.py:1861-1865`:
```
def compute_block6_capital(db, result, adaptive, block2=None):
    capex = result.get('capex', {}) or {}
    capex_needed = _safe_int(capex.get('capex_med')) or _safe_int(capex.get('capex_total'))
    if capex_needed < 500_000 and block2:
        capex_needed = (block2.get('finance') or {}).get('capex_needed') or capex_needed
```
`block2` читается из `08_niche_formats.xlsx` через `_formats_from_fallback_xlsx` → там есть строка `BARBER_STANDARD, capex_standard=7500000`. В `compute_block2_passport:2800-2803`:
```
capex_needed = _safe_int(capex_block.get('capex_med')) or _safe_int(capex_block.get('capex_total'))
if capex_needed < 500_000:
    capex_needed = _safe_int(fm.get('capex_standard'), 0) or capex_needed
```
→ `capex_needed = 7 500 000`.

Итого: `block_4` смотрит в «новый» источник (per-niche, 0), `block6` имеет корректный fallback в «старый» (08_niche_formats, 7.5M). Они физически тянут разные источники, и report_v4 фолбэка не имеет.

### Минимальный fix (описание)
- В `api/report.py` перед использованием `capex_total`/`bk` добавить fallback: если нули и есть `result['block2']['finance']['capex_needed']` — взять его; breakdown разложить по типовому распределению (как делает compute_block6).
- Или синхронизировать data layer (устранить рассинхрон — один fix решает 4 бага).

### Связь с багами 1, 2, 3
Общий корень — несуществующий format_id в per-niche xlsx.

### ДО/ПОСЛЕ
`git show 784196e:api/engine.py:674-684` — идентичный расчёт `capex_med * qty + deposit`. `git show 784196e:api/engine.py:1692-1700` `compute_block6_capital` тоже имеет fallback на block2. Рассинхрон путей `block_4`/`block6` существовал до уборки. → **ДО уборки**.

---

## Баг 5 — `city_check_coef = 1.0` для Актобе (нейтральный)

### Текущее поведение
```json
"block3.affordability": { "city_coef": 1.0, "text_rus": "Платёжеспособность на уровне средней КЗ ..." }
```

### Корневая причина
Это **НЕ баг**. По `config/constants.yaml:55-60`:
```yaml
- id: aktobe
  name_rus: "Актобе"
  region_rus: "Актюбинская область"
  type: regional_capital
  check_coef: 1.00
  legacy_ids: [AKT, AKTOBE, aktobe]
```
Актобе по дизайну имеет `check_coef = 1.00` (база отсчёта). Это соответствует пре-уборочному коду `git show 784196e:api/engine.py:41-46`:
```python
CITY_CHECK_COEF = {
    'almaty': 1.05, 'astana': 1.05, 'atyrau': 1.03,
    'aktobe': 1.00, 'karaganda': 1.00, 'uralsk': 1.00,
    ...
}
```

Функция `_build_city_maps()` (`api/engine.py:112-128`) корректно читает yaml, `get_city_check_coef('aktobe')` возвращает `1.0` (подтверждено runtime-проверкой: `almaty=1.05, shymkent=0.97, semey=0.95`).

### Минимальный fix
Не требуется. Если надо визуально отличать 1.0 от «неизвестный город», в `compute_block3_market` (строка 1612-1614) добавить отдельную ветку для known_base vs unknown.

### ДО/ПОСЛЕ
Значение для aktobe = 1.00 **до и после уборки**. Не баг в обоих состояниях.

### Замечание
Уборка действительно переносила словарь из hardcode в yaml — перенос прошёл корректно, все 15 городов с CLAUDE.md-списком имеют те же коэффициенты (плюс добавлены `turkestan` и `taldykorgan`). Fallback в `get_city_check_coef` = 1.00 (неизвестный город).

---

## Баг 6 — `block9.source="generic"` для BARBER

### Текущее поведение
```json
"block9": {
  "niche_id": "BARBER",
  "source": "generic",
  "risks": [{"title":"Уход мастера с клиентской базой", ...}, ...]
}
```

### Корневая причина
Файл `knowledge/kz/niches/BARBER_insight.md` **отсутствует**.

Код в `api/engine.py:2064-2065`:
```
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
insight_path = os.path.join(repo_root, 'knowledge', 'kz', 'niches', f'{niche_id}_insight.md')
```
Путь правильный (совпадает с фактическим расположением). Но файла нет:
```
ls knowledge/kz/niches/ | grep -i barber → (пусто)
```
→ срабатывает generic-fallback (architype 'A' beauty).

### Про путь
В `api/gemini_rag.py:7-10` путь тоже правильный — `knowledge/kz/niches`.
Сравнение с пре-уборочным кодом: `git show 784196e:api/engine.py:1896`:
```
insight_path = os.path.join(repo_root, 'knowledge', 'niches', f'{niche_id}_insight.md')
```
Старый путь был `knowledge/niches/` (без `kz`). Уборка корректно перенесла файлы в `knowledge/kz/niches/` И обновила код.

### Были ли файлы до уборки?
В `git ls-tree -r 784196e | grep "knowledge/niches/"` — `BARBER_insight.md` **отсутствует**, `COFFEE_insight.md` **отсутствует**. Ниши без insight-файла: BARBER, COFFEE, GROCERY, PIZZA, PVZ, REPAIR_PHONE, SEMIFOOD, SUGARING, SUSHI, TAILOR, WATERPLANT (до уборки — с legacy-именами).

### Минимальный fix
Создать `knowledge/kz/niches/BARBER_insight.md` с секцией `## Риски` / `## Красные флаги` / `## Типичные ошибки новичков`. Никакого правда кода.

### ДО/ПОСЛЕ
**ДО уборки** тоже возвращало `source="generic"` (файла не было и в `knowledge/niches/`). Уборка не ломала и не чинила это.

---

## Баг 7 — сезонность плоская (1.5 млн кроме первых 3 мес рамп-апа)

### Текущее поведение
`block_11_season.data`:
```
Апр: 1 000 000 (ramp 50%)
Май: 1 250 000 (ramp 75%)
Июн: 1 500 000 (ramp 100%)
Июл..Мар: 1 500 000 (всегда, без сезонности)
```
То есть сезонность фактически = константа 1.0 каждый месяц.

### Корневая причина

`api/engine.py:485-487`:
```python
# Сезонность (s01-s12)
s_key = f"s{cal_month:02d}"
season_coef = _safe_float(fin.get(s_key), 1.0)
```

В `niche_formats_BARBER.xlsx` лист FINANCIALS имеет 23 колонки, среди них **нет** `s01..s12`:
```
('format_id','class','check_min','check_med','check_max','traffic_min','traffic_med','traffic_max',
 'cogs_pct','margin_pct','rent_min','rent_med','rent_max','deposit_months','utilities','marketing',
 'consumables','software','transport','loss_pct','sez_month','rampup_months','rampup_start_pct')
```
Сравнение 33 ниш: только 4 ниши имеют `s01..s12` (BAKERY, CARWASH, COFFEE, DONER — по 43 колонки). Остальные 29 — **без** сезонных коэффициентов.

Про `defaults.yaml`:
```yaml
# config/defaults.yaml:25
default_seasonality: [0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]
```
Но код engine.py **никогда** не читает `default_seasonality`. Grep по `seasonality|season` в engine.py даёт только две строки (485-499) и обе работают только с `fin`-словарём. yaml-ключ висит без подключения.

### Минимальный fix (описание)
1. В `api/engine.py` рядом с другими модуль-level дефолтами (~строка 100) добавить:
   ```
   DEFAULT_SEASONALITY = (DEFAULTS_CFG.get('quick_check',{}) or {}).get('default_seasonality') or [1.0]*12
   ```
2. В `calc_revenue_monthly:486-487` заменить fallback:
   ```
   season_coef = _safe_float(fin.get(s_key), DEFAULT_SEASONALITY[cal_month-1])
   ```

### Связь с багами 5
Оба связаны с «yaml-ключи добавлены/перенесены, но не подключены к движку». Но корень разный:
- Баг 5: ключи подключены (`CITY_CHECK_COEF` работает), просто значение для aktobe = 1.00 by design.
- Баг 7: ключ `default_seasonality` не подключён никогда.

### ДО/ПОСЛЕ
`git show 784196e:api/engine.py:354-374` — `calc_revenue_monthly` **идентична** текущей:
```
s_key = f"s{cal_month:02d}"
season_coef = _safe_float(fin.get(s_key), 1.0)
```
→ Баг существовал **ДО уборки**. Уборка ДОБАВИЛА `default_seasonality` в yaml, но не подключила к коду (возможно — забытый шаг уборки).

---

## Анализ зависимостей

### Q1. Связь багов 1 и 2
**Один корень.** Оба срабатывают из-за `db.get_format_row(..., 'BARBER_STANDARD', 'Стандарт') → {}`. Пустой `fin` вызывает баг 1 (rent=0), пустой `staff` вызывает баг 2 (FOT=0). `run_quick_check_v3` получает входные параметры корректно (это видно: `input.area_m2=0` сохранилось, `input.capital=6000000` прошёл) — проблема в отсутствии строк xlsx под этот format_id.

### Q2. Связь багов 3 и 4
**Одна группа.** `render_report_v4` получает от `run_quick_check_v3` структурно корректный `result`, но наполненный нулями. Разрыв не в контракте между функциями, а в том, что:
- report_v4 читает «быстрые» поля из `result.financials` / `result.capex` (баги 3, 4), наполненные из per-niche xlsx (нулевые);
- новые `compute_block*` функции имеют дополнительные fallback в 08_niche_formats.xlsx (block6 → 7.5M).

Итог: **для багов 3 и 4 нет отдельного разрыва между engine и report — обе стороны работают с пустыми данными корректно. Корень тот же, что у 1 и 2** — рассинхрон format_id в двух xlsx.

### Q3. Связь багов 5 и 7
**Разные корни.**
- Баг 5 не баг (Актобе = 1.00 by design). YAML подключён к движку через `_build_city_maps` корректно.
- Баг 7 — `default_seasonality` в yaml НЕ подключён к движку (забыто при уборке).

### Q4. Родительский баг
**Родительский баг — #1/#2/#3/#4 общий корень: рассинхрон `BARBER_STANDARD` между `niche_formats_BARBER.xlsx` и `08_niche_formats.xlsx`.**

Починка этого корня (добавить строки `BARBER_STANDARD` в per-niche xlsx ИЛИ переименовать `BARBER_FULL→BARBER_STANDARD` в per-niche ИЛИ добавить общий fallback в `db.get_format_row`) автоматически закроет **баги 1, 2, 3, 4**.

Отдельные независимые баги: #6 (нет файла insight), #7 (не подключён yaml-ключ).

### Q5. Таблица ДО/ПОСЛЕ

| # | Сравнение (`git show 784196e:api/engine.py`) | Вывод |
|---|---|---|
| 1 | строка 681 (`rent_month = rent_override if ...`) идентична строке 827 сегодня | ДО уборки |
| 2 | строка 642 (`staff = db.get_format_row(...,'STAFF',...)`) идентична 788 | ДО уборки |
| 3 | `render_report_v4` в `git show 784196e:api/report.py` диффуется только по `eq_notes` niche-ID (NAIL→MANICURE итп) — логика идентична | ДО уборки |
| 4 | `compute_block6_capital` fallback на block2 существует в обеих версиях. `capex_med * qty` в 674-684 (old) = 821-830 (new) | ДО уборки |
| 5 | Hard-coded `CITY_CHECK_COEF` в old (41-46) содержал `'aktobe': 1.00`. yaml содержит то же самое | Не баг, значение идентично |
| 6 | old путь `knowledge/niches/`, new путь `knowledge/kz/niches/`. В `git ls-tree -r 784196e` файла BARBER_insight.md в старом месте нет. | ДО уборки (файла нет ни до, ни после) |
| 7 | `calc_revenue_monthly` в old (354-374) идентична текущей (479-499). Разница: в yaml ПОЯВИЛСЯ `default_seasonality`, но не подключён | Баг ДО уборки; уборка добавила ключ в yaml но не подключила |

**Итого:** все 7 «багов» существовали до уборки. Уборка **ни одного из них не создала**. Но уборка также ни одного не починила. Добавление `default_seasonality` в `config/defaults.yaml` — полшага (нет подключения к коду).

---

## Рекомендуемый порядок починки

1. **Баг 1/2/3/4 (один корень — рассинхрон xlsx).** Принять решение по правилу:
   - Вариант A: переименовать в `niche_formats_BARBER.xlsx` format_id `BARBER_FULL→BARBER_STANDARD` (класс «Стандарт»), аналогично для других ниш с подобным рассинхроном (надо проверить отдельно каждую).
   - Вариант B: в `08_niche_formats.xlsx` заменить `BARBER_STANDARD→BARBER_FULL`, `BARBER_PREMIUM→...` для соответствия per-niche данным.
   - Вариант C: в `ZerekDB.get_format_row` сделать фолбэк «если пусто в per-niche — найти ближайший по классу или вернуть медиану».
   После этого 1/2/3/4 закроются одной правкой данных.

2. **Баг 7 (сезонность).** Подключить `default_seasonality` из `defaults.yaml` в `calc_revenue_monthly:486-487`. Минимальная правка — 2 строки.

3. **Баг 6 (BARBER insight).** Создать `knowledge/kz/niches/BARBER_insight.md` по шаблону других `*_insight.md`. Также проверить все 33 available ниши: каких insight-файлов нет (как минимум BARBER, COFFEE — по listing выше).

4. **Баг 5.** Не требует починки. Опционально: в Block 3 сделать фразу «Платёжеспособность на уровне средней КЗ» более узнаваемой для aktobe (но это UX-полировка, не баг).

5. **Доп. контроль.** Добавить smoke-тест: при приёме `/quick-check` проверять, что `db.get_format_row(niche, 'FINANCIALS', format_id, cls)` не пуст — иначе `raise HTTPException(400, "Формат не найден в данных ниши")`. Это предотвратит молчаливые нули в отчёте.

---

## Дополнительные находки

1. **Список available ниш без insight-файлов** (фронт будет молчаливо показывать generic-риски):
   - `knowledge/kz/niches/` содержит 43 файла, но в `config/niches.yaml` available=true у: BARBER, MANICURE, BROW, LASH, SUGARING, MASSAGE, DENTAL, TAILOR, REPAIR_PHONE, COFFEE, BAKERY, CONFECTION, DONER, FASTFOOD, PIZZA, SUSHI, CANTEEN, SEMIFOOD, FRUITSVEGS, FLOWERS, PHARMACY, GROCERY, WATERPLANT, FITNESS, KINDERGARTEN, FURNITURE, AUTOSERVICE, TIRESERVICE, CARWASH, CLEAN, DRYCLEAN, COMPCLUB, PVZ. Отсутствуют файлы insights для: BARBER, COFFEE, GROCERY, PIZZA, PVZ, REPAIR_PHONE, SEMIFOOD, SUGARING, SUSHI, TAILOR, WATERPLANT (проверено `ls knowledge/kz/niches/` vs список). Все эти ниши отдают generic в block9.

2. **Рассинхрон format_id затрагивает не только BARBER.** Судя по шаблону (в 08_niche_formats.xlsx format_id заканчиваются на `_STANDARD/_SOLO/_PREMIUM`, а в per-niche — на свои варианты типа `_MINI/_FULL/_KIOSK`), проблема потенциально касается всех 33 ниш. Нужен отдельный аудит. Для подтверждения — выполнить по каждому xlsx сравнение set(format_id) между двумя файлами.

3. **Отмеченные места с потенциальной «тихой поломкой»:**
   - `api/engine.py:499` — при пустом `fin` трафик=50, чек=1000 (из `_safe_int(...,1000)`), но только в `calc_revenue_monthly`. В `result['financials']['check_med']` пишется строго `_safe_int(fin.get('check_med'))` = 0 без дефолта. Несогласованные дефолты.
   - `api/engine.py:786` — `fmt = db.get_format_row(niche,'FORMATS',format_id,cls)` тоже возвращает `{}`, и `input.format_name = _safe(fmt.get('format_name'), format_id)` = `"BARBER_STANDARD"` (видно в ответе: `"format_name":"BARBER_STANDARD"`). Но блок 2 при этом через 08_niche_formats корректно получает `"Барбершоп 3-5 кресел"` — ещё одна точка рассинхрона.

4. **Контракт `/quick-check` молча глотает несуществующий format_id.** `is_niche_available` проверяет только `niche_id`, но не `format_id`. Это анти-паттерн: фронт может прислать устаревший format_id → бэк вернёт `status=ok` с нулями вместо 400. Рекомендуется валидация входа.

5. **`rampup_start_pct=0.45`** в xlsx для `BARBER_FULL/Стандарт`, но в JSON-ответе при `BARBER_STANDARD` (пустой fin) используется дефолт `0.50` из `defaults.yaml`. Из-за этого расчёты становятся ещё менее точными (дефолты не соответствуют данным ниши).

---

Готово.
