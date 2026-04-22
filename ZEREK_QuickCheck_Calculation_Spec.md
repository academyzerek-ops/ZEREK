# ZEREK Quick Check — Спецификация финансовых расчётов

Документ-контракт. На основе аудита после 7 раундов правок. Чтобы прекратить whack-a-mole в движке и переписать расчётный блок на единой логике.

**Статус**: черновик для продуктового ревью. Раздел 7 содержит открытые вопросы.

---

## Часть 1. Аудит текущего состояния

### 1.1. Функции, считающие финансовые метрики

**Группа A. Ядро (calc_*)** — в `api/engine.py`:

| Функция | Строки | Что делает | Вход → Выход |
|---|---|---|---|
| `calc_revenue_monthly` | 615–635 | Месячная выручка с ramp-up и сезонностью | `fin, cal_month, razgon_month` → `int ₸/мес` |
| `calc_cashflow` | 638–695 | 12-месячный CF с разбивкой OPEX | `fin, staff, capex_total, tax_rate, start_month, months, qty` → `list[dict]` по месяцам |
| `calc_breakeven` | 698–736 | Точка безубыточности (₸ и чеков/день) | `fin, staff, tax_rate, qty` → `{тб_₸, тб_чеков_день, запас_прочности_%}` |
| `calc_payback` | 739–749 | Окупаемость из cashflow (первый мес где cumulative≥0) | `capex_total, cashflow` → `{месяц, статус}` |
| `calc_owner_economics` | 774–827 | Месячная экономика собственника (в карман, соцплатежи) | `fin, staff, tax_rate, rent_total, qty` | `dict` |
| `calc_owner_social_payments` | 760–771 | Соцплатежи ИП на УСН (50 МРП × 22%) | `declared_monthly_base` → `int ₸/мес` |
| `calc_closure_growth_points` | 830–845 | Пороги закрытия / роста | `owner_eco` → `dict` |
| `calc_stress_test` | 848–892 | 3 сценария (плохо/база/хорошо) через owner_economics | `fin, staff, tax_rate, rent_total, qty` → `list` |

**Группа B. Главная** — `run_quick_check_v3` (строки 899–1267):
- собирает xlsx-данные, вызывает `calc_*`, строит `scenarios` (pess/base/opt), возвращает единый `result{}`.

**Группа C. Блоки отчёта (`compute_block*`)**:

| Функция | Строки | Основные метрики |
|---|---|---|
| `compute_unified_payback_months` | 142–193 | **Единая** окупаемость `ceil(startup/monthly_income)`, с обучением |
| `compute_block1_verdict` | 1745–1938 | Цвет светофора + 8 скоринг-пунктов + `main_metrics` |
| `compute_block2_passport` | 3479–3591 | format_type, is_solo, типовой штат, финансовые параметры |
| `compute_block3_market` | 1945–2029 | Рынок (для HOME — note вместо баров) |
| `compute_block4_unit_economics` | 2036–2272 | Разбивка чека по архетипу A–F, breakeven |
| `compute_block5_pnl` | 2813–3016 | P&L за год (3 сценария) + ROI + доход предпринимателя |
| `compute_block6_capital` | 2279–2360 | Структура CAPEX + обучение + дефицит/профицит |
| `compute_block7_scenarios` | 2402–2448 | 24-мес траектория (в Quick Check сейчас НЕ вызывается; заменена сезонностью) |
| `compute_block_season` | 2365–2395 | 12 коэффициентов сезонности (per-niche или default) |
| `compute_block8_stress_test` | 2455–2566 | 2 параметра (трафик −20%, чек −15%) + death_points |
| `compute_block9_risks` | 2616–2779 | Топ-5 рисков (с HOME-фильтром и HOME-specific) |
| `compute_block10_next_steps` | 3305–3360 | Чек-лист действий (с обучением для новичков) |

**Группа D. Скоринг `_score_*`** (используется в block1_verdict):

| Функция | Строки | Метрика | Пороги (из `defaults.yaml`) |
|---|---|---|---|
| `_score_capital` | 1522–1558 | Капитал vs CAPEX-ориентир | `[1.2, 0.95, 0.75]` |
| `_score_roi` | 1561–1599 | ROI годовой | `[0.45, 0.30, 0.15]`; SOLO → 3/3 без ROI |
| `_score_breakeven` | 1602–1609 | Окупаемость | `[6, 12, 18]` мес |
| `_score_saturation` | 1612–1646 | Плотность конкурентов / 10K | `[0.6, 1.0, 1.5]` |
| `_score_experience` | 1649–1653 | Опыт | — |
| `_score_marketing` | 1656–1665 | Маркетинг (в QC всегда «express»=2) | — |
| `_score_stress` | 1668–1677 | Падение прибыли при −20% | `[0.30, 0.50]` |
| `_score_format_city` | 1680–1690 | Формат × размер города | — |

**Группа E. Вспомогательное**: `_archetype_of`, `_scenario_pnl_row`, `_get_canonical_format_meta`, `normalize_city_id`, `get_city_check_coef`, `get_rent_median`, `get_city_tax_rate`, `get_competitors`, `_filter_risks_by_format`.

### 1.2. Таблица «метрика → где считается → формула → UI»

| Метрика | Функция-источник | Формула (упрощённо) | Где в UI |
|---|---|---|---|
| Выручка/мес | `calc_revenue_monthly` | `check × traffic × 30 × season(m) × rampup(m)` | Block5 табл. |
| Выручка/год (pess/base/opt) | `run_quick_check_v3` scenarios | `sum(cashflow_12mo)` для каждого `traffic_k × check_k` | Block5 P&L |
| Прибыль/мес (средняя) | `scenarios.base.прибыль_среднемес` | `прибыль_год / 12` | Block1 main_metrics, Block5 |
| Прибыль/год | `sum(cashflow.прибыль)` | 12 мес c ramp-up и сезонностью | Block5 P&L |
| Чистая прибыль Block5 | `_scenario_pnl_row` | `revenue_y − cogs_y − fot_y − rent_y − marketing_y − other_y − tax_y` | Block5 |
| Точка безубыточности | `calc_breakeven` + локальная в Block4 | `fixed / (avg_check − materials − tax)` | Block4 |
| Окупаемость | `compute_unified_payback_months` | `ceil((capex + training) / monthly_income)` | Block1, Block5 |
| (старый путь окупаемости) | `calc_payback` через cashflow | первый `cumulative ≥ 0` | `result.payback.месяц`, fallback в Block1 |
| ROI годовой | `compute_block5_pnl` | `net_profit / total_investment`, cap 3.0 | Block5 (скрыт для SOLO) |
| Стресс-тест трафик −X% | `compute_block8_stress_test` | `−(X/100) × (rev_year × (1−tax) − materials_year)` | Block8 sensitivities |
| Стресс-тест чек −X% | `compute_block8_stress_test` | `−(X/100) × rev_year × (1−tax)` | Block8 sensitivities |
| Доход SOLO | `compute_block5_pnl` (is_solo_fmt) | `net_profit / 12` (ФОТ=0, без role_salary) | Block5 entrepreneur_income |
| Доход owner_plus_* | `compute_block5_pnl` + восстановление ФОТ | `profit + role_salary` | Block5 |
| Сравнение с avg_salary | `compute_block5_pnl` | `AVG_SALARY_2025[city]` из `constants.yaml` | Block5 region_note (только SOLO) |
| Сезонность (12 коэф) | `compute_block_season` | `s01..s12` из xlsx или `DEFAULT_SEASONALITY` | отдельный блок |
| Стартовый капитал | `compute_block6_capital` | сумма статей из CAPEX + training | Block6 |
| Обучение | `TRAINING_COSTS_BY_EXPERIENCE` | 150К / 40К / 0 по experience | Block6 |

