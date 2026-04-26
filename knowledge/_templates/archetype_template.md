---
id: A0_TEMPLATE
name_rus: Название архетипа
description_short: Короткое описание (~1 строка)
format_options: [HOME, STANDARD, OTHER]

experience_levels:
  none:
    label: "Учусь / только начинаю"
    description_short: "Без опыта, открываю с нуля"
    minutes_per_client: 0
    peak_clients_per_day: 0
    avg_clients_per_day_mature: 0.0
    check_multiplier: 0.85
    training_capex: 0
    working_capital_multiplier: 1.00
    available_formats: []
    risk_note: "..."
  middle:
    label: "..."
    # ...
  experienced:
    label: "..."
    # ...

marketing_strategies:
  conservative:
    label: "Консервативная"
    description_short: "Расту медленно, минимум вложений"
    description_long: |
      ...
    budget_multiplier: 0.20
    ramp_speed: slow
    full_capacity_month: 11
    ramp_curve: [0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 1.00, 1.00]
  middle:
    label: "Средняя"
    budget_multiplier: 1.00
    ramp_speed: normal
    full_capacity_month: 4
    ramp_curve: [0.40, 0.65, 0.85, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00]
  aggressive:
    label: "Агрессивная"
    budget_multiplier: 1.40
    ramp_speed: fast
    full_capacity_month: 3
    ramp_curve: [0.55, 0.80, 0.95, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00]

antipatterns:
  novice_aggressive:
    trigger:
      experience: none
      strategy: aggressive
    severity: high
    block_title: "Предупреждение — антипаттерн"
    block_text: |
      ...

explanation_blocks:
  novice_lower_than_friends:
    trigger:
      experience: none
    page: 3
    block_title: "Почему ваша первая прибыль ниже чем у знакомых"
    block_text: |
      ...

strategy_explanations:
  conservative: |
    Что это значит на практике: ...
  middle: |
    ...
  aggressive: |
    ...
  warning_universal: |
    Важно: стратегия должна соответствовать вашему уровню как мастера. ...

history:
  - date: 2026-04-26
    change: создан файл
    by: Адиль
---

# Архетип A0 · Название

## Описание

Что объединяет ниши этого архетипа. Кто типичный предприниматель.

## Уровни опыта

(текстовое описание + что именно меняется при переходе уровня)

## Стратегии маркетинга

(когда какую выбирать, кому что подходит)

## Антипаттерны

(текстовое описание ловушек, ссылки на блоки антипаттернов)
