# ZEREK Quick Check v2 — Adaptive Survey

Новая архитектура анкеты для Telegram Mini App: вопросы подстраиваются под нишу
(лицензия / формат / локация / площадь / персонал / спец-вопросы). Старая анкета
v1 (`products/quick-check.html`) продолжает работать параллельно и **не меняется**
до момента полной миграции.

## Что изменилось

| Слой | v1 | v2 |
|------|----|----|
| UI-файл | `products/quick-check.html` | `products/quick-check-v2.html` |
| Шаги | 7 фиксированных | 3–10 адаптивных (зависят от ниши) |
| Источник вопросов | хардкод в JS | `/niche-config/{niche_id}` + `07_niches.xlsx` |
| Специфичные вопросы | нет | 17 шт в листе «Специфичные вопросы» |
| Форматы | `/formats/{niche_id}` (per-niche xlsx) | то же + fallback из `08_niche_formats.xlsx` |
| Payload `/quick-check` | 10 полей | + `has_license`, `staff_mode`, `staff_count`, `specific_answers` |

## Новые xlsx-файлы

### `data/kz/07_niches.xlsx` — конфиг адаптивной анкеты

Три листа:

**Лист «Ниши»** (заголовки на 6-й строке Excel, `pandas header=5`):

| колонка | значения | смысл |
|---------|----------|-------|
| `niche_id` | `NOTARY`, `BARBER`, ... | ключ ниши |
| `niche_name` | свободный текст | русское имя |
| `requires_license` | `mandatory` / `optional` / `no` | нужна ли лицензия |
| `license_description` | текст | описание лицензии (например, «Лицензия Минюста РК») |
| `self_operation_possible` | `yes` / `no` | может ли владелец сам работать |
| `class_grades_applicable` | `yes` / `no` | есть ли градация эконом/стандарт/премиум |
| `allowed_location_types` | CSV: `tc,street,home,...` | разрешённые типы локации |
| `default_location_type` | один из allowed | что подставить по умолчанию |
| `area_question_mode` | `required` / `hidden_if_home` / `hidden_always` | логика вопроса о площади |
| `staff_question_mode` | `self_only` / `hired_only` / `choice` / `hidden` | логика вопроса о персонале |
| `specific_questions_ids` | CSV: `Q_CHAIRS,Q_BARBER_TYPE` | какие спец-вопросы применяются |
| `niche_notes` | текст | заметки (необязательно) |

**Лист «Специфичные вопросы»**:

| колонка | пример |
|---------|--------|
| `question_id` | `Q_CHAIRS` |
| `question_text` | «Сколько рабочих мест (кресел/столов)?» |
| `options` | `1\|2\|3-5\|6-10\|10+` (pipe-separated) |
| `applies_to_niches` | `BARBER,MANICURE,BROW,...` |

**Лист «Типы локации»**: справочник `location_id → icon, label` для рендера
в анкете (дублируется в коде движка константой `LOCATION_TYPES_META`, чтобы
работать даже когда xlsx недоступен).

### `data/kz/08_niche_formats.xlsx` — fallback-каталог форматов

Лист «Форматы» (header=5), одна строка на формат. Используется **только как
фолбэк**: если per-niche xlsx (`data/kz/niches/niche_formats_{NICHE}.xlsx`)
пуст или отсутствует, форматы берутся отсюда.

Колонки: `niche_id | format_id | format_name | area_m2 | loc_type | capex_standard | class`.

В настоящий момент покрыто: **58 ниш, 123 формата**.

## Новый эндпоинт

```
GET /niche-config/{niche_id}
```

Возвращает объединённый JSON:

