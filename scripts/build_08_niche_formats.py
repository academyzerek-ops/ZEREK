"""
Builds data/kz/08_niche_formats.xlsx — fallback format catalog for niches that
don't (yet) have a per-niche niche_formats_{NICHE}.xlsx. The engine still
prefers the per-niche xlsx when present; this file only supplies defaults so
Quick Check v2 can render SOMETHING for every niche from the 58-roster.

Sheet «Форматы», header on row 6 (pandas header=5):
  niche_id | format_id | format_name | area_m2 | loc_type | capex_standard | class
"""
from __future__ import annotations

import os
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

# ---------------------------------------------------------------------------
# Formats dataset — 2-3 entries per niche.
#   (format_id_suffix, format_name, area_m2, loc_type, capex_standard, class_tag)
# class_tag:  ""  (нет градации)  |  "эконом"  |  "стандарт"  |  "премиум"
# ---------------------------------------------------------------------------

FORMATS = {
    # ---------- ОБЩЕПИТ ----------
    "BAKERY": [
        ("BAKERY_SMALL",    "Мини-пекарня с витриной",           45,  "street",          12000000, "эконом"),
        ("BAKERY_FULL",     "Пекарня-кафе",                      80,  "street",          22000000, "стандарт"),
        ("BAKERY_PRODUCTION","Производство + доставка B2B",     120, "own_building",    32000000, "премиум"),
    ],
    "CANTEEN": [
        ("CANTEEN_BC",      "Столовая в бизнес-центре",          90,  "business_center", 14000000, "стандарт"),
        ("CANTEEN_ENTER",   "Столовая при предприятии",         140, "own_building",    20000000, "стандарт"),
    ],
    "CATERING": [
        ("CATERING_HOME",   "Домашний кейтеринг",                35,  "home",             3000000, "эконом"),
        ("CATERING_STUDIO", "Студия-цех",                        80, "own_building",    15000000, "стандарт"),
        ("CATERING_EVENT",  "Крупный event-кейтеринг",          150, "own_building",    40000000, "премиум"),
    ],
    "COFFEE": [
        ("COFFEE_KIOSK",    "Островок / кофе с собой",          12, "tc",                6000000, "эконом"),
        ("COFFEE_CAFE",     "Кофейня-кафе",                     60, "street",           18000000, "стандарт"),
        ("COFFEE_SPECIAL",  "Specialty coffee",                 80, "street",           32000000, "премиум"),
    ],
    "CONFECTION": [
        ("CONFECT_HOME",    "Домашний кондитер",                20, "home",              1500000, "эконом"),
        ("CONFECT_WORKSHOP","Кондитерский цех",                 60, "street",           12000000, "стандарт"),
    ],
    "DONER": [
        ("DONER_TAKEOUT",   "Донерная навынос",                 18, "street",            5500000, "эконом"),
        ("DONER_CAFE",      "Донерная с залом",                 55, "street",           14000000, "стандарт"),
    ],
    "FASTFOOD": [
        ("FASTFOOD_TAKE",   "Формат take-away",                 25, "tc",                7000000, "эконом"),
        ("FASTFOOD_CAFE",   "Фастфуд с залом",                  70, "street",           18000000, "стандарт"),
    ],
    "PIZZA": [
        ("PIZZA_DELIVERY",  "Доставка пиццы",                   30, "street",            9000000, "эконом"),
        ("PIZZA_CAFE",      "Пиццерия с залом",                 80, "street",           22000000, "стандарт"),
    ],
    "SUSHI": [
        ("SUSHI_DELIVERY",  "Доставка суши",                    30, "street",            9000000, "эконом"),
        ("SUSHI_BAR",       "Суши-бар с залом",                 75, "street",           26000000, "стандарт"),
    ],
    "BUBBLETEA": [
        ("BUBBLE_KIOSK",    "Островок в ТЦ",                    10, "tc",                4500000, "эконом"),
        ("BUBBLE_CAFE",     "Бабл-ти с залом",                  40, "street",           12000000, "стандарт"),
    ],
    "MEATSHOP": [
        ("MEAT_SMALL",      "Небольшая лавка",                  25, "street",            5500000, "эконом"),
        ("MEAT_STANDARD",   "Полноценная мясная лавка",         50, "street",           12000000, "стандарт"),
    ],
    "FRUITSVEGS": [
        ("FV_KIOSK",        "Киоск",                            10, "market",            2500000, "эконом"),
        ("FV_STORE",        "Овощной магазин",                  40, "street",            7000000, "стандарт"),
    ],
    "SEMIFOOD": [
        ("SEMI_HOME",       "Домашнее производство",            25, "home",              2500000, "эконом"),
        ("SEMI_WORKSHOP",   "Мини-цех",                         70, "own_building",     14000000, "стандарт"),
    ],
    "WATERPLANT": [
        ("WATER_MINI",      "Мини-линия розлива",              100, "own_building",     18000000, "стандарт"),
        ("WATER_FULL",      "Завод розлива",                   300, "own_building",     55000000, "премиум"),
    ],
    "PETSHOP": [
        ("PET_SMALL",       "Зоомагазин мини",                  30, "street",            5000000, "эконом"),
        ("PET_FULL",        "Полноценный зоомагазин",           80, "tc",               14000000, "стандарт"),
    ],

    # ---------- БЬЮТИ ----------
    "BARBER": [
        ("BARBER_SOLO",     "Барбер на одно кресло",            15, "street",            1800000, "эконом"),
        ("BARBER_STANDARD", "Барбершоп 3-5 кресел",             45, "street",            7500000, "стандарт"),
        ("BARBER_PREMIUM",  "Премиум барбершоп",                80, "street",           18000000, "премиум"),
    ],
    "BEAUTY": [
        ("BEAUTY_MINI",     "Салон на 3 кресла",                40, "street",            6000000, "эконом"),
        ("BEAUTY_STANDARD", "Полноценный салон",                80, "street",           16000000, "стандарт"),
        ("BEAUTY_PREMIUM",  "Премиум салон",                   120, "street",           32000000, "премиум"),
    ],
    "MANICURE": [
        ("NAIL_HOME",       "На дому",                          10, "home",              350000, "эконом"),
        ("NAIL_CABINET",    "Кабинет 1-2 мастера",              20, "street",           2200000, "стандарт"),
        ("NAIL_SALON",      "Студия маникюра",                  50, "street",           9000000, "премиум"),
    ],
    "BROW": [
        ("BROW_HOME",       "На дому",                           8, "home",              300000, "эконом"),
        ("BROW_CABINET",    "Свой кабинет",                     18, "street",           2000000, "стандарт"),
    ],
    "LASH": [
        ("LASH_HOME",       "На дому",                           8, "home",              300000, "эконом"),
        ("LASH_CABINET",    "Свой кабинет",                     18, "street",           2000000, "стандарт"),
    ],
    "SUGARING": [
        ("SUGAR_HOME",      "На дому",                          10, "home",              350000, "эконом"),
        ("SUGAR_CABINET",   "Кабинет шугаринга",                20, "street",           2500000, "стандарт"),
    ],
    "MASSAGE": [
        ("MASSAGE_HOME",    "Выезд на дом",                     10, "home",              300000, "эконом"),
        ("MASSAGE_STUDIO",  "Массажная студия",                 40, "street",            7000000, "стандарт"),
    ],
    "COSMETOLOGY": [
        ("COSM_CABINET",    "Кабинет косметолога",              25, "street",            6000000, "стандарт"),
        ("COSM_CLINIC",     "Мини-клиника",                     60, "street",           22000000, "премиум"),
    ],

    # ---------- ЗДОРОВЬЕ ----------
    "DENTAL": [
        ("DENTAL_1CH",      "Кабинет на 1 кресло",              30, "street",           12000000, "эконом"),
        ("DENTAL_CLINIC",   "Клиника на 3-5 кресел",            80, "street",           45000000, "стандарт"),
    ],
    "PHARMACY": [
        ("PHARM_SMALL",     "Небольшая аптека",                 40, "residential_area", 10000000, "стандарт"),
        ("PHARM_FULL",      "Сетевая аптека",                   80, "street",           22000000, "стандарт"),
    ],
    "OPTICS": [
        ("OPTICS_TC",       "Оптика в ТЦ",                      40, "tc",               16000000, "стандарт"),
        ("OPTICS_STREET",   "Оптика-улица с залом",             70, "street",           24000000, "премиум"),
    ],

    # ---------- СПОРТ ----------
    "FITNESS": [
        ("FIT_STUDIO",      "Студия 100 м²",                   100, "residential_area", 14000000, "эконом"),
        ("FIT_CLUB",        "Фитнес-клуб 500 м²",              500, "own_building",     80000000, "стандарт"),
    ],
    "YOGA": [
        ("YOGA_STUDIO",     "Йога-студия",                      80, "residential_complex", 6000000, "стандарт"),
    ],
    "HOTEL": [
        ("HOTEL_HOSTEL",    "Хостел 20 койко-мест",            150, "own_building",     18000000, "эконом"),
        ("HOTEL_3STAR",     "Мини-отель 2-3★",                 400, "own_building",    90000000, "стандарт"),
        ("HOTEL_4STAR",     "Отель 4-5★",                     1200, "own_building",   320000000, "премиум"),
    ],

    # ---------- УСЛУГИ ----------
    "AUTOSERVICE": [
        ("AUTOSERV_1POST",  "Автосервис 1-2 поста",             80, "highway",           5000000, "эконом"),
        ("AUTOSERV_FULL",   "СТО 3-6 постов",                  200, "highway",          20000000, "стандарт"),
    ],
    "TIRESERVICE": [
        ("TIRE_SMALL",      "Шиномонтаж 1 пост",                40, "highway",           3000000, "эконом"),
        ("TIRE_STANDARD",   "Шиномонтаж 2-3 поста",             80, "highway",           8000000, "стандарт"),
    ],
    "CARWASH": [
        ("WASH_SELF",       "Самомойка",                       250, "highway",          28000000, "эконом"),
        ("WASH_MANUAL",     "Ручная мойка 2-3 поста",          120, "highway",          14000000, "стандарт"),
        ("WASH_PREMIUM",    "Премиум автомойка",               160, "own_building",     32000000, "премиум"),
    ],
    "DETAILING": [
        ("DETAIL_BOX1",     "Одиночный бокс",                   80, "highway",           6500000, "стандарт"),
        ("DETAIL_STUDIO",   "Детейлинг-студия",                150, "own_building",     22000000, "премиум"),
    ],
    "AUTOPARTS": [
        ("PARTS_STORE",     "Магазин автозапчастей",            80, "street",           12000000, "стандарт"),
    ],
    "CLEAN": [
        ("CLEAN_SOLO",      "Клининг-ИП",                       10, "home",              500000, "эконом"),
        ("CLEAN_TEAM",      "Клининговая бригада",              60, "business_center",   4000000, "стандарт"),
    ],
    "CARPETCLEAN": [
        ("CARPET_WORKSHOP", "Цех чистки ковров",               120, "own_building",     10000000, "стандарт"),
    ],
    "DRYCLEAN": [
        ("DRY_APPR",        "Приёмка / пункт",                  20, "residential_complex", 2500000, "эконом"),
        ("DRY_FULL",        "Химчистка с оборудованием",        80, "street",           18000000, "стандарт"),
    ],
    "LAUNDRY": [
        ("LAUNDRY_SELF",    "Прачечная самообслуживания",       60, "residential_complex", 14000000, "стандарт"),
        ("LAUNDRY_FULL",    "Промышленная прачечная",          200, "own_building",     42000000, "премиум"),
    ],
    "KINDERGARTEN": [
        ("KG_HOME",         "Домашний сад 8-12 детей",          70, "residential_area",  2500000, "эконом"),
        ("KG_STANDARD",     "Частный сад 30+ детей",           200, "own_building",     18000000, "стандарт"),
    ],
    "KIDSCENTER": [
        ("KIDS_STUDIO",     "Развивающая студия",               80, "residential_area",  5000000, "стандарт"),
        ("KIDS_LARGE",      "Центр с несколькими программами", 200, "street",          16000000, "премиум"),
    ],
    "LANGUAGES": [
        ("LANG_HOME",       "Репетиторство из дома",            15, "home",              400000, "эконом"),
        ("LANG_MICRO",      "Мини-школа на 2-3 аудитории",      60, "business_center",   3500000, "стандарт"),
        ("LANG_FULL",       "Языковая школа",                  150, "street",           14000000, "премиум"),
    ],
    "DRIVING": [
        ("DRIVE_SMALL",     "Автошкола 2-3 машины",             50, "street",           12000000, "эконом"),
        ("DRIVE_FULL",      "Автошкола 8+ машин",              120, "street",           32000000, "стандарт"),
    ],
    "CARGO": [
        ("CARGO_SOLO",      "1 машина",                          0, "home",              8000000, "эконом"),
        ("CARGO_FLEET",     "Парк 5+ машин",                     0, "own_building",     45000000, "стандарт"),
    ],
    "PVZ": [
        ("PVZ_SMALL",       "ПВЗ 15 м²",                        15, "street",            2500000, "стандарт"),
        ("PVZ_FULL",        "ПВЗ 35 м²",                        35, "residential_complex", 4500000, "стандарт"),
    ],
    "REPAIR_PHONE": [
        ("REPAIR_POINT",    "Точка ремонта",                    12, "tc",                1800000, "эконом"),
        ("REPAIR_STUDIO",   "Мастерская",                       25, "street",            4500000, "стандарт"),
    ],
    "TAILOR": [
        ("TAILOR_HOME",     "Ателье на дому",                   15, "home",               500000, "эконом"),
        ("TAILOR_MINI",     "Мини-ателье",                      25, "street",            2500000, "стандарт"),
        ("TAILOR_FULL",     "Полное ателье",                    60, "street",            9000000, "премиум"),
    ],
    "PHOTO": [
        ("PHOTO_HOME",      "Выездной фотограф",                 0, "home",              1500000, "эконом"),
        ("PHOTO_STUDIO",    "Фотостудия с интерьерами",         60, "street",           10000000, "стандарт"),
    ],
    "FLOWERS": [
        ("FLOWER_KIOSK",    "Цветочный киоск",                  12, "street",            2500000, "эконом"),
        ("FLOWER_STUDIO",   "Цветочная студия",                 40, "street",            8000000, "стандарт"),
    ],
    "PRINTING": [
        ("PRINT_SMALL",     "Мини-типография",                  40, "street",            6500000, "стандарт"),
        ("PRINT_FULL",      "Полноценная типография",          150, "own_building",     38000000, "премиум"),
    ],

    # ---------- ТОРГОВЛЯ ----------
    "GROCERY": [
        ("GROC_KIOSK",      "Киоск / минимаркет",               25, "residential_area",  3500000, "эконом"),
        ("GROC_STANDARD",   "Минимаркет",                       80, "residential_area", 14000000, "стандарт"),
        ("GROC_SUPER",      "Супермаркет",                     250, "street",           48000000, "премиум"),
    ],
    "BUILDMAT": [
        ("BUILD_SMALL",     "Небольшой магазин",                80, "street",           12000000, "стандарт"),
        ("BUILD_FULL",      "Полноценный строймаркет",         250, "own_building",     48000000, "премиум"),
    ],
    "COMPCLUB": [
        ("CC_SMALL",        "Клуб 10-15 мест",                  80, "residential_area", 18000000, "стандарт"),
        ("CC_LARGE",        "Киберарена 30+ мест",             200, "street",           60000000, "премиум"),
    ],

    # ---------- ПРОИЗВОДСТВО МЕБЕЛИ ----------
    "FURNITURE": [
        ("FURN_SMALL",      "Цех мебели на заказ",             120, "own_building",     14000000, "стандарт"),
        ("FURN_FULL",       "Мебельное производство",          300, "own_building",     42000000, "премиум"),
    ],
    "LOFTFURNITURE": [
        ("LOFT_SMALL",      "Мастерская лофт-мебели",          120, "own_building",     12000000, "стандарт"),
        ("LOFT_FULL",       "Цех металлоконструкций",          250, "own_building",     32000000, "премиум"),
    ],

    # ---------- B2B-УСЛУГИ ----------
    "ACCOUNTING": [
        ("ACC_SOLO",        "Самозанятый бухгалтер",             0, "home",              250000, "эконом"),
        ("ACC_AGENCY",      "Бухгалтерское агентство",          40, "business_center",   3500000, "стандарт"),
    ],
    "REALTOR": [
        ("REAL_SOLO",       "Независимый риэлтор",               0, "home",              200000, "эконом"),
        ("REAL_AGENCY",     "Агентство недвижимости",           50, "business_center",   4500000, "стандарт"),
    ],
    "NOTARY": [
        ("NOTARY_OFFICE",   "Нотариальная контора",             30, "business_center",   5500000, "стандарт"),
    ],
    "EVALUATION": [
        ("EVAL_SOLO",       "Оценщик-самозанятый",               0, "home",              400000, "эконом"),
        ("EVAL_AGENCY",     "Оценочная компания",               30, "business_center",   3000000, "стандарт"),
    ],
}


