"""
ZEREK Quick Check Engine v3.0
Читает данные из niche_formats_{NICHE}.xlsx (12 листов).
Общие файлы: 01_cities, 05_tax_regimes, 07_niches, 11_rent, 13_macro, 14_competitors, 15_failure, 17_permits.
Пустые ячейки = дефолт (без ошибок).
"""

import pandas as pd
import os
import glob
import math
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "kz")
FORMATS_DIR = os.path.join(DATA_DIR, "niches")
CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")

SEASON_LABELS = ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]


# ─────────────────────────────────────────────────────────────────────────
# YAML-конфиги (константы, расчётные дефолты, дефолты финмодели)
# Загружаются один раз при импорте модуля.
# ─────────────────────────────────────────────────────────────────────────

def _load_yaml(name: str) -> dict:
    """Безопасно читает config/{name}.yaml. Возвращает {} при ошибке."""
    path = os.path.join(CONFIG_DIR, f"{name}.yaml")
    if not os.path.exists(path):
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as fh:
            return yaml.safe_load(fh) or {}
    except Exception as e:
        print(f"⚠️ Не удалось прочитать {path}: {e}")
        return {}


CONSTANTS = _load_yaml("constants")
DEFAULTS_CFG = _load_yaml("defaults")
FINMODEL_DEFAULTS_CFG = _load_yaml("finmodel_defaults")

# Базовые константы (с fallback на старые значения на случай отсутствия yaml)
MRP_2026 = int(CONSTANTS.get("mrp_2026", 4325))
MZP_2026 = int(CONSTANTS.get("mzp_2026", 85000))
NDS_RATE = float(CONSTANTS.get("nds_rate", 0.16))

_OWNER = CONSTANTS.get("owner", {}) or {}
OWNER_CLOSURE_POCKET = int(_OWNER.get("closure_pocket_kzt", 200_000))
OWNER_GROWTH_POCKET = int(_OWNER.get("growth_pocket_kzt", 600_000))
OWNER_SOCIAL_RATE = float(_OWNER.get("social_rate", 0.22))
OWNER_SOCIAL_BASE_MRP = int(_OWNER.get("social_base_mrp", 50))
FOT_MULTIPLIER = float(_OWNER.get("fot_multiplier", 1.175))

_TAXES = CONSTANTS.get("taxes", {}) or {}
DEFAULT_TAX_RATE_PCT = float(_TAXES.get("default_tax_rate_pct", 3))
FALLBACK_TAX_RATE_PCT = float(_TAXES.get("fallback_tax_rate_pct", 4))

# Дефолты для пустых ячеек per-niche xlsx (читаются из defaults.yaml)
_QC_DEFAULTS = (DEFAULTS_CFG.get("quick_check", {}) or {}).get("financial_defaults", {}) or {}
DEFAULTS = {
    'cogs_pct':          float(_QC_DEFAULTS.get('cogs_pct', 0.30)),
    'margin_pct':        float(_QC_DEFAULTS.get('margin_pct', 0.70)),
    'deposit_months':    int(_QC_DEFAULTS.get('deposit_months', 2)),
    'loss_pct':          float(_QC_DEFAULTS.get('loss_pct', 0.02)),
    'sez_month':         int(_QC_DEFAULTS.get('sez_month', 0)),
    'rampup_months':     int(_QC_DEFAULTS.get('rampup_months', 3)),
    'rampup_start_pct':  float(_QC_DEFAULTS.get('rampup_start_pct', 0.50)),
    'repeat_pct':        float(_QC_DEFAULTS.get('repeat_pct', 0.40)),
    'traffic_growth_yr': float(_QC_DEFAULTS.get('traffic_growth_yr', 0.07)),
    'check_growth_yr':   float(_QC_DEFAULTS.get('check_growth_yr', 0.08)),
    'rent_growth_yr':    float(_QC_DEFAULTS.get('rent_growth_yr', 0.10)),
    'fot_growth_yr':     float(_QC_DEFAULTS.get('fot_growth_yr', 0.08)),
    'inflation_yr':      float(_QC_DEFAULTS.get('inflation_yr', 0.10)),
    'deprec_years':      int(_QC_DEFAULTS.get('deprec_years', 7)),
    'fot_multiplier':    FOT_MULTIPLIER,
}

# Сценарные коэффициенты (пессимист/база/оптимист/стресс)
_SC = ((DEFAULTS_CFG.get("quick_check", {}) or {}).get("scenario_coefficients", {}) or {})
SCENARIO_PESS   = _SC.get("pessimistic", {'traffic_k': 0.75, 'check_k': 0.90, 'rent_k': 1.00})
SCENARIO_BASE   = _SC.get("base",        {'traffic_k': 1.00, 'check_k': 1.00, 'rent_k': 1.00})
SCENARIO_OPT    = _SC.get("optimistic",  {'traffic_k': 1.25, 'check_k': 1.10, 'rent_k': 1.00})
SCENARIO_STRESS = _SC.get("stress_bad",  {'traffic_k': 0.75, 'check_k': 0.90, 'rent_k': 1.20})

_B7_SCALE = ((DEFAULTS_CFG.get("quick_check", {}) or {}).get("block7_scale", {}) or {})
B7_SCALE_PESS = float(_B7_SCALE.get("pess", 0.75))
B7_SCALE_BASE = float(_B7_SCALE.get("base", 1.00))
B7_SCALE_OPT  = float(_B7_SCALE.get("opt",  1.25))

