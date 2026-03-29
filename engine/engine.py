"""
ZEREK Quick Check Engine v1.0
Расчётный движок для генерации отчёта Quick Check.
"""

import pandas as pd
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

# ─────────────────────────────────────────────
# 1. ЗАГРУЗКА БАЗЫ ДАННЫХ
# ─────────────────────────────────────────────

class ZerekDB:
    """Единожды загружает все 19 файлов базы данных."""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self._load()

    def _xl(self, filename: str, sheet: str, header: int) -> pd.DataFrame:
        path = os.path.join(self.data_dir, filename)
        return pd.read_excel(path, sheet_name=sheet, header=header)

    def _load(self):
        # 01 — Города
        self.cities = self._xl("01_cities.xlsx", "Города", 4)

        # 02 — Зарплаты по регионам (для коэф.)
        self.wages_region = self._xl("02_wages_by_city.xlsx", "Зарплаты по регионам", 5)

        # 05 — Налоговые режимы
        self.tax_regimes = self._xl("05_tax_regimes.xlsx", "Рекомендации по нишам", 4)

        # 07 — Ниши
        self.niches = self._xl("07_niches.xlsx", "Ниши", 5)

        # 08 — Форматы
        self.formats = self._xl("08_niche_formats.xlsx", "Форматы", 5)

        # 09 — Юнит-экономика (главный лист для движка)
        self.unit_econ = self._xl("09_unit_economics.xlsx", "Сводка для движка", 5)
        self.unit_econ_full = self._xl("09_unit_economics.xlsx", "Юнит-экономика", 5)

        # 10 — CAPEX
        self.capex_totals = self._xl("10_capex.xlsx", "Итоги по форматам", 5)
        self.capex_items  = self._xl("10_capex.xlsx", "CAPEX по форматам", 5)
        self.capex_errors = self._xl("10_capex.xlsx", "Частые ошибки при планировании", 4)

        # 11 — Аренда
        self.rent = self._xl("11_rent_benchmarks.xlsx", "Калькулятор для движка", 5)
        self.rent_tips = self._xl("11_rent_benchmarks.xlsx", "Советы по локации", 4)

        # 12 — Штат и ФОТ
        self.staff_fot = self._xl("12_staff_templates.xlsx", "Сводка ФОТ", 4)
        self.staff_detail = self._xl("12_staff_templates.xlsx", "Штат по форматам", 5)

        # 13 — Макродинамика
        self.inflation = self._xl("13_macro_dynamics.xlsx", "Инфляция по регионам", 5)
        self.kei = self._xl("13_macro_dynamics.xlsx", "Индекс КЭИ", 5)

        # 14 — Конкуренты
        self.competitors = self._xl("14_competitors.xlsx", "Конкуренты по городам", 5)

        # 15 — Паттерны закрытий
        self.failure_patterns = self._xl("15_failure_cases.xlsx", "Паттерны по нишам", 5)

        # 17 — Разрешения
        self.permits = self._xl("17_permits.xlsx", "Разрешения и лицензии", 5)

        # 18 — Поведение потребителей
        self.consumer = self._xl("18_consumer_behavior.xlsx", "Поведение потребителей", 5)

        # 19 — Инфляция по нишам
        self.inflation_niche = self._xl("19_inflation_by_niche.xlsx", "Прогноз роста OPEX", 5)

        print("✅ База данных загружена.")


# ─────────────────────────────────────────────
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ─────────────────────────────────────────────

def get_city(db: ZerekDB, city_id: str) -> dict:
    row = db.cities[db.cities["city_id"] == city_id].iloc[0]
    return row.to_dict()

def get_unit_econ(db: ZerekDB, format_id: str) -> dict:
    row = db.unit_econ[db.unit_econ["format_id"] == format_id].iloc[0]
    return row.to_dict()

def get_unit_econ_full(db: ZerekDB, format_id: str) -> dict:
    row = db.unit_econ_full[db.unit_econ_full["format_id"] == format_id].iloc[0]
    return row.to_dict()

