# Движок ZEREK — поля и формулы

## Финансовая формула (post-migration 2026-04-30)

```
revenue_brutto = check × clients × occupancy_rate × working_days
revenue_net    = revenue_brutto × (1 − commission_pct)
materials      = materials_med  (R12.6 канон)  ИЛИ  revenue × cogs_pct  (legacy)
opex           = rent + marketing + other_opex + materials
tax            = revenue_net × tax_rate
pocket         = revenue_net − opex − tax − social_payments
```

`pocket` = `result.owner_economics.net_in_pocket` = `result.owner_economics.mature_pocket` (alias).

## Year-1 aggregates

В `result.owner_economics`:
- `mature_pocket` — pocket в зрелый месяц (М6+, без ramp/seasonality)
- `ramp_up_avg` — средний месячный pocket за первый год (с ramp curve + сезонностью)
- `year1_total_net` — суммарный годовой net (= ramp_up_avg × 12 ± округление)

Месячные значения с ramp/season: `result.block_5.first_year_chart.months[]`.

## Поля движка (fin row)

Поднимаются из xlsx FINANCIALS + перезаписываются engine-override через formats_r12.

| Поле | Источник | Описание |
|---|---|---|
| `check_med` | xlsx + R12.5 override | Средний чек (₸). Engine применяет `× experience.check_multiplier × city_check_coef`. |
| `traffic_med` | xlsx + R12.5 override | Клиентов/день (mature). После override = `avg_clients × occupancy_rate`. |
| `working_days_per_month` | xlsx fallback 30 + R12.5 override | Рабочих дней/мес. |
| `cogs_pct` | xlsx (legacy) | % materials от revenue. Используется только если `materials_med = 0`. |
| `materials_med` / `_min` / `_max` | xlsx + R12.6 override | **Абсолютное** значение материалов (₸/мес). R12.6 канон. |
| `marketing` | xlsx (legacy) | Старая single-column marketing. Fallback если `marketing_med = 0`. |
| `marketing_med` / `_min` / `_max` | xlsx + R12.6 override | Маркетинг бюджет (₸/мес). |
| `other_opex_med` / `_min` / `_max` | xlsx + R12.6 override | Прочие OPEX консолидированно (₸/мес). R12.6 канон. |
| `consumables`, `software`, `transport`, `sez_month` | xlsx (legacy) | Старая разбивка other_opex. Используется только если `other_opex_med = 0`. |
| `rent_med` | xlsx + R12.5 override | Аренда помещения (₸/мес). |
| `deposit_months` | xlsx + R12.5 override | Депозит = rent_med × deposit_months. |
| `commission_pct` | R12.6 override | Доля выручки, уходящая владельцу площадки/салона. 0.0 для своей точки, 0.50 для аренды места. |
| `strategy`, `r12_level` | engine + override | conservative / middle / aggressive (маркетинг); simple/nice/standard/premium (формат-уровень). |
| `s01..s12` | xlsx + knowledge md | 12 коэф. сезонности (multipliers от среднего). |
| `rampup_months`, `rampup_start_pct` | xlsx | Длительность разгона + старт-доля. |

## Архетип A1 (master-solo) — мультипликаторы опыта

Из `knowledge/archetypes/A1_BEAUTY_SOLO.md`:

| experience | check_multiplier | avg_clients_per_day_mature |
|---|---|---|
| `none` | 0.85 | 3 |
| `middle` | 1.00 | 4.5 |
| `experienced` | 1.20 | 5.5 |

Применяется если `formats_r12.<format>.archetype == 'A1_BEAUTY_SOLO'` (в практике — все beauty-соло форматы).

## City check coefficient

`config/constants.yaml` cities[]: `check_coef`. Для Астаны/Алматы ~ 1.05, для регионов 0.85-1.0. Применяется к `check_med` после experience multiplier.

## Code paths

| Слой | Файл | Роль |
|---|---|---|
| Loader | `api/loaders/niche_loader.py::load_niche_yaml` | merge knowledge md + data yaml |
| Override | `api/engine.py::_apply_r12_5_overrides` | поля fin из formats_r12 |
| Mature P&L | `api/services/economics_service.py::calc_owner_economics` | главная P&L функция |
| Mature aggregates | `api/services/economics_service.py::compute_pnl_aggregates` | mature monthly + yearly avg |
| Month-by-month | `api/services/economics_service.py::simulate_calendar_pnl` | B5 P&L, 12 мес с ramp+season |
| Year-1 aggregates | `api/calculators/quick_check.py` (после danger_zone) | ramp_up_avg + year1_total_net |
| Breakeven | `api/services/economics_service.py::calc_breakeven` | Тб + запас прочности |

## Tax regime

`fin.tax_rate` приходит из `data/niches/<CODE>_data.yaml.formats[].tax_regime.rate_pct`. Стандартные:
- `ip_simplified` — 3% УСН (большинство beauty-соло, общепит, услуги)
- `samozanyaty` — 1% (HOME-форматы, низкий оборот)
- `too_simplified` — 3% (TOO с упрощёнкой)
- `too_oer` — 20% (TOO с общеустановленным режимом)

Подробнее по налогам — [knowledge/taxes/KZ_2026.md](../../knowledge/taxes/KZ_2026.md).