### 1.3. Разрывы и противоречия

#### Р-1. Окупаемость — 3 источника, не все синхронизированы

- `compute_unified_payback_months` — primary для Block 1 (line 1789) и Block 5 (line 2936).
- `calc_payback` → `result.payback.месяц` — **fallback** в Block 1 (line 1790–1791): если helper вернул None, берётся из cashflow.
- `compute_block7_scenarios.roi_month` — независимый, для траектории.

Формулы дают разные числа:
- `compute_unified_payback_months`: `ceil(startup/monthly_avg)` → простая арифметика.
- `calc_payback`: первый месяц где `cumulative ≥ 0` → учитывает ramp-up и сезонность (консервативнее).

Для MANICURE_HOME: helper → 2 мес; `calc_payback.месяц` → None (до 12 мес cumulative не дотягивает → экстраполяция). Светофор показывает «2 мес» из helper. Если helper вдруг вернёт None (редкий кейс), Block 1 упадёт в `calc_payback` и число станет иным.

#### Р-2. Маркетинг — три логики в трёх местах

| Место | Строка | Источник | Фолбэк |
|---|---|---|---|
| `calc_cashflow`, `calc_breakeven` | 653, 710 | `fin.get('marketing')` буквально | `0` |
| `compute_block5_pnl` | 2866–2870 | `marketing_med` → `marketing` → `opex_med × 0.2` | `100_000` |
| `compute_block8_stress_test` | 2489–2497 | `marketing_med` → `marketing` → `opex_med × 0.2` | `100_000` |

Последствие: если в xlsx нет `marketing`, `calc_cashflow` считает маркетинг = 0, а Block 5 P&L и Block 8 — 100К/мес. Тогда `scenarios.base.прибыль_год` (из `calc_cashflow`) и `Block5.base.net_profit` (из `_scenario_pnl_row`) **расходятся** на 1.2М/год только из-за маркетинга.

Для MANICURE_HOME это не проявляется — `marketing_med=45000` заполнено в xlsx. Но для любой будущей HOME-ниши без заполненного маркетинга это снова разорвёт Block 5 vs scenarios.

#### Р-3. Прочие OPEX — в `calc_cashflow` их нет, в Block 5/8 добавляются

В `calc_cashflow` (строки 647–665) прямой колонки `other_opex_med` нет — там только `utilities`, `consumables`, `software`, `transport`, `sez_month` из xlsx. В Block 5 и Block 8 используется синтетическая `other_opex_med` с фолбэком 100К/мес.

Если `utilities + consumables + software + transport + sez` в xlsx ≠ `other_opex_med`, то прибыль из `calc_cashflow` ≠ прибыль из `_scenario_pnl_row`. Для MANICURE_HOME xlsx: все нули, кроме `software=5К`. Значит `calc_cashflow` учитывает 5К/мес «прочих», а Block 5 читает `other_opex_med=5000` — совпало. Но это совпадение, а не инвариант.

#### Р-4. Стресс-тест: база — не зрелый режим

`compute_block8_stress_test` берёт `base_profit_year = scenarios.base.прибыль_год` (line 2474), которая посчитана через `calc_cashflow` **с ramp-up и сезонностью** (то есть это средний год, не зрелый).

Формулы на строках 2500–2506 используют `rev_year = scenarios.base.выручка_год` — тоже средний год. Задача спеки (п. 2.6) требует: «База = ЗРЕЛЫЙ РЕЖИМ». Расхождение: impact занижен примерно на `(rev_mature − rev_avg_y1) / rev_mature ≈ 10–15%`.

#### Р-5. `calc_breakeven` (глобальный) vs local `breakeven_value` в Block 4

`calc_breakeven` (строки 698–736) считает безубыточность через `fixed/(1 − cogs_pct − loss_pct − tax_rate)` — в ₸.