def get_capex(db: ZerekDB, format_id: str) -> dict:
    rows = db.capex_totals[db.capex_totals["format_id"] == format_id]
    if rows.empty:
        # Берём ближайший по нише
        niche = format_id.split("_")[0]
        rows = db.capex_totals[db.capex_totals["niche_id"] == niche]
    row = rows.iloc[0]
    return row.to_dict()

def get_rent_median(db: ZerekDB, city_id: str, loc_type: str) -> tuple:
    """Возвращает (медиана ₸/м², коммуналка ₸/м²)"""
    df = db.rent
    # Точное совпадение
    rows = df[(df["city_id"] == city_id) & (df["Тип локации"].str.contains(loc_type, na=False))]
    if rows.empty:
        # Fallback — любая строка по городу
        rows = df[df["city_id"] == city_id]
    if rows.empty:
        return 5000, 500  # дефолт
    row = rows.iloc[0]
    return row["Медиана (₸/м²/мес)"], row["Коммуналка (₸/м²/мес)"]

def get_fot(db: ZerekDB, format_id: str, city_id: str) -> int:
    """Возвращает ФОТ с налогами работодателя для указанного города."""
    rows = db.staff_fot[db.staff_fot["format_id"] == format_id]
    if rows.empty:
        return 0
    row = rows.iloc[0]
    # Определяем город
    big_cities = ["ALA", "AST", "SHY"]
    mid_cities = ["AKT", "ATY", "AKA", "URA", "KZO"]
    if city_id in big_cities:
        fot_gross = row.get("ФОТ gross Алматы (₸)", 0)
        # Считаем налоги работодателя ~6.5%
        return int(fot_gross * 1.065)
    elif city_id in mid_cities:
        return int(row.get("Расход работодателя Актобе (с налогами ₸)", 0))
    else:
        fot_small = row.get("ФОТ малый город (₸)", 0)
        return int(fot_small * 1.065)

def get_city_wage_coef(db: ZerekDB, city_id: str) -> float:
    """Коэффициент зарплат города относительно Актобе (базовый)."""
    coefs = {
        "ALA": 1.35, "AST": 1.32, "SHY": 0.95,
        "AKT": 1.00, "ATY": 1.40, "AKA": 1.38,
        "URA": 0.92, "TAR": 0.82, "PAV": 0.95,
        "OSK": 0.93, "KOS": 0.87, "KZO": 0.90,
        "SEM": 0.88, "PET": 0.78, "KOK": 0.80,
    }
    return coefs.get(city_id, 1.00)

def get_inflation_region(db: ZerekDB, city_id: str) -> float:
    """Инфляция по региону города (февраль 2026)."""
    city_to_region = {
        "ALA": "г. Алматы", "AST": "г. Астана", "SHY": "г. Шымкент",
        "AKT": "Актюбинская", "ATY": "Атырауская", "AKA": "Мангистауская",
        "URA": "Западно-Казахстанская", "TAR": "Жамбылская", "PAV": "Павлодарская",
        "OSK": "Восточно-Казахстанская", "KOS": "Костанайская", "KZO": "Кызылординская",
        "SEM": "Абай", "PET": "Северо-Казахстанская", "KOK": "Акмолинская",
    }
    region = city_to_region.get(city_id, "Республика Казахстан")
    rows = db.inflation[db.inflation["Регион"] == region]
    if rows.empty:
        return 11.7  # общий КЗ
    return float(rows.iloc[0]["Инфляция фев 2026 (%)"])

def get_competitors_signal(db: ZerekDB, niche_id: str, city_id: str) -> dict:
    df = db.competitors
    rows = df[(df["niche_id"] == niche_id) & (df["city_id"] == city_id)]
    if rows.empty:
        # Берём по нише без города
        rows = df[df["niche_id"] == niche_id]
    if rows.empty:
        return {"уровень": 3, "сигнал": "⚠️ Нет данных по конкуренции", "кол_во": "н/д"}
    row = rows.iloc[0]
    sat = int(row["Уровень насыщения (1-5)"])
    signals = {
        1: "🟢 Очень низкая конкуренция — рынок свободен",
        2: "🟢 Умеренная конкуренция — есть место",
        3: "🟡 Рынок активен — нужна дифференциация",
        4: "🟠 Высокая конкуренция — нужна уникальная локация",
        5: "🔴 Рынок насыщен — высокий риск",
    }
    return {
        "уровень": sat,
        "сигнал": signals.get(sat, ""),
        "кол_во": row["Кол-во конкурентов (оценка)"],
        "лидеры": row.get("Лидеры рынка", ""),
    }