# Пороги вердикта / скоринга
_V = ((DEFAULTS_CFG.get("quick_check", {}) or {}).get("block1_verdict", {}) or {})
BLOCK1_THRESHOLDS = _V.get("thresholds", [17, 12])
_ST = ((DEFAULTS_CFG.get("quick_check", {}) or {}).get("scoring_thresholds", {}) or {})
SCORING_CAPITAL   = _ST.get("capital_ratio", [1.2, 0.95, 0.75])
SCORING_ROI       = _ST.get("roi", [0.45, 0.30, 0.15])
SCORING_BREAKEVEN = _ST.get("breakeven_months", [6, 12, 18])
SCORING_SATURATION = _ST.get("saturation_ratio", [0.6, 1.0, 1.5])
SCORING_STRESS_DROP = _ST.get("stress_drop", [0.30, 0.50])
SCORING_CITY_POP    = _ST.get("city_population_tiers", [150_000, 300_000])

# Бенчмарки плотности
_BM = ((DEFAULTS_CFG.get("quick_check", {}) or {}).get("benchmarks", {}) or {})
BENCHMARK_COMPETITOR_DENSITY_10K = float(_BM.get("competitor_density_per_10k", 0.8))
BENCHMARK_RETAIL_DENSITY_10K     = float(_BM.get("retail_density_per_10k", 0.75))

# Сезонность по умолчанию (12 мес), если у ниши нет s01..s12 в FINANCIALS.
# Средняя зарплата по городам (для сравнения дохода self-employed с «работой по найму»).
AVG_SALARY_2025 = (CONSTANTS.get("avg_salary_2025") or {})
AVG_SALARY_DEFAULT = int(AVG_SALARY_2025.get("_default") or 430000)

DEFAULT_SEASONALITY = list((DEFAULTS_CFG.get("quick_check", {}) or {}).get(
    "default_seasonality",
    [0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20],
))

# Русские подписи статей CAPEX (ключи из capex.breakdown в run_quick_check_v3).
CAPEX_BREAKDOWN_LABELS_RUS = {
    'equipment':   'Оборудование',
    'renovation':  'Ремонт помещения',
    'furniture':   'Мебель и интерьер',
    'first_stock': 'Первый запас материалов',
    'permits_sez': 'Разрешения и регистрация',
    'working_cap': 'Оборотные средства',
    'marketing':   'Стартовый маркетинг',
    'deposit':     'Депозит за аренду',
    'legal':       'Юридическое оформление',
    'training':    'Обучение и курсы',
}

# Стоимость обучения по уровню опыта для ниш с training_required=True
# (MANICURE в Round 6; BARBER/BROW/LASH/SUGARING/COSMETOLOGY/MASSAGE/DENTAL
# будут добавлены по мере калибровки wiki-данных).
TRAINING_COSTS_BY_EXPERIENCE = {
    'none': 150_000,  # с нуля: курс гель-лак + базовые техники, медиана
    'some': 40_000,   # подтянуть недостающее: 1-2 продвинутых курса
    'pro':  0,        # уже профи, обучение не требуется
}


def compute_unified_payback_months(result, adaptive):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import compute_unified_payback_months as _fn
    return _fn(result, adaptive)


_MONTH_NAMES_RUS_FULL = ['Янв','Фев','Мар','Апр','Май','Июн',
                         'Июл','Авг','Сен','Окт','Ноя','Дек']
_MONTH_NAMES_RUS_LONG = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                         'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']


def compute_first_year_chart(result):
    """Thin wrapper → services/seasonality_service (Этап 3 рефакторинга)."""
    from services.seasonality_service import compute_first_year_chart as _fn
    return _fn(result)


def compute_pnl_aggregates(result):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import compute_pnl_aggregates as _fn
    return _fn(result)


# ─────────────────────────────────────────────────────────────────────────
# Города: канонический ID + маппинг из legacy → canonical + check_coef
# ─────────────────────────────────────────────────────────────────────────

def _build_city_maps():
    """Собирает: canonical→data, legacy→canonical, canonical→check_coef."""
    canon_to_data = {}
    legacy_to_canon = {}
    coef_map = {}
    for city in CONSTANTS.get("cities", []) or []:
        cid = city.get("id")
        if not cid:
            continue
        canon_to_data[cid] = city
        coef_map[cid] = float(city.get("check_coef", 1.00))
        # каждый legacy_id → canonical
        for legacy in city.get("legacy_ids", []) or []:
            legacy_to_canon[str(legacy)] = cid
        # сам канонический id тоже нормализуется «в себя»
        legacy_to_canon[cid] = cid
    return canon_to_data, legacy_to_canon, coef_map


CITY_CANON_TO_DATA, CITY_LEGACY_TO_CANON, CITY_CHECK_COEF = _build_city_maps()


def normalize_city_id(city_id: str) -> str:
    """Thin wrapper → loaders/city_loader (Этап 2 рефакторинга)."""
    from loaders.city_loader import normalize_city_id as _fn
    return _fn(city_id)


def get_city_check_coef(city_id: str) -> float:
    """Thin wrapper → loaders/city_loader (Этап 2 рефакторинга)."""
    from loaders.city_loader import get_city_check_coef as _fn
    return _fn(city_id)