```json
{
  "niche_id": "NOTARY",
  "niche_name": "Нотариус",
  "requires_license": "mandatory",
  "license_description": "Лицензия Минюста РК на нотариальную деятельность",
  "self_operation_possible": "yes",
  "class_grades_applicable": "no",
  "allowed_location_types": ["business_center", "street"],
  "default_location_type": "business_center",
  "area_question_mode": "required",
  "staff_question_mode": "choice",
  "specific_questions": [
    {
      "question_id": "Q_NOT_LIC",
      "question_text": "Вы уже имеете лицензию нотариуса?",
      "options": ["да", "нет", "в процессе"]
    }
  ],
  "formats": [
    {
      "format_id": "NOTARY_OFFICE",
      "name": "Нотариальная контора",
      "area_m2": 30,
      "loc_type": "business_center",
      "capex_standard": 5500000,
      "class": "стандарт"
    }
  ],
  "location_types_meta": {
    "business_center": {"label": "Бизнес-центр", "icon": "🏢"},
    "street":          {"label": "Улица / отдельный офис", "icon": "🏪"}
  },
  "niche_notes": "Лицензируемая профессия. Без лицензии запуск невозможен."
}
```

Реализация: `engine.get_niche_config(db, niche_id)` — см. `api/engine.py`.

## Как v2-анкета адаптируется под нишу

**Базовый план шагов:** `city → niche`.

После выбора ниши фронт тянет `GET /niche-config/{niche_id}` и достраивает план:

```
city
niche
[license]       если requires_license == mandatory ИЛИ optional с Q_*_LIC
[format]        если есть форматы
location
[specific]      если есть не-лицензионные спец-вопросы
[area]          если area_question_mode != hidden_always (и loc != home для hidden_if_home)
[staff]         если staff_question_mode != hidden
capital
confirm
```

Валидация каждого шага — на стороне фронта перед активацией кнопки «Далее».

## Расширение `/quick-check`

`QCReq` получил четыре **опциональных** поля (v1 клиент их не шлёт, совместимость
полная):

```python
has_license: Optional[str]       # "yes" / "no" / "in_progress"
staff_mode:  Optional[str]       # "self" / "hired"
staff_count: Optional[int]
specific_answers: Optional[dict] # {"Q_CHAIRS": "3-5", ...}
```

На данный момент **расчёт не меняется** — поля пробрасываются в
`report.user_inputs` только если присланы. Позже движок начнёт их учитывать
(адаптивная финмодель).

## План миграции v1 → v2

1. **Сейчас:** v2 доступна по URL `products/quick-check-v2.html`, v1 — основной
   Mini App URL. Оба живут параллельно.
2. **Этап A** (А/Б-тест): в BotFather настроить два разных web_app URL, дать
   10% трафика на v2.
3. **Этап B:** расширить расчётный движок в `engine.py` чтобы `specific_answers`
   реально влияли на фин-параметры (например, `Q_CHAIRS=3-5` → `staff_count` в
   фин-модели).
4. **Этап C:** переключить главный URL Mini App на v2, v1 — в архив
   (`products/quick-check.legacy.html`).

## Как обновлять конфиг

```bash
# 1. Отредактировать data/kz/07_niches.xlsx (лист «Ниши» и/или «Специфичные вопросы»)
#    ИЛИ пересобрать из Python-источника правды:
python3 scripts/build_07_niches.py

# 2. Если добавили формат фолбэком — пересобрать 08:
python3 scripts/build_08_niche_formats.py

# 3. Коммит и пуш — Railway автоматически подхватит при рестарте.
git add data/kz/07_niches.xlsx data/kz/08_niche_formats.xlsx
git commit -m "data: update Quick Check v2 config"
git push origin main
```

## Список ниш

58 niche_id поддерживается в `07_niches.xlsx`. Полный список — см. первый лист.

Незакрытые на фронте (нет HTML-обзора и/или per-niche xlsx, но конфиг в 07 есть):
`BEAUTY, COMPCLUB, CATERING, HOTEL, LAUNDRY, LOFTFURNITURE, MANICURE, NOTARY,
EVALUATION, OPTICS, PRINTING, REALTOR, TIRESERVICE, YOGA, AUTOPARTS, BUILDMAT,
PETSHOP, ACCOUNTING, MEATSHOP, CARGO, CARPETCLEAN, DETAILING, DRIVING, KIDSCENTER,
LANGUAGES, PHOTO, PHARMACY, BUBBLETEA, FRUITSVEGS, SEMIFOOD, WATERPLANT, ...`
— для них анкета использует fallback-форматы из `08_niche_formats.xlsx`.