def get_failure_pattern(db: ZerekDB, niche_id: str) -> dict:
    rows = db.failure_patterns[db.failure_patterns["niche_id"] == niche_id]
    if rows.empty:
        return {}
    row = rows.iloc[0]
    return row.to_dict()

def get_tax_regime(db: ZerekDB, niche_id: str) -> dict:
    rows = db.tax_regimes[db.tax_regimes["niche_id"] == niche_id]
    if rows.empty:
        return {"Рекомендуемый режим": "Упрощённая декларация", "Регистрация": "ИП"}
    row = rows.iloc[0]
    return row.to_dict()

def get_consumer_behavior(db: ZerekDB, niche_id: str, city_id: str) -> dict:
    df = db.consumer
    rows = df[(df["niche_id"] == niche_id) & (df["city_id"] == city_id)]
    if rows.empty:
        rows = df[df["niche_id"] == niche_id]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()

def get_inflation_niche(db: ZerekDB, niche_id: str) -> dict:
    rows = db.inflation_niche[db.inflation_niche["niche_id"] == niche_id]
    if rows.empty:
        return {"Прогноз роста OPEX в целом %/год": 11.5}
    return rows.iloc[0].to_dict()

def get_permits(db: ZerekDB, niche_id: str) -> pd.DataFrame:
    df = db.permits
    return df[
        df["niche_id"].str.contains(niche_id, na=False) |
        (df["niche_id"] == "ALL")
    ]


# ─────────────────────────────────────────────
# 3. ЯДРО РАСЧЁТОВ
# ─────────────────────────────────────────────

SEASON_LABELS = ["Янв","Фев","Мар","Апр","Май","Июн",
                 "Июл","Авг","Сен","Окт","Ноя","Дек"]

def calc_revenue_monthly(ue: dict, month: int, razgon_month: int) -> int:
    """Выручка в конкретный месяц с учётом разгона и сезонности."""
    base = ue["Выручка/мес (₸)"]

    # Коэф. разгона
    razgon_coefs = {
        1: ue.get("Коэф. м1", 0.4),
        2: ue.get("Коэф. м2", 0.65),
        3: ue.get("Коэф. м3", 0.85),
    }
    razgon = razgon_coefs.get(razgon_month, 1.0)
    if razgon_month > int(ue.get("Разгон мес.", 3)):
        razgon = 1.0

    # Сезонный коэф. (month = 1-12)
    season_min_label = ue.get("Сезон. мин (месяц)", "Янв")
    season_max_label = ue.get("Сезон. макс (месяц)", "Дек")
    season_min_coef  = float(ue.get("Сезон. коэф. мин", 0.85))
    season_max_coef  = float(ue.get("Сезон. коэф. макс", 1.15))

    # Линейная интерполяция сезонности между мин и макс
    min_m = SEASON_LABELS.index(season_min_label) + 1 if season_min_label in SEASON_LABELS else 1
    max_m = SEASON_LABELS.index(season_max_label) + 1 if season_max_label in SEASON_LABELS else 12

    if month == min_m:
        season = season_min_coef
    elif month == max_m:
        season = season_max_coef
    else:
        # Простая аппроксимация: среднее
        season = (season_min_coef + season_max_coef) / 2 + \
                  (0.05 * ((month - min_m) % 12) / 6 - 0.05)
        season = max(season_min_coef, min(season_max_coef, season))

    return int(base * razgon * season)