def _safe(val, default=0):
    """Безопасное чтение — None/NaN → дефолт."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    return val

def _safe_int(val, default=0):
    return int(_safe(val, default))

def _safe_float(val, default=0.0):
    return float(_safe(val, default))


def _get_canonical_format_meta(db, niche_id: str, format_id: str) -> dict:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _get_canonical_format_meta as _fn
    return _fn(db, niche_id, format_id)


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

        # Имена и иконки ниш — из config/niches.yaml (единый источник истины).
        niches_cfg = ((getattr(self, "configs", {}) or {}).get("niches", {}) or {}).get("niches", {}) or {}

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

            cfg_meta = niches_cfg.get(niche_id, {}) or {}
            self.niche_registry[niche_id] = {
                'niche_id': niche_id,
                'name': cfg_meta.get('name_rus', niche_id),
                'icon': cfg_meta.get('icon', '📋'),
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
        """Список ниш из config/niches.yaml с полем `available`.

        Возвращает ВСЕ ниши из yaml (а не только загруженные xlsx), с пометкой
        available=true|false. Фронт сам решает, скрывать ли недоступные.
        Для ниш с available=true подтягиваются иконка/имя/кол-во форматов из
        niche_registry (загруженных xlsx); для остальных — из yaml.
        """
        niches_cfg = ((self.configs or {}).get("niches", {}) or {}).get("niches", {}) or {}
        out = []
        for nid, meta in niches_cfg.items():
            meta = meta or {}
            reg = self.niche_registry.get(nid, {}) or {}
            out.append({
                "niche_id": nid,
                "name": reg.get("name") or meta.get("name_rus", nid),
                "icon": reg.get("icon") or meta.get("icon", "📋"),
                "category": meta.get("category", ""),
                "archetype": meta.get("archetype", ""),
                "formats_count": reg.get("formats_count", 0),
                "available": bool(meta.get("available", False)),
            })
        return out

    def is_niche_available(self, niche_id: str) -> bool:
        """Доступна ли ниша для расчёта Quick Check."""
        niches_cfg = ((self.configs or {}).get("niches", {}) or {}).get("niches", {}) or {}
        meta = niches_cfg.get(niche_id, {}) or {}
        return bool(meta.get("available", False))

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
    """Thin wrapper → loaders/city_loader (Этап 2 рефакторинга)."""
    from loaders.city_loader import get_city as _fn
    return _fn(db, city_id)

def get_city_tax_rate(db: ZerekDB, city_id: str) -> float:
    """Thin wrapper → loaders/tax_loader (Этап 2 рефакторинга)."""
    from loaders.tax_loader import get_city_tax_rate as _fn
    return _fn(db, city_id)

def get_rent_median(db: ZerekDB, city_id: str, loc_type: str) -> tuple:
    """Thin wrapper → loaders/rent_loader (Этап 2 рефакторинга)."""
    from loaders.rent_loader import get_rent_median as _fn
    return _fn(db, city_id, loc_type)

def get_competitors(db: ZerekDB, niche_id: str, city_id: str) -> dict:
    """Thin wrapper → loaders/competitor_loader (Этап 2 рефакторинга)."""
    from loaders.competitor_loader import get_competitors as _fn
    return _fn(db, niche_id, city_id)

def get_failure_pattern(db: ZerekDB, niche_id: str) -> dict:
    """Thin wrapper → loaders/content_loader (Этап 2 рефакторинга)."""
    from loaders.content_loader import get_failure_pattern as _fn
    return _fn(db, niche_id)

def get_permits(db: ZerekDB, niche_id: str) -> list:
    """Thin wrapper → loaders/content_loader (Этап 2 рефакторинга)."""
    from loaders.content_loader import get_permits as _fn
    return _fn(db, niche_id)


# ═══════════════════════════════════════════════
# 3. РАСЧЁТНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════

def calc_revenue_monthly(fin: dict, cal_month: int, razgon_month: int) -> int:
    """Thin wrapper → services/seasonality_service (Этап 3 рефакторинга)."""
    from services.seasonality_service import calc_revenue_monthly as _fn
    return _fn(fin, cal_month, razgon_month)


def calc_cashflow(fin: dict, staff: dict, capex_total: int, tax_rate: float,
                  start_month: int = 1, months: int = 12, qty: int = 1) -> list:
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import calc_cashflow as _fn
    return _fn(fin, staff, capex_total, tax_rate, start_month, months, qty)


def calc_breakeven(fin: dict, staff: dict, tax_rate: float, qty: int = 1) -> dict:
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import calc_breakeven as _fn
    return _fn(fin, staff, tax_rate, qty)


def calc_payback(capex_total: int, cashflow: list) -> dict:
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import calc_payback as _fn
    return _fn(capex_total, cashflow)


# ═══════════════════════════════════════════════
# PHASE 2 — OWNER ECONOMICS
# «В карман собственнику» + точки закрытия/роста + стресс-тест
# Пороги и ставки — из constants.yaml (OWNER_CLOSURE_POCKET,
# OWNER_GROWTH_POCKET, OWNER_SOCIAL_RATE, OWNER_SOCIAL_BASE_MRP).
# ═══════════════════════════════════════════════


def calc_owner_social_payments(declared_monthly_base: int = None) -> int:
    """Thin wrapper → services/pricing_service (Этап 3 рефакторинга)."""
    from services.pricing_service import calc_owner_social_payments as _fn
    return _fn(declared_monthly_base)


def calc_owner_economics(fin: dict, staff: dict, tax_rate: float,
                          rent_month_total: int, qty: int = 1,
                          traffic_k: float = 1.0,
                          check_k: float = 1.0,
                          rent_k: float = 1.0,
                          social: int = None) -> dict:
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import calc_owner_economics as _fn
    return _fn(fin, staff, tax_rate, rent_month_total, qty,
               traffic_k=traffic_k, check_k=check_k, rent_k=rent_k, social=social)


def calc_closure_growth_points(owner_eco: dict) -> dict:
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import calc_closure_growth_points as _fn
    return _fn(owner_eco)


def calc_stress_test(fin: dict, staff: dict, tax_rate: float,
                     rent_month_total: int, qty: int = 1) -> list:
    """Thin wrapper → services/stress_service (Этап 3 рефакторинга)."""
    from services.stress_service import calc_stress_test as _fn
    return _fn(fin, staff, tax_rate, rent_month_total, qty)


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

    # Нормализуем city_id на входе: legacy (ALA/ALMATY/almaty) → canonical.
    city_id = normalize_city_id(city_id)

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

    # ── Канонический мета-формат из 08_niche_formats.xlsx ──
    # Источник истины для capex_standard и typical_staff (masters_canon).
    meta08 = _get_canonical_format_meta(db, niche_id, format_id)

    # ── Множитель «точек/мастеров» ──
    # qty_points из FORMATS (если >1 — пользовательское масштабирование, например
    # 4 автомоечных бокса). Иначе — masters_canon / masters_row, чтобы исправить
    # занижение revenue в случаях когда per-niche FINANCIALS отражает меньший
    # staff, чем канонический 08 (например BARBER_STANDARD: per-niche row = 2
    # барбера, 08.typical_staff = 4 барбера + 1 админ).
    qty_points_raw = _safe_int(fmt.get('qty_points'), 1) if fmt else 1
    headcount_row = _safe_int(staff.get('headcount'), 1) if staff else 1
    masters_canon = meta08.get('masters_count') or 0
    if qty_points_raw > 1:
        seats_mult = float(qty_points_raw)
    elif masters_canon > 0 and headcount_row > 0 and masters_canon > headcount_row:
        seats_mult = masters_canon / max(headcount_row, 1)
    else:
        seats_mult = 1.0

    # Применяем множитель к финансам ниши: трафик и ФОТ масштабируются, чек
    # остаётся таким же (это цена услуги/товара, не зависит от кол-ва мастеров).
    if seats_mult > 1.0:
        fin = dict(fin)
        staff = dict(staff)
        fin['traffic_med'] = int(_safe_int(fin.get('traffic_med'), 0) * seats_mult)
        fin['traffic_min'] = int(_safe_int(fin.get('traffic_min'), 0) * seats_mult)
        fin['traffic_max'] = int(_safe_int(fin.get('traffic_max'), 0) * seats_mult)
        for k in ('fot_net_min','fot_net_med','fot_net_max',
                  'fot_full_min','fot_full_med','fot_full_max'):
            v = _safe_int(staff.get(k), 0)
            if v > 0:
                staff[k] = int(v * seats_mult)
        # Аренда: скейлим по площади 08 vs per-niche area_med, но не сильнее,
        # чем масштаб staff (чтобы не раздуть rent выше реальности).
        try:
            area_row = _safe_int(fmt.get('area_med'), 0) or _safe_int(fmt.get('area_max'), 0)
            area_canon = _safe_int(meta08.get('area_m2'), 0)
            if area_row > 0 and area_canon > area_row:
                area_ratio = min(area_canon / area_row, seats_mult)
                for k in ('rent_min','rent_med','rent_max'):
                    v = _safe_int(fin.get(k), 0)
                    if v > 0:
                        fin[k] = int(v * area_ratio)
        except Exception:
            pass

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
    # Базовые значения — из per-niche CAPEX-листа. Но canonical — 08.capex_standard.
    capex_med_raw = _safe_int(capex_data.get('capex_med'), 0) * qty
    capex_min = _safe_int(capex_data.get('capex_min'), 0) * qty
    capex_max = _safe_int(capex_data.get('capex_max'), 0) * qty
    capex_standard_08 = _safe_int(meta08.get('capex_standard'), 0) * qty
    # Приоритет — 08.capex_standard, если он задан и заметно больше per-niche
    # медианы (которая часто занижена: первая строка CAPEX-листа может
    # соответствовать упрощённому варианту формата).
    if capex_standard_08 > 0 and capex_standard_08 > capex_med_raw * 1.1:
        capex_med = capex_standard_08
        # Расширим диапазон ±25% для min/max, если он был слишком узким.
        if capex_max < capex_med:
            capex_max = int(capex_med * 1.25)
        if capex_min < capex_med * 0.5:
            capex_min = int(capex_med * 0.75)
    else:
        capex_med = capex_med_raw
    deposit_months = _safe_int(fin.get('deposit_months'), DEFAULTS['deposit_months'])

    rent_median_m2, _ = get_rent_median(db, city_id, loc_type)
    rent_month = rent_override if rent_override else _safe_int(fin.get('rent_med'), int(area_m2 * rent_median_m2))
    rent_month_total = rent_month * qty
    deposit = rent_month_total * deposit_months
    # Оборотный капитал (working_cap_3m) — входит в стартовые вложения
    # (помогает пережить период разгона без убытка), поэтому прибавляется
    # к capex_total для payback.
    working_cap = _safe_int(capex_data.get('working_cap_3m'), 0) * qty
    capex_total = capex_med + deposit + working_cap

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
    # Вычитаем ОДНУ ставку (по факту-количеству ставок = headcount × seats_mult
    # если seats_mult применён). Так не получится «срезать полФОТа», когда
    # row.headcount=2 но реальный штат 4.
    staff_adjusted = dict(staff)
    if founder_works and fot_med > 0:
        headcount_row = _safe_int(staff.get('headcount'), 1)
        effective_hc = max(int(round(headcount_row * max(seats_mult, 1.0))), headcount_row, 1)
        one_salary = fot_med // effective_hc
        staff_adjusted['fot_net_med'] = max(0, fot_med - one_salary)
        # fot_full сбрасываем, чтобы пересчитался через multiplier
        if _safe_int(staff.get('fot_full_med'), 0) > 0:
            staff_adjusted['fot_full_med'] = max(0, _safe_int(staff.get('fot_full_med'), 0) - int(one_salary * DEFAULTS['fot_multiplier']))
        else:
            staff_adjusted['fot_full_med'] = 0

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

    # ── 3 сценария (пессимист/база/оптимист) — via services/scenario_service ──
    from services.scenario_service import compute_3_scenarios
    scenarios = compute_3_scenarios(fin, staff_adjusted, capex_total, tax_rate, start_month, qty)

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
                alternatives.append(f"Снизьте класс до Эконом — стартовые вложения {_safe_int(alt_capex.get('capex_med'),0):,} ₸ вместо {capex_med:,} ₸")
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
            "city_population": _safe_int(city.get("Население всего (чел.)")),
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
            "capex_standard": _safe_int(meta08.get('capex_standard'), 0),
            "masters_canon": _safe_int(meta08.get('masters_count'), 0),
            "seats_mult": round(float(seats_mult), 2),
            "training_required": bool(fmt.get('training_required')) if fmt else False,
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
                "marketing": _safe_int(capex_data.get('marketing')) * qty,
                "deposit": _safe_int(capex_data.get('deposit')) * qty,
                "legal": _safe_int(capex_data.get('legal')) * qty,
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
            "marketing": _safe_int(fin.get('marketing')) * qty,
            "marketing_min": _safe_int(fin.get('marketing_min')) * qty,
            "marketing_med": _safe_int(fin.get('marketing_med')) * qty,
            "marketing_max": _safe_int(fin.get('marketing_max')) * qty,
            "other_opex_min": _safe_int(fin.get('other_opex_min')) * qty,
            "other_opex_med": _safe_int(fin.get('other_opex_med')) * qty,
            "other_opex_max": _safe_int(fin.get('other_opex_max')) * qty,
            "sez_month": _safe_int(fin.get('sez_month')),
            "revenue_year1": total_rev_y1,
            "profit_year1": total_profit_y1,
            "tax_rate_pct": tax_rate * 100,
            # Для first_year_chart (и др. потребителей): per-niche ramp-up
            # и сезонность должны быть доступны в result.financials, иначе
            # функции падают на DEFAULT_SEASONALITY/rampup_start_pct=0.50.
            "rampup_months": _safe_int(fin.get('rampup_months'), DEFAULTS.get('rampup_months', 3)),
            "rampup_start_pct": _safe_float(fin.get('rampup_start_pct'), DEFAULTS.get('rampup_start_pct', 0.50)),
            **{f"s{m:02d}": _safe_float(fin.get(f"s{m:02d}"), 0.0) for m in range(1, 13)},
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
    """Thin wrapper → loaders/city_loader (Этап 2 рефакторинга)."""
    from loaders.city_loader import get_inflation_region as _fn
    return _fn(db, city_id)

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
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _split_csv as _fn
    return _fn(val)


def _niche_name_from_registry(db, niche_id: str) -> str:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _niche_name_from_registry as _fn
    return _fn(db, niche_id)


def _formats_from_per_niche_xlsx(db, niche_id: str) -> list:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _formats_from_per_niche_xlsx as _fn
    return _fn(db, niche_id)


def _formats_from_fallback_xlsx(db, niche_id: str) -> list:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _formats_from_fallback_xlsx as _fn
    return _fn(db, niche_id)


def _specific_questions_for_niche(db, niche_id: str, qids: list) -> list:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _specific_questions_for_niche as _fn
    return _fn(db, niche_id, qids)


def get_niche_config(db, niche_id: str) -> dict:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import get_niche_config as _fn
    return _fn(db, niche_id)


# ───────────────────────────────────────────────────────────────────────────
# Quick Check v2 — Survey (per-niche question list)
# ───────────────────────────────────────────────────────────────────────────

def _question_to_dict(row) -> dict:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _question_to_dict as _fn
    return _fn(row)


def _dependencies_for(deps_df, qid: str) -> list:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _dependencies_for as _fn
    return _fn(deps_df, qid)


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
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_capital as _fn
    return _fn(capital_own, capex_needed)


def _score_roi(profit_year, total_investment, is_solo=False):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_roi as _fn
    return _fn(profit_year, total_investment, is_solo=is_solo)


def _score_breakeven(breakeven_months):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_breakeven as _fn
    return _fn(breakeven_months)


def _score_saturation(competitors_count, city_population, niche_id, density_per_10k=None):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_saturation as _fn
    return _fn(competitors_count, city_population, niche_id, density_per_10k=density_per_10k)


def _score_experience(exp):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_experience as _fn
    return _fn(exp)


def _score_marketing(tier='express'):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_marketing as _fn
    return _fn(tier)


def _score_stress(profit_base, profit_pess):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_stress as _fn
    return _fn(profit_base, profit_pess)


def _score_format_city(format_id, format_class, city_population):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _score_format_city as _fn
    return _fn(format_id, format_class, city_population)


def _verdict_statement_template(color, top_weak, top_strong, roi_pct, breakeven_months):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _verdict_statement_template as _fn
    return _fn(color, top_weak, top_strong, roi_pct, breakeven_months)


def _strength_text(p):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _strength_text as _fn
    return _fn(p)


def _risk_text(p, context):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import _risk_text as _fn
    return _fn(p, context)


def compute_block1_verdict(result, adaptive):
    """Thin wrapper → services/verdict_service (Этап 3 рефакторинга)."""
    from services.verdict_service import compute_block1_verdict as _fn
    return _fn(result, adaptive)




# ═══════════════════════════════════════════════
# BLOCK 3 — РЫНОК И КОНКУРЕНТЫ
# ═══════════════════════════════════════════════

def compute_block3_market(db, result, adaptive):
    """Thin wrapper → services/market_service (Этап 3 рефакторинга)."""
    from services.market_service import compute_block3_market as _fn
    return _fn(result)


# ═══════════════════════════════════════════════
# BLOCK 4 — ЮНИТ-ЭКОНОМИКА
# ═══════════════════════════════════════════════

def _archetype_of(db, niche_id):
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import _archetype_of as _fn
    return _fn(db, niche_id)


def compute_block4_unit_economics(db, result, adaptive, block2=None):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import compute_block4_unit_economics as _fn
    return _fn(db, result, adaptive, block2=block2)



# ═══════════════════════════════════════════════
# BLOCK 6 — СТАРТОВЫЙ КАПИТАЛ (CAPEX)
# ═══════════════════════════════════════════════

def compute_block6_capital(db, result, adaptive, block2=None):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import compute_block6_capital as _fn
    return _fn(db, result, adaptive, block2=block2)


# ═══════════════════════════════════════════════
# BLOCK SEASON — СЕЗОННОСТЬ ВЫРУЧКИ ПО МЕСЯЦАМ
# ═══════════════════════════════════════════════

_MONTH_NAMES_RUS = ['янв','фев','мар','апр','май','июн',
                    'июл','авг','сен','окт','ноя','дек']

def compute_block_season(db, result, adaptive):
    """Thin wrapper → services/seasonality_service (Этап 3 рефакторинга).

    Wrapper тянет raw_fin (полную строку FINANCIALS с s01..s12) через loader;
    сервис сам уже вычисляет коэфы + пики. Так сервис не ходит в БД — принцип
    чистоты уровня services соблюдён.
    """
    inp = result.get('input', {}) or {}
    niche_id = inp.get('niche_id', '')
    format_id = inp.get('format_id', '')
    cls = inp.get('class', '') or inp.get('cls', '')
    raw_fin = db.get_format_row(niche_id, 'FINANCIALS', format_id, cls) if niche_id else {}
    from services.seasonality_service import compute_block_season as _fn
    return _fn(raw_fin)


# ═══════════════════════════════════════════════
# BLOCK 7 — мёртв в Quick Check с Round 4 (заменён compute_block_season).
# Функция compute_block7_scenarios удалена (не вызывалась и только
# увеличивала LOC engine.py). Если понадобится для FinModel — восстановить
# из git history по SHA Round 4 или вынести в отдельный модуль.
# ═══════════════════════════════════════════════
# BLOCK 8 — СТРЕСС-ТЕСТ
# ═══════════════════════════════════════════════

def compute_block8_stress_test(db, result, adaptive):
    """Thin wrapper → services/stress_service (Этап 3 рефакторинга)."""
    from services.stress_service import compute_block8_stress_test as _fn
    return _fn(result)


# ═══════════════════════════════════════════════
# BLOCK 9 — РИСКИ НИШИ
# ═══════════════════════════════════════════════


# Constants and filter helpers переехали в services/risk_service.py.
# Здесь только тонкая обёртка для совместимости с импортами engine.


def _filter_risks_by_format(risks_list, format_id):
    """Thin wrapper → services/risk_service (Этап 3 рефакторинга)."""
    from services.risk_service import _filter_risks_by_format as _fn
    return _fn(risks_list, format_id)


def compute_block9_risks(db, result, adaptive):
    """Thin wrapper → services/risk_service (Этап 3 рефакторинга)."""
    from services.risk_service import compute_block9_risks as _fn
    return _fn(db, result, adaptive)


# ═══════════════════════════════════════════════
# BLOCK 5 — P&L ЗА ГОД (Quick Check report, стр. 5)
# Три сценария + ключевые мультипликаторы + доход предпринимателя
# ═══════════════════════════════════════════════

def _cogs_label_by_archetype(archetype):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import _cogs_label_by_archetype as _fn
    return _fn(archetype)


def _scenario_pnl_row(revenue_y, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import _scenario_pnl_row as _fn
    return _fn(revenue_y, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)


def compute_block5_pnl(db, result, adaptive):
    """Thin wrapper → services/economics_service (Этап 3 рефакторинга)."""
    from services.economics_service import compute_block5_pnl as _fn
    return _fn(db, result, adaptive)


# ═══════════════════════════════════════════════
# BLOCK 10 — СЛЕДУЮЩИЕ ШАГИ (Quick Check report, финал)
# План действий / условия / альтернативы по вердикту + CTA upsell
# ═══════════════════════════════════════════════

def _green_action_plan(block2, block1, adaptive=None, result=None):
    """Thin wrapper → services/action_plan_service (Этап 3 рефакторинга)."""
    from services.action_plan_service import _green_action_plan as _fn
    return _fn(block2, block1, adaptive=adaptive, result=result)


def _yellow_conditions(block1, block2):
    """Thin wrapper → services/action_plan_service (Этап 3 рефакторинга)."""
    from services.action_plan_service import _yellow_conditions as _fn
    return _fn(block1, block2)


def _red_alternatives(block1, block2, result, db):
    """Thin wrapper → services/action_plan_service (Этап 3 рефакторинга)."""
    from services.action_plan_service import _red_alternatives as _fn
    return _fn(block1, block2, result, db)


def _upsell_block(color, block1, block2):
    """Thin wrapper → services/action_plan_service (Этап 3 рефакторинга)."""
    from services.action_plan_service import _upsell_block as _fn
    return _fn(color, block1, block2)


def _final_farewell(color, block2):
    """Thin wrapper → services/action_plan_service (Этап 3 рефакторинга)."""
    from services.action_plan_service import _final_farewell as _fn
    return _fn(color, block2)


def compute_block10_next_steps(db, result, adaptive, block1=None, block2=None):
    """Thin wrapper → services/action_plan_service (Этап 3 рефакторинга)."""
    from services.action_plan_service import compute_block10_next_steps as _fn
    return _fn(db, result, adaptive, block1=block1, block2=block2)


# ═══════════════════════════════════════════════
# BLOCK 2 — ПАСПОРТ БИЗНЕСА (Quick Check report, стр. 2)
# Спецификация «ZEREK Quick Check — Блок 2» v1.0
# ═══════════════════════════════════════════════

def _parse_typical_staff(staff_str):
    """'барбер:4|администратор:1' → [{role,count}]."""
    out = []
    if not staff_str: return out
    for chunk in str(staff_str).split('|'):
        if ':' in chunk:
            role, count = chunk.split(':', 1)
            try:
                out.append({'role': role.strip(), 'count': int(count.strip())})
            except Exception:
                pass
    return out


def _split_staff_into_groups(staff_list):
    """Делит на masters/assistants. Мастер = первая роль; админы/помощники/ассистенты/курьеры — ассистенты."""
    if not staff_list:
        return {'masters': [], 'assistants': []}
    assistant_keywords = ['администратор','админ','помощник','ассистент','курьер','уборщик','грумер','консультант','методист','водитель','диспетчер','механик']
    masters, assistants = [], []
    for s in staff_list:
        role = s.get('role', '').lower()
        if any(kw in role for kw in assistant_keywords):
            assistants.append(s)
        else:
            masters.append(s)
    # если все попали в ассистенты, первую группу считаем мастерами
    if not masters and assistants:
        masters = [assistants.pop(0)]
    return {'masters': masters, 'assistants': assistants}


def _subtract_entrepreneur_role(staff_list, role_name):
    """Вычитает одну ставку указанной роли. role_name = 'барбер' / 'администратор' etc."""
    if not role_name or role_name == 'multi':
        return staff_list
    out = []
    subtracted = False
    for s in staff_list:
        if not subtracted and s.get('role', '').lower() == role_name.lower() and s.get('count', 0) > 0:
            new_count = s['count'] - 1
            if new_count > 0:
                out.append({'role': s['role'], 'count': new_count})
            subtracted = True
        else:
            out.append(dict(s))
    return out


def _entrepreneur_role_text(role_id, staff_list):
    """owner_only / owner_plus_{role} / owner_multi → (label, description)."""
    if not role_id or role_id == 'owner_only':
        total = sum(s.get('count', 0) for s in staff_list)
        return {
            'label_rus': 'Только владелец',
            'description_rus': f'Нанимаю всех {total} сотрудников. Не работаю операционно.',
            'subtract_role': None,
        }
    if role_id == 'owner_multi':
        return {
            'label_rus': 'Владелец на нескольких позициях',
            'description_rus': 'Вы закрываете 2+ ставки. Детализация штата — в финмодели.',
            'subtract_role': 'multi',
        }
    if role_id.startswith('owner_plus_'):
        role = role_id[len('owner_plus_'):]
        return {
            'label_rus': f'Владелец + {role}',
            'description_rus': f'Вы закрываете 1 ставку {role}',
            'subtract_role': role,
        }
    return {'label_rus': role_id, 'description_rus': '', 'subtract_role': None}


def _payroll_label(pt):
    return {
        'salary': 'Оклад (фиксированная зарплата)',
        'piece':  'Сдельно / процент с выручки',
        'mixed':  'Смешанно (оклад + %)',
    }.get(pt, '—')


def _experience_label(exp):
    return {
        'none':        'Нет опыта — открываю с нуля',
        'some':        '1–2 года опыта в найме',
        'experienced': '3+ лет опыта / был свой бизнес',
    }.get(exp, '—')


def _format_location(city_name, location_type, location_line, format_type, configs_locations):
    """Собирает строку локации: «Город · Район · Линия» или спец.формулировки."""
    # Спец-случаи по format_type
    if format_type == 'HOME':
        return f'{city_name} · На дому у мастера' if city_name else 'На дому у мастера'
    if format_type == 'MOBILE':
        return f'{city_name} · Выездной формат / доставка' if city_name else 'Выездной формат / доставка'
    if format_type == 'SOLO' or location_type == 'rent_in_salon':
        return f'Аренда в салоне{("  ·  " + city_name) if city_name else ""}'
    if format_type == 'HIGHWAY':
        return f'{city_name} · Трасса / промзона' if city_name else 'Трасса / промзона'
    if format_type == 'PRODUCTION':
        return f'{city_name} · Промзона / своё здание' if city_name else 'Промзона / своё здание'

    loc_rus = ''
    if configs_locations and location_type:
        meta = configs_locations.get(location_type, {}) or {}
        loc_rus = meta.get('label_rus', location_type)

    parts = []
    if city_name: parts.append(city_name)
    if loc_rus: parts.append(loc_rus)
    if location_line in ('line_1', 'line_2'):
        parts.append('1-я линия' if location_line == 'line_1' else '2-я линия')
    return ' · '.join(parts) if parts else '—'


def compute_block2_passport(db, result, adaptive):
    """Собирает Блок 2 — «Паспорт бизнеса»: что именно оценивается."""
    adaptive = adaptive or {}
    inp = result.get('input', {}) or {}
    niche_id = inp.get('niche_id') or ''
    format_id = inp.get('format_id') or ''

    configs = getattr(db, 'configs', {}) or {}
    niches_cfg = (configs.get('niches', {}) or {}).get('niches', {}) or {}
    locations_cfg = (configs.get('locations', {}) or {}).get('locations', {}) or {}

    niche_meta = niches_cfg.get(niche_id, {}) or {}
    niche_icon = niche_meta.get('icon', '📋')
    niche_name_rus = niche_meta.get('name_rus', niche_id)

    # Формат — из 08_niche_formats.xlsx
    formats = _formats_from_fallback_xlsx(db, niche_id)
    fm = next((f for f in formats if f.get('format_id') == format_id), {})
    format_name_rus = fm.get('format_name', format_id)
    class_level = (fm.get('class', '') or '').strip().lower()
    area_m2 = _safe_int(fm.get('area_m2'), 0)
    # format_type — из xlsx (если нет, дефолт STANDARD)
    format_type = ''
    df_fb = getattr(db, 'niches_formats_fallback', pd.DataFrame())
    if df_fb is not None and not df_fb.empty and 'format_type' in df_fb.columns:
        row = df_fb[(df_fb['niche_id'].astype(str) == niche_id) & (df_fb['format_id'].astype(str) == format_id)]
        if not row.empty:
            format_type = str(row.iloc[0].get('format_type', '') or '').strip()
    if not format_type:
        format_type = 'STANDARD'

    # Штат из xlsx
    typical_staff_raw = ''
    if df_fb is not None and not df_fb.empty and 'typical_staff' in df_fb.columns:
        row = df_fb[(df_fb['niche_id'].astype(str) == niche_id) & (df_fb['format_id'].astype(str) == format_id)]
        if not row.empty:
            typical_staff_raw = str(row.iloc[0].get('typical_staff', '') or '').strip()
    staff_list = _parse_typical_staff(typical_staff_raw)
    staff_groups = _split_staff_into_groups(staff_list)

    # Роль предпринимателя — из adaptive
    ent_role_id = adaptive.get('entrepreneur_role') or 'owner_only'
    ent = _entrepreneur_role_text(ent_role_id, staff_list)
    staff_after = _subtract_entrepreneur_role(staff_list, ent['subtract_role'])
    staff_after_groups = _split_staff_into_groups(staff_after)

    # Локация
    city_name = inp.get('city_name', '') or ''
    loc_type = inp.get('loc_type', '') or adaptive.get('loc_type', '')
    loc_line = adaptive.get('location_line', '')
    location_rus = _format_location(city_name, loc_type, loc_line, format_type, locations_cfg)

    # Финансы
    capex_block = result.get('capex', {}) or {}
    capex_needed = _safe_int(capex_block.get('capex_med')) or _safe_int(capex_block.get('capex_total'))
    # fallback на format.capex_standard если движок 0
    if capex_needed < 500_000:
        capex_needed = _safe_int(fm.get('capex_standard'), 0) or capex_needed
    capital_own = _safe_int(adaptive.get('capital_own')) if adaptive.get('capital_own') else None

    if capital_own is None:
        capital_diff_status = 'not_specified'
        capital_diff = None
        capital_diff_pct = None
    else:
        capital_diff = capital_own - capex_needed
        capital_diff_pct = (capital_diff / capex_needed) if capex_needed else 0
        if capital_diff_pct >= 0.05:
            capital_diff_status = 'surplus'
        elif capital_diff_pct >= -0.05:
            capital_diff_status = 'match'
        elif capital_diff_pct >= -0.30:
            capital_diff_status = 'deficit'
        else:
            capital_diff_status = 'critical_deficit'

    return {
        'niche_id': niche_id,
        'niche_name_rus': niche_name_rus,
        'niche_icon': niche_icon,
        'format_id': format_id,
        'format_name_rus': format_name_rus,
        'class_level_rus': class_level or 'стандарт',
        'area_m2': area_m2 if area_m2 > 0 and format_type not in ('HOME','SOLO','MOBILE') else 0,
        'area_visible': area_m2 > 0 and format_type not in ('HOME','SOLO'),
        'location_rus': location_rus,
        'format_type': format_type,
        'is_solo': format_type in ('SOLO', 'HOME') or not staff_list,
        'typical_staff': {
            'masters':    staff_groups['masters'],
            'assistants': staff_groups['assistants'],
            'total':      sum(s.get('count', 0) for s in staff_list),
        },
        'staff_after_entrepreneur': {
            'masters':    staff_after_groups['masters'],
            'assistants': staff_after_groups['assistants'],
            'total':      sum(s.get('count', 0) for s in staff_after),
        },
        'entrepreneur_role': {
            'id': ent_role_id,
            'label_rus': ent['label_rus'],
            'description_rus': ent['description_rus'],
        },
        'finance': {
            'capital_own': capital_own,
            'capex_needed': capex_needed,
            'capital_diff': capital_diff,
            'capital_diff_status': capital_diff_status,
        },
        'payroll_type_rus': _payroll_label(adaptive.get('payroll_type')),
        'experience_rus': _experience_label(adaptive.get('experience')),
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
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import get_formats_v2 as _fn
    return _fn(db, niche_id)


def get_entrepreneur_roles(typical_staff: list) -> list:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import get_entrepreneur_roles as _fn
    return _fn(typical_staff)


def get_quickcheck_survey(db, niche_id: str, format_id: str = None) -> dict:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import get_quickcheck_survey as _fn
    return _fn(db, niche_id, format_id)


def get_niche_survey(db, niche_id: str, tier: str = "express") -> dict:
    """Thin wrapper → loaders/niche_loader (Этап 2 рефакторинга)."""
    from loaders.niche_loader import get_niche_survey as _fn
    return _fn(db, niche_id, tier)
