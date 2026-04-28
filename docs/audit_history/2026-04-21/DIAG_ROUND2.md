# DIAG_ROUND2 — Quick Check 7 багов, диагностика

Запрос: `BARBER/BARBER_STANDARD/aktobe/capital=null/entrepreneur_role=owner_plus_master/experience=some/payroll_type=piece`.

## Текущий вывод движка

| Метрика | Текущее | Целевое |
|---|---|---|
| revenue/мес (base) | 1 201 650 (из owner_eco.revenue 1.26M) | 2.5–3.5 млн |
| revenue range block1 | 811 тыс–1.2 млн | 2.0–2.9 млн |
| profit/мес (base из PNL) | 508 002 | 500–900 тыс |
| annual_roi (block5) | 6.09 = **609%** | 30–60% |
| total_investment (block5) | 1 000 000 | ≈8 660 000 (7.5M capex + deposit + working) |
| payback (block1) | 3 мес (base) | 11–15 мес |
| entrepreneur_income_range | 550 тыс–886 тыс | 400–700 тыс (меньше profit) |
| capital_score | 1/3 «клиент не указал» | 2/3 «не указан, нейтрально» |
| saturation_score | 2/3 «нет данных» | зависит от density 0.9 vs 0.75 бенчмарк ≈ 1.2 → 1/3 «перенасыщен» |
| marketing_score | 1/2 «в экспресс не спрашиваем» | 2/2 |

## По каждому багу — куда смотреть

### #1 CAPEX бенчмарк не читается
- `engine.py:1473` — `capex_needed = _safe_int(capex_block.get('capex_med')) or _safe_int(capex_block.get('capex_total'))`
- `capex_block.capex_med = 1 000 000` (из per-niche CAPEX.capex_med для первой строки, 2-барбера) — НЕ из `08_niche_formats.xlsx.capex_standard=7 500 000`.
- Также `_score_capital` с `capital_own=0` → ветка «не указал» даёт 1 балл вместо 2. Нужно 2.
- Fix: передать в `_score_capital` capex_standard из 08 как фолбэк приоритетом. Ветка `capital_own is None` → 2 балла.

### #2 ROI с неправильным знаменателем
- `engine.py:2297-2307` в `compute_block5_pnl`: `total_investment = capital_own or capex_med or capex_total` — при capital=None даёт 1M. annual_roi = 6M/1M = 6.09 = 609%.
- Fix: `total_investment = capital_own or capex_standard_from_08 or capex_med` с приоритетом 08. Также sanity-cap.

### #3 Окупаемость по неверной формуле
- `engine.py:603-613` `calc_payback(capex_total, cashflow)`. capex_total=1.16M (1M capex + 160K deposit). net_profit~646K/mo → 1.8 мес. Округлено до 3 (из cumulative CF).
- Fix: `capex_total` должен считаться через 08 `capex_standard` (7.5M) + deposit + working_cap. Тогда 8.5M / 646K = 13 мес.

### #4 Насыщенность рынка не читается
- `engine.py:1338-1354` `_score_saturation(competitors_count, city_pop, niche_id)`: считает density как `competitors_count/(city_pop/10000)`. 
- `engine.py:1477` `city_pop = _safe_int(inp.get('city_population'), 0)` — но `inp` содержит только `city_id/city_name`, не `city_population`. → city_pop=0 → возвращает "Нет данных о конкурентах".
- При этом данные есть: `result.market.competitors.density_per_10k=0.9`, `competitors_count=55`. Нужно использовать готовый `density_per_10k`.
- Fix: в `_score_saturation` принимать density напрямую и/или читать `competitors_count/(market.population/10000)`, а также передавать сам density_per_10k.

### #5 Маркетинговый бюджет всегда штрафует
- `engine.py:1364-1366` `_score_marketing` возвращает 1/2.
- Fix: вернуть 2/2 с note «параметр оценивается в FinModel». max=2 остаётся.

### #6 Доход предпринимателя > прибыли
- `engine.py:2308-2330` блок5 считает `entrepreneur_income = profit_monthly + role_salary` где `profit_monthly = pnl_base.net_profit/12 = 508K` и `role_salary = fot_monthly/headcount = 3.38M/12/2 = 141K` → total 649K.
- НО: `fot_monthly` в pnl уже включает зарплаты ВСЕХ мастеров (2 × 282K = **564K**, ×12=6.77M, но в pnl fot=3.38M/год **странно мало**… на самом деле 282K/мес × 12 = 3.38M/год. Т.е. headcount=2 × salary~120K только).
- При `entrepreneur_role=owner_plus_master` владелец закрывает 1 позицию → из FOT должно быть вычтено 1 оклад. Сейчас это не делается в pnl_base (работает только старый `founder_works` через `staff_adjusted`).
- Fix: при `entrepreneur_role != owner_only` в `compute_block5_pnl` уменьшать fot на role_salary перед расчётом pnl.
- Также: `role_salary_monthly` сейчас = `fot_monthly/headcount` — это среднее, а надо ставку той роли, которую закрывает владелец. Для простоты берём `fot_full_med/headcount` из staff.
- block1 `ent_income_base = prof_base + role_salary` (строка 1535): `role_salary = fot_med` (весь ФОТ). Это и есть бага — используется весь ФОТ вместо одной ставки!
  - `engine.py:1533-1534`: `fot_med = staff.fot_net_med=240K`, и `role_salary = fot_med` → 240K. profit_base_monthly=646K → total=886K. Это верхняя граница диапазона.
  - profit_pess_monthly=310K → 550K.
  - Но profit_range=310-646K. Entrepreneur income > profit потому что role_salary прибавляется к profit, а profit уже посчитан с полным FOT.
- Правильный fix block1: `role_salary = fot_net_med / headcount` (одна ставка). И вычесть её из profit тоже.

### #7 Выручка занижена (qty_points не учитывается)
- `engine.py:479-499` `calc_revenue_monthly`: `base_rev = check * traffic * 30`. Без qty_points/seats.
- В per-niche FORMATS: `seats_min=2, seats_max=3, qty_points=1`. В FINANCIALS для BARBER_STANDARD две строки: первая (2 кресла, traffic=12, rent=80K), вторая (3 кресла, traffic=15, rent=120K). `get_format_row` всегда берёт **первую**.
- При этом 08_niche_formats: `typical_staff='барбер:4|администратор:1'` — это эталон «4 барбера».
- Fix: `calc_revenue_monthly` умножать на `qty_points` ИЛИ на `seats_max` из FORMATS. Но данные qty_points=1. Альтернатива: использовать masters_count из `08.typical_staff` как множитель.
- Предлагаемый подход: в `run_quick_check_v3` читать `format_meta.qty_points` (если >1 → использовать); фолбэк — masters_count из 08 `typical_staff`.

## Новые риски (без правок)
- Per-niche BARBER FINANCIALS имеет 2 строки для STANDARD → движок всегда берёт первую (2-кресла). Не трогаем xlsx, но это причина занижения. Лечим через qty_points/masters_count.

## Что НЕ баг но подозрительно
- В `_score_capital` нет ветки «capital_own is None» — только `if not capital_own` что true и для 0 и для None. Нужно отличать.
- `staff.fot_net_med=240K` при `headcount=2` — значит 120K/барбер/мес. Это очень низко для Актобе. Спека по #6 даёт ставку 200K. Но данные xlsx неприкосновенны.