def calc_cashflow(
    ue: dict,
    fot: int,
    rent_month: int,
    capex: int,
    tax_rate: float = 0.03,
    start_month: int = 1,   # календарный месяц открытия (1-12)
    months: int = 12,
) -> list:
    """
    Возвращает список dict по каждому месяцу:
    {month, rev, cogs, gross, fot, rent, util, marketing, other, tax, opex, profit, cumulative}
    """
    results = []
    cumulative = -capex  # стартуем с минусом CAPEX

    cogs_pct   = float(ue.get("COGS%", 30)) / 100
    util_pct   = 0.04   # коммуналка ~4% (нет отдельной колонки в сводке)
    mkt_pct    = 0.03   # маркетинг ~3%
    other_pct  = 0.02   # прочие ~2%

    for i in range(months):
        razgon_month = i + 1  # месяц с начала работы
        cal_month = ((start_month - 1 + i) % 12) + 1  # календарный месяц

        rev    = calc_revenue_monthly(ue, cal_month, razgon_month)
        cogs   = int(rev * cogs_pct)
        gross  = rev - cogs
        util   = int(rev * util_pct)
        mkt    = int(rev * mkt_pct)
        other  = int(rev * other_pct)
        tax    = int(rev * tax_rate)
        opex   = fot + rent_month + util + mkt + other + tax
        profit = gross - opex
        cumulative += profit

        results.append({
            "месяц": i + 1,
            "кал_месяц": SEASON_LABELS[cal_month - 1],
            "выручка": rev,
            "cogs": cogs,
            "валовая_прибыль": gross,
            "фот": fot,
            "аренда": rent_month,
            "коммуналка": util,
            "маркетинг": mkt,
            "прочие": other,
            "налог": tax,
            "opex": opex,
            "прибыль": profit,
            "нарастающий": cumulative,
        })

    return results


def calc_breakeven(ue: dict, fot: int, rent_month: int) -> dict:
    """Точка безубыточности в ₸ и единицах."""
    cogs_pct = float(ue.get("COGS%", 30)) / 100
    util_pct, mkt_pct, other_pct = 0.04, 0.03, 0.02
    tax_rate = 0.03

    # Постоянные расходы в месяц
    fixed = fot + rent_month

    # Переменные как % от выручки
    variable_pct = cogs_pct + util_pct + mkt_pct + other_pct + tax_rate

    # ТБ выручка = fixed / (1 - variable_pct)
    tb_rev = fixed / (1 - variable_pct)
    tb_units = tb_rev / float(ue.get("Чек (₸)", 1000))
    days = float(ue.get("Дней/мес", 26))
    tb_per_day = tb_units / days

    return {
        "тб_выручка": int(tb_rev),
        "тб_единиц_мес": int(tb_units),
        "тб_единиц_день": round(tb_per_day, 1),
        "текущий_трафик": float(ue.get("Трафик/день", 0)),
        "запас_прочности_%": round((float(ue.get("Трафик/день", 0)) - tb_per_day) / float(ue.get("Трафик/день", 1)) * 100, 1),
    }


def calc_payback(capex: int, cashflow: list) -> dict:
    """Месяц окупаемости из Cash Flow."""
    for cf in cashflow:
        if cf["нарастающий"] >= 0:
            return {"месяц": cf["месяц"], "статус": "✅ Окупается в горизонте 12 мес."}
    avg_profit = sum(cf["прибыль"] for cf in cashflow[-3:]) / 3
    if avg_profit > 0:
        extra = capex / avg_profit
        return {
            "месяц": round(12 + extra, 1),
            "статус": f"⚠️ Окупаемость ~{round(12 + extra, 1)} мес. — за горизонтом 12 мес."
        }
    return {"месяц": None, "статус": "🔴 Не окупается при текущих параметрах"}


