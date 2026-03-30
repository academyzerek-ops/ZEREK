"""
ZEREK Quick Check Engine v2.0
Расчётный движок для генерации отчёта Quick Check.
Обновлено: НК РК 2026, 3 сценария, B2B предупреждения, ставки маслихатов.
"""

import pandas as pd
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")

SEASON_LABELS = ["Янв","Фев","Мар","Апр","Май","Июн",
                 "Июл","Авг","Сен","Окт","Ноя","Дек"]

# МРП и МЗП 2026 (Закон №239-VIII от 08.12.2025)
MRP_2026 = 4325
MZP_2026 = 85000

# ─────────────────────────────────────────────
# 1. ЗАГРУЗКА БАЗЫ ДАННЫХ
# ─────────────────────────────────────────────

class ZerekDB:
    """Загружает все файлы базы данных включая новые таблицы v2."""

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self._load()

    def _xl(self, filename: str, sheet: str = None, header: int = 0) -> pd.DataFrame:
        path = os.path.join(self.data_dir, filename)
        if not os.path.exists(path):
            print(f"⚠️ Файл не найден: {filename}")
            return pd.DataFrame()
        if sheet:
            return pd.read_excel(path, sheet_name=sheet, header=header)
        return pd.read_excel(path, header=header)

    def _load(self):
        # ── Существующие таблицы ──
        self.cities = self._xl("01_cities.xlsx", "Города", 4)
        self.wages_region = self._xl("02_wages_by_city.xlsx", "Зарплаты по регионам", 5)
        self.niches = self._xl("07_niches.xlsx", "Ниши", 5)
        self.formats = self._xl("08_niche_formats.xlsx", "Форматы", 5)
        self.unit_econ = self._xl("09_unit_economics.xlsx", "Сводка для движка", 5)
        self.unit_econ_full = self._xl("09_unit_economics.xlsx", "Юнит-экономика", 5)
        self.capex_totals = self._xl("10_capex.xlsx", "Итоги по форматам", 5)
        self.capex_items = self._xl("10_capex.xlsx", "CAPEX по форматам", 5)
        self.capex_errors = self._xl("10_capex.xlsx", "Частые ошибки при планировании", 4)
        self.rent = self._xl("11_rent_benchmarks.xlsx", "Калькулятор для движка", 5)
        self.rent_tips = self._xl("11_rent_benchmarks.xlsx", "Советы по локации", 4)
        self.staff_fot = self._xl("12_staff_templates.xlsx", "Сводка ФОТ", 4)
        self.staff_detail = self._xl("12_staff_templates.xlsx", "Штат по форматам", 5)
        self.inflation = self._xl("13_macro_dynamics.xlsx", "Инфляция по регионам", 5)
        self.kei = self._xl("13_macro_dynamics.xlsx", "Индекс КЭИ", 5)
        self.competitors = self._xl("14_competitors.xlsx", "Конкуренты по городам", 5)
        self.failure_patterns = self._xl("15_failure_cases.xlsx", "Паттерны по нишам", 5)
        self.permits = self._xl("17_permits.xlsx", "Разрешения и лицензии", 5)
        self.consumer = self._xl("18_consumer_behavior.xlsx", "Поведение потребителей", 5)
        self.inflation_niche = self._xl("19_inflation_by_niche.xlsx", "Прогноз роста OPEX", 5)

        # ── Новые таблицы v2 ──

        # 05 — Налоги 2026 (обновлённый файл с тем же именем)
        self.tax_regimes = self._xl("05_tax_regimes.xlsx", "tax_regimes_2026", 0)
        self.city_tax_rates = self._xl("05_tax_regimes.xlsx", "city_ud_rates_2026", 0)
        self.b2b_warnings = self._xl("05_tax_regimes.xlsx", "b2b_nds_warnings", 0)
        self.payroll_taxes = self._xl("05_tax_regimes.xlsx", "payroll_taxes_2026", 0)
        self.key_params = self._xl("05_tax_regimes.xlsx", "key_params_2026", 0)

        # 20 — Коэффициенты сценариев (пессимист/база/оптимист)
        self.scenarios = self._xl("20_scenario_coefficients.xlsx", "scenario_coefficients", 0)

        # 21 — OPEX бенчмарки по статьям
        self.opex_bench = self._xl("21_opex_benchmarks.xlsx", "opex_benchmarks", 0)

        # 22 — Масштабирование штата по обороту
        self.staff_scaling = self._xl("22_staff_scaling.xlsx", "staff_scaling", 0)

        print("✅ База данных v2 загружена.")


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
        niche = format_id.split("_")[0]
        rows = db.capex_totals[db.capex_totals["niche_id"] == niche]
    return rows.iloc[0].to_dict()

