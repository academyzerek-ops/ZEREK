# Как добавить новую нишу через YAML

> Гайд для расширения каталога ниш ZEREK Quick Check.
> Опирается на YAML-first архитектуру из Этапа 7 рефакторинга.
>
> **Время:** 30-60 мин на нишу (зависит от готовности данных).

---

## Шаги (TL;DR)

1. Скопировать `data/niches/MANICURE_data.yaml` → `data/niches/{NICHE}_data.yaml`.
2. Заполнить поля для всех форматов ниши.
3. Прописать ниши в `data/kz/niches_registry.yaml` (поле `status: production_ready` или `wiki_only`).
4. Обновить `niche_loader.overlay_yaml_on_xlsx`: добавить niche_id в whitelist.
5. Прогон через API: `/quick-check` с новым `niche_id`.

Регрессия 4/4 baseline должна остаться 4/4 (новая ниша не в baseline).

---

## Шаг 1. Скопировать YAML-шаблон

```bash
cp data/niches/MANICURE_data.yaml data/niches/BARBER_data.yaml
```

`MANICURE_data.yaml` — единственный полностью заполненный YAML на момент Этапа 8. Используй его как образец.

---

## Шаг 2. Заполнить поля

Структура YAML (см. полный пример в `MANICURE_data.yaml`):

```yaml
niche:
  id: BARBER                    # совпадает с именем файла без _data.yaml
  name_ru: "Барбершоп"
  industry: beauty              # для группировки в UI
  trend: stable                 # growing | stable | declining

seasonality:
  pattern: [...12 коэф...]      # помесячные коэффициенты, среднее ≈ 1.0
  best_start_months: [3, 4, 5]
  worst_start_months: [10, 11, 12]

formats:
  - id: HOME                    # короткий ID (full = BARBER_HOME)
    label_ru: "Барбер на дому"
    archetype: solo             # solo | owner_works | with_staff
    legal_form: ip              # ip | too
    needs_location: false       # требуется ли аренда

    avg_check:
      min: 2500
      med: 3500
      max: 5000

    traffic:
      max_per_day: 8            # физ. максимум 1 мастера
      load_med: 0.55            # реалистичная загрузка (после ramp)
      load_min: 0.30
      load_max: 0.80
      working_days_per_month: 26

    capex:
      base_total: 250000        # сумма всех items.med
      items:
        equipment: { label_ru: "Оборудование", med: 100000 }
        furniture: { label_ru: "Мебель", med: 30000 }
        first_stock: { label_ru: "Первичные материалы", med: 40000 }
        permits: { label_ru: "Разрешения", med: 5000 }
        working_capital: { label_ru: "Оборотные средства", med: 50000 }
        marketing_start: { label_ru: "Стартовый маркетинг", med: 20000 }
        legal: { label_ru: "Юр. оформление", med: 5000 }
      training:
        required: true          # критично для барберов?
        amounts_by_experience:
          none: 100000          # обучение с нуля
          some: 30000           # подтянуть слабые техники
          pro: 0                # уже профи

    ramp_up:
      months: 3
      start_pct: 0.30

    marketing:
      med_monthly: 35000
      min_monthly: 20000
      max_monthly: 60000

    other_opex:
      med_monthly: 5000

    fot:
      monthly: 0                # ИП = нет ФОТ
      headcount: 0

    cogs_pct: 0.10              # материалы как % от выручки

    tax_regime:
      type: ip_simplified
      rate_pct: 3.0

    risks_format_specific:      # ID рисков из секции risks ниже
      - id: physical_health
      - id: income_ceiling_solo

  # — повторить блок formats для SOLO/STANDARD/PREMIUM —

risks:
  - id: physical_health         # уникальный ID риска
    title_ru: "Зависимость от физсостояния"
    body_ru: "..."
    probability: medium         # low | medium | high
    impact: high                # low | medium | high
    what_to_do_ru: "..."
  # — добавить остальные risks —

upsells:
  - name_ru: "Стрижка бороды"
    avg_addition: 1500
    take_rate: 0.40
    margin_pct: 0.85
```

### Где взять числа

- **avg_check, cogs_pct, marketing**: wiki-обзор ниши (`wiki/kz/{NICHE}.html`).
- **traffic.max_per_day**: физический предел одного мастера (см. wiki, инсайты).
- **capex**: ресерч цен март 2026, кейсы из YouTube.
- **fot, headcount**: 08_niche_formats.xlsx (если уже откалибровано) или ресерч.
- **ramp_up**: 3 мес для услуг, 5-6 мес для retail/общепита.
- **seasonality**: 14_niches.xlsx или экспертная оценка.

---

## Шаг 3. Включить нишу в `data/kz/niches_registry.yaml`

```yaml
niches:
  - code: BARBER
    name_ru: "Барбершоп"
    aliases: []
    archetype: "A"             # A=услуги, B=общепит, C=retail, D=абонементы, E=проектный, F=мощность
    category: "beauty"
    icon: "💈"
    status: production_ready   # production_ready | wiki_only | research — определяет видимость в /niches
    cta: quick_check
    has_insight: true
    has_data: true
    has_calibration: true
    has_wiki: true
    insight_path: "knowledge/kz/niches/BARBER_insight.md"
    data_path: "data/niches/BARBER_data.yaml"
    calibration_path: "data/kz/niches/niche_formats_BARBER.xlsx"
    wiki_path: "wiki/kz/ZEREK_Barber.html"
    notes: ""
```