def build_rows():
    out = []
    for niche_id, lst in FORMATS.items():
        for fid, fname, area, loc, capex, cls in lst:
            out.append({
                "niche_id": niche_id,
                "format_id": fid,
                "format_name": fname,
                "area_m2": area,
                "loc_type": loc,
                "capex_standard": capex,
                "class": cls,
            })
    return out


def write_workbook(out_path: str) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Форматы"

    title_font = Font(bold=True, size=14)
    ws.cell(row=1, column=1, value="ZEREK — Форматы ниш (fallback catalog).").font = title_font
    ws.cell(row=2, column=1, value="Используется Quick Check v2 когда в per-niche xlsx нет форматов.")
    ws.cell(row=3, column=1, value=f"Ниш с форматами: {len(FORMATS)}")
    ws.cell(row=4, column=1, value="class: эконом / стандарт / премиум ('' если без градации).")

    headers = ["niche_id", "format_id", "format_name", "area_m2", "loc_type",
               "capex_standard", "class"]
    header_fill = PatternFill(start_color="1F1F2E", end_color="1F1F2E", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx, h in enumerate(headers, start=1):
        c = ws.cell(row=6, column=col_idx, value=h)
        c.font = header_font
        c.fill = header_fill

    for i, row in enumerate(build_rows(), start=7):
        for j, h in enumerate(headers, start=1):
            ws.cell(row=i, column=j, value=row.get(h, ""))

    widths = {1: 16, 2: 22, 3: 40, 4: 10, 5: 18, 6: 18, 7: 12}
    for col, w in widths.items():
        ws.column_dimensions[ws.cell(row=6, column=col).column_letter].width = w

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    wb.save(out_path)
    total = sum(len(v) for v in FORMATS.values())
    print(f"✅ {out_path} — {len(FORMATS)} ниш, {total} форматов")


if __name__ == "__main__":
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = os.path.join(repo_root, "data", "kz", "08_niche_formats.xlsx")
    write_workbook(out)
