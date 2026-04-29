# A2 — Мастер за % в чужой структуре

**Мастер работает в чужом салоне / спа / фитнес-клубе, отдаёт долю выручки владельцу площадки.**

## Описание

Подвид A1 с фиксированным `commission_pct > 0`. Мастер не платит аренду места — вместо этого делится выручкой. Маркетинг минимален (часть бренд-маркетинга делает площадка). Своих расходников меньше (часть базовых даёт салон) — но не всех.

Состояние: **в коде через A1 + commission_pct**. Реализован как режим A1 в MANICURE SALON_RENT.

## Формула

Та же что A1, но:
- `commission_pct = 0.30 ... 0.60` (типично 0.50)
- `rent_per_month_astana = 0`
- `deposit_months = 0`
- `marketing` ниже чем для своей точки (площадка делает базу)

```
revenue_brutto = check × clients × occupancy_rate × working_days
revenue_net    = revenue_brutto × (1 − commission_pct)        ← основная разница с A1
materials      = materials_med (свои расходники)
opex           = marketing + other_opex + materials            ← rent = 0
tax            = revenue_net × tax_rate
pocket         = revenue_net − opex − tax − social_payments
```

## Поля движка

Те же что A1. Ключевые:
- `commission_pct` — 0.30 (демпинговый), 0.40 (стандарт), 0.50 (Астана/Алматы топ-салон), 0.60 (премиум-бренд) — диапазон по реальной КЗ-практике.
- `marketing` — обычно меньше A1 «своя точка»: ~50% от уровня STUDIO с тем же чеком.

## Используется в

- **MANICURE SALON_RENT** standard (commission=0.5, чек 7500)
- **MANICURE SALON_RENT** premium (commission=0.5, чек 9500)
- **BARBER SALON_RENT** — план: барбер арендует место в чужом барбершопе (TBD calibration, commission_pct TBD)
- **MASSAGE RENT_FITNESS** — план: массажист в фитнес-клубе/спа (TBD, commission_pct TBD)
- **BROW SALON_RENT** — план: бровист в чужом салоне (TBD)
- **EMPLOYED_SPA** для MASSAGE — Адиль уточнит, наёмный за оклад исключается принципом #1, либо это commission-модель.

## Особенности

- `commission_pct` фиксируется для всего расчёта (не зависит от experience). Влияет на pocket пропорционально.
- Tax считается от `revenue_net` (master's actual income) — не от brutto. Это ключевая разница с trivial commission-as-expense интерпретацией.
- Налоговый режим обычно `samozanyaty` (1% СЗ) — поскольку оборот мастера ≤ 12K МРП/год = ~52M ₸.

## Чего нет

- Найма за оклад. Это нарушает принцип #1.
- Своей аренды помещения (это уже A1 STUDIO, не A2).
