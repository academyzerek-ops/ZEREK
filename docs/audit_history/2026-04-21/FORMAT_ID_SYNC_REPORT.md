# ZEREK — Аудит рассинхрона format_id
**Дата:** 2026-04-21
**Источники:**
- per-niche: `data/kz/niches/niche_formats_{NICHE}.xlsx` (лист FORMATS)
- агрегат:  `data/kz/08_niche_formats.xlsx` (лист «Форматы»)

## Сводка

| Статус | Кол-во ниш | Доля |
|---|---|---|
| SYNC     | 0 | 0% |
| PARTIAL  | 18 | 55% |
| MISMATCH | 15 | 45% |
| NO_PER_NICHE_FILE | 0 | 0% |
| NO_08_ROWS        | 0 | 0% |

Всего проверено ниш (available=true): **33**.

Ни одна из 33 доступных ниш не синхронизирована между двумя источниками. Рассинхрон тотальный.

## Таблица по нишам

| Ниша | Статус | per-niche format_id | 08_niche_formats format_id | Пересечение | Рекомендация |
|---|---|---|---|---|---|
| AUTOSERVICE | MISMATCH | AUTO_GARAGE, AUTO_SERVICE, AUTO_SPEC, AUTO_FULL | AUTOSERV_1POST, AUTOSERV_FULL | ∅ | ручной разбор: разное количество (4 vs 2) |
| CANTEEN | MISMATCH | CANTEEN_OFFICE, CANTEEN_CITY, CANTEEN_CATERING | CANTEEN_BC, CANTEEN_ENTER | ∅ | ручной разбор: разное количество (3 vs 2) |
| CARWASH | MISMATCH | CARWASH_MANUAL_S, CARWASH_MANUAL_L, CARWASH_SELF_BOX, CARWASH_SELF_OPEN, CARWASH_AUTO | WASH_SELF, WASH_MANUAL | ∅ | ручной разбор: разное количество (5 vs 2) |
| COMPCLUB | MISMATCH | CYBER_MINI, CYBER_MEDIUM, CYBER_PREMIUM | CC_SMALL, CC_LARGE | ∅ | ручной разбор: разное количество (3 vs 2) |
| CONFECTION | MISMATCH | CONF_HOME, CONF_CABINET, CONF_STUDIO | CONFECT_HOME, CONFECT_WORKSHOP | ∅ | ручной разбор: разное количество (3 vs 2) |
| FITNESS | MISMATCH | FITNESS_STUDIO, FITNESS_CROSSFIT, FITNESS_MMA, FITNESS_GYM | FIT_STUDIO, FIT_CLUB | ∅ | ручной разбор: разное количество (4 vs 2) |
| FLOWERS | MISMATCH | FLOWERS_KIOSK, FLOWERS_SHOP, FLOWERS_STUDIO | FLOWER_KIOSK, FLOWER_STUDIO | ∅ | ручной разбор: разное количество (3 vs 2) |
| FURNITURE | MISMATCH | FURN_SOLO, FURN_WORKSHOP, FURN_FACTORY | FURN_SMALL, FURN_FULL | ∅ | ручной разбор: разное количество (3 vs 2) |
| GROCERY | MISMATCH | GROCERY_MINI, GROCERY_MEDIUM, GROCERY_SPEC | GROC_KIOSK, GROC_STANDARD, GROC_SUPER | ∅ | переименовать 3↔3 1-к-1 (семантика: GROCERY_MINI/GROCERY_MEDIUM/GROCERY_SPEC → GROC_KIOSK/GROC_STANDARD/GROC_SUPER) |
| KINDERGARTEN | MISMATCH | KINDER_HOME, KINDER_MINI, KINDER_FULL | KG_HOME, KG_STANDARD | ∅ | ручной разбор: разное количество (3 vs 2) |
| PHARMACY | MISMATCH | PHARMA_MINI, PHARMA_STD | PHARM_SMALL, PHARM_FULL | ∅ | переименовать 2↔2 1-к-1 (семантика: PHARMA_MINI/PHARMA_STD → PHARM_SMALL/PHARM_FULL) |
| REPAIR_PHONE | MISMATCH | REP_KIOSK, REP_SHOP | REPAIR_POINT, REPAIR_STUDIO | ∅ | переименовать 2↔2 1-к-1 (семантика: REP_KIOSK/REP_SHOP → REPAIR_POINT/REPAIR_STUDIO) |
| SUGARING | MISMATCH | SUGARING_HOME, SUGARING_RENT, SUGARING_OWN | SUGAR_HOME, SUGAR_SOLO, SUGAR_CABINET | ∅ | переименовать 3↔3 1-к-1 (семантика: SUGARING_HOME/SUGARING_RENT/SUGARING_OWN → SUGAR_HOME/SUGAR_SOLO/SUGAR_CABINET) |
| TIRESERVICE | MISMATCH | TIRE_MOBILE, TIRE_MINI, TIRE_FULL | TIRE_SMALL, TIRE_STANDARD | ∅ | ручной разбор: разное количество (3 vs 2) |
| WATERPLANT | MISMATCH | WATER_FILTER, WATER_WELL, WATER_VENDING | WATER_MINI, WATER_FULL | ∅ | ручной разбор: разное количество (3 vs 2) |
| BAKERY | PARTIAL | BAKERY_MINI, BAKERY_CRAFT, BAKERY_CONFECT, BAKERY_CAFE, BAKERY_ISLAND, BAKERY_PRODUCTION | BAKERY_SMALL, BAKERY_FULL, BAKERY_PRODUCTION | BAKERY_PRODUCTION | per-niche шире: в per-niche есть лишние BAKERY_MINI, BAKERY_CRAFT, BAKERY_CONFECT, BAKERY_CAFE, BAKERY_ISLAND — объединить/удалить или добавить в 08 |
| BARBER | PARTIAL | BARBER_SOLO, BARBER_MINI, BARBER_FULL | BARBER_SOLO, BARBER_STANDARD, BARBER_PREMIUM | BARBER_SOLO | переименовать BARBER_MINI, BARBER_FULL → BARBER_STANDARD, BARBER_PREMIUM (или обратно) |
| BROW | PARTIAL | BROW_HOME, BROW_RENT, BROW_CABINET | BROW_HOME, BROW_SOLO, BROW_CABINET | BROW_CABINET, BROW_HOME | переименовать BROW_RENT → BROW_SOLO (или обратно) |
| CLEAN | PARTIAL | CLEAN_SOLO, CLEAN_TEAM, CLEAN_COMPANY | CLEAN_SOLO, CLEAN_TEAM | CLEAN_SOLO, CLEAN_TEAM | per-niche шире: в per-niche есть лишние CLEAN_COMPANY — объединить/удалить или добавить в 08 |
| COFFEE | PARTIAL | COFFEE_VENDING, COFFEE_KIOSK, COFFEE_ISLAND, COFFEE_MOBILE, COFFEE_MINI, COFFEE_FULL, COFFEE_SELF | COFFEE_KIOSK, COFFEE_CAFE, COFFEE_SPECIAL | COFFEE_KIOSK | per-niche шире: в per-niche есть лишние COFFEE_VENDING, COFFEE_ISLAND, COFFEE_MOBILE, COFFEE_MINI, COFFEE_FULL, COFFEE_SELF — объединить/удалить или добавить в 08 |
| DENTAL | PARTIAL | DENTAL_CABINET, DENTAL_CLINIC | DENTAL_1CH, DENTAL_CLINIC | DENTAL_CLINIC | переименовать DENTAL_CABINET → DENTAL_1CH (или обратно) |
| DONER | PARTIAL | DONER_KIOSK, DONER_MINI, DONER_CAFE, DONER_DELIVERY | DONER_TAKEOUT, DONER_CAFE | DONER_CAFE | per-niche шире: в per-niche есть лишние DONER_KIOSK, DONER_MINI, DONER_DELIVERY — объединить/удалить или добавить в 08 |
| DRYCLEAN | PARTIAL | DRY_POINT, DRY_MINI, DRY_FULL | DRY_APPR, DRY_FULL | DRY_FULL | per-niche шире: в per-niche есть лишние DRY_POINT, DRY_MINI — объединить/удалить или добавить в 08 |
| FASTFOOD | PARTIAL | FASTFOOD_KIOSK, FASTFOOD_MINI, FASTFOOD_CAFE, FASTFOOD_DARK | FASTFOOD_TAKE, FASTFOOD_CAFE | FASTFOOD_CAFE | per-niche шире: в per-niche есть лишние FASTFOOD_KIOSK, FASTFOOD_MINI, FASTFOOD_DARK — объединить/удалить или добавить в 08 |
| FRUITSVEGS | PARTIAL | FV_KIOSK, FV_SHOP, FV_WHOLESALE | FV_KIOSK, FV_STORE | FV_KIOSK | per-niche шире: в per-niche есть лишние FV_SHOP, FV_WHOLESALE — объединить/удалить или добавить в 08 |
| LASH | PARTIAL | LASH_HOME, LASH_RENT, LASH_CABINET | LASH_HOME, LASH_SOLO, LASH_CABINET | LASH_CABINET, LASH_HOME | переименовать LASH_RENT → LASH_SOLO (или обратно) |
| MANICURE | PARTIAL | NAIL_HOME, NAIL_RENT, NAIL_CABINET, NAIL_STUDIO | NAIL_HOME, NAIL_SOLO, NAIL_CABINET, NAIL_SALON | NAIL_CABINET, NAIL_HOME | переименовать NAIL_RENT, NAIL_STUDIO → NAIL_SOLO, NAIL_SALON (или обратно) |
| MASSAGE | PARTIAL | MASSAGE_CABINET, MASSAGE_STUDIO | MASSAGE_HOME, MASSAGE_SOLO, MASSAGE_STUDIO | MASSAGE_STUDIO | 08 шире: в 08 есть лишние MASSAGE_HOME, MASSAGE_SOLO — добавить в per-niche или удалить из 08 |
| PIZZA | PARTIAL | PIZZA_DELIVERY, PIZZA_TAKEAWAY, PIZZA_CAFE, PIZZA_COMBO | PIZZA_DELIVERY, PIZZA_CAFE | PIZZA_CAFE, PIZZA_DELIVERY | per-niche шире: в per-niche есть лишние PIZZA_TAKEAWAY, PIZZA_COMBO — объединить/удалить или добавить в 08 |
| PVZ | PARTIAL | PVZ_SMALL, PVZ_MULTI | PVZ_SMALL, PVZ_FULL | PVZ_SMALL | переименовать PVZ_MULTI → PVZ_FULL (или обратно) |
| SEMIFOOD | PARTIAL | SEMI_HOME, SEMI_MINI, SEMI_FULL | SEMI_HOME, SEMI_WORKSHOP | SEMI_HOME | per-niche шире: в per-niche есть лишние SEMI_MINI, SEMI_FULL — объединить/удалить или добавить в 08 |
| SUSHI | PARTIAL | SUSHI_DELIVERY, SUSHI_BAR, SUSHI_COMBO | SUSHI_DELIVERY, SUSHI_BAR | SUSHI_BAR, SUSHI_DELIVERY | per-niche шире: в per-niche есть лишние SUSHI_COMBO — объединить/удалить или добавить в 08 |
| TAILOR | PARTIAL | TAILOR_HOME, TAILOR_MINI, TAILOR_FULL | TAILOR_HOME, TAILOR_MINI | TAILOR_HOME, TAILOR_MINI | per-niche шире: в per-niche есть лишние TAILOR_FULL — объединить/удалить или добавить в 08 |