def get_rent_median(db: ZerekDB, city_id: str, loc_type: str) -> tuple:
    df = db.rent
    rows = df[(df["city_id"] == city_id) & (df["Тип локации"].str.contains(loc_type, na=False))]
    if rows.empty:
        rows = df[df["city_id"] == city_id]
    if rows.empty:
        return 5000, 500
    row = rows.iloc[0]
    return row["Медиана (₸/м²/мес)"], row["Коммуналка (₸/м²/мес)"]

def get_fot(db: ZerekDB, format_id: str, city_id: str) -> int:
    rows = db.staff_fot[db.staff_fot["format_id"] == format_id]
    if rows.empty:
        return 0
    row = rows.iloc[0]
    big_cities = ["ALA", "AST", "SHY"]
    mid_cities = ["AKT", "ATY", "AKA", "URA", "KZO"]
    if city_id in big_cities:
        fot_gross = row.get("ФОТ gross Алматы (₸)", 0)
        return int(fot_gross * 1.065)
    elif city_id in mid_cities:
        return int(row.get("Расход работодателя Актобе (с налогами ₸)", 0))
    else:
        fot_small = row.get("ФОТ малый город (₸)", 0)
        return int(fot_small * 1.065)

def get_city_wage_coef(db: ZerekDB, city_id: str) -> float:
    coefs = {
        "ALA": 1.35, "AST": 1.32, "SHY": 0.95,
        "AKT": 1.00, "ATY": 1.40, "AKA": 1.38,
        "URA": 0.92, "TAR": 0.82, "PAV": 0.95,
        "OSK": 0.93, "KOS": 0.87, "KZO": 0.90,
        "SEM": 0.88, "PET": 0.78, "KOK": 0.80,
    }
    return coefs.get(city_id, 1.00)

def get_inflation_region(db: ZerekDB, city_id: str) -> float:
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
        return 11.7
    return float(rows.iloc[0]["Инфляция фев 2026 (%)"])

def get_competitors_signal(db: ZerekDB, niche_id: str, city_id: str) -> dict:
    df = db.competitors
    rows = df[(df["niche_id"] == niche_id) & (df["city_id"] == city_id)]
    if rows.empty:
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
    return rows.iloc[0].to_dict()

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
# 2b. НОВЫЕ ФУНКЦИИ v2 — налоги, сценарии, штат
# ─────────────────────────────────────────────

def get_city_tax_rate(db: ZerekDB, city_id: str) -> float:
    """Ставка УД по городу на основе решений маслихатов 2026."""
    if db.city_tax_rates.empty:
        return 4.0
    rows = db.city_tax_rates[db.city_tax_rates["city_id"] == city_id]
    if rows.empty:
        return 4.0  # базовая ставка НК РК
    return float(rows.iloc[0]["ud_rate_pct"])


def get_b2b_warning(db: ZerekDB, niche_id: str, format_id: str) -> dict:
    """Предупреждение о B2B и НДС для конкретной ниши/формата."""
    if db.b2b_warnings.empty:
        return {"b2b_likelihood": "low", "warning": "", "recommendation": ""}

    # Сначала точное совпадение по формату
    rows = db.b2b_warnings[db.b2b_warnings["format_id"] == format_id]
    if rows.empty:
        # Потом по нише с ALL
        rows = db.b2b_warnings[
            (db.b2b_warnings["niche_id"] == niche_id) &
            (db.b2b_warnings["format_id"] == "ALL")
        ]
    if rows.empty:
        return {"b2b_likelihood": "low", "warning": "", "recommendation": ""}

    row = rows.iloc[0]
    return {
        "b2b_likelihood": row.get("b2b_likelihood", "low"),
        "warning": row.get("b2b_warning_ru", ""),
        "recommendation": row.get("recommendation_ru", ""),
    }


