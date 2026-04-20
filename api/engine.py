"""
ZEREK Quick Check Engine v3.0
Читает данные из niche_formats_{NICHE}.xlsx (12 листов).
Общие файлы: 01_cities, 05_tax_regimes, 07_niches, 11_rent, 13_macro, 14_competitors, 15_failure, 17_permits.
Пустые ячейки = дефолт (без ошибок).
"""

import pandas as pd
import os
import glob
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kz")
FORMATS_DIR = os.path.join(DATA_DIR, "niches")

SEASON_LABELS = ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]
MRP_2026 = 4325
MZP_2026 = 85000

# Дефолты для пустых ячеек
DEFAULTS = {
    'cogs_pct': 0.30,
    'margin_pct': 0.70,
    'deposit_months': 2,
    'loss_pct': 0.02,
    'sez_month': 0,
    'rampup_months': 3,
    'rampup_start_pct': 0.50,
    'repeat_pct': 0.40,
    'traffic_growth_yr': 0.07,
    'check_growth_yr': 0.08,
    'rent_growth_yr': 0.10,
    'fot_growth_yr': 0.08,
    'inflation_yr': 0.10,
    'deprec_years': 7,
    'fot_multiplier': 1.175,  # налоги работодателя
}

# Ценовые коэффициенты по городам (база = Актобе 1.00)
CITY_CHECK_COEF = {
    'almaty': 1.05, 'astana': 1.05, 'atyrau': 1.03,
    'aktobe': 1.00, 'karaganda': 1.00, 'uralsk': 1.00,
    'ust_kamenogorsk': 1.00, 'aktau': 1.00,
    'shymkent': 0.97, 'pavlodar': 0.97, 'kostanay': 0.97,
    'semey': 0.95, 'taraz': 0.95, 'petropavlovsk': 0.95, 'kyzylorda': 0.95,
}

def get_city_check_coef(city_id: str) -> float:
    """Ценовой коэффициент города. Алматы/Астана +5%, мелкие -5%."""
    return CITY_CHECK_COEF.get(city_id, 1.00)