## Рассинхрон по паттернам

### Паттерн 1: HOME/RENT/CABINET (per-niche) vs HOME/SOLO/CABINET (08) — бьюти-мастера с арендой
Семантика идентична, отличается только ID середины: `*_RENT` ↔ `*_SOLO` (оба = «мастер в чужом салоне»).
Ниши: BROW, LASH, MANICURE, SUGARING. Это шаблон архетипа A (услуги с мастерами).

### Паттерн 2: SOLO/MINI/FULL (per-niche) vs SOLO/STANDARD/PREMIUM (08)
Per-niche использует «размерную» схему, 08 — «классовую». BARBER — эталонный пример.
Ниши (полный или частичный вариант): BARBER, KINDERGARTEN, CONFECTION, SUGARING (после учёта пункта 1).

### Паттерн 3: KIOSK/SHOP/STUDIO (per-niche) vs KIOSK/STUDIO (08) — одна лишняя опция в per-niche
Per-niche добавляет промежуточный формат, которого нет в 08.
Ниши: FLOWERS (`FLOWERS_SHOP` лишний), FRUITSVEGS (`FV_SHOP` лишний), GROCERY (3 vs 3, но ID всех трёх разные).

### Паттерн 4: per-niche шире по количеству (4-7 vs 2-3)
В per-niche дополнительные форматы («DELIVERY», «COMBO», «KIOSK» и пр.), которых нет в 08.
Ниши: BAKERY (6 vs 3), COFFEE (7 vs 3), DONER (4 vs 2), FASTFOOD (4 vs 2), PIZZA (4 vs 2), SUSHI (3 vs 2),
AUTOSERVICE (4 vs 2), CARWASH (5 vs 2), TIRESERVICE (3 vs 2), CLEAN (3 vs 2), DRYCLEAN (3 vs 2),
TAILOR (3 vs 2), SEMIFOOD (3 vs 2), FITNESS (4 vs 2), FURNITURE (3 vs 2), WATERPLANT (3 vs 2),
CANTEEN (3 vs 2), COMPCLUB (3 vs 2), KINDERGARTEN (3 vs 2).