def get_scenario_coefs(db: ZerekDB, format_id: str) -> dict:
    """Коэффициенты для 3 сценариев по формату."""
    if db.scenarios.empty:
        return {
            "pess": {"traffic": 0.65, "check": 0.90},
            "base": {"traffic": 1.00, "check": 1.00},
            "opt":  {"traffic": 1.25, "check": 1.10},
        }
    rows = db.scenarios[db.scenarios["format_id"] == format_id]
    if rows.empty:
        return {
            "pess": {"traffic": 0.65, "check": 0.90},
            "base": {"traffic": 1.00, "check": 1.00},
            "opt":  {"traffic": 1.25, "check": 1.10},
        }
    row = rows.iloc[0]
    return {
        "pess": {
            "traffic": float(row.get("pessimistic_traffic_coef", 0.65)),
            "check":   float(row.get("pessimistic_check_coef", 0.90)),
        },
        "base": {
            "traffic": float(row.get("base_traffic_coef", 1.00)),
            "check":   float(row.get("base_check_coef", 1.00)),
        },
        "opt": {
            "traffic": float(row.get("optimistic_traffic_coef", 1.25)),
            "check":   float(row.get("optimistic_check_coef", 1.10)),
        },
    }


def get_opex_benchmarks(db: ZerekDB, format_id: str) -> dict:
    """Детальные OPEX бенчмарки по формату."""
    if db.opex_bench.empty:
        return {}
    rows = db.opex_bench[db.opex_bench["format_id"] == format_id]
    if rows.empty:
        return {}
    return rows.iloc[0].to_dict()


def get_staff_scaling(db: ZerekDB, format_id: str) -> list:
    """Штат по этапам роста для формата."""
    if db.staff_scaling.empty:
        return []
    rows = db.staff_scaling[db.staff_scaling["format_id"] == format_id]
    if rows.empty:
        return []
    result = []
    for _, row in rows.iterrows():
        result.append({
            "stage": row.get("stage", ""),
            "stage_label": row.get("stage_label_ru", ""),
            "role": row.get("role_ru", ""),
            "headcount": int(row.get("headcount", 0)),
            "salary": int(row.get("salary_kzt", 0)),
            "is_owner": bool(row.get("is_owner_role", False)),
            "notes": row.get("notes_ru", ""),
        })
    return result


def calc_staff_fot_by_stage(staff_list: list, stage: str) -> dict:
    """Считает ФОТ для конкретного этапа с налогами работодателя."""
    EMPLOYER_TAX_UD = 0.115  # ОПВР 3.5% + СО 5% + ООСМС 3% (соцналог отменён для УД)

    stage_staff = [s for s in staff_list if s["stage"] == stage]
    total_salary = 0
    total_fot = 0
    headcount = 0

    for s in stage_staff:
        if s["is_owner"]:
            continue  # собственник — без зарплаты
        gross = s["salary"] * s["headcount"]
        total_salary += gross
        total_fot += int(gross * (1 + EMPLOYER_TAX_UD))
        headcount += s["headcount"]

    return {
        "stage": stage,
        "headcount": headcount,
        "total_salary": total_salary,
        "total_fot_with_taxes": total_fot,
        "staff": stage_staff,
    }


