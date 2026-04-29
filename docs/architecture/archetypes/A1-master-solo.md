# A1 — Мастер-одиночка

**Самозанятый или ИП-одиночка, всё делает сам, никого не нанимает.**

## Описание

Один мастер = одна точка дохода. Ограничитель — время мастера и его пропускная способность за рабочий день. Нет ФОТ, нет наёмного штата.

Состояние: **в коде, рабочий**. Реализован для MANICURE (R12.5/R12.6 пилот).

## Формула

```
revenue_brutto = check × clients × occupancy_rate × working_days
revenue_net    = revenue_brutto × (1 − commission_pct)   ← если работа в чужой структуре
materials      = materials_med  (R12.6)  ИЛИ  revenue × cogs_pct  (legacy)
opex           = rent + marketing + other_opex + materials
tax            = revenue_net × tax_rate
pocket         = revenue_net − opex − tax − social_payments
```

## Поля движка (formats_r12 канон)

```yaml
formats_r12:
  - id: <FORMAT>
    archetype: A1_BEAUTY_SOLO
    available_experience: ['none', 'middle', 'experienced']  # подмножество
    available_for_levels: false  # или true с levels:{...}
    base_check: {astana: NNNN}              # базовый чек для Астаны
    working_days_per_month: 22 | 26 | 28
    occupancy_rate: 0.85                    # реалистичная загрузка (0.0–1.0)
    cogs_pct: 0.0                           # если materials_med задан абсолютом
    rent_per_month_astana: NNNN | 0
    deposit_months: 0 | 2
    commission_pct: 0.0 | 0.50              # 0.5 для аренды места в чужом салоне
    materials_med / _min / _max: NNNN       # ± 55% / 155% от med
    marketing:    {med_monthly, min_monthly, max_monthly}
    other_opex:   {med_monthly, min_monthly, max_monthly}
```

Для форматов с уровнями (`available_for_levels: true`) — те же поля **внутри** `levels.<lvl>`. Уровень побеждает target (см. `_apply_r12_5_overrides`).

## Множители опыта (knowledge/archetypes/A1_BEAUTY_SOLO.md)

| experience | check_multiplier | avg_clients_per_day_mature |
|---|---|---|
| `none` | 0.85 | 3 |
| `middle` | 1.00 | 4.5 |
| `experienced` | 1.20 | 5.5 |

Engine:
- `fin['check_med'] = base_check_astana × check_multiplier × city_check_coef`
- `fin['traffic_med'] = round(avg_clients × occupancy_rate)`

## Используется в

- **MANICURE** — все 4 формата (HOME / STUDIO simple+nice / SALON_RENT std+prem / MALL_SOLO). SALON_RENT использует A1 + `commission_pct=0.5`.
- **BROW** — план: HOME / STUDIO simple+nice / SALON_RENT (TBD калибровка)
- **SUGARING** — план: HOME / STUDIO simple+nice (TBD)
- **MASSAGE** — план: HOME / OWN_OFFICE (часть форматов; RENT_FITNESS использует A2)
- **BARBER** — мастер: STUDIO simple+nice+mall + SALON_RENT (TBD)

## Особенности

- `occupancy_rate` — opt-in, default 1.0. Для beauty-соло реалистичный потолок = 0.85 (бронирования никогда на 100%).
- HOME форматы: working_days=22 (соло-мастер дома работает реже), остальные 26 (без выходных в beauty).
- Для SALON_RENT (аренда места) `commission_pct=0.5` означает что 50% revenue уходит салону, остальное — мастеру. `rent_per_month=0` (плата = комиссия).

## Чего нет в архетипе

- `fot_*` — мастер-одиночка не на найме, нет з/п.
- `headcount` — всегда 0 или 1 (= сам мастер, не штат).
- Multi-master logic — это **не A1**. См. B1/B2.
