# ZEREK — Инвентаризация ниш

**Дата:** 2026-04-21  
**Коммит:** `7fcc482`  

## Используемые источники

1. `config/niches.yaml` — каноничный реестр ниш (62 записи)
2. `data/kz/niches/niche_formats_*.xlsx` — per-niche расчётные файлы (33 файла)
3. `data/kz/08_niche_formats.xlsx`, лист «Форматы» — матрица форматов для всех ниш
4. `knowledge/kz/niches/*_insight.md` — текстовые инсайты для Block 9 Quick Check (44 файла)
5. `wiki/kz/*.html` — публичные wiki-обзоры как лид-магнит (48 файлов)

## Методология

1. **niche_id из yaml**: прямо ключи раздела `niches:` (UPPERCASE).
2. **per-niche xlsx**: парсил имя `niche_formats_{NICHE}.xlsx`; для каждого через `openpyxl` проверял наличие листов `FINANCIALS` и `STAFF` и смотрел, есть ли хотя бы одна непустая строка данных ниже заголовка (строка считается непустой, если в ней есть хотя бы одна непустая ячейка).
3. **08_niche_formats.xlsx**: читал лист «Форматы», пропускал первые 6 служебных строк (шапка на строке 6, индекс 5), собирал уникальные значения колонки `niche_id`.
4. **insight.md**: брал префикс до `_insight.md`; размер через `os.path.getsize` в KB.
5. **wiki html**: маппил имена файлов формата `ZEREK_*.html` на niche_id через явный словарь (CamelCase → UPPERCASE + отдельные случаи типа `BrowLash` → `BROW` + `LASH`, `RepairPhone` → `REPAIR_PHONE`). Файл `ZEREK_Epilation.html` — общее wiki «эпиляция и депиляция», не сопоставлен с конкретным niche_id в yaml, учтён как «неприсоединённый wiki».

## Таблица ниш