### Паттерн 5: KIOSK-аналоги с разными префиксами
Разные префиксы для одной ниши: `FLOWERS_KIOSK` vs `FLOWER_KIOSK` (без `S`), `WASH_*` vs `CARWASH_*`,
`CC_*` vs `CYBER_*`, `PHARM_*` vs `PHARMA_*`, `KG_*` vs `KINDER_*`, `FIT_*` vs `FITNESS_*`,
`GROC_*` vs `GROCERY_*`, `AUTOSERV_*` vs `AUTO_*`, `REPAIR_*` vs `REP_*`, `TIRE_*` (оба, но с разными суффиксами),
`SUGAR_*` vs `SUGARING_*`. Это префиксные неконсистентности — семантика близка, но ID разведены.
Ниши (подмножество MISMATCH): CARWASH, COMPCLUB, PHARMACY, KINDERGARTEN, FITNESS, GROCERY, AUTOSERVICE, REPAIR_PHONE, SUGARING.

### Паттерн 6: прочие отдельные отклонения
- **DENTAL**: `DENTAL_CABINET` (per) vs `DENTAL_1CH` (08), пересечение на `DENTAL_CLINIC`.
- **PVZ**: per имеет `PVZ_MULTI`, 08 — `PVZ_FULL`.
- **REPAIR_PHONE**: полный разнобой `REP_KIOSK/REP_SHOP` vs `REPAIR_POINT/REPAIR_STUDIO`.
- **MASSAGE**: в 08 три формата (HOME/SOLO/STUDIO), в per-niche только два (CABINET/STUDIO).