def _safe(val, default=0):
    """Безопасное чтение — None/NaN → дефолт."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return val

def _safe_int(val, default=0):
    return int(_safe(val, default))

def _safe_float(val, default=0.0):
    return float(_safe(val, default))


# ═══════════════════════════════════════════════
# 1. ЗАГРУЗКА БАЗЫ ДАННЫХ v3
# ═══════════════════════════════════════════════

class ZerekDB:
    """Загружает общие файлы + файлы ниш из data/formats/."""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.formats_dir = os.path.join(data_dir, "niches")
        self.niche_data = {}  # {niche_id: {sheet_name: DataFrame}}
        self._load_common()
        self._load_niches()

    def _xl(self, filename: str, sheet: str = None, header: int = 0) -> pd.DataFrame:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            print(f"⚠️ Файл не найден: {filename}")
            return pd.DataFrame()
        try:
            if sheet:
                return pd.read_excel(path, sheet_name=sheet, header=header)
            return pd.read_excel(path, header=header)
        except Exception as e:
            print(f"⚠️ Ошибка чтения {filename}/{sheet}: {e}")
            return pd.DataFrame()

    def _load_common(self):
        """Загрузка общих файлов + Quick Check v2 конфиг (07_niches, 08_niche_formats)."""
        self.cities = self._xl("01_cities.xlsx", "Города", 4)
        # Quick Check v2 config (optional — если файлов нет, возвращаются дефолты)
        self.niches_config = self._xl("07_niches.xlsx", "Ниши", 5)
        self.niches_questions = self._xl("07_niches.xlsx", "Специфичные вопросы", 5)
        self.niches_formats_fallback = self._xl("08_niche_formats.xlsx", "Форматы", 5)
        # Quick Check v2 surveys (catalog + applicability + dependencies)
        self.surveys_questions = self._xl("09_surveys.xlsx", "Вопросы", 5)
        self.surveys_applic = self._xl("09_surveys.xlsx", "Применимость", 5)
        self.surveys_deps = self._xl("09_surveys.xlsx", "Зависимости", 5)
        # v1.0 spec: config YAMLs (niches/archetypes/locations/questionnaire)
        self._load_yaml_configs()
        self.rent = self._xl("11_rent_benchmarks.xlsx", "Калькулятор для движка", 5)
        self.inflation = self._xl("13_macro_dynamics.xlsx", "Инфляция по регионам", 5)
        self.competitors = self._xl("14_competitors.xlsx", "Конкуренты по городам", 5)
        self.failure_patterns = self._xl("15_failure_cases.xlsx", "Паттерны по нишам", 5)
        self.permits = self._xl("17_permits.xlsx", "Разрешения и лицензии", 5)
        self.inflation_niche = self._xl("19_inflation_by_niche.xlsx", "Прогноз роста OPEX", 5)

        # Налоги 2026
        self.tax_regimes = self._xl("05_tax_regimes.xlsx", "tax_regimes_2026", 0)
        self.city_tax_rates = self._xl("05_tax_regimes.xlsx", "city_ud_rates_2026", 0)

        print(f"✅ Общие файлы загружены.")

    def _load_niches(self):
        """Сканирует data/niches/ и загружает все niche_formats_{NICHE}.xlsx. Список ниш = список файлов."""
        if not os.path.exists(self.formats_dir):
            print(f"⚠️ Папка {self.formats_dir} не найдена. Ниши не загружены.")
            return

        pattern = os.path.join(self.formats_dir, "niche_formats_*.xlsx")
        files = glob.glob(pattern)

        SHEETS = ['FORMATS','STAFF','FINANCIALS','CAPEX','GROWTH','TAXES',
                  'MARKET','LAUNCH','INSIGHTS','PRODUCTS','MARKETING','SUPPLIERS','SURVEY','LOCATIONS']

        # Маппинг niche_id → название + иконка (для API и анкеты)
        NICHE_NAMES = {
            # Общепит
            'COFFEE': 'Кофейня', 'BAKERY': 'Пекарня', 'DONER': 'Донерная',
            'PIZZA': 'Пиццерия', 'SUSHI': 'Суши-бар', 'FASTFOOD': 'Фастфуд',
            'CANTEEN': 'Столовая',
            # Красота
            'BARBER': 'Барбершоп', 'NAIL': 'Маникюр', 'LASH': 'Ресницы',
            'SUGARING': 'Шугаринг', 'BROW': 'Брови', 'MASSAGE': 'Массаж',
            # Здоровье
            'DENTAL': 'Стоматология', 'FITNESS': 'Фитнес',
            # Авто
            'CARWASH': 'Автомойка', 'AUTOSERVICE': 'Автосервис', 'TIRE': 'Шиномонтаж',
            # Торговля
            'GROCERY': 'Продуктовый магазин', 'PHARMA': 'Аптека',
            'FLOWERS': 'Цветочный магазин', 'FRUITSVEGS': 'Овощи и фрукты',
            # Услуги
            'CLEAN': 'Клининг', 'DRYCLEAN': 'Химчистка',
            'REPAIR_PHONE': 'Ремонт телефонов', 'KINDERGARTEN': 'Частный детский сад',
            'PVZ': 'Пункт выдачи заказов',
            # Производство
            'SEMIFOOD': 'Полуфабрикаты', 'CONFECTION': 'Кондитер на заказ',
            'WATER': 'Производство воды',
            # Другое
            'TAILOR': 'Ателье', 'CYBERCLUB': 'Компьютерный клуб',
            'FURNITURE': 'Мебель на заказ',
        }
        NICHE_ICONS = {
            'COFFEE': '☕', 'BAKERY': '🥐', 'DONER': '🌯',
            'PIZZA': '🍕', 'SUSHI': '🍣', 'FASTFOOD': '🍔',
            'CANTEEN': '🍽', 'BARBER': '💈', 'NAIL': '💅',
            'LASH': '👁', 'SUGARING': '✨', 'BROW': '✏',
            'MASSAGE': '💆', 'DENTAL': '🦷', 'FITNESS': '🏋',
            'CARWASH': '🚗', 'AUTOSERVICE': '🔧', 'TIRE': '🛞',
            'GROCERY': '🛒', 'PHARMA': '💊', 'FLOWERS': '💐',
            'FRUITSVEGS': '🍎', 'CLEAN': '🧹', 'DRYCLEAN': '👔',
            'REPAIR_PHONE': '📱', 'KINDERGARTEN': '👶', 'PVZ': '📦',
            'SEMIFOOD': '🥟', 'CONFECTION': '🎂', 'WATER': '💧',
            'TAILOR': '🧵', 'CYBERCLUB': '🎮', 'FURNITURE': '🪑',
        }

        self.niche_registry = {}  # {niche_id: {name, icon, formats_count}}

        for fpath in sorted(files):
            fname = os.path.basename(fpath)
            niche_id = fname.replace("niche_formats_", "").replace(".xlsx", "")

            self.niche_data[niche_id] = {}
            for sheet in SHEETS:
                try:
                    df = pd.read_excel(fpath, sheet_name=sheet, header=2)
                    if 'format_id' in df.columns:
                        df = df[df['format_id'].notna()]
                        df = df[~df['format_id'].astype(str).str.startswith('▬')]
                    self.niche_data[niche_id][sheet] = df
                except Exception:
                    self.niche_data[niche_id][sheet] = pd.DataFrame()

            # Считаем кол-во форматов
            fmt_df = self.niche_data[niche_id].get('FORMATS', pd.DataFrame())
            fmt_count = len(fmt_df['format_id'].unique()) if not fmt_df.empty and 'format_id' in fmt_df.columns else 0

            self.niche_registry[niche_id] = {
                'niche_id': niche_id,
                'name': NICHE_NAMES.get(niche_id, niche_id),
                'icon': NICHE_ICONS.get(niche_id, '📋'),
                'formats_count': fmt_count,
            }

            loaded = len([s for s in SHEETS if not self.niche_data[niche_id][s].empty])
            print(f"  📂 {niche_id}: {loaded}/{len(SHEETS)} листов, {fmt_count} форматов")

        print(f"✅ Загружено ниш: {len(self.niche_data)}")

    def get_niche_sheet(self, niche_id: str, sheet: str) -> pd.DataFrame:
        """Получить лист данных по нише."""
        if niche_id not in self.niche_data:
            return pd.DataFrame()
        return self.niche_data[niche_id].get(sheet, pd.DataFrame())

    def get_format_row(self, niche_id: str, sheet: str, format_id: str, cls: str) -> dict:
        """Получить строку по format_id + class. Фоллбэк: если класс не найден,
        берём первую доступную строку с этим format_id (некоторые форматы
        существуют только в одном классе, например BARBER_SOLO только «Эконом»)."""
        df = self.get_niche_sheet(niche_id, sheet)
        if df.empty:
            return {}
        fid_mask = df['format_id'].astype(str) == format_id
        if 'class' in df.columns:
            rows = df[fid_mask & (df['class'].astype(str) == cls)]
            if rows.empty:
                rows = df[fid_mask]
        else:
            rows = df[fid_mask]
        if rows.empty:
            return {}
        return rows.iloc[0].to_dict()

    def get_format_all_rows(self, niche_id: str, sheet: str, format_id: str, cls: str = None) -> pd.DataFrame:
        """Получить все строки по format_id (и опц. class). Для PRODUCTS, INSIGHTS, MARKETING."""
        df = self.get_niche_sheet(niche_id, sheet)
        if df.empty:
            return pd.DataFrame()
        # Фильтр: format_id = конкретный ИЛИ 'ALL'
        mask_fid = (df['format_id'].astype(str) == format_id) | (df['format_id'].astype(str) == 'ALL')
        if cls:
            mask_cls = (df['class'].astype(str) == cls) | (df['class'].astype(str) == 'ALL')
            return df[mask_fid & mask_cls]
        return df[mask_fid]

    def get_available_niches(self) -> list:
        """Список загруженных ниш с названиями и иконками (из файлов в data/niches/)."""
        return list(self.niche_registry.values())

    def get_formats_for_niche(self, niche_id: str) -> list:
        """Список форматов для ниши (уникальные format_id)."""
        df = self.get_niche_sheet(niche_id, 'FORMATS')
        if df.empty:
            return []
        return df[['format_id','format_name']].drop_duplicates().to_dict('records')

    def get_survey(self, niche_id: str) -> list:
        """Анкета для ниши из листа SURVEY."""
        df = self.get_niche_sheet(niche_id, 'SURVEY')
        if df.empty:
            return []
        return df.to_dict('records')

    def get_locations(self, niche_id: str) -> list:
        """Типы локации для ниши из листа LOCATIONS."""
        df = self.get_niche_sheet(niche_id, 'LOCATIONS')
        if df.empty:
            return []
        return df.to_dict('records')

    def get_classes_for_format(self, niche_id: str, format_id: str) -> list:
        """Доступные классы для формата из столбца classes_available."""
        df = self.get_niche_sheet(niche_id, 'FORMATS')
        if df.empty or 'classes_available' not in df.columns:
            return ['Эконом','Стандарт','Бизнес','Премиум']
        rows = df[df['format_id'].astype(str) == format_id]
        if rows.empty:
            return ['Эконом','Стандарт','Бизнес','Премиум']
        val = rows.iloc[0].get('classes_available','')
        if not val or str(val) == 'nan':
            return ['Эконом','Стандарт','Бизнес','Премиум']
        return [c.strip() for c in str(val).split('|')]


# ═══════════════════════════════════════════════
# 2. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════

def get_city(db: ZerekDB, city_id: str) -> dict:
    if db.cities.empty or "city_id" not in db.cities.columns:
        return {"city_id": city_id, "Город": city_id, "Население всего (чел.)": 0}
    rows = db.cities[db.cities["city_id"] == city_id]
    if rows.empty:
        return {"city_id": city_id, "Город": city_id, "Население всего (чел.)": 0}
    return rows.iloc[0].to_dict()

def get_city_tax_rate(db: ZerekDB, city_id: str) -> float:
    if db.city_tax_rates.empty:
        return 4.0
    rows = db.city_tax_rates[db.city_tax_rates["city_id"] == city_id]
    if rows.empty:
        return 4.0
    return float(rows.iloc[0].get("ud_rate_pct", 4.0))

def get_rent_median(db: ZerekDB, city_id: str, loc_type: str) -> tuple:
    if db.rent.empty:
        return (3000, 500)
    try:
        df = db.rent
        rows = df[(df["city_id"] == city_id) & (df["loc_type"] == loc_type)]
        if rows.empty:
            rows = df[df["city_id"] == city_id]
        if rows.empty:
            return (3000, 500)
        r = rows.iloc[0]
        return (int(r.get("rent_per_m2_median", 3000)), int(r.get("utilities_per_m2", 500)))
    except KeyError:
        return (3000, 500)

def get_competitors(db: ZerekDB, niche_id: str, city_id: str) -> dict:
    if db.competitors.empty:
        return {"уровень": 3, "сигнал": "Нет данных о конкуренции", "кол_во": "н/д", "лидеры": ""}
    try:
        rows = db.competitors[(db.competitors["niche_id"] == niche_id) & (db.competitors["city_id"] == city_id)]
    except KeyError:
        return {"уровень": 3, "сигнал": "Нет данных о конкуренции", "кол_во": "н/д", "лидеры": ""}
    if rows.empty:
        return {"уровень": 3, "сигнал": "Нет данных о конкуренции", "кол_во": "н/д", "лидеры": ""}
    row = rows.iloc[0]
    sat = _safe_int(row.get("Уровень насыщения (1-5)"), 3)
    signals = {1:"🟢 Рынок свободен",2:"🟢 Есть место",3:"🟡 Нужна дифференциация",4:"🟠 Высокая конкуренция",5:"🔴 Рынок насыщен"}
    return {"уровень": sat, "сигнал": signals.get(sat,""), "кол_во": row.get("Кол-во конкурентов (оценка)",""), "лидеры": row.get("Лидеры рынка","")}

def get_failure_pattern(db: ZerekDB, niche_id: str) -> dict:
    if db.failure_patterns.empty:
        return {}
    try:
        rows = db.failure_patterns[db.failure_patterns["niche_id"] == niche_id]
        if rows.empty:
            return {}
        return rows.iloc[0].to_dict()
    except KeyError:
        return {}

def get_permits(db: ZerekDB, niche_id: str) -> list:
    if db.permits.empty:
        return []
    try:
        df = db.permits
        rows = df[df["niche_id"].str.contains(niche_id, na=False) | (df["niche_id"] == "ALL")]
        return rows.to_dict("records") if not rows.empty else []
    except KeyError:
        return []


# ═══════════════════════════════════════════════
# 3. РАСЧЁТНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════

def calc_revenue_monthly(fin: dict, cal_month: int, razgon_month: int) -> int:
    """Выручка за 1 месяц с учётом сезонности и разгона."""
    check = _safe_int(fin.get('check_med'), 1000)
    traffic = _safe_int(fin.get('traffic_med'), 50)
    base_rev = check * traffic * 30

    # Сезонность (s01-s12)
    s_key = f"s{cal_month:02d}"
    season_coef = _safe_float(fin.get(s_key), 1.0)

    # Разгон
    rampup_months = _safe_int(fin.get('rampup_months'), DEFAULTS['rampup_months'])
    rampup_start = _safe_float(fin.get('rampup_start_pct'), DEFAULTS['rampup_start_pct'])

    if razgon_month <= rampup_months:
        progress = rampup_start + (1.0 - rampup_start) * (razgon_month / rampup_months)
        razgon_coef = min(progress, 1.0)
    else:
        razgon_coef = 1.0

    return int(base_rev * season_coef * razgon_coef)


def calc_cashflow(fin: dict, staff: dict, capex_total: int, tax_rate: float,
                  start_month: int = 1, months: int = 12, qty: int = 1) -> list:
    """Cash Flow на N месяцев. qty = кол-во боксов/точек."""
    results = []
    cumulative = -capex_total

    fot = _safe_int(staff.get('fot_net_med'), 0)
    # Если fot_full есть — используем, иначе считаем
    fot_full = _safe_int(staff.get('fot_full_med'), 0)
    if fot_full == 0 and fot > 0:
        fot_full = int(fot * DEFAULTS['fot_multiplier'])

    rent = _safe_int(fin.get('rent_med'), 0) * qty
    cogs_pct = _safe_float(fin.get('cogs_pct'), DEFAULTS['cogs_pct'])
    utilities = _safe_int(fin.get('utilities'), 0) * qty
    marketing = _safe_int(fin.get('marketing'), 0)
    consumables = _safe_int(fin.get('consumables'), 0) * qty
    software = _safe_int(fin.get('software'), 0)
    transport = _safe_int(fin.get('transport'), 0)
    loss_pct = _safe_float(fin.get('loss_pct'), DEFAULTS['loss_pct'])
    sez = _safe_int(fin.get('sez_month'), DEFAULTS['sez_month'])

    for i in range(months):
        razgon_month = i + 1
        cal_month = ((start_month - 1 + i) % 12) + 1

        rev = calc_revenue_monthly(fin, cal_month, razgon_month) * qty
        cogs = int(rev * cogs_pct)
        gross = rev - cogs
        losses = int(rev * loss_pct)
        tax = int(rev * tax_rate)

        total_opex = fot_full + rent + utilities + marketing + consumables + software + transport + losses + sez + tax
        profit = gross - total_opex
        cumulative += profit

        results.append({
            "месяц": i + 1,
            "кал_месяц": SEASON_LABELS[cal_month - 1],
            "выручка": rev,
            "cogs": cogs,
            "валовая_прибыль": gross,
            "фот": fot_full,
            "аренда": rent,
            "коммуналка": utilities,
            "маркетинг": marketing,
            "расходники": consumables,
            "софт": software,
            "транспорт": transport,
            "потери": losses,
            "сэз": sez,
            "налог": tax,
            "opex": total_opex,
            "прибыль": profit,
            "нарастающий": cumulative,
        })

    return results


def calc_breakeven(fin: dict, staff: dict, tax_rate: float, qty: int = 1) -> dict:
    """Точка безубыточности — включает ВСЕ постоянные расходы."""
    check = _safe_int(fin.get('check_med'), 1000)
    cogs_pct = _safe_float(fin.get('cogs_pct'), DEFAULTS['cogs_pct'])
    loss_pct = _safe_float(fin.get('loss_pct'), DEFAULTS['loss_pct'])

    fot_full = _safe_int(staff.get('fot_full_med'), 0)
    if fot_full == 0:
        fot_full = int(_safe_int(staff.get('fot_net_med'), 0) * DEFAULTS['fot_multiplier'])

    rent = _safe_int(fin.get('rent_med'), 0) * qty
    utilities = _safe_int(fin.get('utilities'), 0) * qty
    marketing = _safe_int(fin.get('marketing'), 0)
    consumables = _safe_int(fin.get('consumables'), 0) * qty
    software = _safe_int(fin.get('software'), 0)
    transport = _safe_int(fin.get('transport'), 0)
    sez = _safe_int(fin.get('sez_month'), 0)

    fixed = fot_full + rent + utilities + marketing + consumables + software + transport + sez
    variable_pct = cogs_pct + loss_pct + tax_rate

    if variable_pct >= 1.0:
        return {"тб_₸": 0, "тб_чеков_день": 0, "запас_прочности_%": 0, "чек_для_тб": check, "fixed_total": fixed}

    tb_revenue = int(fixed / (1 - variable_pct))
    tb_checks_day = int(tb_revenue / 30 / check) if check > 0 else 0

    # Выручка для запаса прочности = check * traffic * 30 (без разгона, полная мощность)
    traffic = _safe_int(fin.get('traffic_med'), 50)
    rev_full = check * traffic * 30 * qty
    safety = round((rev_full - tb_revenue) / rev_full * 100, 1) if rev_full > 0 else 0

    return {
        "тб_₸": tb_revenue,
        "тб_чеков_день": tb_checks_day,
        "запас_прочности_%": safety,
        "чек_для_тб": check,
        "fixed_total": fixed,
    }


def calc_payback(capex_total: int, cashflow: list) -> dict:
    for cf in cashflow:
        if cf["нарастающий"] >= 0:
            return {"месяц": cf["месяц"], "статус": f"✅ Окупается на {cf['месяц']}-й месяц"}
    avg_profit = sum(cf["прибыль"] for cf in cashflow[-3:]) / 3 if cashflow else 0
    if avg_profit > 0:
        remaining = abs(cashflow[-1]["нарастающий"])
        extra = remaining / avg_profit
        m = round(12 + extra, 1)
        return {"месяц": m, "статус": f"⚠️ Окупаемость ~{m} мес."}
    return {"месяц": None, "статус": "🔴 Не окупается при текущих параметрах"}


# ═══════════════════════════════════════════════
# PHASE 2 — OWNER ECONOMICS
# «В карман собственнику» + точки закрытия/роста + стресс-тест
# ═══════════════════════════════════════════════

OWNER_CLOSURE_POCKET = 200_000   # ниже зарплаты наёмного продавца — смысла вести бизнес нет
OWNER_GROWTH_POCKET = 600_000    # 3× закрытие — уровень, с которого можно масштабироваться


def calc_owner_social_payments(declared_monthly_base: int = None) -> int:
    """
    Обязательные соцплатежи собственника-ИП на Упрощёнке (РК 2026):
    ОПВ 10% + ОПВР 3.5% + ОСМС ~5% от 1.4 МРП + СО 3.5% ≈ 18-22% от базы.
    По умолчанию считаем базу = 50 МРП (≈216 250 ₸) — типично для активного ИП на УСН.
    Возвращает ₸/мес.
    """
    if declared_monthly_base is None:
        declared_monthly_base = MRP_2026 * 50
    base = min(declared_monthly_base, MRP_2026 * 50)
    return int(base * 0.22)


def calc_owner_economics(fin: dict, staff: dict, tax_rate: float,
                          rent_month_total: int, qty: int = 1,
                          traffic_k: float = 1.0,
                          check_k: float = 1.0,
                          rent_k: float = 1.0,
                          social: int = None) -> dict:
    """
    Месячная экономика собственника с полной разбивкой OPEX.
    Возвращает выручку, COGS, валовую, OPEX-разбивку, налог, соцплатежи и
    «в карман». Коэффициенты *_k используются в стресс-тесте.
    """
    check = _safe_int(fin.get('check_med'), 1000) * check_k
    traffic = _safe_float(fin.get('traffic_med'), 50) * traffic_k
    revenue = int(check * traffic * 30 * qty)

    cogs_pct = _safe_float(fin.get('cogs_pct'), DEFAULTS['cogs_pct'])
    cogs = int(revenue * cogs_pct)
    gross = revenue - cogs

    fot_full = _safe_int(staff.get('fot_full_med'), 0)
    if fot_full == 0:
        fot_full = int(_safe_int(staff.get('fot_net_med'), 0) * DEFAULTS['fot_multiplier'])

    rent = int(rent_month_total * rent_k)
    utilities = _safe_int(fin.get('utilities'), 0) * qty
    marketing = _safe_int(fin.get('marketing'), 0)
    consumables = _safe_int(fin.get('consumables'), 0) * qty
    software = _safe_int(fin.get('software'), 0)
    transport = _safe_int(fin.get('transport'), 0)
    sez = _safe_int(fin.get('sez_month'), DEFAULTS['sez_month'])
    other = consumables + software + transport + sez

    opex_total = fot_full + rent + marketing + utilities + other
    profit_before_tax = gross - opex_total
    tax_amount = int(revenue * tax_rate)
    social_amount = social if social is not None else calc_owner_social_payments()
    net_in_pocket = profit_before_tax - tax_amount - social_amount

    return {
        'revenue': revenue, 'cogs': cogs, 'gross': gross,
        'opex_breakdown': {
            'rent': rent,
            'fot': fot_full,
            'marketing': marketing,
            'utilities': utilities,
            'other': other,
        },
        'opex_total': opex_total,
        'profit_before_tax': profit_before_tax,
        'tax_amount': tax_amount,
        'tax_rate_pct': round(tax_rate * 100, 2),
        'social_payments': social_amount,
        'net_in_pocket': net_in_pocket,
    }


def calc_closure_growth_points(owner_eco: dict) -> dict:
    """Переводит пороги «в карман» в пороги месячной выручки при той же структуре затрат."""
    pocket = owner_eco.get('net_in_pocket', 0)
    revenue = owner_eco.get('revenue', 0)
    if pocket <= 0 or revenue <= 0:
        return {
            'closure_pocket': OWNER_CLOSURE_POCKET, 'closure_revenue': 0,
            'growth_pocket': OWNER_GROWTH_POCKET, 'growth_revenue': 0,
        }
    ratio = revenue / pocket
    return {
        'closure_pocket': OWNER_CLOSURE_POCKET,
        'closure_revenue': int(OWNER_CLOSURE_POCKET * ratio),
        'growth_pocket': OWNER_GROWTH_POCKET,
        'growth_revenue': int(OWNER_GROWTH_POCKET * ratio),
    }


def calc_stress_test(fin: dict, staff: dict, tax_rate: float,
                     rent_month_total: int, qty: int = 1) -> list:
    """Настоящий стресс-тест: плохо / база / хорошо. «В карман» по каждому сценарию."""
    scenarios = [
        {'key': 'bad',  'label': 'Если всё плохо',     'color': 'red',
         'params': 'Трафик −25%, чек −10%, аренда +20%',
         'traffic_k': 0.75, 'check_k': 0.90, 'rent_k': 1.20},
        {'key': 'base', 'label': 'Базовый сценарий',   'color': 'blue',
         'params': 'Расчётные показатели',
         'traffic_k': 1.00, 'check_k': 1.00, 'rent_k': 1.00},
        {'key': 'good', 'label': 'Если всё хорошо',    'color': 'green',
         'params': 'Трафик +20%, чек +10%',
         'traffic_k': 1.20, 'check_k': 1.10, 'rent_k': 1.00},
    ]
    out = []
    for sc in scenarios:
        eco = calc_owner_economics(
            fin, staff, tax_rate, rent_month_total, qty,
            traffic_k=sc['traffic_k'], check_k=sc['check_k'], rent_k=sc['rent_k'],
        )
        out.append({
            'key': sc['key'], 'label': sc['label'], 'color': sc['color'],
            'params': sc['params'],
            'revenue': eco['revenue'],
            'net_in_pocket': eco['net_in_pocket'],
        })
    return out


# ═══════════════════════════════════════════════
# 4. ГЛАВНАЯ ФУНКЦИЯ — QUICK CHECK v3
# ═══════════════════════════════════════════════

def run_quick_check_v3(
    db: ZerekDB,
    city_id: str,
    niche_id: str,
    format_id: str,
    cls: str,               # Эконом/Стандарт/Бизнес/Премиум
    area_m2: float,
    loc_type: str,
    capital: int = 0,
    qty: int = 1,           # кол-во боксов/точек
    founder_works: bool = False,  # учредитель сам работает?
    rent_override: int = None,
    start_month: int = 4,
) -> dict:
    """
    Quick Check v3 — полный расчёт из новых шаблонов (12 листов).
    Возвращает структурированный dict для отчёта.
    """

    # ── Данные из шаблона ниши ──
    fmt = db.get_format_row(niche_id, 'FORMATS', format_id, cls)
    fin = db.get_format_row(niche_id, 'FINANCIALS', format_id, cls)
    staff = db.get_format_row(niche_id, 'STAFF', format_id, cls)
    capex_data = db.get_format_row(niche_id, 'CAPEX', format_id, cls)
    tax_data = db.get_format_row(niche_id, 'TAXES', format_id, cls)

    # Контентные данные
    products = db.get_format_all_rows(niche_id, 'PRODUCTS', format_id, cls)
    insights = db.get_format_all_rows(niche_id, 'INSIGHTS', format_id, cls)
    marketing = db.get_format_all_rows(niche_id, 'MARKETING', format_id, cls)
    market = db.get_format_row(niche_id, 'MARKET', format_id, cls)

    # ── Общие данные ──
    city = get_city(db, city_id)
    competitors = get_competitors(db, niche_id, city_id)
    failure = get_failure_pattern(db, niche_id)
    permits_list = get_permits(db, niche_id)

    # ── Ставка налога по городу ──
    tax_rate = get_city_tax_rate(db, city_id) / 100

    # ── Ценовой коэффициент города ──
    city_coef = get_city_check_coef(city_id)
    if city_coef != 1.0:
        fin = dict(fin)  # копия чтобы не менять оригинал
        if fin.get('check_med'):
            fin['check_med'] = int(float(fin['check_med']) * city_coef)
        if fin.get('check_min'):
            fin['check_min'] = int(float(fin['check_min']) * city_coef)
        if fin.get('check_max'):
            fin['check_max'] = int(float(fin['check_max']) * city_coef)
        if fin.get('revenue_med'):
            fin['revenue_med'] = int(float(fin['revenue_med']) * city_coef)

    # ── CAPEX ──
    capex_med = _safe_int(capex_data.get('capex_med'), 0) * qty
    capex_min = _safe_int(capex_data.get('capex_min'), 0) * qty
    capex_max = _safe_int(capex_data.get('capex_max'), 0) * qty
    deposit_months = _safe_int(fin.get('deposit_months'), DEFAULTS['deposit_months'])

    rent_median_m2, _ = get_rent_median(db, city_id, loc_type)
    rent_month = rent_override if rent_override else _safe_int(fin.get('rent_med'), int(area_m2 * rent_median_m2))
    rent_month_total = rent_month * qty
    deposit = rent_month_total * deposit_months
    capex_total = capex_med + deposit

    # ── Капитал / инвестиции ──
    fot_med = _safe_int(staff.get('fot_net_med'), 0)
    reserve_3m = int((fot_med + rent_month_total) * 3)
    if capital > 0:
        capital_gap = capital - capex_total
        if capital_gap >= 0:
            capital_signal = "Капитала достаточно"
        else:
            capital_signal = f"Стартовые вложения {capex_total:,} ₸, ваш бюджет {capital:,} ₸."
        reserve_months = round(capital_gap / (fot_med + rent_month_total), 1) if capital_gap > 0 and (fot_med + rent_month_total) > 0 else 0
    else:
        capital_gap = 0
        capital_signal = ""
        reserve_months = 0

    # ── Если учредитель сам работает — корректировка ФОТ ──
    staff_adjusted = dict(staff)
    if founder_works and fot_med > 0:
        headcount = _safe_int(staff.get('headcount'), 1)
        if headcount > 0:
            one_salary = fot_med // headcount
            staff_adjusted['fot_net_med'] = max(0, fot_med - one_salary)
            staff_adjusted['fot_full_med'] = 0  # пересчитает движок

    # ── Cash Flow базовый ──
    cashflow = calc_cashflow(fin, staff_adjusted, capex_total, tax_rate, start_month, 12, qty)

    # ── Точка безубыточности ──
    breakeven = calc_breakeven(fin, staff_adjusted, tax_rate, qty)

    # ── Окупаемость ──
    payback = calc_payback(capex_total, cashflow)

    # ── Phase 2: экономика собственника ──
    owner_eco = calc_owner_economics(fin, staff_adjusted, tax_rate, rent_month_total, qty)
    closure_growth = calc_closure_growth_points(owner_eco)
    stress_test = calc_stress_test(fin, staff_adjusted, tax_rate, rent_month_total, qty)
    # Окупаемость по чистой прибыли в карман (месяцев)
    owner_payback_m = int(round(capex_total / owner_eco['net_in_pocket'])) if owner_eco['net_in_pocket'] > 0 else None

    # ── 3 сценария (пессимист/база/оптимист) ──
    scenarios = {}
    for label, traffic_k, check_k in [('pess',0.75,0.90),('base',1.0,1.0),('opt',1.25,1.10)]:
        fin_sc = dict(fin)
        fin_sc['traffic_med'] = int(_safe_int(fin.get('traffic_med'),50) * traffic_k)
        fin_sc['check_med'] = int(_safe_int(fin.get('check_med'),1000) * check_k)
        sc_cf = calc_cashflow(fin_sc, staff_adjusted, capex_total, tax_rate, start_month, 12, qty)
        sc_payback = calc_payback(capex_total, sc_cf)
        sc_rev = sum(cf["выручка"] for cf in sc_cf)
        sc_profit = sum(cf["прибыль"] for cf in sc_cf)
        scenarios[label] = {
            "трафик_день": fin_sc['traffic_med'],
            "чек": fin_sc['check_med'],
            "выручка_год": sc_rev,
            "прибыль_год": sc_profit,
            "прибыль_среднемес": int(sc_profit / 12),
            "окупаемость": sc_payback,
        }

    # ── Вердикт ──
    score = 0; reasons = []
    if capital > 0:
        if capital_gap >= 0: score += 2
        else: score -= 2; reasons.append("Бюджет может быть недостаточен для выбранного класса — рассмотрите снижение уровня вложений")

    safety = breakeven.get("запас_прочности_%", 0)
    if safety >= 30: score += 2
    elif safety >= 10: score += 1
    else: score -= 1; reasons.append("Запас прочности невысокий — важно обеспечить стабильный поток клиентов")

    pb_m = payback.get("месяц")
    if pb_m and pb_m <= 18: score += 2
    elif pb_m and pb_m <= 30: score += 1
    else: score -= 1; reasons.append("Срок окупаемости длительный — убедитесь что готовы к долгому возврату вложений")

    sat = competitors.get("уровень", 3)
    if sat <= 2: score += 1
    elif sat >= 4: score -= 1; reasons.append("В вашем городе высокая конкуренция в этой нише — нужна сильная дифференциация")

    if score >= 5:
        verdict = {"color":"green","text":"Расчёты показывают хороший потенциал. Убедитесь что сможете обеспечить заложенный трафик и средний чек.","score":score,"reasons":reasons}
    elif score >= 2:
        verdict = {"color":"yellow","text":"Бизнес может быть прибыльным, но обратите внимание на факторы ниже.","score":score,"reasons":reasons}
    else:
        verdict = {"color":"red","text":"При текущих параметрах есть серьёзные риски. Рекомендуем пересмотреть формат, класс или локацию.","score":score,"reasons":reasons}

    # ── Рекомендации при минусе ──
    alternatives = []
    if verdict["color"] == "red":
        # Предложить другой класс
        if cls != "Эконом":
            alt_capex = db.get_format_row(niche_id, 'CAPEX', format_id, 'Эконом')
            if alt_capex:
                alternatives.append(f"Снизьте класс до Эконом — CAPEX {_safe_int(alt_capex.get('capex_med'),0):,} ₸ вместо {capex_med:,} ₸")
        # Предложить другую локацию
        if rent_month_total > _safe_int(fin.get('rent_min'), 0) * qty:
            alternatives.append(f"Рассмотрите спальный район — аренда может быть на 30-40% ниже")

    # ── Сборка отчёта ──
    total_rev_y1 = sum(cf["выручка"] for cf in cashflow)
    total_profit_y1 = sum(cf["прибыль"] for cf in cashflow)

    return {
        "input": {
            "city_id": city_id,
            "city_name": city.get("Город", ""),
            "niche_id": niche_id,
            "format_id": format_id,
            "format_name": _safe(fmt.get('format_name'), format_id),
            "class": cls,
            "area_m2": area_m2,
            "loc_type": loc_type,
            "capital": capital,
            "qty": qty,
            "founder_works": founder_works,
            "start_month": start_month,
        },

        "market": {
            "population": _safe_int(city.get("Население всего (чел.)")),
            "competitors": competitors,
            "target_audience": _safe(market.get('target_audience'), ''),
            "competition_1_5": _safe_int(market.get('competition_1_5'), 3),
            "utp": _safe(market.get('utp'), ''),
        },

        "capex": {
            "capex_min": capex_min,
            "capex_med": capex_med,
            "capex_max": capex_max,
            "deposit": deposit,
            "total": capex_total,
            "capital": capital,
            "gap": capital_gap,
            "signal": capital_signal,
            "reserve_months": reserve_months,
            "breakdown": {
                "equipment": _safe_int(capex_data.get('equipment')) * qty,
                "renovation": _safe_int(capex_data.get('renovation')) * qty,
                "furniture": _safe_int(capex_data.get('furniture')) * qty,
                "first_stock": _safe_int(capex_data.get('first_stock')) * qty,
                "permits_sez": _safe_int(capex_data.get('permits_sez')) * qty,
                "working_cap": _safe_int(capex_data.get('working_cap_3m')) * qty,
            },
            "investment_range": {
                "min": capex_total,
                "max": capex_total + reserve_3m,
                "note": "Оборудование, ремонт, депозит аренды + резерв 3 мес.",
            },
        },

        "staff": {
            "positions": _safe(staff.get('positions'), ''),
            "headcount": _safe_int(staff.get('headcount')),
            "founder_role": _safe(staff.get('founder_role'), ''),
            "fot_net_med": _safe_int(staff_adjusted.get('fot_net_med')),
            "fot_full_med": _safe_int(staff_adjusted.get('fot_full_med')) or int(_safe_int(staff_adjusted.get('fot_net_med')) * DEFAULTS['fot_multiplier']),
            "schedule": _safe(staff.get('schedule'), ''),
        },

        "financials": {
            "check_med": _safe_int(fin.get('check_med')),
            "traffic_med": _safe_int(fin.get('traffic_med')),
            "cogs_pct": _safe_float(fin.get('cogs_pct'), DEFAULTS['cogs_pct']),
            "margin_pct": _safe_float(fin.get('margin_pct'), DEFAULTS['margin_pct']),
            "rent_month": rent_month_total,
            "opex_med": _safe_int(fin.get('opex_med')) * qty,
            "sez_month": _safe_int(fin.get('sez_month')),
            "revenue_year1": total_rev_y1,
            "profit_year1": total_profit_y1,
            "tax_rate_pct": tax_rate * 100,
        },

        "breakeven": breakeven,
        "scenarios": scenarios,
        "payback": payback,

        "owner_economics": {
            **owner_eco,
            **closure_growth,
            "stress_test": stress_test,
            "owner_payback_months": owner_payback_m,
        },

        "tax": {
            "regime": _safe(tax_data.get('tax_regime'), 'Упрощёнка'),
            "simplified_ok": _safe(tax_data.get('simplified_ok'), 'Да'),
            "b2b": _safe(tax_data.get('b2b'), 'Нет'),
            "nds_risk": _safe(tax_data.get('nds_risk'), 'Нет'),
            "rate_pct": tax_rate * 100,
        },

        "verdict": verdict,
        "alternatives": alternatives,

        "risks": {
            "failure_pattern": failure,
            "permits": permits_list[:5],
            "competitors": competitors,
        },

        # Контентные блоки для отчёта
        "products": products.to_dict("records") if not products.empty else [],
        "insights": insights.to_dict("records") if not insights.empty else [],
        "marketing": marketing.to_dict("records") if not marketing.empty else [],

        "cashflow": cashflow,
    }


# ═══════════════════════════════════════════════
# ОБРАТНАЯ СОВМЕСТИМОСТЬ
# ═══════════════════════════════════════════════

# Экспорт для старого кода (будет удалён после миграции)
def get_inflation_region(db, city_id):
    rows = db.inflation[db.inflation.get("region_id", db.inflation.columns[0]) == city_id] if not db.inflation.empty else pd.DataFrame()
    return 10.0

def render_report(result):
    """Заглушка — будет переписан в report_v3.py"""
    return str(result)


# ═══════════════════════════════════════════════
# QUICK CHECK v2 — Adaptive Survey Config
# ═══════════════════════════════════════════════

# Справочник типов локации для рендера в анкете v2.
LOCATION_TYPES_META = {
    "tc":                  {"label": "Торговый центр",           "icon": "🏬"},
    "street":              {"label": "Улица / отдельный офис",   "icon": "🏪"},
    "home":                {"label": "Из дома",                   "icon": "🏠"},
    "highway":             {"label": "Возле дороги",              "icon": "🛣️"},
    "residential_complex": {"label": "Коммерция в ЖК",            "icon": "🏢"},
    "business_center":     {"label": "Бизнес-центр",              "icon": "🏢"},
    "market":              {"label": "Рынок / павильон",          "icon": "🛍️"},
    "online":              {"label": "Только онлайн",             "icon": "🌐"},
    "residential_area":    {"label": "Спальный район",            "icon": "🏘️"},
    "own_building":        {"label": "Отдельное здание",          "icon": "🏛️"},
}


def _split_csv(val) -> list:
    """'a, b,c' → ['a','b','c']; пусто / NaN → []."""
    if val is None:
        return []
    s = str(val).strip()
    if not s or s.lower() == "nan":
        return []
    return [p.strip() for p in s.split(",") if p.strip()]


def _niche_name_from_registry(db, niche_id: str) -> str:
    info = db.niche_registry.get(niche_id, {})
    return info.get("name", niche_id)


def _formats_from_per_niche_xlsx(db, niche_id: str) -> list:
    """Форматы из data/kz/niches/niche_formats_{NICHE}.xlsx (лист FORMATS)."""
    df = db.get_niche_sheet(niche_id, "FORMATS")
    if df.empty or "format_id" not in df.columns:
        return []
    cols = [c for c in ["format_id", "format_name", "area_m2", "loc_type",
                        "capex_standard", "class"] if c in df.columns]
    return df[cols].drop_duplicates(subset=["format_id"]).to_dict("records")


def _formats_from_fallback_xlsx(db, niche_id: str) -> list:
    """Форматы из data/kz/08_niche_formats.xlsx, если per-niche xlsx пуст."""
    df = getattr(db, "niches_formats_fallback", pd.DataFrame())
    if df is None or df.empty or "niche_id" not in df.columns:
        return []
    rows = df[df["niche_id"].astype(str) == niche_id]
    if rows.empty:
        return []
    keep = [c for c in ["format_id", "format_name", "area_m2", "loc_type",
                        "capex_standard", "class"] if c in rows.columns]
    return rows[keep].to_dict("records")


def _specific_questions_for_niche(db, niche_id: str, qids: list) -> list:
    """По списку question_id собирает полные определения вопросов."""
    out = []
    if not qids:
        return out
    df = getattr(db, "niches_questions", pd.DataFrame())
    if df is None or df.empty or "question_id" not in df.columns:
        return out
    for qid in qids:
        row = df[df["question_id"].astype(str) == qid]
        if row.empty:
            continue
        r = row.iloc[0]
        opts_raw = str(r.get("options", "")).strip()
        options = [o.strip() for o in opts_raw.split("|")] if opts_raw and opts_raw.lower() != "nan" else []
        out.append({
            "question_id": qid,
            "question_text": str(r.get("question_text", qid)).strip(),
            "options": options,
        })
    return out


def get_niche_config(db, niche_id: str) -> dict:
    """Возвращает конфиг адаптивной анкеты Quick Check v2 для указанной ниши.

    Формат соответствует спеке из docs/ADAPTIVE_SURVEY.md:
        {niche_id, niche_name, requires_license, license_description,
         self_operation_possible, class_grades_applicable,
         allowed_location_types: [...], default_location_type,
         area_question_mode, staff_question_mode,
         specific_questions: [{question_id, question_text, options}],
         formats: [{format_id, name, area_m2, capex_standard, ...}],
         location_types_meta: {...}}
    """
    cfg_df = getattr(db, "niches_config", pd.DataFrame())

    # Дефолт когда нет конфига / ниши в нём нет
    fallback_loc = ["street", "own_building"]
    config = {
        "niche_id": niche_id,
        "niche_name": _niche_name_from_registry(db, niche_id),
        "requires_license": "no",
        "license_description": "",
        "self_operation_possible": "no",
        "class_grades_applicable": "yes",
        "allowed_location_types": fallback_loc,
        "default_location_type": "street",
        "area_question_mode": "required",
        "staff_question_mode": "choice",
        "specific_questions": [],
        "formats": [],
        "location_types_meta": LOCATION_TYPES_META,
        "niche_notes": "",
    }

    if cfg_df is not None and not cfg_df.empty and "niche_id" in cfg_df.columns:
        rows = cfg_df[cfg_df["niche_id"].astype(str) == niche_id]
        if not rows.empty:
            r = rows.iloc[0]
            allowed = _split_csv(r.get("allowed_location_types", ""))
            default_loc = str(r.get("default_location_type", "") or "").strip() or (
                allowed[0] if allowed else "street"
            )
            qids = _split_csv(r.get("specific_questions_ids", ""))
            name_override = str(r.get("niche_name", "") or "").strip()
            config.update({
                "niche_name": name_override or config["niche_name"],
                "requires_license": str(r.get("requires_license", "no") or "no").strip(),
                "license_description": str(r.get("license_description", "") or "").strip(),
                "self_operation_possible": str(r.get("self_operation_possible", "no") or "no").strip(),
                "class_grades_applicable": str(r.get("class_grades_applicable", "yes") or "yes").strip(),
                "allowed_location_types": allowed or fallback_loc,
                "default_location_type": default_loc,
                "area_question_mode": str(r.get("area_question_mode", "required") or "required").strip(),
                "staff_question_mode": str(r.get("staff_question_mode", "choice") or "choice").strip(),
                "specific_questions": _specific_questions_for_niche(db, niche_id, qids),
                "niche_notes": str(r.get("niche_notes", "") or "").strip(),
            })

    # Форматы: сначала per-niche xlsx (реальные данные движка), потом fallback-каталог.
    formats = _formats_from_per_niche_xlsx(db, niche_id)
    if not formats:
        formats = _formats_from_fallback_xlsx(db, niche_id)

    # Нормализуем поля
    normalized = []
    for f in formats:
        normalized.append({
            "format_id": str(f.get("format_id", "")).strip(),
            "name": str(f.get("format_name", "") or "").strip(),
            "area_m2": _safe_float(f.get("area_m2", 0)),
            "loc_type": str(f.get("loc_type", "") or "").strip(),
            "capex_standard": _safe_int(f.get("capex_standard", 0)),
            "class": str(f.get("class", "") or "").strip().lower(),
        })
    config["formats"] = [f for f in normalized if f["format_id"]]

    # Отфильтруем location_types_meta до только разрешённых типов
    allowed_types = set(config["allowed_location_types"])
    config["location_types_meta"] = {
        k: v for k, v in LOCATION_TYPES_META.items() if k in allowed_types
    }

    return config


# ───────────────────────────────────────────────────────────────────────────
# Quick Check v2 — Survey (per-niche question list)
# ───────────────────────────────────────────────────────────────────────────

def _question_to_dict(row) -> dict:
    """Превращает строку из листа «Вопросы» в JSON-friendly dict."""
    opts_raw = str(row.get("options", "") or "").strip()
    options = [o.strip() for o in opts_raw.split("|")] if opts_raw and opts_raw.lower() != "nan" else []
    def num(v):
        try:
            return float(v) if v is not None and str(v).lower() != "nan" else None
        except Exception:
            return None
    return {
        "qid":          str(row.get("qid", "")).strip(),
        "question_text":str(row.get("question_text", "") or "").strip(),
        "input_type":   str(row.get("input_type", "") or "").strip(),
        "options":      options,
        "placeholder":  str(row.get("placeholder", "") or "").strip(),
        "min":          num(row.get("min")),
        "max":          num(row.get("max")),
        "step":         num(row.get("step")),
        "unit":         str(row.get("unit", "") or "").strip(),
        "help":         str(row.get("help", "") or "").strip(),
    }


def _dependencies_for(deps_df, qid: str) -> list:
    """Список зависимостей для qid из листа «Зависимости»."""
    if deps_df is None or deps_df.empty:
        return []
    rows = deps_df[deps_df["qid"].astype(str) == qid]
    out = []
    for _, r in rows.iterrows():
        out.append({
            "depends_on": str(r.get("depends_on", "") or "").strip(),
            "condition":  str(r.get("condition", "") or "").strip(),
            "action":     str(r.get("action", "") or "show").strip(),
        })
    return out


# ═══════════════════════════════════════════════
# BLOCK 1 — ВЕРДИКТ (Quick Check report, первая страница)
# Согласно спецификации «ZEREK Quick Check — Блок 1» v1.0
# ═══════════════════════════════════════════════

def _fmt_range_kzt(low, high):
    """Форматирует диапазон в 'X–Y тыс/млн ₸' для главных цифр."""
    if low is None or high is None:
        return '—'
    if low == high:
        return _fmt_kzt(low)
    return f"{_fmt_kzt_short(low)}–{_fmt_kzt_short(high)}"

def _fmt_kzt(v):
    if v is None: return '—'
    v = int(v)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f} млн ₸".replace('.0 млн','  млн').rstrip().replace('.',',')
    if abs(v) >= 1_000:
        return f"{v//1_000} тыс ₸"
    return f"{v} ₸"

def _fmt_kzt_short(v):
    if v is None: return '—'
    v = int(v)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}".rstrip('0').rstrip('.') + ' млн'
    if abs(v) >= 1_000:
        return f"{v//1_000} тыс"
    return f"{v}"


def _score_capital(capital_own, capex_needed):
    if not capex_needed:
        return {'score': 1, 'label': 'Капитал vs бенчмарк', 'note': 'Нет данных по CAPEX бенчмарку'}
    if not capital_own:
        return {'score': 1, 'label': 'Капитал vs бенчмарк', 'note': 'Клиент не указал капитал — нейтрально'}
    ratio = capital_own / capex_needed
    if ratio >= 1.2:  return {'score': 3, 'label': 'Капитал vs бенчмарк', 'note': f'Профицит: капитал на {int((ratio-1)*100)}% выше бенчмарка', 'ratio': ratio}
    if ratio >= 0.95: return {'score': 2, 'label': 'Капитал vs бенчмарк', 'note': 'Бюджет соответствует бенчмарку', 'ratio': ratio}
    if ratio >= 0.75: return {'score': 1, 'label': 'Капитал vs бенчмарк', 'note': f'Дефицит {int((1-ratio)*100)}% — терпимо', 'ratio': ratio, 'gap_kzt': int(capex_needed - capital_own)}
    return {'score': 0, 'label': 'Капитал vs бенчмарк', 'note': f'Дефицит критичный: {int((1-ratio)*100)}%', 'ratio': ratio, 'gap_kzt': int(capex_needed - capital_own)}


def _score_roi(profit_year, total_investment):
    # Валидация: total_investment должен быть разумным (хотя бы 500K ₸ для любого малого бизнеса)
    if not total_investment or total_investment < 500_000:
        return {'score': 1, 'label': 'ROI годовой', 'note': 'Не хватает данных о капитале'}
    roi = (profit_year or 0) / total_investment
    # Ограничение на абсурдные значения (баг в движке — cap на 10x годовой)
    if roi > 10:
        return {'score': 1, 'label': 'ROI годовой', 'note': 'Требуется уточнение расчётов'}
    pct = int(round(roi * 100))
    if roi >= 0.45: return {'score': 3, 'label': 'ROI годовой', 'note': f'ROI {pct}% — выше среднего для малого бизнеса', 'roi': roi}
    if roi >= 0.30: return {'score': 2, 'label': 'ROI годовой', 'note': f'ROI {pct}% — нормальный', 'roi': roi}
    if roi >= 0.15: return {'score': 1, 'label': 'ROI годовой', 'note': f'ROI {pct}% — ниже нормы, но положительный', 'roi': roi}
    return {'score': 0, 'label': 'ROI годовой', 'note': f'ROI {pct}% — не окупает капитал', 'roi': roi}


def _score_breakeven(breakeven_months):
    if breakeven_months is None:
        return {'score': 0, 'label': 'Точка безубыточности', 'note': 'Бизнес не окупается за 18 мес'}
    if breakeven_months <= 6:  return {'score': 3, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес — быстрая', 'months': breakeven_months}
    if breakeven_months <= 12: return {'score': 2, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес', 'months': breakeven_months}
    if breakeven_months <= 18: return {'score': 1, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес — долго', 'months': breakeven_months}
    return {'score': 0, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес — слишком долго', 'months': breakeven_months}


def _score_saturation(competitors_count, city_population, niche_id):
    """density = competitors / (population/10K). Бенчмарк — условный (1.0 для retail, 0.8 общий)."""
    if not competitors_count or not city_population:
        return {'score': 2, 'label': 'Насыщенность рынка', 'note': 'Нет данных о конкурентах'}
    density = competitors_count / (city_population / 10000)
    benchmark = 0.8
    ratio = density / benchmark
    if ratio <= 0.6: return {'score': 3, 'label': 'Насыщенность рынка', 'note': f'Рынок недонасыщен: {round(density,1)} конкурентов на 10K жителей', 'density': density}
    if ratio <= 1.0: return {'score': 2, 'label': 'Насыщенность рынка', 'note': f'Норма: {round(density,1)} конкурентов на 10K', 'density': density}
    if ratio <= 1.5: return {'score': 1, 'label': 'Насыщенность рынка', 'note': f'Перенасыщен: {round(density,1)} конкурентов на 10K', 'density': density}
    return {'score': 0, 'label': 'Насыщенность рынка', 'note': f'Высокая конкуренция: {round(density,1)} на 10K', 'density': density}


def _score_experience(exp):
    if exp == 'experienced': return {'score': 3, 'label': 'Опыт предпринимателя', 'note': '3+ лет опыта снижает риск первого года'}
    if exp == 'some':        return {'score': 2, 'label': 'Опыт предпринимателя', 'note': '1-2 года опыта — стандартно'}
    if exp == 'none':        return {'score': 0, 'label': 'Опыт предпринимателя', 'note': 'Нет опыта — риск первого года до 45%'}
    return {'score': 1, 'label': 'Опыт предпринимателя', 'note': 'Опыт не указан'}


def _score_marketing(tier='express'):
    # В Quick Check нейтрально (1 балл из 2). FinModel переопределит.
    return {'score': 1, 'label': 'Маркетинговый бюджет', 'note': 'В экспресс-оценке не спрашиваем — нейтральный балл', 'max': 2}


def _score_stress(profit_base, profit_pess):
    if profit_base is None or profit_pess is None:
        return {'score': 1, 'label': 'Устойчивость к стрессу'}
    if profit_pess > 0:
        drop = (profit_base - profit_pess) / profit_base if profit_base else 0
        if drop < 0.30: return {'score': 3, 'label': 'Устойчивость к стрессу', 'note': 'Бизнес устойчив к падению ключевого параметра на 20%'}
        if drop < 0.50: return {'score': 2, 'label': 'Устойчивость к стрессу', 'note': 'Умеренно устойчив — падение выручки терпимое'}
        return {'score': 1, 'label': 'Устойчивость к стрессу', 'note': 'Хрупкая модель — небольшое падение трафика больно бьёт'}
    return {'score': 0, 'label': 'Устойчивость к стрессу', 'note': 'При падении параметра на 20% — убыток'}


def _score_format_city(format_id, format_class, city_population):
    # Матрица «формат-класс × размер города»
    small = (city_population or 0) < 150_000
    mid = 150_000 <= (city_population or 0) < 300_000
    cls = (format_class or '').lower()
    if cls == 'премиум' and small:
        return {'score': 0, 'label': 'Соответствие формата городу', 'note': 'Премиум-формат в малом городе — узкая ЦА'}
    if cls == 'премиум' and mid:
        return {'score': 1, 'label': 'Соответствие формата городу', 'note': 'Премиум-формат в среднем городе — ограниченная ЦА'}
    return {'score': 3, 'label': 'Соответствие формата городу', 'note': 'Формат подходит для города'}


def _verdict_statement_template(color, top_weak, top_strong, roi_pct, breakeven_months):
    """Шаблонный вердикт (fallback когда Gemini не подключён)."""
    strong_name = (top_strong or {}).get('label', '')
    weak_name = (top_weak or {}).get('label', '')
    weak_note = (top_weak or {}).get('note', '')

    if color == 'green':
        if top_weak and top_weak.get('score', 0) <= 1:
            bm = f' Окупаемость {breakeven_months} мес — держите запас кассы.' if breakeven_months else ''
            return f'Бизнес реалистичен и окупается.{bm}'
        return f'Бизнес реалистичен и окупается. Главное преимущество — {strong_name.lower()}.'

    if color == 'yellow':
        return f'Бизнес возможен, но требует внимания. Главный риск — {weak_name.lower()}: {weak_note.lower()}.'

    # red
    return f'В текущей конфигурации бизнес не окупается в разумные сроки. Требуется пересмотр — главный слабый пункт: {weak_name.lower()}.'


def _strength_text(p):
    """Тезис для плюса."""
    n = p.get('note') or ''
    return n if n else p.get('label', '')

def _risk_text(p, context):
    """Тезис для риска — с конкретной рекомендацией."""
    label = p.get('label', '')
    if label == 'Капитал vs бенчмарк':
        gap = p.get('gap_kzt')
        if gap:
            return f'Дефицит капитала {_fmt_kzt(gap)} — найдите дополнительное финансирование или урежьте формат.'
        return p.get('note') or 'Бюджет не соответствует формату.'
    if label == 'Точка безубыточности':
        months = p.get('months')
        if months and months >= 12:
            return f'Окупаемость {months} мес — заложите запас кассы на первые 6-12 мес.'
        return p.get('note') or 'Окупаемость долгая — нужен запас.'
    if label == 'Насыщенность рынка':
        return (p.get('note') or '') + ' — без сильного УТП сложно взять долю.'
    if label == 'Опыт предпринимателя':
        return 'Отсутствие опыта повышает риск первого года. Найдите ментора или партнёра с опытом в нише.'
    if label == 'Устойчивость к стрессу':
        return 'Бизнес чувствителен к падению ключевого параметра. Маркетинг и удержание клиентов в первые 6 мес — приоритет.'
    if label == 'Соответствие формата городу':
        return 'Премиум-формат в выбранном городе — узкая платёжеспособная ЦА. Рассмотрите стандартный класс.'
    if label == 'ROI годовой':
        return 'ROI ниже среднего. Пересмотрите CAPEX или ожидаемую выручку.'
    if label == 'Маркетинговый бюджет':
        return 'Маркетинг будет ключевым — не экономьте на первом старте.'
    return p.get('note') or label


def compute_block1_verdict(result, adaptive):
    """Главная функция. Принимает результат run_quick_check_v3 + adaptive-ответы
    (из specific_answers v1.0 спеки: experience, entrepreneur_role, capital_own, capital_needed)
    и возвращает блок 1 вердикта."""
    adaptive = adaptive or {}
    inp = result.get('input', {}) or {}
    fin = result.get('financials', {}) or {}
    capex_block = result.get('capex', {}) or {}
    scenarios = result.get('scenarios', {}) or {}
    breakeven = result.get('breakeven', {}) or {}
    payback = result.get('payback', {}) or {}
    risks_block = result.get('risks', {}) or {}
    owner_eco = result.get('owner_economics', {}) or {}
    # Собираем total_investment из всех возможных ключей capex
    total_investment = (
        _safe_int(capex_block.get('capex_total'), 0)
        + _safe_int(owner_eco.get('working_capital'), 0)
    )
    if total_investment < 500_000:
        # Фолбэк: ищем в других ключах
        for k in ('capex_med', 'capex', 'total_investment', 'capex_high'):
            v = _safe_int(capex_block.get(k), 0)
            if v >= 500_000:
                total_investment = v
                break

    # ── Собираем скоринг ──
    capex_needed = _safe_int(capex_block.get('capex_med')) or _safe_int(capex_block.get('capex_total'))
    capital_own = _safe_int(adaptive.get('capital_own')) if adaptive.get('capital_own') else 0
    profit_year = _safe_int(fin.get('profit_year1'), 0)
    breakeven_months = payback.get('месяц') or breakeven.get('месяц')
    city_pop = _safe_int(inp.get('city_population'), 0)
    competitors_count = 0
    comp_block = risks_block.get('competitors') or {}
    if isinstance(comp_block, dict):
        competitors_count = _safe_int(comp_block.get('competitors_count')) or _safe_int(comp_block.get('n'))
    exp = adaptive.get('experience') or ''

    profit_base = _safe_int((scenarios.get('base') or {}).get('прибыль_среднемес'), 0)
    profit_pess = _safe_int((scenarios.get('pess') or {}).get('прибыль_среднемес'), 0)

    format_class = inp.get('class') or inp.get('cls') or ''
    format_id = inp.get('format_id', '')

    scoring_items = [
        _score_capital(capital_own, capex_needed),
        _score_roi(profit_year, total_investment),
        _score_breakeven(breakeven_months),
        _score_saturation(competitors_count, city_pop, inp.get('niche_id', '')),
        _score_experience(exp),
        _score_marketing('express'),
        _score_stress(profit_base, profit_pess),
        _score_format_city(format_id, format_class, city_pop),
    ]
    total_score = sum(it.get('score', 0) for it in scoring_items)
    max_score = sum(it.get('max', 3) for it in scoring_items)

    # ── Цвет ──
    if total_score >= 17:   color = 'green'
    elif total_score >= 12: color = 'yellow'
    else:                   color = 'red'

    # Топ-3 strong / weak
    sorted_desc = sorted(scoring_items, key=lambda x: -x.get('score', 0))
    sorted_asc  = sorted(scoring_items, key=lambda x: x.get('score', 0))
    strengths_items = sorted_desc[:3]
    risks_items = sorted_asc[:3]

    # ── Главные цифры (диапазоны) ──
    rev_base = _safe_int((scenarios.get('base') or {}).get('выручка_год'), 0) // 12
    rev_pess = _safe_int((scenarios.get('pess') or {}).get('выручка_год'), 0) // 12
    rev_opt  = _safe_int((scenarios.get('opt')  or {}).get('выручка_год'), 0) // 12
    prof_base = profit_base
    prof_pess = profit_pess
    bk_base = _safe_int(payback.get('месяц'))
    sc_pess_pb = (scenarios.get('pess') or {}).get('окупаемость')
    if isinstance(sc_pess_pb, dict):
        bk_pess = _safe_int(sc_pess_pb.get('месяц'))
    else:
        bk_pess = _safe_int(sc_pess_pb)

    # Ваш доход предпринимателя
    ent_role = adaptive.get('entrepreneur_role') or 'owner_only'
    role_salary = 0
    if ent_role and ent_role != 'owner_only':
        # Получим ставку роли — upper bound по FOT / headcount
        fot_med = _safe_int(result.get('staff', {}).get('fot_net_med'))
        role_salary = fot_med  # грубая оценка
    ent_income_base = prof_base + role_salary
    ent_income_pess = max(0, prof_pess + role_salary)

    main_metrics = {
        'revenue_range':        _fmt_range_kzt(rev_pess, rev_base),
        'profit_range':         _fmt_range_kzt(prof_pess, prof_base) if prof_pess >= 0 else f'0–{_fmt_kzt_short(prof_base)}',
        'breakeven_range':      (f"{bk_base}–{bk_pess} мес" if bk_pess and bk_pess != bk_base else (f"{bk_base} мес" if bk_base else '—')),
        'entrepreneur_income_range': _fmt_range_kzt(ent_income_pess, ent_income_base),
    }

    # ── Вердикт-предложение (шаблон) ──
    statement = _verdict_statement_template(color, risks_items[0] if risks_items else None,
                                            strengths_items[0] if strengths_items else None,
                                            None, bk_base)

    # ── Тексты плюсов и рисков ──
    strengths_texts = [_strength_text(p) for p in strengths_items if p.get('score', 0) >= 2]
    # если плюсов меньше 3 — допишем generic
    while len(strengths_texts) < 3 and strengths_items:
        p = strengths_items[len(strengths_texts) % len(strengths_items)]
        t = _strength_text(p)
        if t not in strengths_texts:
            strengths_texts.append(t)
        else:
            break
    risks_texts = [_risk_text(p, {'city': inp.get('city_name', '')}) for p in risks_items]

    return {
        'color': color,
        'score': total_score,
        'max_score': max_score,
        'verdict_statement': statement,
        'main_metrics': main_metrics,
        'strengths': strengths_texts[:3],
        'risks': risks_texts[:3],
        'scoring': {
            'items': scoring_items,
            'strongest': strengths_items[:3],
            'weakest': risks_items[:3],
        },
    }


def _load_yaml_configs_on(self):
    """Загружает config/*.yaml в self.configs. Вызывается из _load_common."""
    try:
        import yaml
    except ImportError:
        self.configs = {}
        print("⚠️ PyYAML не установлен — config/*.yaml пропущен")
        return
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_dir = os.path.join(repo_root, "config")
    self.configs = {}
    for name in ("niches", "archetypes", "locations", "questionnaire"):
        path = os.path.join(config_dir, f"{name}.yaml")
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                self.configs[name] = yaml.safe_load(fh) or {}
        except Exception as e:
            print(f"⚠️ Не удалось прочитать {path}: {e}")
            self.configs[name] = {}

# bind as method on ZerekDB
ZerekDB._load_yaml_configs = _load_yaml_configs_on


# ───────────────────────────────────────────────────────────────────────────
# v1.0 spec — formats from 08_niche_formats.xlsx with extended fields
# ───────────────────────────────────────────────────────────────────────────

def get_formats_v2(db, niche_id: str) -> list:
    """Читает 08_niche_formats.xlsx и возвращает форматы ниши с расширенными полями:
       format_type, allowed_locations, typical_staff (разбит в список)."""
    df = getattr(db, "niches_formats_fallback", pd.DataFrame())
    if df is None or df.empty or "niche_id" not in df.columns:
        return []
    rows = df[df["niche_id"].astype(str) == niche_id]
    out = []
    for _, r in rows.iterrows():
        staff_raw = str(r.get("typical_staff", "") or "").strip()
        staff = []
        if staff_raw and staff_raw.lower() != "nan":
            for chunk in staff_raw.split("|"):
                if ":" in chunk:
                    role, count = chunk.split(":", 1)
                    try:
                        staff.append({"role": role.strip(), "count": int(count.strip())})
                    except Exception:
                        pass
        allowed_raw = str(r.get("allowed_locations", "") or "").strip()
        allowed = [a.strip() for a in allowed_raw.split(",")] if allowed_raw and allowed_raw not in ("auto", "nan") else []
        out.append({
            "format_id":         str(r.get("format_id", "") or "").strip(),
            "format_name":       str(r.get("format_name", "") or "").strip(),
            "area_m2":           _safe_float(r.get("area_m2", 0)),
            "capex_standard":    _safe_int(r.get("capex_standard", 0)),
            "class":             str(r.get("class", "") or "").strip().lower(),
            "format_type":       str(r.get("format_type", "STANDARD") or "STANDARD").strip(),
            "allowed_locations": allowed if allowed_raw != "auto" else [],
            "auto_location":     allowed_raw == "auto",
            "typical_staff":     staff,
        })
    return [f for f in out if f["format_id"]]


def get_entrepreneur_roles(typical_staff: list) -> list:
    """Из typical_staff генерирует варианты роли предпринимателя."""
    if not typical_staff:
        return []
    staff_parts = [f"{s['count']} {s['role']}" for s in typical_staff]
    staff_list_text = " + ".join(staff_parts)
    opts = [
        {
            "id": "owner_only",
            "label_rus": f"Только владелец (нанимаю всех: {staff_list_text})",
            "fot_reduction_role": None,
        }
    ]
    # Per-role options: one per unique role
    unique_roles = []
    for s in typical_staff:
        if s["role"] not in unique_roles:
            unique_roles.append(s["role"])
    for role in unique_roles:
        opts.append({
            "id": f"owner_plus_{role}",
            "label_rus": f"Владелец + {role} (закрываю 1 ставку)",
            "fot_reduction_role": role,
        })
    if len(unique_roles) >= 2:
        opts.append({
            "id": "owner_multi",
            "label_rus": "Владелец работает на нескольких позициях",
            "fot_reduction_role": "multi",
        })
    return opts


def get_quickcheck_survey(db, niche_id: str, format_id: str = None) -> dict:
    """Возвращает полную конфигурацию Quick Check анкеты (8 вопросов) для ниши.

    Если format_id указан — добавляет резолвенные метаданные (allowed_locations
    отфильтрованные, entrepreneur_roles сгенерированные). Фронт применяет
    visibility logic на основе format_type.
    """
    configs = getattr(db, "configs", {})
    niches_cfg = configs.get("niches", {}).get("niches", {})
    archetypes_cfg = configs.get("archetypes", {}).get("archetypes", {})
    locations_cfg = configs.get("locations", {}).get("locations", {})
    questionnaire_cfg = configs.get("questionnaire", {}).get("questionnaire", {})
    qc_cfg = questionnaire_cfg.get("quickcheck", {})

    niche_meta = niches_cfg.get(niche_id, {})
    archetype = niche_meta.get("archetype", "")
    archetype_meta = archetypes_cfg.get(archetype, {})

    formats = get_formats_v2(db, niche_id)
    selected_format = None
    if format_id:
        for f in formats:
            if f["format_id"] == format_id:
                selected_format = f
                break

    entrepreneur_roles = []
    if selected_format:
        entrepreneur_roles = get_entrepreneur_roles(selected_format.get("typical_staff", []))

    return {
        "niche_id": niche_id,
        "niche_name": niche_meta.get("name_rus", niche_id),
        "archetype": archetype,
        "archetype_name": archetype_meta.get("name_rus", ""),
        "revenue_formula": archetype_meta.get("revenue_formula", ""),
        "category": niche_meta.get("category", ""),
        "icon": niche_meta.get("icon", ""),
        "questions": qc_cfg.get("questions", []),
        "formats": formats,
        "selected_format_id": format_id,
        "selected_format": selected_format,
        "entrepreneur_roles": entrepreneur_roles,
        "locations_meta": locations_cfg,
    }


def get_niche_survey(db, niche_id: str, tier: str = "express") -> dict:
    """Возвращает упорядоченный список вопросов для указанной ниши и tier'а.

    Структура ответа:
      {
        niche_id: "BARBER",
        tier: "express",
        questions: [
          {qid, question_text, input_type, options, min, max, step, unit, help,
           required, order, depends_on: [{depends_on, condition, action}, ...]},
          ...
        ]
      }
    """
    tier = (tier or "express").lower()
    if tier not in ("express", "finmodel"):
        tier = "express"

    catalog = getattr(db, "surveys_questions", pd.DataFrame())
    applic  = getattr(db, "surveys_applic", pd.DataFrame())
    deps    = getattr(db, "surveys_deps", pd.DataFrame())

    out = {"niche_id": niche_id, "tier": tier, "questions": []}

    if catalog is None or catalog.empty or applic is None or applic.empty:
        return out

    # 1. Берём строки applicability для (niche, tier) или wildcard niche='*'
    mask = ((applic["niche_id"].astype(str) == niche_id) | (applic["niche_id"].astype(str) == "*")) \
           & (applic["tier"].astype(str) == tier)
    rows = applic[mask].copy()
    if rows.empty:
        return out

    # 2. Сортируем по order
    rows = rows.sort_values("order")

    # 3. Для каждой строки — подтягиваем из каталога метаданные вопроса
    catalog_idx = {str(r["qid"]).strip(): r for _, r in catalog.iterrows()}
    for _, ar in rows.iterrows():
        qid = str(ar.get("qid", "")).strip()
        cat_row = catalog_idx.get(qid)
        if cat_row is None:
            continue
        q = _question_to_dict(cat_row)
        q["order"]      = int(ar.get("order") or 0)
        q["required"]   = str(ar.get("required", "yes") or "yes").strip()
        q["depends_on"] = _dependencies_for(deps, qid)
        out["questions"].append(q)

    return out