def build_tax_recommendation(db: ZerekDB, city_id: str, niche_id: str,
                              format_id: str, annual_revenue: int) -> dict:
    """Полная рекомендация по налоговому режиму."""
    ud_rate = get_city_tax_rate(db, city_id)
    b2b = get_b2b_warning(db, niche_id, format_id)

    # Базовая рекомендация
    if b2b["b2b_likelihood"] == "high":
        regime = "ОУР (общеустановленный режим)"
        explanation = (
            f"Ваши клиенты — юрлица на ОУР. Они НЕ смогут взять НДС в зачёт "
            f"по вашим счетам на упрощёнке. Это снижает вашу конкурентоспособность. "
            f"Рекомендуем ТОО на ОУР (КПН 20% + НДС 16%). Ваши клиенты смогут зачесть НДС."
        )
        tax_amount = int(annual_revenue * 0.20 * 0.3)  # ~30% маржи × 20% КПН — упрощённо
    else:
        regime = f"ИП на упрощённой декларации ({ud_rate}%)"
        explanation = (
            f"При вашем обороте упрощёнка оптимальна. "
            f"Ставка в вашем городе: {ud_rate}% от дохода, оплата раз в полгода. "
            f"Минимум отчётности. Социальный налог отменён для упрощёнки в 2026 году."
        )
        tax_amount = int(annual_revenue * ud_rate / 100)

    # Порог НДС для информации
    nds_threshold = 10000 * MRP_2026  # 43 250 000 ₸

    return {
        "рекомендация": regime,
        "ставка_города_%": ud_rate,
        "объяснение": explanation,
        "налог_примерный_год": tax_amount,
        "b2b_предупреждение": b2b["warning"],
        "b2b_рекомендация": b2b["recommendation"],
        "b2b_likelihood": b2b["b2b_likelihood"],
        "порог_ндс": nds_threshold,
        "мрп_2026": MRP_2026,
    }


# ─────────────────────────────────────────────
# 3. ЯДРО РАСЧЁТОВ
# ─────────────────────────────────────────────

def calc_revenue_monthly(ue: dict, month: int, razgon_month: int) -> int:
    """Выручка в конкретный месяц с учётом разгона и сезонности."""
    base = ue["Выручка/мес (₸)"]
    razgon_coefs = {
        1: ue.get("Коэф. м1", 0.4),
        2: ue.get("Коэф. м2", 0.65),
        3: ue.get("Коэф. м3", 0.85),
    }
    razgon = razgon_coefs.get(razgon_month, 1.0)
    if razgon_month > int(ue.get("Разгон мес.", 3)):
        razgon = 1.0

    season_min_label = ue.get("Сезон. мин (месяц)", "Янв")
    season_max_label = ue.get("Сезон. макс (месяц)", "Дек")
    season_min_coef  = float(ue.get("Сезон. коэф. мин", 0.85))
    season_max_coef  = float(ue.get("Сезон. коэф. макс", 1.15))
    min_m = SEASON_LABELS.index(season_min_label) + 1 if season_min_label in SEASON_LABELS else 1
    max_m = SEASON_LABELS.index(season_max_label) + 1 if season_max_label in SEASON_LABELS else 12

    if month == min_m:
        season = season_min_coef
    elif month == max_m:
        season = season_max_coef
    else:
        season = (season_min_coef + season_max_coef) / 2 + \
                  (0.05 * ((month - min_m) % 12) / 6 - 0.05)
        season = max(season_min_coef, min(season_max_coef, season))

    return int(base * razgon * season)