## Рекомендация по унификации

### 1. Какой источник считать каноничным

**Каноничным нужно считать per-niche** `data/kz/niches/niche_formats_{NICHE}.xlsx` — вот пруфы из `api/engine.py`:

- `db.get_formats_for_niche(niche_id)` (строка 331) читает **только per-niche FORMATS** — это и есть реализация эндпоинта `GET /formats/{niche_id}` (см. `api/main.py:135-142`).
- Функция `_formats_from_per_niche_xlsx` (строка 1095) — основной источник; `_formats_from_fallback_xlsx` (строка 1105) назван именно как fallback.
- Per-niche xlsx содержит 14 листов: FORMATS, STAFF, FINANCIALS, CAPEX, GROWTH, TAXES, MARKET, LAUNCH, INSIGHTS, PRODUCTS, MARKETING, SUPPLIERS, SURVEY, LOCATIONS. Связь по `format_id` используется во всех таблицах расчёта. Поменять ID здесь — значит сломать связанность 14 таблиц.
- 08 используется в двух местах: (а) `/formats-v2/{niche_id}` через `get_formats_v2` (engine.py:2890) — это параллельный эндпоинт для новой спеки с полями format_type / allowed_locations / typical_staff; (б) `_build_quickcheck_v3` (engine.py:2761) тянет `format_type`/`typical_staff` из 08 для рендера отчёта Quick Check v3. То есть 08 даёт метаданные, которых нет в per-niche.

Итог: per-niche — основной источник (формат/расчёты), 08 — вспомогательная шина метаданных (format_type, allowed_locations, typical_staff). Нужно привести ID в 08 к ID per-niche — и добавить в 08 те `format_id`, которых там не хватает.

### 2. Сколько xlsx нужно править

**Сценарий A (каноничным считаем per-niche — рекомендуется):**
- Правим **1 файл**: `data/kz/08_niche_formats.xlsx`.
- Меняем 33 блока строк (по одному на каждую доступную нишу).
- В 33 нишах нужно переименовать часть ID и/или добавить недостающие строки. Для ниш с per-niche > 08 (пункт 4-й паттерн) придётся **дозаполнять** метаданные (format_type, allowed_locations, typical_staff).