| niche_id | name_rus | в yaml | available | per-niche xlsx | 08 rows | insight md | wiki html | Что нужно для запуска в Quick Check |
|---|---|---|---|---|---|---|---|---|
| `ACCOUNTING` | Бухгалтерский аутсорсинг | ✓ | ✗ | ✗ | ✓ | ✓ (25.7 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `AUTOPARTS` | Автозапчасти | ✓ | ✗ | ✗ | ✓ | ✓ (20.6 KB) | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать wiki-обзор |
| `AUTOSERVICE` | Автосервис | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (21.5 KB) | ✓ | ничего, готово к запуску |
| `BAKERY` | Пекарня | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (16.8 KB) | ✗ | создать wiki-обзор |
| `BARBER` | Барбершоп | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✗ | ✓ | создать insight.md для Block 9 |
| `BEAUTY` | Салон красоты | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `BROW` | Брови и ресницы | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (18.0 KB) | ✓ | ничего, готово к запуску |
| `BUBBLETEA` | Островок напитков | ✓ | ✗ | ✗ | ✓ | ✓ (22.5 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `BUILDMAT` | Строительные материалы | ✓ | ✗ | ✗ | ✓ | ✓ (20.4 KB) | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать wiki-обзор |
| `CANTEEN` | Столовая | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (17.6 KB) | ✓ | ничего, готово к запуску |
| `CARGO` | Грузоперевозки | ✓ | ✗ | ✗ | ✓ | ✓ (12.1 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `CARPETCLEAN` | Чистка ковров | ✓ | ✗ | ✗ | ✓ | ✓ (24.7 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `CARWASH` | Автомойка | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✗ | ✓ | создать insight.md для Block 9 |
| `CATERING` | Кейтеринг | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `CLEAN` | Клининг | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✗ | ✓ | создать insight.md для Block 9 |
| `COFFEE` | Кофейня | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✗ | ✓ | создать insight.md для Block 9 |
| `COMPCLUB` | Компьютерный клуб | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (22.7 KB) | ✗ | создать wiki-обзор |
| `CONFECTION` | Кондитерская | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (17.5 KB) | ✓ | ничего, готово к запуску |
| `COSMETOLOGY` | Косметология | ✓ | ✗ | ✗ | ✓ | ✓ (19.1 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `CROSSFIT` | Кроссфит | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `DENTAL` | Стоматология | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (19.3 KB) | ✓ | ничего, готово к запуску |
| `DETAILING` | Детейлинг | ✓ | ✗ | ✗ | ✓ | ✓ (25.4 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `DONER` | Донерная | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✗ | ✓ | создать insight.md для Block 9 |
| `DRIVING` | Автошкола | ✓ | ✗ | ✗ | ✓ | ✓ (15.2 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `DRYCLEAN` | Химчистка одежды | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (14.4 KB) | ✓ | ничего, готово к запуску |
| `EVALUATION` | Оценочные услуги | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `FASTFOOD` | Фастфуд | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (18.8 KB) | ✓ | ничего, готово к запуску |
| `FITNESS` | Фитнес-клуб | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (21.2 KB) | ✓ | ничего, готово к запуску |
| `FLOWERS` | Цветочный магазин | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (18.0 KB) | ✓ | ничего, готово к запуску |
| `FOOTBALL_SCHOOL` | Футбольная школа | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `FRUITSVEGS` | Овощи и фрукты | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (17.5 KB) | ✓ | ничего, готово к запуску |
| `FURNITURE` | Производство корпусной мебели | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (15.3 KB) | ✓ | ничего, готово к запуску |
| `GROCERY` | Продуктовый магазин | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✗ | ✗ | создать insight.md для Block 9, создать wiki-обзор |
| `GROUP_FITNESS` | Групповой фитнес | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `HOTEL` | Хостел | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9, создать wiki-обзор |
| `KIDSCENTER` | Детский центр | ✓ | ✗ | ✗ | ✓ | ✓ (23.1 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `KINDERGARTEN` | Частный детский сад | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (15.6 KB) | ✓ | ничего, готово к запуску |
| `LANGUAGES` | Языковая школа | ✓ | ✗ | ✗ | ✓ | ✓ (11.6 KB) | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать wiki-обзор |
| `LASH` | Ресницы | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (19.7 KB) | ✓ | ничего, готово к запуску |
| `LAUNDRY` | Прачечная | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9, создать wiki-обзор |
| `LOFTFURNITURE` | Производство лофт-мебели | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `MANICURE` | Маникюр | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (14.4 KB) | ✓ | ничего, готово к запуску |
| `MARTIAL_ARTS` | Единоборства | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `MASSAGE` | Массажный салон | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (18.3 KB) | ✓ | ничего, готово к запуску |
| `MEATSHOP` | Мясная лавка | ✓ | ✗ | ✗ | ✓ | ✓ (35.4 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `NOTARY` | Нотариус | ✓ | ✗ | ✗ | ✓ | ✗ | ✓ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9 |
| `OPTICS` | Оптика | ✓ | ✗ | ✗ | ✓ | ✓ (19.2 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `PETSHOP` | Зоомагазин | ✓ | ✗ | ✗ | ✓ | ✓ (11.0 KB) | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать wiki-обзор |
| `PHARMACY` | Аптека | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (13.0 KB) | ✓ | ничего, готово к запуску |
| `PHOTO` | Фотостудия | ✓ | ✗ | ✗ | ✓ | ✓ (23.2 KB) | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать wiki-обзор |
| `PIZZA` | Пиццерия | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (15.9 KB) | ✓ | ничего, готово к запуску |
| `PRINTING` | Типография | ✓ | ✗ | ✗ | ✓ | ✗ | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать insight.md для Block 9, создать wiki-обзор |
| `PVZ` | Пункт выдачи заказов | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (11.4 KB) | ✓ | ничего, готово к запуску |
| `REALTOR` | Риэлторские услуги | ✓ | ✗ | ✗ | ✓ | ✓ (13.3 KB) | ✓ | создать per-niche xlsx с FINANCIALS/STAFF |
| `REPAIR_PHONE` | Ремонт телефонов | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (24.0 KB) | ✓ | ничего, готово к запуску |
| `SEMIFOOD` | Полуфабрикаты | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (18.2 KB) | ✓ | ничего, готово к запуску |
| `SUGARING` | Шугаринг | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (20.2 KB) | ✗ | создать wiki-обзор |
| `SUSHI` | Суши | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (16.9 KB) | ✓ | ничего, готово к запуску |
| `TAILOR` | Ателье | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (11.3 KB) | ✓ | ничего, готово к запуску |
| `TIRESERVICE` | Шиномонтаж | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (15.5 KB) | ✗ | создать wiki-обзор |
| `WATERPLANT` | Розлив воды | ✓ | ✓ | ✓ FINANCIALS✓ STAFF✓ | ✓ | ✓ (19.5 KB) | ✓ | ничего, готово к запуску |
| `YOGA` | Йога-студия | ✓ | ✗ | ✗ | ✓ | ✓ (22.7 KB) | ✗ | создать per-niche xlsx с FINANCIALS/STAFF, создать wiki-обзор |

## Сводка

- Всего уникальных niche_id в проекте: **62**
- Готовых к запуску в Quick Check (yaml=✓, available=✓, per-niche xlsx=✓ FINANCIALS/STAFF, 08=✓, insight=✓): **27**
  - `AUTOSERVICE`, `BAKERY`, `BROW`, `CANTEEN`, `COMPCLUB`, `CONFECTION`, `DENTAL`, `DRYCLEAN`, `FASTFOOD`, `FITNESS`, `FLOWERS`, `FRUITSVEGS`, `FURNITURE`, `KINDERGARTEN`, `LASH`, `MANICURE`, `MASSAGE`, `PHARMACY`, `PIZZA`, `PVZ`, `REPAIR_PHONE`, `SEMIFOOD`, `SUGARING`, `SUSHI`, `TAILOR`, `TIRESERVICE`, `WATERPLANT`
- Нужна только per-niche xlsx: **17** — `ACCOUNTING`, `AUTOPARTS`, `BUBBLETEA`, `BUILDMAT`, `CARGO`, `CARPETCLEAN`, `COSMETOLOGY`, `DETAILING`, `DRIVING`, `KIDSCENTER`, `LANGUAGES`, `MEATSHOP`, `OPTICS`, `PETSHOP`, `PHOTO`, `REALTOR`, `YOGA`
- Нужен только insight.md: **6** — `BARBER`, `CARWASH`, `CLEAN`, `COFFEE`, `DONER`, `GROCERY`
- Нужно всё создавать (нет ни per-niche xlsx, ни insight, ни строк в 08): **0** — нет
- В wiki есть обзор, но ниши нет в yaml: **0** — нет
- Ниши в yaml без wiki: **14** — `AUTOPARTS`, `BAKERY`, `BUILDMAT`, `COMPCLUB`, `GROCERY`, `HOTEL`, `LANGUAGES`, `LAUNDRY`, `PETSHOP`, `PHOTO`, `PRINTING`, `SUGARING`, `TIRESERVICE`, `YOGA`
- Ниши где available=✓, но per-niche xlsx отсутствует / FINANCIALS пуст (ломают Quick Check): **0** — нет

## Примечание

Файл `wiki/kz/ZEREK_Epilation.html` — обзорная страница «эпиляция и депиляция» без прямого соответствия одному `niche_id` в yaml (близкая по смыслу `SUGARING` — лишь частный случай). Учтён как «неприсоединённый wiki-лид-магнит».