def calc_cashflow(
    ue: dict,
    fot: int,
    rent_month: int,
    capex: int,
    tax_rate: float = 0.04,  # обновлено: 4% базовая ставка 2026
    start_month: int = 1,
    months: int = 12,
    opex_bench: dict = None,
) -> list:
    """Cash Flow на 12 месяцев с детальными OPEX."""
    results = []
    cumulative = -capex

    # Если есть OPEX бенчмарки — используем их, иначе старые %
    if opex_bench:
        cogs_pct = float(opex_bench.get("consumables_pct", 0.30))
        util_fixed = int(opex_bench.get("utilities_fixed_kzt", 0))
        mkt_pct = float(opex_bench.get("marketing_pct", 0.03))
        mkt_fixed = int(opex_bench.get("marketing_fixed_kzt", 30000))
        pkg_pct = float(opex_bench.get("packaging_pct", 0))
        soft_fixed = int(opex_bench.get("software_kzt", 5000))
        trans_fixed = int(opex_bench.get("transport_kzt", 0))
        misc_pct = float(opex_bench.get("misc_pct", 0.02))
    else:
        cogs_pct = float(ue.get("COGS%", 30)) / 100
        util_fixed = 0
        mkt_pct = 0.03
        mkt_fixed = 0
        pkg_pct = 0
        soft_fixed = 5000
        trans_fixed = 0
        misc_pct = 0.02

    for i in range(months):
        razgon_month = i + 1
        cal_month = ((start_month - 1 + i) % 12) + 1
        rev = calc_revenue_monthly(ue, cal_month, razgon_month)

        cogs = int(rev * cogs_pct)
        gross = rev - cogs
        util = util_fixed if util_fixed else int(rev * 0.04)
        mkt = mkt_fixed + int(rev * mkt_pct)
        pkg = int(rev * pkg_pct)
        soft = soft_fixed
        trans = trans_fixed
        other = int(rev * misc_pct)
        tax = int(rev * tax_rate)

        opex = fot + rent_month + util + mkt + pkg + soft + trans + other + tax
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
            "упаковка": pkg,
            "по_касса": soft,
            "транспорт": trans,
            "прочие": other,
            "налог": tax,
            "opex": opex,
            "прибыль": profit,
            "нарастающий": cumulative,
        })

    return results


def calc_breakeven(ue: dict, fot: int, rent_month: int, tax_rate: float = 0.04,
                   opex_bench: dict = None) -> dict:
    """Точка безубыточности в ₸ и единицах."""
    if opex_bench:
        cogs_pct = float(opex_bench.get("consumables_pct", 0.30))
        variable_pct = cogs_pct + float(opex_bench.get("marketing_pct", 0.03)) + \
                       float(opex_bench.get("packaging_pct", 0)) + \
                       float(opex_bench.get("misc_pct", 0.02)) + tax_rate
        fixed_extra = int(opex_bench.get("utilities_fixed_kzt", 0)) + \
                      int(opex_bench.get("marketing_fixed_kzt", 0)) + \
                      int(opex_bench.get("software_kzt", 0)) + \
                      int(opex_bench.get("transport_kzt", 0))
    else:
        cogs_pct = float(ue.get("COGS%", 30)) / 100
        variable_pct = cogs_pct + 0.04 + 0.03 + 0.02 + tax_rate
        fixed_extra = 0

    fixed = fot + rent_month + fixed_extra

    if variable_pct >= 1:
        return {"тб_выручка": 0, "тб_единиц_мес": 0, "тб_единиц_день": 0,
                "текущий_трафик": 0, "запас_прочности_%": 0}

    tb_rev = fixed / (1 - variable_pct)
    check = float(ue.get("Чек (₸)", 1000))
    tb_units = tb_rev / check
    days = float(ue.get("Дней/мес", 26))
    tb_per_day = tb_units / days
    current_traffic = float(ue.get("Трафик/день", 0))

    safety = 0
    if current_traffic > 0:
        safety = round((current_traffic - tb_per_day) / current_traffic * 100, 1)

    return {
        "тб_выручка": int(tb_rev),
        "тб_единиц_мес": int(tb_units),
        "тб_единиц_день": round(tb_per_day, 1),
        "текущий_трафик": current_traffic,
        "запас_прочности_%": safety,
    }


def calc_payback(capex: int, cashflow: list) -> dict:
    for cf in cashflow:
        if cf["нарастающий"] >= 0:
            return {"месяц": cf["месяц"], "статус": "✅ Окупается в горизонте 12 мес."}
    avg_profit = sum(cf["прибыль"] for cf in cashflow[-3:]) / 3
    if avg_profit > 0:
        remaining = abs(cashflow[-1]["нарастающий"])
        extra = remaining / avg_profit
        return {
            "месяц": round(12 + extra, 1),
            "статус": f"⚠️ Окупаемость ~{round(12 + extra, 1)} мес."
        }
    return {"месяц": None, "статус": "🔴 Не окупается при текущих параметрах"}