**Сценарий B (каноничным считаем 08):**
- Правим **33 файла** per-niche — каждый содержит `format_id` в 14 листах.
- На каждом per-niche xlsx нужно: переименовать `format_id` в FORMATS, STAFF, FINANCIALS, CAPEX, GROWTH, TAXES, MARKET, LAUNCH, INSIGHTS, PRODUCTS, MARKETING, SUPPLIERS, SURVEY (LOCATIONS — без `format_id`).
- В нишах, где per-niche имеет **больше** форматов (19 из 33 — см. паттерн 4), пришлось бы **удалить** проработанные форматы и данные в 13 листах. Это потеря контента.

Сценарий A на порядок дешевле и безопаснее: 1 xlsx против 33 xlsx × 13 листов.

### 3. Сложность переименования — где нельзя 1-к-1

Ниши, где **количество форматов не совпадает** (match 1-к-1 невозможен, нужен ручной разбор содержимого):

| Ниша | per-niche | 08 | Разница |
|---|---|---|---|
| AUTOSERVICE | 4 | 2 | +2 |
| CANTEEN | 3 | 2 | +1 |
| CARWASH | 5 | 2 | +3 |
| COMPCLUB | 3 | 2 | +1 |
| CONFECTION | 3 | 2 | +1 |
| FITNESS | 4 | 2 | +2 |
| FLOWERS | 3 | 2 | +1 |
| FURNITURE | 3 | 2 | +1 |
| KINDERGARTEN | 3 | 2 | +1 |
| TIRESERVICE | 3 | 2 | +1 |
| WATERPLANT | 3 | 2 | +1 |
| BAKERY | 6 | 3 | +3 |
| CLEAN | 3 | 2 | +1 |
| COFFEE | 7 | 3 | +4 |
| DONER | 4 | 2 | +2 |
| DRYCLEAN | 3 | 2 | +1 |
| FASTFOOD | 4 | 2 | +2 |
| FRUITSVEGS | 3 | 2 | +1 |
| MASSAGE | 2 | 3 | -1 |
| PIZZA | 4 | 2 | +2 |
| SEMIFOOD | 3 | 2 | +1 |
| SUSHI | 3 | 2 | +1 |
| TAILOR | 3 | 2 | +1 |

Всего: **23 ниш** требуют ручного разбора (какой формат из per-niche маппить на какой из 08, что удалить / что добавить).

Ниши, где **количество совпадает** (простое 1-к-1 переименование возможно):

| Ниша | Формат (per → 08) |
|---|---|
| GROCERY | GROCERY_MINI→GROC_KIOSK, GROCERY_MEDIUM→GROC_STANDARD, GROCERY_SPEC→GROC_SUPER |
| PHARMACY | PHARMA_MINI→PHARM_SMALL, PHARMA_STD→PHARM_FULL |
| REPAIR_PHONE | REP_KIOSK→REPAIR_POINT, REP_SHOP→REPAIR_STUDIO |
| SUGARING | SUGARING_HOME→SUGAR_HOME, SUGARING_RENT→SUGAR_SOLO, SUGARING_OWN→SUGAR_CABINET |
| BARBER | BARBER_SOLO=BARBER_SOLO, BARBER_MINI→BARBER_STANDARD, BARBER_FULL→BARBER_PREMIUM |
| BROW | BROW_HOME=BROW_HOME, BROW_CABINET=BROW_CABINET, BROW_RENT→BROW_SOLO |
| DENTAL | DENTAL_CLINIC=DENTAL_CLINIC, DENTAL_CABINET→DENTAL_1CH |
| LASH | LASH_HOME=LASH_HOME, LASH_CABINET=LASH_CABINET, LASH_RENT→LASH_SOLO |
| MANICURE | NAIL_HOME=NAIL_HOME, NAIL_CABINET=NAIL_CABINET, NAIL_RENT→NAIL_SOLO, NAIL_STUDIO→NAIL_SALON |
| PVZ | PVZ_SMALL=PVZ_SMALL, PVZ_MULTI→PVZ_FULL |

