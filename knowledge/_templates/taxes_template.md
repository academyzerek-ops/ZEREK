---
year: 2026
country: KZ

mrp: 0                       # Месячный расчётный показатель, ₸
mzp: 0                       # Минимальная зарплата, ₸
subsistence_min: 0           # Прожиточный минимум, ₸
nds_rate_pct: 16             # НДС, %
nds_threshold_kzt: 0         # Порог обязательной регистрации НДС, ₸/год

ud_default_rate_pct: 4       # Базовая ставка УД (УСН) до маслихата
ud_limit_kzt: 0              # Лимит УД, ₸/год (= 600 000 МРП)

ud_rates_by_city:
  astana: 3
  almaty: 3
  shymkent: 2
  # ... остальные города

ip_minimum_taxes_per_month_kzt: 21675   # ОПВ + ВОСМС + ИПН за нулевой доход
ip_minimum_taxes_per_year_kzt: 260100

payroll_taxes:
  opv_pct: 10
  opvr_pct: 3.5
  vosms_pct: 2
  oosms_pct: 3
  so_pct: 5
  ipn_base_pct: 10
  ipn_progressive_threshold_mrp: 8500
  kpn_pct: 20

tax_regimes:
  - id: UD
    name_rus: Упрощённая декларация (УД)
    rate_pct: 4
    nds_payer: false
    limit_kzt: 0
    notes: |
      Базовая ставка 4%, маслихат может опустить до 2% или поднять до 6%.
  - id: SELF
    name_rus: Самозанятый
    rate_pct: 4
    nds_payer: false
    limit_kzt: 1470500
    notes: |
      Лимит 340 МРП/мес. Заменил патент с 01.01.2026.
  - id: OUR
    name_rus: Общеустановленный режим (ОУР)
    rate_pct: 20
    nds_payer: true
    limit_kzt: 0
    notes: |
      КПН 20% / ИПН прогрессивный 10-15%. НДС 16%.
  - id: KFH
    name_rus: СНР для КФХ
    rate_pct: 0
    nds_payer: false
    limit_kzt: 0
    notes: |
      Только сельхозпроизводители.

history:
  - date: 2026-04-26
    change: создан файл
    by: Адиль
---

# Налоги Казахстан YYYY

## Ключевые изменения года

Что важно — что изменилось vs предыдущий год.

## ИП на УД

Как считаются обязательные платежи для ИП.

## Порог НДС

Когда нужно регистрироваться по НДС.

## Замечания

Особенности — патент отменён, B2B нюансы, региональные ставки.