def calc_tam_sam_som(city: dict, niche_id: str, competitors: dict) -> dict:
    """TAM/SAM/SOM по демографии города и конкурентной среде."""
    pop = int(city.get("Население всего (чел.)", 0))
    working = int(city.get("Трудоспособные 16-62 (чел.)", 0))
    men_1845 = int(city.get("Мужчины ~18-45 (оценка)", 0))
    women_1850 = int(city.get("Женщины ~18-50 (оценка)", 0))
    children = int(city.get("Дети 0-15 (чел.)", 0))

    # TAM — потенциальная аудитория по нише
    tam_map = {
        "COFFEE":  working,
        "DONER":   working,
        "CARWASH": men_1845,
        "CLEAN":   working,
        "GROCERY": pop,
        "PHARMA":  pop,
        "BARBER":  men_1845,
        "MANICURE": women_1850,
    }
    tam = tam_map.get(niche_id, working)

    # SAM — реально достижимый (с учётом радиуса 1-2 км)
    # Типовой охват одной точки: 2-5% от TAM города
    sam_pct_map = {
        "COFFEE": 0.03, "DONER": 0.04, "CARWASH": 0.05,
        "CLEAN": 0.08, "GROCERY": 0.03, "PHARMA": 0.03,
        "BARBER": 0.06, "MANICURE": 0.06,
    }
    sam_pct = sam_pct_map.get(niche_id, 0.04)
    sam = int(tam * sam_pct)

    # SOM — реалистичная доля с учётом конкуренции
    sat = competitors.get("уровень", 3)
    som_pct_map = {1: 0.30, 2: 0.25, 3: 0.15, 4: 0.10, 5: 0.07}
    som = int(sam * som_pct_map.get(sat, 0.15))

    return {
        "tam": tam,
        "tam_label": "потенциальная аудитория ниши",
        "sam": sam,
        "sam_label": "охват одной точки (радиус ~2 км)",
        "som": som,
        "som_label": "реалистичная доля с учётом конкуренции",
    }


# ─────────────────────────────────────────────
# 4. ГЛАВНАЯ ФУНКЦИЯ — ПОЛНЫЙ РАСЧЁТ
# ─────────────────────────────────────────────