Всего: **10 ниш** можно переименовать автоматически (одно целевое значение на каждый ID). Но даже здесь смысл класса нужно сверять: например, в **PVZ** `PVZ_SMALL` у per-niche = «стандарт», у 08 = «эконом» — простое переименование без пересмотра class даст неверный расчёт.

### 4. Приоритизация

По объёму правок в 08 (в убывающем порядке):
- **Большой разрыв** (разница ≥ 2 формата): CARWASH (5→2), COFFEE (7→3), BAKERY (6→3), AUTOSERVICE (4→2), FITNESS (4→2), DONER (4→2), FASTFOOD (4→2), PIZZA (4→2), MANICURE (4 vs 4 но только 2 пересечения).
- **Маленький разрыв** (1 формат или только переименования): BARBER, BROW, LASH, SUGARING, DENTAL, PVZ, CLEAN, DRYCLEAN, TAILOR, SUSHI, SEMIFOOD, PHARMACY, REPAIR_PHONE, FLOWERS, FURNITURE, TIRESERVICE, WATERPLANT, COMPCLUB, KINDERGARTEN, CANTEEN, CONFECTION, FRUITSVEGS, GROCERY, MASSAGE.

## Дополнительные находки

### Расхождения полей на пересекающихся format_id

Даже там, где `format_id` совпадают между двумя источниками, содержимое может расходиться (area_med/area_m2, class, format_name). Это значит: исправление ID — только первый шаг; нужна вторая итерация по выравниванию данных.

| Ниша | format_id | Поле | per-niche | 08 | Расхождение |
|---|---|---|---|---|---|
| BAKERY | BAKERY_PRODUCTION | area (med/m2) | 80 | 120 | да |
| BAKERY | BAKERY_PRODUCTION | class | эконом | премиум | да |
| BAKERY | BAKERY_PRODUCTION | format_name | Пекарня-производство B2B | Производство + B2B | да |
| BARBER | BARBER_SOLO | area (med/m2) | 3 | 15 | да |
| BARBER | BARBER_SOLO | format_name | Аренда кресла | Барбер-одиночка | да |
| BROW | BROW_CABINET | area (med/m2) | 12 | 18 | да |
| BROW | BROW_HOME | area (med/m2) | 3 | 8 | да |
| BROW | BROW_HOME | format_name | На дому | Мастер на дому | да |
| CLEAN | CLEAN_SOLO | format_name | Самозанятый | Клининг-ИП | да |
| CLEAN | CLEAN_TEAM | class | эконом | стандарт | да |
| CLEAN | CLEAN_TEAM | format_name | Бригада | Клининговая бригада | да |
| COFFEE | COFFEE_KIOSK | area (med/m2) | 4 | 12 | да |
| COFFEE | COFFEE_KIOSK | format_name | Кофе с собой | Островок / кофе с собой | да |
| DENTAL | DENTAL_CLINIC | format_name | Клиника | Клиника 3-5 кресел | да |
| DONER | DONER_CAFE | area (med/m2) | 40 | 55 | да |
| DONER | DONER_CAFE | format_name | Донер-кафе | Донерная с залом | да |
| DRYCLEAN | DRY_FULL | format_name | Полная химчистка | Химчистка с оборудованием | да |
| FASTFOOD | FASTFOOD_CAFE | area (med/m2) | 50 | 70 | да |
| FASTFOOD | FASTFOOD_CAFE | format_name | Фастфуд-кафе | Фастфуд с залом | да |
| LASH | LASH_CABINET | area (med/m2) | 12 | 18 | да |
| LASH | LASH_HOME | area (med/m2) | 5 | 8 | да |
| LASH | LASH_HOME | format_name | На дому | Мастер на дому | да |
| MANICURE | NAIL_CABINET | area (med/m2) | 12 | 20 | да |
| MANICURE | NAIL_CABINET | format_name | Свой кабинет | Кабинет 1-2 мастера | да |
| MANICURE | NAIL_HOME | area (med/m2) | 5 | 10 | да |
| MANICURE | NAIL_HOME | format_name | На дому | Мастер на дому | да |
| MASSAGE | MASSAGE_STUDIO | area (med/m2) | 45 | 40 | да |
| MASSAGE | MASSAGE_STUDIO | format_name | Студия | Массажная студия | да |
| PIZZA | PIZZA_CAFE | area (med/m2) | 60 | 80 | да |
| PIZZA | PIZZA_DELIVERY | area (med/m2) | 35 | 30 | да |
| PVZ | PVZ_SMALL | class | стандарт | эконом | да |
| PVZ | PVZ_SMALL | format_name | Мини-ПВЗ | ПВЗ 15 м² | да |
| SEMIFOOD | SEMI_HOME | area (med/m2) | 10 | 25 | да |
| SUSHI | SUSHI_BAR | area (med/m2) | 60 | 75 | да |
| TAILOR | TAILOR_HOME | area (med/m2) | 5 | 15 | да |
| TAILOR | TAILOR_HOME | format_name | На дому | Ателье на дому | да |
| TAILOR | TAILOR_MINI | area (med/m2) | 15 | 25 | да |
| TAILOR | TAILOR_MINI | class | эконом | стандарт | да |