---

## Шаг 4. Подключить YAML overlay для ниши

Открой `api/loaders/niche_loader.py`, найди:

```python
def overlay_yaml_on_xlsx(xlsx_row, niche_id, sheet, format_id, cls=None):
    if niche_id != "MANICURE":
        return xlsx_row
    if format_id in _YAML_SKIP_FORMATS:
        return xlsx_row
```

Замени условие на whitelist нескольких ниш:

```python
_YAML_NICHES = {"MANICURE", "BARBER"}  # ← добавь сюда

def overlay_yaml_on_xlsx(xlsx_row, niche_id, sheet, format_id, cls=None):
    if niche_id not in _YAML_NICHES:
        return xlsx_row
    # MANICURE_HOME — единственный формат с xlsx-канон baseline.
    # Для других ниш xlsx может быть пустым — YAML всё перезапишет.
    if format_id in _YAML_SKIP_FORMATS:
        return xlsx_row
    ...
```

Если у новой ниши есть откалиброванный xlsx-формат, который НЕ должен переписываться YAML (как MANICURE_HOME), добавь его в `_YAML_SKIP_FORMATS`.

---

## Шаг 5. Прогон через API

```bash
# 1. Проверить что ниша появилась в каталоге
curl https://web-production-921a5.up.railway.app/niches | jq '.niches[] | select(.niche_id == "BARBER")'

# 2. Прогнать /quick-check
curl -X POST https://web-production-921a5.up.railway.app/quick-check \
  -H "Content-Type: application/json" \
  -d '{
    "city_id": "almaty",
    "niche_id": "BARBER",
    "format_id": "BARBER_HOME",
    "capex_level": "стандарт",
    "loc_type": "home",
    "capital": 300000,
    "start_month": 5,
    "specific_answers": {"experience": "some", "entrepreneur_role": "owner_plus_master"}
  }' | jq '.result.block1'
```

Ожидание: `color in ('green'|'yellow'|'red')`, `score`, `strengths`, `risks`.

---

## Шаг 6. Регрессия

Прогнать локальную регрессию — должна остаться 4/4:

```bash
python3 tests/local/regress.py
```

Если новая ниша случайно сломала baseline (например, попала в скоринг или фильтры) — откат YAML overlay для этой ниши, расследовать.

---

## Шаг 7. (Опционально) Добавить integration-тест

```python
# tests/integration/test_quick_check.py
def test_barber_home_pipeline():
    req = _make_req(
        niche_id="BARBER", format_id="BARBER_HOME",
        capital=300_000, loc_type="home",
        specific_answers={"experience": "some", "entrepreneur_role": "owner_plus_master"},
    )
    calc = QuickCheckCalculator(_db)
    report = calc.run(req)
    assert "block1" in report
    assert report["block1"]["color"] in ("green", "yellow", "red")
```

---

## Шаг 8. Опубликовать

После успеха через локальную регрессию:

```bash
git add data/niches/BARBER_data.yaml data/kz/niches_registry.yaml api/loaders/niche_loader.py tests/integration/test_quick_check.py
git commit -m "feat(niche): add BARBER YAML data + enable for Quick Check"
git push origin claude/...
# → PR в main → Railway деплой
```

---

## Контракт обязательных полей YAML

Минимальный набор для расчёта Quick Check:

| YAML путь | xlsx эквивалент | Зачем |
|---|---|---|
| `formats[].id` | `format_id` (берётся как `{NICHE}_{id}`) | Идентификация формата |
| `formats[].avg_check.med` | `check_med` | Средний чек |
| `formats[].traffic.max_per_day` × `load_med` | `traffic_med` | Реалистичная загрузка |
| `formats[].cogs_pct` | `cogs_pct` | Материалы как % от выручки |
| `formats[].marketing.med_monthly` | `marketing_med` | Месячный маркетинг бюджет |
| `formats[].other_opex.med_monthly` | `other_opex_med` | Прочие OPEX |
| `formats[].ramp_up.months` | `rampup_months` | Месяцев на разгон |
| `formats[].ramp_up.start_pct` | `rampup_start_pct` | С какого % старт |
| `formats[].fot.monthly` | `fot_full_med` (через ×1.115) | Брутто ФОТ |
| `formats[].fot.headcount` | `headcount` | Размер штата |
| `formats[].capex.base_total` | `capex_med` | Сумма стартовых вложений |
| `formats[].tax_regime.type` | `tax_regime` (Упрощёнка ИП/ТОО или ОУР) | Налоговая модель |
| `seasonality.pattern` (12 чисел) | s01..s12 | Сезонные коэффициенты |

Опциональные:
- `formats[].capex.items.training.amounts_by_experience` — обучение
- `formats[].rent.area_m2` — для расчёта аренды через rent_loader
- `risks[]` — список рисков (используется в Block 9 после YAML risks integration в Этапе 9+)