def run_quick_check(
    db: ZerekDB,
    city_id: str,
    niche_id: str,
    format_id: str,
    area_m2: float,
    loc_type: str,       # "Спальный район стрит" / "Центр стрит 1 лин" / "ТЦ" / "Отдельное здание/бокс"
    capital: int,        # стартовый капитал пользователя в ₸
    rent_override: int = None,  # если пользователь знает аренду — указывает вручную
    start_month: int = 4,       # апрель по умолчанию
    capex_level: str = "стандарт",  # "эконом" / "стандарт" / "премиум"
) -> dict:
    """
    Запускает полный расчёт Quick Check.
    Возвращает структурированный словарь со всеми блоками отчёта.
    """

    # ── Шаг 1: Данные города ──
    city = get_city(db, city_id)

    # ── Шаг 2: Юнит-экономика формата ──
    ue = get_unit_econ(db, format_id)

    # ── Шаг 3: CAPEX ──
    capex_row = get_capex(db, format_id)
    capex_cols = {
        "эконом": "CAPEX эконом (₸)",
        "стандарт": "CAPEX стандарт (₸)",
        "премиум": "CAPEX премиум (₸)",
    }
    capex = int(capex_row.get(capex_cols[capex_level], 0))

    # Депозит аренды (2 мес.) добавляем к CAPEX
    rent_median, util_per_m2 = get_rent_median(db, city_id, loc_type)
    rent_month = rent_override if rent_override else int(area_m2 * rent_median)
    deposit = rent_month * 2
    capex_total = capex + deposit

    # ── Шаг 4: ФОТ ──
    fot = get_fot(db, format_id, city_id)
    if fot == 0:
        # Fallback: считаем из % в юнит-экономике
        fot = int(ue["Выручка/мес (₸)"] * float(ue.get("ФОТ%", 25)) / 100)

    # ── Шаг 5: Cash Flow 12 месяцев ──
    cashflow = calc_cashflow(
        ue=ue,
        fot=fot,
        rent_month=rent_month,
        capex=capex_total,
        start_month=start_month,
    )

    # ── Шаг 6: Точка безубыточности ──
    breakeven = calc_breakeven(ue, fot, rent_month)

    # ── Шаг 7: Окупаемость ──
    payback = calc_payback(capex_total, cashflow)

    # ── Шаг 8: TAM/SAM/SOM ──
    competitors = get_competitors_signal(db, niche_id, city_id)
    tam_sam_som = calc_tam_sam_som(city, niche_id, competitors)

    # ── Шаг 9: Капитал — достаточно? ──
    capital_gap = capital - capex_total
    capital_signal = (
        "✅ Капитала достаточно" if capital_gap >= 0
        else f"🔴 Не хватает {abs(capital_gap):,} ₸ (нужно {capex_total:,} ₸ с депозитом)"
    )

    # ── Шаг 10: Прогноз год 2 ──
    inf_niche = get_inflation_niche(db, niche_id)
    opex_growth = float(str(inf_niche.get("Прогноз роста OPEX в целом %/год", 11.5))
                        .replace("%","").strip()) / 100
    inf_region = get_inflation_region(db, city_id)
    avg_profit_y1 = sum(cf["прибыль"] for cf in cashflow) / 12
    avg_profit_y2 = avg_profit_y1 * (1 + 0.07) * (1 - opex_growth * 0.5)

    # ── Шаг 11: Паттерны рисков ──
    failure = get_failure_pattern(db, niche_id)
    tax_regime = get_tax_regime(db, niche_id)
    consumer = get_consumer_behavior(db, niche_id, city_id)
    permits = get_permits(db, niche_id)

    # ── Шаг 12: Сводные метрики ──
    total_rev_y1    = sum(cf["выручка"] for cf in cashflow)
    total_profit_y1 = sum(cf["прибыль"] for cf in cashflow)
    base_rev        = int(ue["Выручка/мес (₸)"])
    base_margin     = float(ue.get("Операц. маржа%", 0))

    return {
        # Входные параметры
        "input": {
            "city_id": city_id,
            "city_name": city.get("Город", ""),
            "niche_id": niche_id,
            "format_id": format_id,
            "area_m2": area_m2,
            "loc_type": loc_type,
            "capital": capital,
            "start_month": start_month,
            "capex_level": capex_level,
        },

        # Блок 1: Рынок
        "market": {
            "population": int(city.get("Население всего (чел.)", 0)),
            "working_age": int(city.get("Трудоспособные 16-62 (чел.)", 0)),
            "men_1845": int(city.get("Мужчины ~18-45 (оценка)", 0)),
            "women_1850": int(city.get("Женщины ~18-50 (оценка)", 0)),
            "growth_rate": city.get("Темп прироста 2025 %", 0),
            "tam_sam_som": tam_sam_som,
            "competitors": competitors,
        },

        # Блок 2: CAPEX
        "capex": {
            "оборудование_и_ремонт": capex,
            "депозит_аренды": deposit,
            "итого": capex_total,
            "капитал_пользователя": capital,
            "сигнал": capital_signal,
            "уровень": capex_level,
        },

        # Блок 3: Финансовая модель
        "financials": {
            "базовая_выручка_мес": base_rev,
            "чек": int(ue.get("Чек (₸)", 0)),
            "трафик_день": int(ue.get("Трафик/день", 0)),
            "cogs_pct": float(ue.get("COGS%", 0)),
            "fot_мес": fot,
            "аренда_мес": rent_month,
            "маржа_опер_pct": base_margin,
            "выручка_год1": total_rev_y1,
            "прибыль_год1": total_profit_y1,
            "прибыль_среднемес_год1": int(avg_profit_y1),
            "прибыль_среднемес_год2_прогноз": int(avg_profit_y2),
        },

        # Блок 4: Точка безубыточности
        "breakeven": breakeven,

        # Блок 5: Окупаемость
        "payback": payback,

        # Блок 6: Cash Flow 12 месяцев
        "cashflow": cashflow,

        # Блок 7: Макро
        "macro": {
            "инфляция_регион_%": inf_region,
            "рост_opex_прогноз_%": opex_growth * 100,
        },

        # Блок 8: Риски и паттерны
        "risks": {
            "паттерн_закрытий": failure,
            "разрешения": permits.to_dict("records"),
            "конкуренты": competitors,
        },

        # Блок 9: Рекомендации
        "recommendations": {
            "налоговый_режим": tax_regime,
            "поведение_клиентов": consumer,
            "советы_локация": [],
        },
    }