def calc_tam_sam_som(city: dict, niche_id: str, competitors: dict) -> dict:
    pop = int(city.get("Население всего (чел.)", 0))
    working = int(city.get("Трудоспособные 16-62 (чел.)", 0))
    men_1845 = int(city.get("Мужчины ~18-45 (оценка)", 0))
    women_1850 = int(city.get("Женщины ~18-50 (оценка)", 0))

    tam_map = {
        "COFFEE": working, "DONER": working, "CARWASH": men_1845,
        "CLEAN": working, "GROCERY": pop, "PHARMA": pop,
        "BARBER": men_1845, "MANICURE": women_1850,
    }
    tam = tam_map.get(niche_id, working)

    sam_pct_map = {
        "COFFEE": 0.03, "DONER": 0.04, "CARWASH": 0.05,
        "CLEAN": 0.08, "GROCERY": 0.03, "PHARMA": 0.03,
        "BARBER": 0.06, "MANICURE": 0.06,
    }
    sam = int(tam * sam_pct_map.get(niche_id, 0.04))

    sat = competitors.get("уровень", 3)
    som_pct_map = {1: 0.30, 2: 0.25, 3: 0.15, 4: 0.10, 5: 0.07}
    som = int(sam * som_pct_map.get(sat, 0.15))

    return {
        "tam": tam, "tam_label": "потенциальная аудитория ниши",
        "sam": sam, "sam_label": "охват одной точки (радиус ~2 км)",
        "som": som, "som_label": "реалистичная доля с учётом конкуренции",
    }


def build_verdict(capital_gap: int, breakeven: dict, payback: dict,
                  competitors: dict) -> dict:
    """Итоговая экспертная оценка: зелёный/жёлтый/красный."""
    score = 0
    reasons = []

    # Капитал
    if capital_gap >= 0:
        score += 2
    else:
        score -= 2
        reasons.append("Недостаточно капитала")

    # Запас прочности
    safety = breakeven.get("запас_прочности_%", 0)
    if safety >= 30:
        score += 2
    elif safety >= 10:
        score += 1
    else:
        score -= 1
        reasons.append("Низкий запас прочности")

    # Окупаемость
    payback_m = payback.get("месяц")
    if payback_m and payback_m <= 18:
        score += 2
    elif payback_m and payback_m <= 30:
        score += 1
    else:
        score -= 1
        reasons.append("Долгая окупаемость")

    # Конкуренция
    sat = competitors.get("уровень", 3)
    if sat <= 2:
        score += 1
    elif sat >= 4:
        score -= 1
        reasons.append("Высокая конкуренция")

    # Вердикт
    if score >= 5:
        color = "green"
        text = "Проект рекомендован к запуску"
        emoji = "✅"
    elif score >= 2:
        color = "yellow"
        text = "Проект требует доработки"
        emoji = "⚠️"
    else:
        color = "red"
        text = "Высокий риск — рекомендуем пересмотреть параметры"
        emoji = "🔴"

    return {
        "color": color,
        "text": text,
        "emoji": emoji,
        "score": score,
        "reasons": reasons,
    }


# ─────────────────────────────────────────────
# 4. ГЛАВНАЯ ФУНКЦИЯ — ПОЛНЫЙ РАСЧЁТ v2
# ─────────────────────────────────────────────