В `compute_block4_unit_economics` архетип A (строки 2103–2130, плюс polish#13 патч строк ~2120–2133) безубыточность пересчитывается заново через unit-экономику `fixed_per_master / (avg_check − piece_rate − materials − tax)`. Для SOLO с `rent=0` и `opex_med=None` исходная формула давала 0, patch добавил `fin.marketing_med + fin.other_opex_med` как fixed. Теперь MANICURE_HOME даёт 11 услуг/мес.

Два значения безубыточности в `result`:
- `breakeven.тб_₸` (глобальный, из `calc_breakeven`): может быть 0 для HOME.
- `block4.metrics.breakeven_value` (локальный, `int(fixed_per_master/var_margin)`): 11.

В UI показывается только второе. Первое в UI не идёт, но остаётся в данных и его может случайно прочитать будущий потребитель.

#### Р-6. Fallback-значения не совпадают с данными xlsx

В `compute_block8_stress_test` исторически были фолбэки `rent=150_000`, `fot=300_000` — после critical#1 Round 8 они убраны. Но в других местах остались:
- `calc_revenue_monthly`: `check=1000`, `traffic=50` (line 619–620).
- `calc_cashflow`: `fot=300_000`, `rent=150_000` в строке 641 (нужно проверить — если ещё остались).
- `compute_block5_pnl`: `marketing=100_000`, `other_opex=100_000` (line 2868, 2878).
- `compute_block4_unit_economics`: `avg_check=3000`, `traffic=30` (line 2043–2044).

Если в xlsx что-то пусто, цифры разъедутся между блоками.

#### Р-7. Ramp-up применён к выручке, но окупаемость его игнорирует

`compute_unified_payback_months` (строки 177–178) использует `scenarios.base.прибыль_среднемес` — это средний месяц первого года (с ramp-up). Но знаменатель должен быть «что клиент будет получать в зрелости», иначе первый год искусственно занижает окупаемость в 1/1 и затягивает её.

С другой стороны, `calc_payback` через cashflow **учитывает** ramp-up корректно (cumulative растёт медленнее в первые 3 мес). Задача (п. 2.8) требует единую формулу `capex / monthly_net_income_average_over_y1` — то есть helper это делает правильно. Но тогда для бизнесов с долгим ramp-up (>6 мес) окупаемость в helper будет заниженной. Решение спеки: взять `avg_over_y1`, как сейчас.

#### Р-8. `compute_block7_scenarios` мёртвый в Quick Check

После Round 4 bug#8 `compute_block7_scenarios` больше не вызывается в `/quick-check` (заменён `compute_block_season`), но функция по-прежнему существует и может импортироваться finmodel'ом. 1700+ строк мёртвого кода в `engine.py` (оценка из Round 5 notes). В новом движке можно вынести в отдельный модуль или удалить.

#### Р-9. ROI для STANDARD использует `net_profit / total_investment` без учёта времени

`compute_block5_pnl` строки 2908–2942: `raw_roi = net_profit / total_investment`, cap 3.0 (300%). Это годовой ROI, но:
- `net_profit` здесь — первый год с ramp-up (занижен на 10–15%).
- `total_investment` — priority `capital_own → capex_standard_08 → capex_med → capex_total`, то есть может быть capex без working_cap.

Для BARBER_STANDARD baseline показал ROI=211% (>100%) — это реалистично для STANDARD со средней прибылью 1.2 млн/мес, но формулу стоит проверить: правильнее делить на полные стартовые вложения (capex + подушка), не только на «capex_standard».

#### Р-10. `compute_block1_verdict.main_metrics` больше не показывается на фронте

После Round 4 bug#4 секция «Главные цифры» из Block 1 удалена на фронте, но backend продолжает вычислять и возвращать `main_metrics` с 4 полями (revenue_range, profit_range, breakeven_range, entrepreneur_income_range). Мёртвый payload ~200 байт на каждый запрос.

#### Р-11. Stress-test death_points пересчитывают marketing отдельно от Block 5

В `compute_block8_stress_test` (строки 2489–2497) есть дублированный расчёт фиксированных расходов (включая маркетинг с fallback) — отдельно от `compute_block5_pnl`. Если фолбэк-значения вдруг разойдутся, `death_points` покажет один порог, а Block 5 P&L — другое число прибыли (потому что marketing разный). Нужно единое место вычисления `fixed_monthly`.

#### Р-12. `region_note` (avg_salary) только для SOLO

`compute_block5_pnl` (строки 2976–2989) формирует сравнительную ремарку только если `is_solo_fmt=True`. Для STANDARD/PREMIUM этого блока нет вообще. Это намеренно (задача polish#6), но в спеке надо зафиксировать — иначе при перепиcке кто-то добавит «для честности» и сломает консистентность.

#### Р-13. `result` после `render_report_v4` не содержит `capex`, `scenarios`, `payback` на верхнем уровне

Из аудитного probe видно: `result.keys() = ['input', 'owner_economics', 'health', 'block_1'..'block_10', 'block_11_season', 'block_12_checklist', 'block1'..'block10', 'block_season', 'user_inputs']`. То есть в API-ответе нет прямого `capex`, `scenarios`, `payback` — всё упаковано в блоки.

`report.render_report_v4` перекладывает данные. При переписке движка надо решить: оставить полный `result` (как передаётся в `compute_block*`) или только агрегаты. Сейчас `compute_block*` получают полный `result`, но клиенту отдаются только блоки. Это нормально, но не задокументировано.

---

## Часть 2. Утверждённые финансовые решения (аксиомы)

Все пункты ниже — **решения продуктового владельца**, не обсуждаются. Новая расчётная логика должна их реализовать.

### 2.1. Налоговая модель
- **ИП на упрощённой декларации (УСН)**: вся прибыль после налога → предпринимателю в карман. ФОТ предпринимателя = 0. Альтернативная стоимость труда **не вычитается**.
- **ТОО на ОУР**: собственник в штате, его зарплата — часть ФОТ. Прибыль ТОО считается отдельно от его зарплаты.
- **Для HOME/SOLO по умолчанию — ИП**.

### 2.2. Метод учёта
- Кассовый метод (не начисления).
- Амортизация **не рассчитывается**.
- Маркетинг — расходы периода.
- Обучение (если `experience=none|some`) — часть стартовых вложений, **не амортизируется**.

### 2.3. Ramp-up (разгон)
- `rampup_months` и `rampup_start_pct` из FINANCIALS.
- Линейная интерполяция: `m=1 → rampup_start_pct`, `m=rampup_months → 100%`, `m>rampup_months → 100%`.
- Применяется **к выручке** (количество услуг растёт, чек не меняется).
- Должен влиять на: месячный P&L, окупаемость, средний год.
- **Не должен влиять** на: зрелый P&L, стресс-тест (база = зрелый).

### 2.4. Сезонность
- `s01..s12` из FINANCIALS; сумма ≈ 12, среднее ≈ 1.0.
- Применяется к выручке **после** ramp-up.
- Влияет на: месячный P&L в инфографике, средний годовой P&L.
- **Не влияет** на: зрелый средний P&L (там сезонность усредняется в 1.0).

### 2.5. «Зрелый режим» vs «Средний за год»
- **Зрелый режим**: выручка × 1.0 ramp × 1.0 season. «Стабильное значение после выхода на мощность». Используется в: стресс-тесте, юнит-экономике, точке безубыточности.
- **Средний за год (первый)**: `sum(12 мес) / 12` (с ramp и сезонностью). Используется в: P&L-таблице за год, окупаемости.

Для бизнеса с `rampup=3 мес` / `start=0.30`: средний год ≈ 0.83 × зрелый.

### 2.6. Стресс-тест
- **База**: ЗРЕЛЫЙ РЕЖИМ (revenue × 1 × 1, без ramp и season).
- Параметры: Загрузка/трафик −20%, Средний чек −15%.
- Формула для трафик −X%:
  ```
  revenue_new_mature = revenue_mature × (1 − X/100)
  materials_new_mature = materials_mature × (1 − X/100)
  tax_new_mature = revenue_new_mature × tax_rate
  фиксированные (ФОТ, аренда, маркетинг, прочие) — не меняются
  profit_new_mature = revenue_new_mature − materials_new_mature − tax_new_mature − fixed_monthly
  delta_mature_monthly = profit_mature − profit_new_mature
  impact_year = delta_mature_monthly × 12
  ```
- Формула для чек −X%:
  ```
  revenue_new_mature = revenue_mature × (1 − X/100)
  materials_new_mature = materials_mature  // НЕ меняется (те же услуги)
  остальное по аналогии
  ```
- Результат возвращается в ₸/год (отрицательное = потеря).

### 2.7. Точка безубыточности
- Метод: unit-экономика (для архетипа A услуг).
- **Переменные на услугу**: материалы + налог.
- **Фиксированные в месяц**: ФОТ + аренда + маркетинг + прочие расходы (всё что не зависит от объёма).
- `breakeven_units = ceil(fixed_monthly / (avg_check − variable_per_service))`.
- Для HOME-форматов `fixed_monthly` = `marketing_med + other_opex_med` (rent=0, fot=0).
- Для MANICURE_HOME: `50_000 / (5_250 − 630 − 157) ≈ 11.2 → ceil = 12` услуг/мес (задача говорит «11 услуг» — результат текущего `int()`, но спека требует `ceil`).

### 2.8. Окупаемость
- Формула: `payback_months = ceil(capex_total / monthly_net_income_average_over_y1)`.
- Знаменатель — средний месячный доход за первый год (с ramp-up и сезонностью).
- Для ИП: `net_income = прибыль` (вся в карман).
- Для ТОО: `net_income = дивиденды + зарплата собственника`.
- **ОДНА формула во всех местах** (светофор, карточка окупаемости, главные цифры).
- `capex_total` = все статьи из CAPEX + training_cost (если применимо).

### 2.9. 3 сценария (пессимист / база / оптимист)
- Меняется **только**: `traffic_k`, `check_k` (коэффициенты из `defaults.yaml`).
- ФОТ, аренда, маркетинг — одинаковые во всех сценариях.
- В UI пояснение клиенту: «Пессимист = худший старт. База = типичный ход. Оптимист = всё идёт хорошо.»

### 2.10. Сравнение с средней зарплатой региона
- Только для HOME/SOLO форматов.
- `if доход < avg_salary_city` → «Ниже средней зарплаты по {city} (~{X} тыс). Для старта — рабочий вариант.»
- `if доход ≥ avg_salary_city` → «Выше средней зарплаты. Неплохой уровень для самозанятости.»
- Для STANDARD/PREMIUM — **не показывать**.

---

## Часть 3. Целевая последовательность расчёта

10 шагов от входа до выхода. Каждый — изолированная функция-фаза.

### Шаг 1. Загрузка входных данных

**Из анкеты**: `city_id, niche_id, format_id, experience, capital, founder_works (из format_id), specific_answers`.

**Из `xlsx FORMATS`**: `format_type, class, area_m2, loc_type, qty_points, training_required`.

**Из `xlsx FINANCIALS`**: `check_min/med/max, traffic_min/med/max, cogs_pct, rent_med, marketing_med, other_opex_med, utilities, consumables, software, transport, sez_month, loss_pct, rampup_months, rampup_start_pct, s01..s12`.

**Из `xlsx CAPEX`**: `capex_min/med/max, equipment, renovation, furniture, first_stock, permits_sez, working_cap_3m, marketing, deposit, legal`.

**Из `xlsx STAFF`**: `headcount, fot_net_med, fot_full_med, positions, founder_role`.

**Из `08_niche_formats.xlsx`**: `capex_standard, masters_count, area_m2` (канон).

**Из `xlsx 05_tax_regimes`**: `tax_rate` по городу.
**Из `xlsx 11_rent_benchmarks`**: `rent_median_m2` по городу × loc_type.
**Из `config/constants.yaml`**: `avg_salary_2025[city]`, `check_coef[city]`, `TRAINING_COSTS_BY_EXPERIENCE`.
**Из `config/defaults.yaml`**: `SCENARIO_*`, `DEFAULT_SEASONALITY`, `SCORING_*`, `BLOCK1_THRESHOLDS`.

### Шаг 2. Нормализация параметров

- Для HOME/SOLO (`format_id.endswith('_HOME')` или `'_SOLO'`): `founder_works = True`, `fot_monthly = 0`, `headcount = 0`.
- Для STANDARD/PREMIUM: `founder_works = (entrepreneur_role ∈ owner_plus_*)`, `fot_monthly` берётся из STAFF.
- Если `founder_works=True` и `headcount ≥ 1`: вычесть одну ставку из ФОТ (`fot_monthly -= fot_monthly/headcount`).
- Если `training_required=True` и `experience ∈ {none, some}`: `training_cost = TRAINING_COSTS_BY_EXPERIENCE[experience]` (150К / 40К).
- Ценовой коэффициент города: `check_med *= city_coef` (например Астана 1.05).
- Если `marketing_med` не задан — fallback: **НЕ 100К/мес**, а `0` или осмысленный дефолт по архетипу (см. Р-6 и вопрос 7.1).

### Шаг 3. Расчёт зрелого месячного P&L

«Зрелый» = ramp=1.0 и season=1.0.

```
revenue_mature_m = check_med × traffic_med × 30  (или × work_days для услуг)
materials_m = revenue_mature_m × cogs_pct
tax_m = revenue_mature_m × tax_rate
fixed_m = fot_monthly + rent_monthly + marketing_med + other_opex_med
profit_mature_m = revenue_mature_m − materials_m − tax_m − fixed_m
```

### Шаг 4. Расчёт 12-месячного P&L с ramp-up и сезонностью

```
для m = 1..12:
  cal_m = ((start_month − 1 + m − 1) mod 12) + 1
  season = s{cal_m:02d}   (или DEFAULT_SEASONALITY[cal_m − 1])
  if m ≤ rampup_months:
    ramp = rampup_start_pct + (1 − rampup_start_pct) × m / rampup_months
  else:
    ramp = 1.0
  revenue_m = revenue_mature_m × ramp × season
  materials_m = revenue_m × cogs_pct
  tax_m = revenue_m × tax_rate
  profit_m = revenue_m − materials_m − tax_m − fixed_m
  cumulative_m = cumulative_{m−1} + profit_m   (m=0: −capex_total)
```

### Шаг 5. Расчёт средних годовых показателей

```
revenue_year_avg = sum(revenue_m for m in 1..12)
materials_year_avg = sum(materials_m)
tax_year_avg = sum(tax_m)
profit_year_avg = sum(profit_m)
profit_month_avg = profit_year_avg / 12
```

**Важно**: эти цифры используются в P&L за год (Block 5) и в окупаемости. **Не используются** в стресс-тесте.

### Шаг 6. Расчёт окупаемости

```
capex_total = capex_med + deposit + working_cap + training_cost
payback_months = ceil(capex_total / profit_month_avg)
```

Если `profit_month_avg ≤ 0` → `payback_months = None` (→ UI показывает «не окупается за первый год»).

**ВАЖНО**: эта формула используется **везде** где показывается окупаемость (Block 1, Block 5, планы действий). Не пересчитывать нигде более.

### Шаг 7. Расчёт точки безубыточности

```
variable_per_service = avg_check × cogs_pct + avg_check × tax_rate
                    = avg_check × (cogs_pct + tax_rate)
fixed_monthly = fot_monthly + rent_monthly + marketing_med + other_opex_med
breakeven_services = ceil(fixed_monthly / (avg_check − variable_per_service))
```

Если `avg_check − variable_per_service ≤ 0` → `breakeven = ∞` (модель убыточна при любой загрузке).

### Шаг 8. Расчёт стресс-теста

База — зрелый режим (Шаг 3).

**Трафик −X% (X=20)**:
```
revenue_new = revenue_mature_m × (1 − X/100)
materials_new = materials_m × (1 − X/100)          // пропорционально
tax_new = revenue_new × tax_rate
profit_new = revenue_new − materials_new − tax_new − fixed_monthly
impact_year_traffic = (profit_new − profit_mature_m) × 12  // отрицательно
```

**Чек −X% (X=15)**:
```
revenue_new = revenue_mature_m × (1 − X/100)
materials_new = materials_m                         // НЕ меняется
tax_new = revenue_new × tax_rate
profit_new = revenue_new − materials_new − tax_new − fixed_monthly
impact_year_avg_check = (profit_new − profit_mature_m) × 12
```

**Death points** (пороги убытка):
```
traffic_threshold_pct = 1 − fixed_monthly / (revenue_mature_m × (1 − tax_rate − cogs_pct))
avg_check_threshold_pct = 1 − fixed_monthly / (revenue_mature_m × (1 − tax_rate) − materials_m)
```

Возвращать в процентах и округлять до целого (напр. «падение >63% ведёт в минус»).

### Шаг 9. Расчёт 3 сценариев

```
для scenario in [pess (0.75, 0.90), base (1.00, 1.00), opt (1.25, 1.10)]:
  traffic_sc = traffic_med × traffic_k
  check_sc = check_med × check_k
  // ФОТ, аренда, маркетинг — базовые, НЕ меняются
  повторить Шаги 3–5 с новыми traffic_sc, check_sc
  вернуть revenue_year_avg, profit_year_avg, profit_month_avg
```

Используется в Block 5 P&L таблице.

### Шаг 10. Формирование вердикта (светофор)

8 компонентов скоринга (строки 1838–1846). Каждый даёт 0–3 балла.

```
items = [
  _score_capital(capital_own, capex_needed),
  _score_roi(profit_year, total_investment, is_solo=...),
  _score_breakeven(payback_months),                     // из Шага 6
  _score_saturation(competitors_count, city_pop, niche_id, density),
  _score_experience(experience),
  _score_marketing('express'),
  _score_stress(profit_base, profit_pess),
  _score_format_city(format_id, class, city_pop),
]
total_score = sum(item.score)
max_score = sum(item.max=3)  // = 24

if total_score ≥ 17: color = 'green'
elif total_score ≥ 12: color = 'yellow'
else: color = 'red'
```

Пороги 17/12 из `defaults.yaml.block1_verdict.thresholds`.

**Для SOLO**: ROI → 3/3 с note «не применим», чтобы SOLO-форматы не штрафовались.

### (Дополнительно) Шаг 11. Сравнение с avg_salary (только для SOLO)

```
if is_solo_fmt:
  avg_salary = constants.avg_salary_2025[city_id] or 430000
  if profit_month_avg < avg_salary:
    region_note = f"Ниже средней зарплаты по {city} (~{k} тыс ₸). ..."
  else:
    region_note = f"Выше средней зарплаты. Неплохой уровень для самозанятости."
```

---

## Часть 4. Тестовый пример: MANICURE_HOME / Астана / experience=none

**Входные данные (из актуального xlsx)**:

| Параметр | Значение | Источник |
|---|---|---|
| `check_med` (xlsx) | 5000 | FINANCIALS |
| `city_coef` Астаны | 1.05 | constants.yaml |
| `avg_check` (после коэф) | **5 250** | city_coef × check_med |
| `traffic_med` | 3 | FINANCIALS (см. вопрос 7.2) |
| `cogs_pct` | 0.12 | FINANCIALS |
| `rent_monthly` | 0 | loc_type=home |
| `fot_monthly` | 0 | SOLO |
| `marketing_med` | 45 000 | FINANCIALS |
| `other_opex_med` | 5 000 | FINANCIALS |
| `tax_rate` | 0.03 | Астана УСН 3% |
| `rampup_months` | 3 | FINANCIALS |
| `rampup_start_pct` | 0.30 | FINANCIALS |
| `s01..s12` | 0.80, 0.85, 1.15, 0.75, 1.10, 1.10, 1.00, 1.00, 1.00, 0.95, 0.85, 1.30 | FINANCIALS |
| `start_month` | 4 (апрель) | вход |
| `capex_base` | 330 000 | CAPEX (сумма статей) |
| `training_cost` (experience=none) | 150 000 | TRAINING_COSTS_BY_EXPERIENCE |
| **`capex_total`** | **480 000** | capex_base + training |

### Шаг 3. Зрелый месячный P&L

```
revenue_mature = 5 250 × 3 × 30 = 472 500 ₸/мес
materials = 472 500 × 0.12 = 56 700 ₸/мес
tax = 472 500 × 0.03 = 14 175 ₸/мес
fixed = 0 + 0 + 45 000 + 5 000 = 50 000 ₸/мес
profit_mature = 472 500 − 56 700 − 14 175 − 50 000 = 351 625 ₸/мес
```

### Шаг 4. 12-месячный P&L (start_month=4, апрель)

| Мес | cal | season | ramp | revenue | profit |
|---|---|---|---|---|---|
| 1 | 4 (апр) | 0.75 | 0.533 | 188 913 | 116 569 |
| 2 | 5 (май) | 1.10 | 0.767 | 398 641 | 302 989 |
| 3 | 6 (июн) | 1.10 | 1.000 | 519 750 | 410 989 |
| 4 | 7 (июл) | 1.00 | 1.000 | 472 500 | 351 625 |
| 5 | 8 (авг) | 1.00 | 1.000 | 472 500 | 351 625 |
| 6 | 9 (сен) | 1.00 | 1.000 | 472 500 | 351 625 |
| 7 | 10 (окт) | 0.95 | 1.000 | 448 875 | 330 003 |
| 8 | 11 (ноя) | 0.85 | 1.000 | 401 625 | 286 758 |
| 9 | 12 (дек) | 1.30 | 1.000 | 614 250 | 481 494 |
| 10 | 1 (янв) | 0.80 | 1.000 | 378 000 | 310 380 |
| 11 | 2 (фев) | 0.85 | 1.000 | 401 625 | 286 758 |
| 12 | 3 (мар) | 1.15 | 1.000 | 543 375 | 416 610 |

Формула `profit_m = revenue_m × (1 − 0.12 − 0.03) − 50 000 = revenue_m × 0.85 − 50 000`.

### Шаг 5. Средний год

```
revenue_year_avg ≈ 5 312 554 ₸
materials_year_avg ≈ 637 506 ₸
tax_year_avg ≈ 159 377 ₸
fixed_year = 50 000 × 12 = 600 000 ₸
profit_year_avg ≈ 5 312 554 × 0.85 − 600 000 = 3 915 671 ₸
profit_month_avg ≈ 326 306 ₸/мес
```

Коэффициент к зрелому: `3 915 671 / (351 625 × 12) = 3 915 671 / 4 219 500 ≈ 0.928` — ramp-up и сезонность «съели» 7% за первый год.

(В текущем движке `baseline.прибыль_год = 3 756 236`, т.е. ~3.76 млн — отличие ~4% связано с двойным учётом чего-то или мелкой деталью сезонности. Требует сверки при переписке — вопрос 7.3.)

### Шаг 6. Окупаемость

```
payback_months = ceil(480 000 / 326 306) = ceil(1.471) = 2 мес
```

✅ Совпадает с текущим Block 5 / Block 1 (после critical#2 синхронизированы через helper).

### Шаг 7. Точка безубыточности

```
variable_per_service = 5 250 × (0.12 + 0.03) = 5 250 × 0.15 = 787.5 ₸
contribution_margin = 5 250 − 787.5 = 4 462.5 ₸
fixed_monthly = 50 000 ₸
breakeven = ceil(50 000 / 4 462.5) = ceil(11.20) = 12 услуг/мес
```

Текущий движок даёт **11** (использует `int()`, не `ceil`). Спека требует `ceil` → **12**.

### Шаг 8. Стресс-тест

**Трафик −20% (от зрелого)**:
```
revenue_new = 472 500 × 0.80 = 378 000
materials_new = 56 700 × 0.80 = 45 360
tax_new = 378 000 × 0.03 = 11 340
profit_new = 378 000 − 45 360 − 11 340 − 50 000 = 271 300 ₸/мес
delta_month = 351 625 − 271 300 = 80 325 ₸/мес
impact_year_traffic = −80 325 × 12 ≈ −963 900 ₸/год
```

**Чек −15% (от зрелого)**:
```
revenue_new = 472 500 × 0.85 = 401 625
materials_new = 56 700  (НЕ меняется)
tax_new = 401 625 × 0.03 = 12 049
profit_new = 401 625 − 56 700 − 12 049 − 50 000 = 282 876 ₸/мес
delta_month = 351 625 − 282 876 = 68 749 ₸/мес
impact_year_check = −68 749 × 12 ≈ −824 988 ₸/год
```

**Death points**:
```
traffic_threshold_pct = 1 − 600 000 / (5 312 554 × (1 − 0.03 − 0.12))
                      = 1 − 600 000 / 4 515 671
                      = 1 − 0.133 = 0.867 ≈ 87%
avg_check_threshold_pct = 1 − 600 000 / (5 312 554 × 0.97 − 637 506)
                        = 1 − 600 000 / (5 153 177 − 637 506)
                        = 1 − 600 000 / 4 515 671 ≈ 87%
```

Для SOLO-мастера с минимальными фикс-расходами обе точки смерти совпадают и очень далёкие — это ожидаемо для модели с низкими постоянными расходами.

**Текущее** (после critical#1, средний год, не зрелый):
- трафик −20% → −903 121 (занижен на ~6% из-за ramp-up effect)
- чек −15% → −772 965

Расхождение 6% — именно оно и есть «база = средний, а не зрелый» (Р-4).

### Шаг 9. 3 сценария

| Сценарий | `traffic_k` | `check_k` | revenue_year_avg (~, ₸) | profit_month_avg (~, ₸) |
|---|---|---|---|---|
| Пессимист | 0.75 | 0.90 | 3 586 K | 203 K |
| База | 1.00 | 1.00 | 5 313 K | 326 K |
| Оптимист | 1.25 | 1.10 | 7 304 K | 467 K |

Цифры оптимиста аппроксимация (ramp и season те же, ФОТ/аренда/маркетинг фикс).

### Шаг 10. Вердикт (светофор)

Для MANICURE_HOME/none на Астане скоринг складывается примерно так (по текущему движку):

| Компонент | Балл | Заметка |
|---|---|---|
| Капитал vs ориентир | 2 | capital=None → «не указан, условный» |
| ROI годовой | 3/3 | SOLO: «не применим, работаете сами» |
| Точка безубыточности (окупаемость) | 3 | 2 мес — быстрая |
| Насыщенность | — | для HOME фильтруется (Р-5 predыд. раунда) |
| Опыт | 0 | experience=none |
| Маркетинг | 2 | express |
| Устойчивость к стрессу | 3 | profit_base=326К, pess≈203К, drop=0.38 → 2 или 3 |
| Формат × город | 3 | HOME в megacity — ок |

Сумма ≈ 16–18. Порог green=17 → **жёлтый/зелёный**. В текущем движке — зелёный. После пересборки может быть другим.

### Итоговая сводка для MANICURE_HOME/Астана/exp=none (целевая)

| Метрика | Значение | Источник (Шаг) |
|---|---|---|
| Зрелая месячная выручка | 472 500 ₸ | 3 |
| Зрелая месячная прибыль | 351 625 ₸ | 3 |
| Средняя годовая выручка | 5 312 554 ₸ | 5 |
| Средняя годовая прибыль | 3 915 671 ₸ | 5 |
| Средняя месячная прибыль за первый год | 326 306 ₸ | 5 |
| Окупаемость | 2 мес | 6 |
| Точка безубыточности | 12 услуг/мес | 7 |
| Стресс трафик −20% | −963 900 ₸/год | 8 |
| Стресс чек −15% | −824 988 ₸/год | 8 |
| Death point трафик | 87% | 8 |

---

## Часть 5. Карта метрик → UI

| Блок UI | Метрика в UI | Источник (Шаг) | Формат вывода |
|---|---|---|---|
| **Block 2 «Паспорт»** | format_type, is_solo, typical_staff | 2 (норм.) | Категориально |
| **Block 2 finance** | Monthly revenue / profit / capex | 3 (зрелый) | Диапазон |
| **Block 3 «Рынок»** | competitors, density, city_coef | xlsx | Блок / HOME — note |
| **Block 4 «Юнит-эко»** | avg_check, checks_per_day (медиана) | Шаг 1 | 5 250 ₸ / 3 чека |
| **Block 4** | max_checks_per_day | Шаг 1 (для SOLO: max 6) | 6 при 100% загрузке |
| **Block 4** | breakdown чека (%) | Шаг 3 | Материалы / Аренда / В карман |
| **Block 4** | Точка безубыточности | Шаг 7 | 12 услуг/мес (с пояснением) |
| **Block 5 «Финансы год»** | Revenue pess/base/opt | Шаг 9 | 3 колонки |
| **Block 5** | Net profit pess/base/opt | Шаг 9 | 3 колонки |
| **Block 5** | Маржи (валовая, опер., чистая) | Шаг 5 / базовый | В % |
| **Block 5** | Окупаемость (для SOLO вместо ROI) | Шаг 6 | «2 мес» |
| **Block 5** | ROI годовой (для STANDARD/PREMIUM) | Шаг 5 | «211% — выше среднего» |
| **Block 5** | «Ориентир по региону» (доход) | Шаг 5 | В ₸/мес + region_note |
| **Block 5** | region_note (только SOLO) | Шаг 11 | Сравнение с avg_salary |
| **Block 6 «Стартовый капитал»** | capex_structure | Шаг 2 | Список статей с обучением |
| **Block 6** | Итого / нужно | Шаг 2 | `capex_total` |
| **Block 6** | Дефицит / профицит | Шаг 2 + capital_own | Процент + actions |
| **Block 7 (сезонность)** | 12 коэффициентов | xlsx s01..s12 | Бар-чарт |
| **Block 8 «Стресс-тест»** | Impact трафик −20% | Шаг 8 | «−964 тыс ₸/год» |
| **Block 8** | Impact чек −15% | Шаг 8 | «−825 тыс ₸/год» |
| **Block 8** | Death points | Шаг 8 | «падение >87% ведёт в минус» |
| **Block 9 «Риски»** | Топ-5 рисков | insight.md + HOME-specific | Список с «Что делать» |
| **Block 1 «Светофор»** | Цвет (green/yellow/red) | Шаг 10 | + Что работает / требует внимания |
| **Block 10 «План действий»** | Чек-лист 60 дней | Шаг 10 | С учётом обучения |

**Источник-инвариант для окупаемости**:
Block 1 `breakeven_range`, Block 5 `payback_months`, Block 6 action «Кредит» (монтлли платёж — считается отдельно, не через payback) — все читают из **Шаг 6** через единый helper `compute_unified_payback_months`. Никаких ветвлений.

---

## Часть 6. Критичные правила и грабли (на основе 7 раундов)

1. **Не маскировать баги расчётов UI-фильтрами.**
   Пример: в Round 4–7 было «если impact > 200 — значит рубли, иначе проценты». Так бага в движке (`base_op_profit=1` из-за фолбэков 300К ФОТ для HOME) была спрятана, а не починена. В Round 8 пришлось переделывать с нуля. Фикс — в движке.

2. **Не считать одну метрику в двух местах по разным формулам.**
   Окупаемость до Round 8 считалась минимум в 3 местах (`calc_payback`, `compute_block5_pnl`, `compute_block1_verdict`) — давала разные числа. Теперь единый helper `compute_unified_payback_months`. Всё, что отдаётся клиенту, **должно** брать из одного источника.

3. **Ramp-up применяется к выручке → должен применяться везде, где используется годовая прибыль первого года.**
   Если ramp-up попадает в cashflow, то: P&L за год — средний (с ramp), окупаемость — через средний месяц. Стресс-тест — от **зрелого** режима (без ramp). Это разные базы, и не путать.

4. **Фолбэки ломают консистентность.**
   `100К/мес маркетинг` и `100К/мес прочие` — если хотя бы в одном блоке падаем на этот фолбэк, а в другом берётся xlsx-значение — получаем разрыв прибыли. Все фолбэки должны быть **либо 0** (пользователь увидит «не учтено»), **либо явные в одном месте модуля и переиспользуемые**.

5. **ИП не платит себе зарплату. ФОТ = 0, но доход = вся прибыль.**
   Не добавлять «минимальную ставку 200К» если ФОТ подрезан до 0 (прежний баг — при `founder_works=True` и `headcount=1` код рисовал фиктивные 200К «ставка в штате»).

6. **Округление: `ceil` для консервативности.**
   - Окупаемость: `ceil` (11.3 мес → 12 мес).
   - Breakeven services: `ceil` (11.2 услуг → 12).
   Не использовать `round` (может округлить вниз и создать «невозможные» цифры).

7. **Сезонность и ramp-up — это про первый год. После — зрелость.**
   - Месячные графики в UI: с ramp и season.
   - Средний P&L за год: с ramp и season.
   - Стресс-тест, unit-экономика, точка безубыточности: от **зрелого** режима.

8. **«Чек − 15%» не меняет materials.**
   Меняет только выручку (услуг столько же, материалы те же). Это отдельная формула от «трафик − 20%» (пропорциональное падение revenue и materials).

9. **training_cost плюсуется к CAPEX только для бьюти-ниш.**
   Флаг `training_required` в FORMATS. Для остальных ниш (COFFEE, PVZ и т.п.) не применяется.

10. **avg_salary comparison — только для HOME/SOLO.**
    STANDARD/PREMIUM это не показывают.

---

## Часть 7. Открытые вопросы для продуктового владельца

Эти места в спеке намеренно оставлены без однозначного ответа. Нужно решение Адиля до начала переписки.

### 7.1. Фолбэк маркетинга для ниш без `marketing_med` в xlsx

**Контекст**: сейчас `compute_block5_pnl` падает на `100_000 ₸/мес` если xlsx пустой. Это круглая цифра из воздуха.

**Варианты**:
- **(a)** Фолбэк `0` — если не указано, считаем 0 маркетинга. Клиент увидит очень высокую прибыль для неоткалиброванных ниш и жёлтый флажок «калибровка неполная» в Block 5.
- **(b)** Фолбэк «% от revenue» — например, 5% от `revenue_mature`. Физически осмысленнее, но скрывает факт отсутствия данных.
- **(c)** Валидация: если `marketing_med` пусто, `/quick-check` возвращает 400 «ниша не откалибрована» — жёсткая защита от неправильных цифр.

**Рекомендация**: (c) строго, (a) как промежуточное решение пока не все ниши откалиброваны.

### 7.2. `traffic_med=3` для MANICURE_HOME — это «реалистичная загрузка» или «максимум»?

В задаче prompt'а писалось, что `traffic_med` — это пропускная способность (до 6 при 100%), а «3» — уже после `load_med=0.50`. Но в xlsx `traffic_med=3` без отдельного `load_med`.

**Варианты**:
- **(a)** `traffic_med` — это уже «реалистичная медиана в день» (3 клиенток/день среднее, без load_pct). Тогда зрелая выручка 3×5250×30 = 472К. Это текущий расчёт.
- **(b)** `traffic_med` — это потолок (6), а реальная загрузка 50%. Тогда нужно ввести `load_med` в xlsx для всех бьюти-ниш и пересчитать всё.

**Рекомендация**: (a) — `traffic_med` = «среднее в день по факту». Для отображения на UI «максимум при 100% загрузке» использовать отдельный lookup (как в compute_block4 polish#E через `max_checks_per_day = max(int(traffic/load), traffic+1, 6)`).

### 7.3. Расхождение `profit_year_avg` между ручным счётом (3.91 млн) и движком (3.76 млн) ~4%

Вероятные источники:
- Двойной учёт чего-то в calc_cashflow (например `sez_month` или `consumables`).
- Разное применение `loss_pct` (в `calc_cashflow` потери вычитаются, в моей ручной формуле — нет).
- Округление `int()` vs `round()`.

**Решение**: при переписке — явно выписать формулу `profit_m` для Шага 4 и сверить 1:1 с Шагом 3. Не должно быть хвостовых расходов, не учтённых в спеке.

### 7.4. `compute_block8_stress_test.death_points` — правильная ли интерпретация?

Для MANICURE_HOME death point = «падение >87% ведёт в минус». Это математически верно (фикс-расходы 50К, выручка 472К, запас огромный). Но пользователь может подумать «87% это нормально, можно падать». На самом деле при падении трафика даже на 40% прибыль усыхает вдвое.

**Варианты**:
- **(a)** Оставить death_points как есть (порог убыточности) и объяснить текстом.
- **(b)** Убрать death_points для HOME-моделей с минимальной fixed — они выглядят неадекватно.
- **(c)** Заменить на «падение на 20% убирает X% прибыли, на 40% — Y%, на 60% — Z%» (шкала чувствительности вместо пороговой точки).

### 7.5. `working_capital` внутри `capex_total` — включать ли в `payback`?

Сейчас `capex_total = capex_med + deposit + working_cap`. `working_cap` — это «оборотка на 3 месяца», не безвозвратное вложение. С одной стороны, её тоже надо «окупить» (да, возвращается в операционный цикл). С другой — это не амортизируемый актив, а «подушка», которая никуда не девается.

**Варианты**:
- **(a)** Включать в `capex_total` для payback (сейчас). Окупаемость консервативнее.
- **(b)** Не включать — payback считать только от безвозвратных вложений (equipment, furniture, renovation, permits, training).

**Рекомендация**: (a), как сейчас. Чтобы клиент не удивлялся «почему окупаемость 1 мес», когда по факту нужно ещё 45К для оборотки.

### 7.6. Сценарии (Шаг 9) — оптимист с `fot × 1.15`?

Текущий `_scenario_pnl_row` для оптимиста увеличивает ФОТ на 15% (комментарий «сдельщики получают больше»). Это ломает правило 2.9 «ФОТ фиксирован во всех сценариях».

**Варианты**:
- **(a)** Убрать `× 1.15` — ФОТ одинаковый во всех 3 сценариях.
- **(b)** Оставить, но задокументировать в спеке как «при росте выручки 25%, переменная часть сдельной ФОТ растёт на 15%».

**Рекомендация**: (a) — для Quick Check проще и честнее. Для FinModel можно оставить (b).

### 7.7. Текущий фолбэк `marketing=100К` уже ломает SOLO для NICHE без xlsx

Если в будущем добавится, скажем, BARBER_HOME и в FINANCIALS пропущена колонка `marketing_med`, фолбэк 100К/мес даст 1.2 млн/год маркетинга для мастера на дому. Это нонсенс.

**Действие**: вместе с переписью — валидация на старте: при `format_type in (HOME, SOLO)` обязательное наличие `marketing_med` и `other_opex_med` в xlsx. Иначе явная ошибка в логах + `/quick-check` возвращает 400.

---

## Приложение A. Структура `result{}` — что возвращает движок

```
result = {
    'input': {city_id, niche_id, format_id, cls, ..., training_required},
    # ── Расчётные агрегаты ──
    'market': {...},
    'capex': {capex_min/med/max, total, breakdown{}, deposit, working_cap},
    'staff': {headcount, fot_net_med, fot_full_med},
    'financials': {check_med, traffic_med, cogs_pct, marketing_med, other_opex_med, rent_month},
    'scenarios': {pess: {...}, base: {...}, opt: {...}},
    'breakeven': {тб_₸, тб_чеков_день, запас_прочности_%},
    'payback': {месяц, статус},        # calc_payback, сейчас fallback
    'cashflow': [12 мес],
    'owner_economics': {...},
    'tax': {regime, rate_pct},
    # ── Отчётные блоки ──
    'block1': compute_block1_verdict(result),  # светофор
    'block2': compute_block2_passport(result),
    'block3': compute_block3_market(result),
    'block4': compute_block4_unit_economics(result),
    'block5': compute_block5_pnl(result),
    'block6': compute_block6_capital(result),
    'block_season': compute_block_season(result),
    'block8': compute_block8_stress_test(result),
    'block9': compute_block9_risks(result),
    'block10': compute_block10_next_steps(result),
}
```

После `render_report_v4` и `main.clean`:
- Старый API оставляет `block_1..10` (с underscore), новый — `block1..10` (без).
- `scenarios`, `capex`, `payback` остаются в `result`, но пути их вложены в блоки для UI.

При переписке: решить, хранить ли агрегаты на верхнем уровне или только внутри блоков.

## Приложение B. Файлы и lines, которые надо «похоронить» при переписке

- `calc_stress_test` (строки 848–892) — используется внутри `run_quick_check_v3` для `owner_economics`, но по сути дублирует `compute_block8_stress_test`. Оставить один.
- `compute_block7_scenarios` (строки 2402–2448) — мёртвый в Quick Check после Round 4. Вынести в `finmodel` модуль или удалить.
- `main_metrics` в `block1` (строки 1837–1847) — не рендерится после Round 4 bug#4. Удалить.
- Фолбэки `100_000` для маркетинга и other_opex в `compute_block5_pnl` / `compute_block8_stress_test` — заменить на единую валидационную ошибку.
- `base_profit_year` из scenarios в `compute_block8_stress_test` — заменить на `profit_mature_m × 12` (Шаг 3).

---

*Конец спецификации. Готов к продуктовому ревью. После утверждения части 2 и ответов на часть 7 — переписка расчётного блока движка как единой Python-модели по Шагам 1–10.*
