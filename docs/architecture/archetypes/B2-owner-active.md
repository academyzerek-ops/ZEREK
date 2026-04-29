# B2 — Владелец-наёмщик (активный)

**Владелец нанимает мастеров на оклад / оклад+%, сам не делает услуги клиентам.**

## Описание

Высокая step-up в управление: salary FOT — крупная статья расходов. Владелец отвечает за загрузку мастеров (если простой — он платит, мастер не теряет). Marketing — приоритет №1.

Состояние: **TBD — не в коде**. Концептуально описан.

## Формула (концепция)

```
N_masters       = headcount по штатке
master_capacity = check × clients × occupancy_rate × working_days   (на одного)
revenue_owner   = N_masters × master_capacity                       (вся выручка идёт через салон)

fot_total       = N_masters × (salary_base + premium_pct × master_capacity)
                                    ← оклад + % с выручки (опц.)
opex_owner      = rent_full_premise + marketing + materials + utilities + reception_fot + other_opex
                                    ← marketing обычно крупный, тк нужно загружать мастеров
tax             = revenue_owner × tax_rate (TOO 3% или 20% если ОУР)
pocket_owner    = revenue_owner − fot_total − opex_owner − tax
```

## Поля движка (TBD)

```yaml
formats_r12:
  - id: <FORMAT>
    archetype: B2_OWNER_ACTIVE
    n_masters_med / _min / _max: 5
    master_salary_base_med: NNNN          # оклад на мастера в месяц
    master_premium_pct: 0.0 | 0.20         # % от выручки мастера сверх оклада (если есть)
    employer_taxes_pct: 0.115              # 11.5% соц.налогов работодателя
    rent_full_premise_med: NNNN
    reception_fot_med: NNNN
    materials_owner_med: NNNN
    marketing_med: NNNN                     # обычно высокий
    master_capacity_check / clients / occupancy: ... (per-master productivity)
```

## Используется в

- **BEAUTY салон ACTIVE** (зонтичная beauty-ниша, режим 2 из 2)
- **BARBER SHOP_EMPLOY** — владелец нанимает барберов на оклад
- **COSMETOLOGY PREMIUM** — премиум-косметология с врачами-сотрудниками (отдельный under-archetype, см. CO1 если развернётся)

## Особенности

- **FOT — главная статья расходов**, обычно 40-55% revenue. Малая ошибка в загрузке мастеров → убыток.
- Маркетинг **обязательный**: если мастер простаивает, всё равно платится оклад.
- Налоги работодателя 11.5% (ОПВР 5% + СО 3.5% + ВОСМС 3%) — учитываются как `fot_full = fot_net × 1.115`.
- Налоговый режим: чаще TOO упрощёнка 3% (если оборот ≤ 600K МРП/год), или TOO ОУР 20% при превышении.

## Что НЕ надо ставить в B2

- Mode «найма за оклад как единственный путь» — это противоречит принципу #1 (не считаем зарплату работника). Здесь мы считаем экономику **владельца**, нанимающего мастеров.
- Mixing с B1 — если в одной точке часть мастеров на окладе, часть на %, нужно описать как **отдельный B2.5 архетип** или составной формат (TBD).

## Связь с экономикой мастера

В B2 расчёт мастера НЕ показывается через ZEREK — мастер тут не предприниматель, а наёмный работник (вне ЦА). Если мастер хочет «открыть свой бизнес» — это уже A1 или A2.