def run_quick_check(
    db: ZerekDB,
    city_id: str,
    niche_id: str,
    format_id: str,
    area_m2: float,
    loc_type: str,
    capital: int,
    rent_override: int = None,
    start_month: int = 4,
    capex_level: str = "стандарт",
) -> dict:
    """
    Запускает полный расчёт Quick Check v2.
    Возвращает структурированный словарь для 9 блоков отчёта.
    Включает 3 сценария, B2B предупреждения, ставки маслихатов, экспертную оценку.
    """

    # ── Базовые данные ──
    city = get_city(db, city_id)
    ue = get_unit_econ(db, format_id)

    # ── CAPEX ──
    capex_row = get_capex(db, format_id)
    capex_cols = {"эконом": "CAPEX эконом (₸)", "стандарт": "CAPEX стандарт (₸)", "премиум": "CAPEX премиум (₸)"}
    capex = int(capex_row.get(capex_cols[capex_level], 0))
    capex_all = {
        "эконом": int(capex_row.get("CAPEX эконом (₸)", 0)),
        "стандарт": int(capex_row.get("CAPEX стандарт (₸)", 0)),
        "премиум": int(capex_row.get("CAPEX премиум (₸)", 0)),
    }

    rent_median, util_per_m2 = get_rent_median(db, city_id, loc_type)
    rent_month = rent_override if rent_override else int(area_m2 * rent_median)
    deposit = rent_month * 2
    capex_total = capex + deposit

    # ── ФОТ ──
    fot = get_fot(db, format_id, city_id)
    if fot == 0:
        fot = int(ue["Выручка/мес (₸)"] * float(ue.get("ФОТ%", 25)) / 100)

    # ── Ставка налога по городу ──
    tax_rate = get_city_tax_rate(db, city_id) / 100

    # ── OPEX бенчмарки ──
    opex_bench = get_opex_benchmarks(db, format_id)

    # ── Сценарии (пессимист/база/оптимист) ──
    sc = get_scenario_coefs(db, format_id)
    base_check = int(ue.get("Чек (₸)", 0))
    base_traffic = int(ue.get("Трафик/день", 0))
    base_rev = int(ue.get("Выручка/мес (₸)", 0))

    scenarios = {}
    for label, coefs in sc.items():
        s_traffic = int(base_traffic * coefs["traffic"])
        s_check = int(base_check * coefs["check"])
        s_rev = int(base_rev * coefs["traffic"] * coefs["check"])

        # Создаём модифицированную юнит-экономику для сценария
        ue_scenario = ue.copy()
        ue_scenario["Выручка/мес (₸)"] = s_rev

        s_cashflow = calc_cashflow(
            ue=ue_scenario, fot=fot, rent_month=rent_month, capex=capex_total,
            tax_rate=tax_rate, start_month=start_month, opex_bench=opex_bench or None,
        )
        s_breakeven = calc_breakeven(ue, fot, rent_month, tax_rate, opex_bench or None)
        s_payback = calc_payback(capex_total, s_cashflow)
        s_avg_profit = sum(cf["прибыль"] for cf in s_cashflow) / 12

        scenarios[label] = {
            "трафик_день": s_traffic,
            "чек": s_check,
            "выручка_мес": s_rev,
            "прибыль_среднемес": int(s_avg_profit),
            "окупаемость": s_payback,
            "cashflow": s_cashflow,
        }

    # ── Основной Cash Flow (базовый сценарий) ──
    cashflow = scenarios["base"]["cashflow"]
    breakeven = calc_breakeven(ue, fot, rent_month, tax_rate, opex_bench or None)
    payback = scenarios["base"]["окупаемость"]

    # ── TAM/SAM/SOM ──
    competitors = get_competitors_signal(db, niche_id, city_id)
    tam_sam_som = calc_tam_sam_som(city, niche_id, competitors)

    # ── Капитал ──
    capital_gap = capital - capex_total
    capital_signal = (
        "✅ Капитала достаточно" if capital_gap >= 0
        else f"🔴 Не хватает {abs(capital_gap):,} ₸"
    )
    reserve_months = round(capital_gap / (fot + rent_month), 1) if capital_gap > 0 and (fot + rent_month) > 0 else 0

    # ── Штат по этапам ──
    staff_stages = get_staff_scaling(db, format_id)
    staff_start = calc_staff_fot_by_stage(staff_stages, "start") if staff_stages else {}
    staff_growth = calc_staff_fot_by_stage(staff_stages, "growth") if staff_stages else {}
    staff_scale = calc_staff_fot_by_stage(staff_stages, "scale") if staff_stages else {}

    # ── Налоговая рекомендация ──
    total_rev_y1 = sum(cf["выручка"] for cf in cashflow)
    tax_rec = build_tax_recommendation(db, city_id, niche_id, format_id, total_rev_y1)

    # ── Макро ──
    inf_niche = get_inflation_niche(db, niche_id)
    opex_growth = float(str(inf_niche.get("Прогноз роста OPEX в целом %/год", 11.5))
                        .replace("%","").strip()) / 100
    inf_region = get_inflation_region(db, city_id)

    # ── Риски ──
    failure = get_failure_pattern(db, niche_id)
    consumer = get_consumer_behavior(db, niche_id, city_id)
    permits = get_permits(db, niche_id)

    # ── Вердикт ──
    verdict = build_verdict(capital_gap, breakeven, payback, competitors)

    total_profit_y1 = sum(cf["прибыль"] for cf in cashflow)
    base_margin = float(ue.get("Операц. маржа%", 0))

    # ── РЕЗУЛЬТАТ ──
    return {
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

        # Блок 1: Обзор рынка
        "market": {
            "population": int(city.get("Население всего (чел.)", 0)),
            "working_age": int(city.get("Трудоспособные 16-62 (чел.)", 0)),
            "men_1845": int(city.get("Мужчины ~18-45 (оценка)", 0)),
            "women_1850": int(city.get("Женщины ~18-50 (оценка)", 0)),
            "growth_rate": city.get("Темп прироста 2025 %", 0),
            "tam_sam_som": tam_sam_som,
            "competitors": competitors,
            "consumer_behavior": consumer,
        },

        # Блок 2: Локация
        "location": {
            "rent_month": rent_month,
            "rent_benchmark_m2": rent_median,
            "rent_per_m2": int(rent_month / area_m2) if area_m2 > 0 else 0,
            "deposit": deposit,
        },

        # Блок 3: Инвестиции (CAPEX)
        "capex": {
            "оборудование_и_ремонт": capex,
            "депозит_аренды": deposit,
            "итого": capex_total,
            "все_уровни": capex_all,
            "капитал_пользователя": capital,
            "разница": capital_gap,
            "запас_месяцев": reserve_months,
            "сигнал": capital_signal,
            "уровень": capex_level,
        },

        # Блок 4: Штат
        "staff": {
            "start": staff_start,
            "growth": staff_growth,
            "scale": staff_scale,
            "all_stages": staff_stages,
        },

        # Блок 5: OPEX
        "opex": {
            "фот": fot,
            "аренда": rent_month,
            "benchmarks": opex_bench,
            "рост_opex_прогноз_%": opex_growth * 100,
        },

        # Блок 6: Выручка и ТБ (3 сценария)
        "scenarios": {
            "pess": {k: v for k, v in scenarios["pess"].items() if k != "cashflow"},
            "base": {k: v for k, v in scenarios["base"].items() if k != "cashflow"},
            "opt":  {k: v for k, v in scenarios["opt"].items() if k != "cashflow"},
        },
        "breakeven": breakeven,

        # Блок 7: Окупаемость
        "payback": {
            "pess": scenarios["pess"]["окупаемость"],
            "base": scenarios["base"]["окупаемость"],
            "opt":  scenarios["opt"]["окупаемость"],
        },

        # Блок 8: Налоги
        "tax": tax_rec,

        # Блок 9: Итоговая оценка
        "verdict": verdict,
        "risks": {
            "паттерн_закрытий": failure,
            "разрешения": permits.to_dict("records"),
            "конкуренты": competitors,
        },

        # Cash Flow (базовый, полный — для таблицы)
        "cashflow": cashflow,

        # Сводка
        "financials": {
            "базовая_выручка_мес": base_rev,
            "чек": base_check,
            "трафик_день": base_traffic,
            "cogs_pct": float(ue.get("COGS%", 0)),
            "fot_мес": fot,
            "аренда_мес": rent_month,
            "маржа_опер_pct": base_margin,
            "выручка_год1": total_rev_y1,
            "прибыль_год1": total_profit_y1,
            "налоговая_ставка_%": tax_rate * 100,
        },

        # Макро
        "macro": {
            "инфляция_регион_%": inf_region,
            "рост_opex_прогноз_%": opex_growth * 100,
            "мрп_2026": MRP_2026,
            "мзп_2026": MZP_2026,
        },
    }
