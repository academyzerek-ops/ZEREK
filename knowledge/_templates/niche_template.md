---
id: NICHE_ID
name_rus: Название ниши
icon: 📋
archetype: A1_BEAUTY_SOLO     # ссылка на knowledge/archetypes/A1_BEAUTY_SOLO.md
available: true                # false = скрыть из списка ниш в Mini App

seasonality:
  s01: 1.00     # январь
  s02: 1.00     # февраль
  s03: 1.00     # март
  s04: 1.00
  s05: 1.00
  s06: 1.00
  s07: 1.00
  s08: 1.00
  s09: 1.00
  s10: 1.00
  s11: 1.00
  s12: 1.00     # декабрь

formats:
  HOME:
    label_rus: Мастер на дому
    description_short: Соло-мастер работает у себя дома, без аренды
    available_for_experience: [none]
    base_check_astana: 0
    rent_per_month_astana: 0
    deposit_months: 0
    working_days_per_month: 22
    utilities_per_month: 0
    other_opex_per_month: 0
    cogs_pct: 0.10
    tax_regime_id: UD
    capex_items:
      equipment: 0
      furniture: 0
      first_stock: 0
      permits: 0
      working_capital: 0
      marketing_start: 0
      legal: 0
    capex_base_total: 0      # сумма capex_items без обучения и без депозита
    marketing_phases:
      ramp_m1_m3: 0
      tuning_m4_m6: 0
      mature_m7_m12: 0

  STUDIO:
    label_rus: Свой кабинет
    available_for_experience: [middle, experienced]
    working_days_per_month: 22
    rent_per_month_astana: 0
    deposit_months: 2
    utilities_per_month: 0
    other_opex_per_month: 0
    cogs_pct: 0.10
    tax_regime_id: UD
    capex_items:
      equipment: 0
      furniture: 0
      renovation: 0
      first_stock: 0
      permits: 0
      working_capital: 0
      marketing_start: 0
      legal: 0
    capex_base_total: 0
    marketing_phases:
      ramp_m1_m3: 0
      tuning_m4_m6: 0
      mature_m7_m12: 0
    levels:
      simple:
        label_rus: Простой кабинет
        description_short: Базовое оборудование, минимальный ремонт
        base_check_astana: 0
        capex_extras: {}        # дельта к капексу
      nice:
        label_rus: Приличный кабинет
        description_short: Дизайн, качественная мебель
        base_check_astana: 0
        capex_extras:
          furniture: 100000
          renovation: 130000
          marketing_start: 30000

risks_table:
  - id: rent_dependency
    label_rus: Зависимость от арендодателя
    probability: средняя
    impact: высокое
    what_to_do: фиксировать ставку на 1+ год, контракт письменный
    applies_to_formats: [STUDIO, SALON_RENT]
  # ... 3-5 рисков для ниши

growth_scenarios:
  stagnation:
    label: "Сценарий 1 — стагнация"
    description: "..."
    outcome_year3: "..."
  development:
    label: "Сценарий 2 — развитие"
    description: "..."
    outcome_year3: "..."
  expansion:
    label: "Сценарий 3 — рост"
    description: "..."
    outcome_year3: "..."

history:
  - date: 2026-04-26
    change: создан файл
    by: Адиль
---

# Ниша

## О нише

Краткое описание — кто типичный клиент, как формируется выручка, специфика.

## Сезонность

Когда пики, когда просадки, особенности (8 марта, школьные выпускные, праздники).

## Информационные блоки PDF

### Про материалы (стр. 7)

> Какой текст пойдёт в info_block о материалах в PDF (для STUDIO/SALON_RENT/MALL_SOLO).

### Две модели аренды (стр. 11, для SALON_RENT)

> Текст про фикс vs процент.

## Реальные кейсы

(Заполняется со временем по мере наблюдений Адиля)

## Замечания

Прочее — что заметили в реальных Quick Check, идеи для калибровки.
