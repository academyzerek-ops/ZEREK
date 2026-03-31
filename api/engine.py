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

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
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
        """Загрузка общих файлов. Список ниш = файлы в data/niches/ (07_niches удалён)."""
        self.cities = self._xl("01_cities.xlsx", "Города", 4)
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
                  'MARKET','LAUNCH','INSIGHTS','PRODUCTS','MARKETING','SUPPLIERS','SURVEY']

        # Маппинг niche_id → название (для API)
        NICHE_NAMES = {
            'COFFEE': 'Кофейня', 'BAKERY': 'Пекарня', 'CARWASH': 'Автомойка',
            'DONER': 'Донерная', 'BARBER': 'Барбершоп', 'CLEAN': 'Клининг',
            'GROCERY': 'Продуктовый магазин', 'PHARMA': 'Аптека',
            'BEAUTY': 'Салон красоты', 'FITNESS': 'Фитнес', 'PIZZA': 'Пиццерия',
            'SUSHI': 'Суши-бар', 'LAUNDRY': 'Прачечная', 'FLOWERS': 'Цветочный',
            'PET': 'Зоомагазин', 'KIDS': 'Детский центр', 'AUTO_SERVICE': 'Автосервис',
            'TIRE': 'Шиномонтаж', 'COWORKING': 'Коворкинг', 'HOOKAH': 'Кальянная',
            'FAST_FOOD': 'Фаст-фуд', 'CLOTHING': 'Магазин одежды',
            'DENTAL': 'Стоматология', 'COURIER': 'Курьерская служба',
            'REPAIR_PHONE': 'Ремонт телефонов', 'PHOTO': 'Фотостудия',
            'PRINTING': 'Типография', 'TRAVEL': 'Турагентство',
            'TUTORING': 'Репетиторский центр', 'STATIONERY': 'Канцелярия',
        }
        NICHE_ICONS = {
            'COFFEE': '☕', 'BAKERY': '🥐', 'CARWASH': '🚗', 'DONER': '🌯',
            'BARBER': '💈', 'CLEAN': '🧹', 'GROCERY': '🛒', 'PHARMA': '💊',
            'BEAUTY': '💅', 'FITNESS': '🏋️', 'PIZZA': '🍕', 'SUSHI': '🍣',
            'LAUNDRY': '👔', 'FLOWERS': '💐', 'PET': '🐾', 'KIDS': '🧒',
            'AUTO_SERVICE': '🔧', 'TIRE': '🛞', 'COWORKING': '💻', 'HOOKAH': '💨',
            'FAST_FOOD': '🍔', 'CLOTHING': '👗', 'DENTAL': '🦷', 'COURIER': '📦',
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
        """Получить строку по format_id + class. Возвращает dict или {} если не найдено."""
        df = self.get_niche_sheet(niche_id, sheet)
        if df.empty:
            return {}
        mask = (df['format_id'].astype(str) == format_id) & (df['class'].astype(str) == cls)
        rows = df[mask]
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
    """Точка безубыточности."""
    check = _safe_int(fin.get('check_med'), 1000)
    cogs_pct = _safe_float(fin.get('cogs_pct'), DEFAULTS['cogs_pct'])
    loss_pct = _safe_float(fin.get('loss_pct'), DEFAULTS['loss_pct'])

    fot_full = _safe_int(staff.get('fot_full_med'), 0)
    if fot_full == 0:
        fot_full = int(_safe_int(staff.get('fot_net_med'), 0) * DEFAULTS['fot_multiplier'])

    rent = _safe_int(fin.get('rent_med'), 0) * qty
    utilities = _safe_int(fin.get('utilities'), 0) * qty
    software = _safe_int(fin.get('software'), 0)
    sez = _safe_int(fin.get('sez_month'), 0)

    fixed = fot_full + rent + utilities + software + sez
    variable_pct = cogs_pct + loss_pct + tax_rate

    if variable_pct >= 1.0:
        return {"тб_₸": 0, "тб_чеков_день": 0, "запас_прочности_%": 0}

    tb_revenue = int(fixed / (1 - variable_pct))
    tb_checks_day = int(tb_revenue / 30 / check) if check > 0 else 0

    rev_med = _safe_int(fin.get('revenue_med'), 0) * qty
    safety = round((rev_med - tb_revenue) / rev_med * 100, 1) if rev_med > 0 else 0

    return {
        "тб_₸": tb_revenue,
        "тб_чеков_день": tb_checks_day,
        "запас_прочности_%": safety,
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
    capital: int,
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

    # ── Капитал ──
    capital_gap = capital - capex_total
    capital_signal = "✅ Капитала достаточно" if capital_gap >= 0 else f"🔴 Не хватает {abs(capital_gap):,} ₸"

    fot_med = _safe_int(staff.get('fot_net_med'), 0)
    reserve_months = round(capital_gap / (fot_med + rent_month_total), 1) if capital_gap > 0 and (fot_med + rent_month_total) > 0 else 0

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
    if capital_gap >= 0: score += 2
    else: score -= 2; reasons.append("Недостаточно капитала")

    safety = breakeven.get("запас_прочности_%", 0)
    if safety >= 30: score += 2
    elif safety >= 10: score += 1
    else: score -= 1; reasons.append("Низкий запас прочности")

    pb_m = payback.get("месяц")
    if pb_m and pb_m <= 18: score += 2
    elif pb_m and pb_m <= 30: score += 1
    else: score -= 1; reasons.append("Долгая окупаемость")

    sat = competitors.get("уровень", 3)
    if sat <= 2: score += 1
    elif sat >= 4: score -= 1; reasons.append("Высокая конкуренция")

    if score >= 5:
        verdict = {"color":"green","emoji":"✅","text":"Проект рекомендован к запуску","score":score,"reasons":reasons}
    elif score >= 2:
        verdict = {"color":"yellow","emoji":"⚠️","text":"Проект требует доработки","score":score,"reasons":reasons}
    else:
        verdict = {"color":"red","emoji":"🔴","text":"Высокий риск — пересмотрите параметры","score":score,"reasons":reasons}

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