Всего таких расхождений: **38** (по 23 уникальных пар `ниша/format_id`).

Характерные кейсы:
- **BARBER_SOLO**: area_med=3 м² (per-niche «Аренда кресла») vs area_m2=15 м² (08 «Барбер-одиночка»). Это **разные бизнес-модели** под одним ID — критичная смысловая коллизия.
- **BAKERY_PRODUCTION**: per = эконом/80 м² «Пекарня-производство B2B», 08 = премиум/120 м² «Производство + B2B». Тот же ID, но разный class и area.
- **CLEAN_TEAM**, **PVZ_SMALL**, **TAILOR_MINI** — разные class у одного и того же format_id.
- **MANICURE/NAIL_HOME**, **LASH_HOME**, **BROW_HOME**, **TAILOR_HOME** — стабильное расхождение area_med (per ≈ 5) vs area_m2 (08 ≈ 8-15). Вероятно, в per-niche это «рабочее место», в 08 — «квартира».

### Ниши с available=false, для которых есть данные

В 08 есть строки для **29** ниш с `available: false` (и ни одного per-niche xlsx для них):
`BEAUTY`, `COSMETOLOGY`, `OPTICS`, `PHOTO`, `DETAILING`, `NOTARY`, `BUBBLETEA`, `CATERING`, `MEATSHOP`, `AUTOPARTS`, `BUILDMAT`, `PETSHOP`, `YOGA`, `LANGUAGES`, `KIDSCENTER`, `ACCOUNTING`, `CROSSFIT`, `MARTIAL_ARTS`, `FOOTBALL_SCHOOL`, `GROUP_FITNESS`, `REALTOR`, `EVALUATION`, `LOFTFURNITURE`, `PRINTING`, `CARGO`, `CARPETCLEAN`, `LAUNDRY`, `DRIVING`, `HOTEL`.

Это не ошибка — 08 задумывался как спецификация на все 62 ниши (архив «готовых шаблонов»), а per-niche существует только для активных. Но при будущем переключении `available: true` для, например, BEAUTY, сразу возникнет ситуация «08 есть, per-niche нет» — и `db.get_formats_for_niche(BEAUTY)` вернёт пустой список. Нужно завести ручной чек-лист: «открыть нишу = создать per-niche xlsx».

## Методология (коротко)

1. Список ниш взят из `config/niches.yaml` — фильтр `available: true` даёт 33 позиции из 62.
2. Per-niche читался через `openpyxl` read-only из `data/kz/niches/niche_formats_{NICHE}.xlsx`, лист `FORMATS`. Заголовок находился по ячейке `format_id` (строка 3). Так как в per-niche одна строка = одна (format_id × class) комбинация, при извлечении множества `format_id` делался dedup по первой встречной строке.
3. Агрегат читался из `data/kz/08_niche_formats.xlsx`, лист `Форматы`. Заголовок — строка 6 (`niche_id, format_id, format_name, area_m2, capex_standard, class, format_type, allowed_locations, typical_staff`). Фильтр по `niche_id == NICHE`.
4. Колонка «класс»: для per-niche бралась `class` (строковые значения «Эконом/Стандарт/Бизнес/Премиум»), для 08 — `class` (русские строчные значения «эконом/стандарт/премиум»). Регистры приводились к lower() при сравнении.
5. Колонка «площадь»: для per-niche сравнивали `area_med`, для 08 — `area_m2` (одна колонка). Пустые значения (`None`/`nan`) пропускались.
6. Подсчёт пересечения делался через `set(per.format_id) & set(08.format_id)`. Статус: SYNC (множества равны), PARTIAL (есть пересечение), MISMATCH (нет пересечения).
