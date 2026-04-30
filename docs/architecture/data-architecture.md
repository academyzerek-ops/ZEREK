# Архитектура данных — три слоя

Описана в [CLAUDE.md § Ниши](../../CLAUDE.md#ниши--архитектура-данных-post-migration-2026-04-29). Резюме здесь:

## Слои

### 1. Registry (meta-индекс)

`data/kz/niches_registry.yaml` — **единственный источник правды** по списку и статусам ниш.

Поля записи: `code`, `name_ru`, `aliases`, `archetype`, `category`, `icon`, `status`, `cta`, флаги наличия артефактов (`has_*`) + пути (`*_path`), `notes`.

Статусы: `production_ready / wiki_only / research / idea`.

### 2. Business data (per niche)

`data/niches/<CODE>_data.yaml` — структурированные бизнес-данные ниши:
- `formats[]` — legacy R12.5 schema (поднимается xlsx FINANCIALS row)
- `formats_r12[]` — R12.6 канон (per-level overrides)
- `seasonality` — сезонные коэффициенты
- `risks`, `growth_scenarios`, `info_blocks_r12`, `upsells`, `action_plan`, `report_overrides`, `meta`

### 3. Engine calibration (xlsx) — ДВА файла на ниши

#### 3a. Per-niche xlsx
`data/kz/niches/niche_formats_<CODE>.xlsx` — runtime-cache движка для конкретной ниши. 14 листов: FORMATS, FINANCIALS, STAFF, CAPEX, GROWTH, TAXES, MARKET, LAUNCH, INSIGHTS, PRODUCTS, MARKETING, SUPPLIERS, SURVEY, LOCATIONS. Используется для финансовых расчётов внутри `/quick-check`.

#### 3b. Aggregate xlsx (общий для всех ниш)
`data/kz/08_niche_formats.xlsx` — **второй runtime-cache, читается отдельным endpoint'ом**. Содержит rows по format_id для каждой niche: format_name, area_m2, capex_standard, class, format_type, typical_staff, allowed_locations.

**Используется в endpoint `/formats-v2/<niche_id>`** (api/loaders/niche_loader.py::get_formats_v2). Это та анкета которую видит юзер в Mini App (`qc-v3.html`) при выборе формата. **Mini App не читает per-niche xlsx, только этот aggregate.**

**Производный от YAML.** При изменении YAML — синхронизируются **оба** xlsx (per-niche FINANCIALS + 08_niche_formats). Расхождение YAML vs xlsx = баг, чинится в пользу YAML. **Если калибрист обновил только per-niche xlsx, юзер всё равно увидит старые данные в анкете** (R14.2 урок: 30.04.2026 Адиль 3 раза присылал скриншот с устаревшими форматами потому что 08-файл не был синхронизирован).

### 4. Insight (текст)

`knowledge/kz/niches/<CODE>_insight.md` — текстовый материал для большинства ниш. Для R12.6 пилота (MANICURE): `knowledge/niches/<CODE>.md` (без `_insight` суффикса). **Без структурированных данных по форматам.**

## Loader merge

`api/loaders/niche_loader.py::load_niche_yaml(niche_id)` делает merge:
- база = `knowledge/niches/<CODE>.md` frontmatter (insight + meta)
- override = `data/niches/<CODE>_data.yaml` (structured data wins)

## Правило добавления / изменения

**Всегда сначала YAML, потом ручная синхронизация xlsx.** Никогда не вписывать бизнес-данные напрямую в xlsx минуя YAML — это создаёт рассинхрон.

## Engine override path (R12.5/R12.6)

`api/engine.py::_apply_r12_5_overrides(fin, niche_id, format_id, experience, strategy, level)` поднимает в `fin` поля из `data/niches/<CODE>_data.yaml.formats_r12[].levels.<level>`:
- `base_check_astana → fin['check_med']` (× experience.check_multiplier × city_check_coef)
- `avg_clients_per_day_mature → fin['traffic_med']` (× occupancy_rate)
- `working_days_per_month`, `cogs_pct`, `rent_per_month_astana`, `deposit_months`
- `commission_pct`, `materials_med/min/max`
- `marketing.{med,min,max}_monthly → fin['marketing_med/min/max']`
- `other_opex.{med,min,max}_monthly → fin['other_opex_med/min/max']`
- `strategy`, `r12_level` (для downstream сервисов)

**Приоритет:** `level_data` побеждает `target` (уровень над форматом).
