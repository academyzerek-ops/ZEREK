# ZEREK — архитектурная документация

> **Источник правды по структуре проекта.** Перед калибровкой / расширением любой ниши читай файлы этой папки. Не переспрашивай Адиля по тому что уже описано — оно тут.

См. также: [CLAUDE.md](../../CLAUDE.md) (общие правила репо), [data/kz/niches_registry.yaml](../../data/kz/niches_registry.yaml) (единый реестр ниш).

---

## Структура

### Корневые файлы

| Файл | Что описывает |
|---|---|
| [principles.md](principles.md) | 6 общих правил (ЦА, фильтры, тон). Применяются ко всем нишам. |
| [data-architecture.md](data-architecture.md) | Три слоя данных (registry / yaml / xlsx) + loader merge + engine override path. |
| [engine.md](engine.md) | Финансовая формула, поля fin row, multipliers, code path map. |

### Архетипы расчёта — [archetypes/](archetypes/)

| Архетип | Описание | Состояние |
|---|---|---|
| [A1 — Мастер-одиночка](archetypes/A1-master-solo.md) | Соло, без найма | ✓ в коде (MANICURE pilot) |
| [A2 — Мастер за %](archetypes/A2-master-rent-out.md) | В чужой структуре, commission_pct>0 | ✓ в коде (через A1) |
| [B1 — Владелец-сдатчик](archetypes/B1-owner-passive.md) | Пассивная сдача мест за % или фикс | ⚠ TBD — engine extension |
| [B2 — Владелец-наёмщик](archetypes/B2-owner-active.md) | Активный найм мастеров на оклад | ⚠ TBD — engine extension |

### Категории ниш — [categories/](categories/)

| Категория | Прогресс калибровки | Файл |
|---|---|---|
| **Beauty** | 1/7 (MANICURE ✓; BROW/SUGARING/MASSAGE/COSMETOLOGY/BARBER/BEAUTY салон — TBD) | [BEAUTY.md](categories/BEAUTY.md) |
| Food | 0/N (TBD) | [FOOD.md](categories/FOOD.md) |
| Auto | 0/N (TBD) | [AUTO.md](categories/AUTO.md) |
| Services | 0/N (TBD) | [SERVICES.md](categories/SERVICES.md) |
| Education | 0/N (TBD) | [EDUCATION.md](categories/EDUCATION.md) |
| Retail | 0/N (TBD) | [RETAIL.md](categories/RETAIL.md) |

---

## Прогресс работы

### Сделано

- ✓ MANICURE: solo-master калибровка (4 формата × уровни). Архетипы A1 + A2. Spec в `data/niches/MANICURE_data.yaml`. Числа подтверждены smoke-тестом 2026-04-30 (commit 5715916).
- ✓ Engine: A1 + A2 в коде, поля `commission_pct`, `materials_med`, `occupancy_rate`, `working_days_per_month` подняты через `_apply_r12_5_overrides`.
- ✓ Loader merge: knowledge md + data/niches/yaml (commit 91fbac6).
- ✓ Архитектура трёх слоёв задокументирована (CLAUDE.md commit c1b49b6).
- ✓ Архитектурная документация (этот файл и соседи).

### Бэклог

**Beauty калибровки** (по порядку Адиля):
1. BROW → 2. SUGARING → 3. MASSAGE → 4. COSMETOLOGY → 5. BARBER → 6. BEAUTY салон.

**Engine extensions** перед B1/B2 ниш:
- B1: `calc_owner_b1_economics`, поля `n_masters`, `commission_in_pct`, `rent_per_master`, etc.
- B2: `calc_owner_b2_economics`, поля `n_masters`, `master_salary_base`, `master_premium_pct`, `employer_taxes_pct`, etc.
- Ветки в `compute_pnl_aggregates` и `simulate_calendar_pnl` для каждого архетипа.

**Drift в MANICURE STUDIO** (minor):
- STUDIO_simple_mid +32%, STUDIO_simple_exp +29%, STUDIO_nice_mid +23% — pocket выше Адилевских диапазонов. Possibly требует тонкой калибровки traffic / occupancy / opex для STUDIO middle опыта. В бэклоге, не блокер.

**Калибровочный аудит** (из 2026-04-29):
- 7 HTTP 400 + 7 distortion в legacy ниш (BROW HOME/SOLO, CLEAN_TEAM, CONFECTION_HOME, и др.) — старая schema, отсутствуют marketing/other_opex для эконом-форматов.

**Аудит (2026-04-29) бэклог:**
- #3 Архетип A1 на BARBER/BROW/SUGARING (после калибровки)
- #4 Анти-паттерн «новичок+агрессивный» на не-A1 ниши
- #6 ФОТ helper duplication
- #10 README.md root — нормальный quick-start
- #14 FORMAT_ID_SYNC re-check
- #16 FITNESS regression test

---

## Правила добавления / изменения

### Новая ниша

1. Открыть [categories/<CATEGORY>.md](categories/) — добавить запись в сводку.
2. Подобрать архетип из [archetypes/](archetypes/).
3. Создать `data/niches/<CODE>_data.yaml` — formats[] + formats_r12[] (per-level если есть).
4. Создать `data/kz/niches/niche_formats_<CODE>.xlsx` — runtime-cache.
5. Добавить в `data/kz/niches_registry.yaml` со status: idea / research / wiki_only / production_ready.
6. Smoke /quick-check на 1-2 комбинациях.
7. Обновить категорийный README + сводку.

### Новый архетип

Только если **нельзя** представить через существующий через параметры. Тогда:
1. Создать `archetypes/<NN-name>.md` — спека (формула, поля, кому нужен).
2. Имплементировать `calc_*_economics` в `api/services/economics_service.py`.
3. Расширить `_apply_r12_5_overrides` под новые поля.
4. Branch в `compute_pnl_aggregates` и `simulate_calendar_pnl`.
5. Обновить `archetypes/README.md` (✓ в коде).

### Изменение принципа

1. Обновить `principles.md` (один блок на одно изменение).
2. Если затрагивает действующие ниши — пометить в их категорийном файле как «принцип Х изменён, пересчитать».
3. Реализовать пересчёт ниш отдельной серией коммитов (не вместе с принципом).

### Когда переспрашивать Адиля

Только если:
- Архитектурный вопрос **не покрыт** этой папкой и [CLAUDE.md](../../CLAUDE.md).
- Есть конфликт между разными источниками (registry vs yaml vs принципы).
- Числа калибровки (Адиль — финансист, **числа** диктует он).

В остальном — читай файл, пиши код, обновляй файл.
