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

    # ── 3 сценария (пессимист/база/оптимист) — коэффициенты из defaults.yaml ──
    scenarios = {}
    _scenario_coefs = [
        ('pess', SCENARIO_PESS['traffic_k'], SCENARIO_PESS['check_k']),
        ('base', SCENARIO_BASE['traffic_k'], SCENARIO_BASE['check_k']),
        ('opt',  SCENARIO_OPT['traffic_k'],  SCENARIO_OPT['check_k']),
    ]
    for label, traffic_k, check_k in _scenario_coefs:
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
    """Баллы за капитал vs CAPEX-бенчмарк.

    Правила:
    - capital_own = None/неизвестно → 2 балла «не указан — расчёт условный».
      НЕ штрафуем за отсутствие ответа, это не факт бизнеса.
    - capex_needed = 0 → 1 балл «нет бенчмарка» (реально редко — 08 заполнен).
    - capital >= capex*1.2 → 3 балла «капитал с запасом»
    - capital в [capex*0.95, capex*1.2) → 2 балла «соответствует»
    - capital в [capex*0.75, capex*0.95) → 1 балл «на грани»
    - capital < capex*0.75 → 0 баллов «критический дефицит»
    """
    if not capex_needed:
        return {'score': 1, 'label': 'Капитал vs ориентир',
                'note': 'Нет данных по ориентиру стартовых вложений'}
    if capital_own is None or capital_own == 0:
        return {'score': 2, 'label': 'Капитал vs ориентир',
                'note': f'Капитал не указан — расчёт условный. Ориентир стартовых вложений: {int(capex_needed):,} ₸.'.replace(',', ' ')}
    ratio = capital_own / capex_needed
    t_excel, t_match, t_low = SCORING_CAPITAL  # пороги: профицит / норма / терпимо
    if ratio >= t_excel:
        return {'score': 3, 'label': 'Капитал vs ориентир',
                'note': f'Капитал с запасом: на {int((ratio-1)*100)}% выше ориентира',
                'ratio': ratio}
    if ratio >= t_match:
        return {'score': 2, 'label': 'Капитал vs ориентир',
                'note': 'Капитал соответствует ориентиру',
                'ratio': ratio}
    if ratio >= t_low:
        return {'score': 1, 'label': 'Капитал vs ориентир',
                'note': f'Капитал на грани: дефицит {int((1-ratio)*100)}%',
                'ratio': ratio,
                'gap_kzt': int(capex_needed - capital_own)}
    return {'score': 0, 'label': 'Капитал vs ориентир',
            'note': f'Критический дефицит капитала: {int((1-ratio)*100)}%',
            'ratio': ratio,
            'gap_kzt': int(capex_needed - capital_own)}


def _score_roi(profit_year, total_investment, is_solo=False):
    """Скоринг годового ROI.

    - is_solo=True (HOME/SOLO форматы) → ROI не применим, полный балл 3/3
      с пояснением. Self-employed зарабатывает трудом, не капиталом.
    - total_investment < 500K → 1 балл «недостаточно данных».
    - roi > 3.0 (300%) → sanity-cap: ROI=300%, 1 балл «проверьте капитал».
    - пороги из defaults.yaml (SCORING_ROI = [hi, mid, lo] = [0.45, 0.30, 0.15]).
    """
    if is_solo:
        return {'score': 3, 'label': 'ROI годовой',
                'note': 'Вы работаете сами — нет расходов на зарплату сотрудников'}
    if not total_investment or total_investment < 500_000:
        return {'score': 1, 'label': 'ROI годовой',
                'note': 'Недостаточно данных о капитале'}
    roi = (profit_year or 0) / total_investment
    # Sanity-cap: ROI >300% — всегда ошибка входных данных/расчёта.
    if roi > 3.0:
        return {'score': 1, 'label': 'ROI годовой',
                'note': 'ROI > 300% — проверьте указанный капитал',
                'roi': 3.0,
                'roi_raw': round(roi, 2)}
    pct = int(round(roi * 100))
    t_hi, t_mid, t_lo = SCORING_ROI
    if roi >= t_hi:
        return {'score': 3, 'label': 'ROI годовой',
                'note': f'ROI {pct}% — выше среднего для малого бизнеса',
                'roi': roi}
    if roi >= t_mid:
        return {'score': 2, 'label': 'ROI годовой',
                'note': f'ROI {pct}% — нормальный',
                'roi': roi}
    if roi >= t_lo:
        return {'score': 1, 'label': 'ROI годовой',
                'note': f'ROI {pct}% — ниже нормы, но положительный',
                'roi': roi}
    return {'score': 0, 'label': 'ROI годовой',
            'note': f'ROI {pct}% — не окупает капитал',
            'roi': roi}


def _score_breakeven(breakeven_months):
    t_fast, t_mid, t_slow = SCORING_BREAKEVEN
    if breakeven_months is None:
        return {'score': 0, 'label': 'Точка безубыточности', 'note': f'Бизнес не окупается за {t_slow} мес'}
    if breakeven_months <= t_fast: return {'score': 3, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес — быстрая', 'months': breakeven_months}
    if breakeven_months <= t_mid:  return {'score': 2, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес', 'months': breakeven_months}
    if breakeven_months <= t_slow: return {'score': 1, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес — долго', 'months': breakeven_months}
    return {'score': 0, 'label': 'Точка безубыточности', 'note': f'Окупаемость {breakeven_months} мес — слишком долго', 'months': breakeven_months}


def _score_saturation(competitors_count, city_population, niche_id, density_per_10k=None):
    """Насыщенность рынка через плотность конкурентов на 10K жителей.

    Приоритет — `density_per_10k` (готовый float из 14_competitors.xlsx).
    Фолбэк — пересчёт через `competitors_count / (population/10000)`.
    Бенчмарк — из defaults.yaml (benchmarks.competitor_density_per_10k).
    """
    density = None
    try:
        if density_per_10k is not None and float(density_per_10k) > 0:
            density = float(density_per_10k)
    except Exception:
        density = None
    if density is None:
        if not competitors_count or not city_population:
            return {'score': 2, 'label': 'Насыщенность рынка', 'note': 'Нет данных о конкурентах'}
        density = competitors_count / (city_population / 10000)
    benchmark = BENCHMARK_COMPETITOR_DENSITY_10K
    ratio = density / benchmark if benchmark else 0
    t_low, t_mid, t_hi = SCORING_SATURATION
    if ratio <= t_low:
        return {'score': 3, 'label': 'Насыщенность рынка',
                'note': f'Рынок недонасыщен: {round(density,1)} конкурентов на 10K жителей',
                'density': density}
    if ratio <= t_mid:
        return {'score': 2, 'label': 'Насыщенность рынка',
                'note': f'Норма: {round(density,1)} конкурентов на 10K',
                'density': density}
    if ratio <= t_hi:
        return {'score': 1, 'label': 'Насыщенность рынка',
                'note': f'Высокая конкуренция: {round(density,1)} конкурентов на 10K',
                'density': density}
    return {'score': 0, 'label': 'Насыщенность рынка',
            'note': f'Рынок перенасыщен: {round(density,1)} на 10K',
            'density': density}


def _score_experience(exp):
    if exp == 'experienced': return {'score': 3, 'label': 'Опыт предпринимателя', 'note': '3+ лет опыта снижает риск первого года'}
    if exp == 'some':        return {'score': 2, 'label': 'Опыт предпринимателя', 'note': '1-2 года опыта — стандартно'}
    if exp == 'none':        return {'score': 0, 'label': 'Опыт предпринимателя', 'note': 'Нет опыта — риск первого года до 45%'}
    return {'score': 1, 'label': 'Опыт предпринимателя', 'note': 'Опыт не указан'}


def _score_marketing(tier='express'):
    """В Quick Check этот параметр не опрашивается — не штрафуем.

    Полный балл (2/2) с явной меткой «оценивается в FinModel», чтобы итоговый
    score не занижался из-за отсутствующих данных, которые по воронке
    собираются только на следующем шаге (9 000 ₸ финансовая модель).
    """
    return {'score': 2, 'label': 'Маркетинговый бюджет',
            'note': 'Параметр оценивается в FinModel — в экспресс-оценке полный балл',
            'max': 2}


def _score_stress(profit_base, profit_pess):
    if profit_base is None or profit_pess is None:
        return {'score': 1, 'label': 'Устойчивость к стрессу'}
    t_stable, t_moderate = SCORING_STRESS_DROP
    if profit_pess > 0:
        drop = (profit_base - profit_pess) / profit_base if profit_base else 0
        if drop < t_stable:   return {'score': 3, 'label': 'Устойчивость к стрессу', 'note': 'Бизнес устойчив к падению ключевого параметра на 20%'}
        if drop < t_moderate: return {'score': 2, 'label': 'Устойчивость к стрессу', 'note': 'Умеренно устойчив — падение выручки терпимое'}
        return {'score': 1, 'label': 'Устойчивость к стрессу', 'note': 'Хрупкая модель — небольшое падение трафика больно бьёт'}
    return {'score': 0, 'label': 'Устойчивость к стрессу', 'note': 'При падении параметра на 20% — убыток'}


def _score_format_city(format_id, format_class, city_population):
    # Матрица «формат-класс × размер города»
    t_small, t_mid = SCORING_CITY_POP
    small = (city_population or 0) < t_small
    mid = t_small <= (city_population or 0) < t_mid
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
    if label == 'Капитал vs ориентир':
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
        return 'ROI ниже среднего. Пересмотрите стартовые вложения или ожидаемую выручку.'
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
    # ── Собираем скоринг ──
    # CAPEX-бенчмарк: приоритет — 08_niche_formats.xlsx.capex_standard (проброшен
    # в result.input). Фолбэк: capex_block.capex_med / capex_total из per-niche
    # xlsx (часто занижен, если в CAPEX листе несколько строк под format_id).
    capex_standard_08 = _safe_int(inp.get('capex_standard'), 0)
    capex_med_perniche = _safe_int(capex_block.get('capex_med')) or _safe_int(capex_block.get('capex_total'))
    capex_needed = capex_standard_08 if capex_standard_08 > 0 else capex_med_perniche
    # capital_own: None если не передали, 0 если передали 0. Для скоринга
    # отличаем «не указано» (None) от «указано 0».
    capital_own_raw = adaptive.get('capital_own')
    if capital_own_raw is None or capital_own_raw == '':
        capital_own = None
    else:
        try:
            capital_own = int(capital_own_raw) or None
        except (TypeError, ValueError):
            capital_own = None

    # total_investment для ROI = фактически вложенный капитал (capital_own),
    # либо CAPEX-бенчмарк из 08 (правильный знаменатель), либо capex_total
    # per-niche (запасной вариант). См. баг #2.
    total_investment = (capital_own or 0) or capex_standard_08 or _safe_int(capex_block.get('capex_total'), 0)
    if total_investment < 500_000:
        for k in ('capex_med', 'capex', 'total_investment', 'capex_high'):
            v = _safe_int(capex_block.get(k), 0)
            if v >= 500_000:
                total_investment = v
                break
    profit_year = _safe_int(fin.get('profit_year1'), 0)
    # Единая формула окупаемости (Шаг 6 спеки): ceil(capex_total /
    # monthly_net_income_avg). Одна и та же helper используется в Block 1,
    # Block 5, планах действий — НИКАКИХ fallback'ов.
    breakeven_months = compute_unified_payback_months(result, adaptive)
    city_pop = _safe_int(inp.get('city_population'), 0)
    if not city_pop:
        city_pop = _safe_int((result.get('market', {}) or {}).get('population'), 0)
    competitors_count = 0
    density_per_10k = 0.0
    comp_block = risks_block.get('competitors') or {}
    if isinstance(comp_block, dict):
        competitors_count = _safe_int(comp_block.get('competitors_count')) or _safe_int(comp_block.get('n'))
        density_per_10k = _safe_float(comp_block.get('density_per_10k'), 0.0)
    # Фолбэк — из market.competitors (то же содержимое, но иной путь).
    if not density_per_10k:
        mkt_comp = (result.get('market', {}) or {}).get('competitors') or {}
        if isinstance(mkt_comp, dict):
            density_per_10k = _safe_float(mkt_comp.get('density_per_10k'), 0.0)
            if not competitors_count:
                competitors_count = _safe_int(mkt_comp.get('competitors_count'))
    exp = adaptive.get('experience') or ''

    profit_base = _safe_int((scenarios.get('base') or {}).get('прибыль_среднемес'), 0)
    profit_pess = _safe_int((scenarios.get('pess') or {}).get('прибыль_среднемес'), 0)

    format_class = inp.get('class') or inp.get('cls') or ''
    format_id = inp.get('format_id', '')

    format_id_upper = (format_id or '').upper()
    is_solo_fmt_b1 = bool(inp.get('founder_works')) and (
        format_id_upper.endswith('_HOME') or format_id_upper.endswith('_SOLO')
    )
    scoring_items = [
        _score_capital(capital_own, capex_needed),
        _score_roi(profit_year, total_investment, is_solo=is_solo_fmt_b1),
        _score_breakeven(breakeven_months),
        _score_saturation(competitors_count, city_pop, inp.get('niche_id', ''),
                          density_per_10k=density_per_10k),
        _score_experience(exp),
        _score_marketing('express'),
        _score_stress(profit_base, profit_pess),
        _score_format_city(format_id, format_class, city_pop),
    ]
    total_score = sum(it.get('score', 0) for it in scoring_items)
    max_score = sum(it.get('max', 3) for it in scoring_items)

    # ── Цвет (пороги из defaults.yaml: block1_verdict.thresholds) ──
    _t_green, _t_yellow = BLOCK1_THRESHOLDS
    if total_score >= _t_green:    color = 'green'
    elif total_score >= _t_yellow: color = 'yellow'
    else:                          color = 'red'

    # Топ-3 strong / weak
    sorted_desc = sorted(scoring_items, key=lambda x: -x.get('score', 0))
    sorted_asc  = sorted(scoring_items, key=lambda x: x.get('score', 0))
    strengths_items = sorted_desc[:3]
    # Для HOME-форматов пункт «Насыщенность рынка» противоречит блоку 3
    # «рынок недонасыщен»: в HOME-сегменте клиенты находят мастеров через
    # Instagram, а не по плотности салонов. Исключаем из рисков, чтобы не
    # было противоречия «недонасыщен ↔ без УТП сложно взять долю».
    risks_pool = sorted_asc
    if is_solo_fmt_b1 or format_id_upper.endswith('_HOME'):
        risks_pool = [it for it in risks_pool if it.get('label') != 'Насыщенность рынка']
    risks_items = risks_pool[:3]

    # ── Главные цифры (диапазоны) ──
    rev_base = _safe_int((scenarios.get('base') or {}).get('выручка_год'), 0) // 12
    rev_pess = _safe_int((scenarios.get('pess') or {}).get('выручка_год'), 0) // 12
    rev_opt  = _safe_int((scenarios.get('opt')  or {}).get('выручка_год'), 0) // 12
    prof_base = profit_base
    prof_pess = profit_pess
    # Окупаемость — через тот же unified helper (breakeven_months уже
    # пересчитан выше). bk_pess ≈ bk_base × 1.3 (консервативная оценка
    # для пессимистичного сценария).
    bk_base = _safe_int(breakeven_months) if breakeven_months is not None else _safe_int(payback.get('месяц'))
    sc_pess_pb = (scenarios.get('pess') or {}).get('окупаемость')
    if isinstance(sc_pess_pb, dict):
        bk_pess = _safe_int(sc_pess_pb.get('месяц'))
    else:
        bk_pess = _safe_int(sc_pess_pb)

    # Ваш доход предпринимателя
    # При `owner_plus_*` владелец закрывает одну ставку (ставка роли = ФОТ /
    # headcount). Прибыль уже посчитана с учётом всей ФОТ; чтобы не было
    # двойного учёта, из прибыли ВЫЧИТАЕМ эту ставку, а потом прибавляем её
    # обратно как «role_salary» (итог: доход = ставка + остаток прибыли).
    ent_role = adaptive.get('entrepreneur_role') or 'owner_only'
    staff_block = result.get('staff', {}) or {}
    fot_full = _safe_int(staff_block.get('fot_full_med'), 0) or _safe_int(staff_block.get('fot_net_med'), 0)
    hc = max(
        _safe_int(staff_block.get('headcount'), 1) or 1,
        _safe_int(inp.get('masters_canon'), 0) or 0,
        1,
    )
    role_salary = int(fot_full / hc) if fot_full and hc else 0
    if ent_role and ent_role not in ('owner_only', 'owner_multi') and role_salary > 0:
        ent_income_base = max(0, prof_base - role_salary) + role_salary  # = prof_base
        ent_income_pess = max(0, prof_pess - role_salary) + role_salary
        # Упрощённо: доход = ставка + (прибыль − ставка) = прибыль.
        # Это корректно когда headcount покрывает владельца. В отчёте
        # показываем ставку и остаток отдельно.
        ent_income_base = prof_base
        ent_income_pess = max(0, prof_pess)
    elif ent_role == 'owner_multi':
        # Владелец совмещает несколько ставок — добавка ~35% ФОТ сверх профита.
        bonus = int(fot_full * 0.35)
        ent_income_base = prof_base + bonus
        ent_income_pess = max(0, prof_pess + bonus)
    else:
        # owner_only — доход = чистая прибыль.
        ent_income_base = prof_base
        ent_income_pess = max(0, prof_pess)

    # main_metrics удалено: секция «Главные цифры» в Block 1 убрана с фронта
    # в Round 4 bug#4 (после переноса светофора в конец). Цифры показываются
    # в Block 5 (P&L) и Block 6 (CAPEX). Backend больше не формирует этот
    # мёртвый payload.

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
        'strengths': strengths_texts[:3],
        'risks': risks_texts[:3],
        'scoring': {
            'items': scoring_items,
            'strongest': strengths_items[:3],
            'weakest': risks_items[:3],
        },
    }


# ═══════════════════════════════════════════════
# BLOCK 3 — РЫНОК И КОНКУРЕНТЫ
# ═══════════════════════════════════════════════

def compute_block3_market(db, result, adaptive):
    inp = result.get('input', {}) or {}
    risks = result.get('risks', {}) or {}
    comp = risks.get('competitors') or {}

    # HOME-форматы: 2GIS и агрегаторы не отражают реального рынка мастеров
    # на дому (точки не публичные). Показываем ориентир, а не нули.
    format_id_up = (inp.get('format_id') or '').upper()
    if format_id_up.endswith('_HOME'):
        return {
            'type': 'home_market_note',
            'message': ('Для мастера на дому конкуренция формируется в '
                        'Instagram и TikTok. 2GIS и агрегаторы не отражают '
                        'реального рынка домашних мастеров. Ищите конкурентов '
                        'через хэштеги Instagram по вашему городу и району.'),
        }

    competitors_count = _safe_int(comp.get('competitors_count')) or _safe_int(comp.get('n')) or 0
    city_name = inp.get('city_name', '') or inp.get('city_id', '')
    city_pop = _safe_int(inp.get('city_population'), 0)

    # Приоритет — готовый density_per_10k из xlsx (через get_competitors).
    # Фолбэк — пересчёт competitors_count / (population / 10000).
    density_raw = _safe_float(comp.get('density_per_10k'), 0.0)
    if density_raw > 0:
        density = density_raw
    else:
        density = (competitors_count / (city_pop / 10000)) if city_pop else 0
    benchmark_density = BENCHMARK_RETAIL_DENSITY_10K
    saturation_pct = (density / benchmark_density * 100) if benchmark_density else 0

    # Цвет насыщенности
    if saturation_pct <= 60:
        sat_color = 'green'; sat_text = 'Рынок недонасыщен — есть пространство для входа даже без сильного УТП'
    elif saturation_pct <= 110:
        sat_color = 'yellow'; sat_text = 'Рынок умеренно насыщен — есть пространство для входа при сильном УТП'
    elif saturation_pct <= 150:
        sat_color = 'orange'; sat_text = 'Рынок насыщен — для успеха нужен чёткий отличительный фактор (локация, сервис, цена)'
    else:
        sat_color = 'red'; sat_text = 'Рынок перенасыщен — высокий риск долгой окупаемости из-за конкуренции'

    # Платёжеспособность — упрощённо, на коэффициенте города
    city_coef = get_city_check_coef(inp.get('city_id', '')) or 1.0
    affordability_index = city_coef  # проксирует «городской чек ÷ бенчмарк»
    if affordability_index >= 1.15:
        afford_text = f'Платёжеспособность на {int((affordability_index-1)*100)}% выше средней по РК — можно закладывать премиум-чек'
    elif affordability_index >= 1.0:
        afford_text = 'Платёжеспособность на уровне средней по РК — стандартные цены рынка работают хорошо'
    elif affordability_index >= 0.85:
        afford_text = f'Платёжеспособность на {int((1-affordability_index)*100)}% ниже средней по РК — учтите при ценообразовании'
    else:
        afford_text = f'Платёжеспособность на {int((1-affordability_index)*100)}% ниже средней по РК — премиум-форматы рискованны'

    # Конкуренты — список если есть
    competitors_list = []
    if isinstance(comp.get('top'), list):
        for c in comp['top'][:5]:
            competitors_list.append({
                'name': c.get('name') or c.get('title') or '—',
                'rating': c.get('rating'),
                'reviews': c.get('reviews') or c.get('reviews_count'),
                'district': c.get('district') or '',
            })

    return {
        'city': city_name,
        'saturation': {
            'competitors_count': competitors_count,
            'density_city': round(density, 2),
            'density_benchmark': benchmark_density,
            'pct_of_benchmark': int(saturation_pct),
            'color': sat_color,
            'text_rus': sat_text,
        },
        'competitors_list': competitors_list,
        'affordability': {
            'city_coef': round(affordability_index, 2),
            'text_rus': afford_text,
        },
    }


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

# Фильтры рисков по формату: если title/text содержит любое ключевое слово
# (case-insensitive), риск исключается. Для HOME-форматов общие риски про
# аренду/помещение/найм не релевантны (мастер работает дома один).
FORMAT_RISK_FILTERS = {
    'MANICURE_HOME': {'exclude_keywords': ['аренд', 'помещен', 'найм', 'договор', 'уход мастер', 'наём']},
    'BARBER_HOME':   {'exclude_keywords': ['аренд', 'помещен', 'найм', 'договор', 'уход мастер', 'наём']},
    'BROW_HOME':     {'exclude_keywords': ['аренд', 'помещен', 'найм', 'договор', 'наём']},
    'LASH_HOME':     {'exclude_keywords': ['аренд', 'помещен', 'найм', 'договор', 'наём']},
    'SUGARING_HOME': {'exclude_keywords': ['аренд', 'помещен', 'найм', 'договор', 'наём']},
}

# Специфичные риски для мастера на дому (бьюти-ниши). Добавляются сверху
# списка после фильтрации общих.
HOME_SPECIFIC_RISKS = [
    {'title': 'Зависимость от физсостояния', 'probability': 'СРЕДНЯЯ', 'impact': 'ВЫСОКОЕ',
     'text': 'Болезнь, беременность, травма рук = ноль дохода. Подушка безопасности на 3 мес — must have.',
     'mitigation': 'Отложить 3 мес расходов на подушку. Страхование от нетрудоспособности.'},
    {'title': 'Потолок дохода одного мастера', 'probability': 'ВЫСОКАЯ', 'impact': 'СРЕДНЕЕ',
     'text': 'Максимум 5-7 клиенток в день физически. Чтобы расти дальше — поднимайте средний чек (дизайн, укрепление, уход) или планируйте переезд в свою студию через 1-2 года.',
     'mitigation': 'Апсейл (укрепление, дизайн, уход за кожей рук). План перехода в свою студию через 1-2 года — это даст возможность работать с мастерами и больше клиентов.'},
    {'title': 'Санитарные нормы без контроля', 'probability': 'СРЕДНЯЯ', 'impact': 'ВЫСОКОЕ',
     'text': 'Дома проще забить на стерилизацию. Один случай грибка/инфекции — репутация уничтожена.',
     'mitigation': 'Автоклав / сухожар. Инструменты одноразовые где можно. Фото стерилизации в сторис.'},
]


def _filter_risks_by_format(risks_list, format_id):
    """Исключает риски, чей title/text содержит exclude_keywords формата."""
    flt = FORMAT_RISK_FILTERS.get(format_id or '')
    if not flt:
        return risks_list
    kws = [k.lower() for k in flt.get('exclude_keywords') or []]
    if not kws:
        return risks_list
    out = []
    for r in risks_list:
        blob = ((r.get('title') or '') + ' ' + (r.get('text') or '')).lower()
        if any(k in blob for k in kws):
            continue
        out.append(r)
    return out


def compute_block9_risks(db, result, adaptive):
    """Читает insight-файл ниши и извлекает топ-5 рисков. Fallback — generic риски по архетипу."""
    import re
    from loaders.content_loader import load_insight_md
    inp = result.get('input', {}) or {}
    niche_id = inp.get('niche_id', '')

    # Generic риски по архетипу (fallback)
    arch = _archetype_of(db, niche_id)
    generic_risks = {
        'A': [
            {'title':'Уход мастера с клиентской базой', 'probability':'ВЫСОКАЯ', 'impact':'КРИТИЧНОЕ',
             'text':'В нишах услуг клиенты привязаны к мастеру. Уход мастера может забрать 40-60% его клиентов.',
             'mitigation':'Программа удержания мастеров. CRM салона, не личная. Минимум 2 мастера на 1 позицию.'},
            {'title':'Открытие конкурента в радиусе 300м', 'probability':'СРЕДНЯЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Бьюти-ниши стадно растут. Новый конкурент в районе может забрать 20-30% трафика.',
             'mitigation':'Долгосрочный договор аренды. Программа лояльности. Работа с соцсетями.'},
            {'title':'Сезонная просадка янв-фев', 'probability':'ВЫСОКАЯ', 'impact':'ТЕРПИМОЕ',
             'text':'После новогодних расходов спрос падает. Просадка до −25%.',
             'mitigation':'Запас оборотки на 2 мес. Сезонные акции и пакеты.'},
            {'title':'Проблемы с аксессуарами / расходниками', 'probability':'СРЕДНЯЯ', 'impact':'ТЕРПИМОЕ',
             'text':'Курс, логистика, импорт — срывы поставок материалов.',
             'mitigation':'Запас расходников на 2 мес. 2-3 поставщика вместо одного.'},
            {'title':'Регулирование (СЭС, лицензии)', 'probability':'НИЗКАЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Проверки СЭС, претензии по документам, особенно для мед.ниш.',
             'mitigation':'Проверить все разрешения ДО открытия. Договор с юристом.'},
        ],
        'B': [
            {'title':'Скачок food cost', 'probability':'ВЫСОКАЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Продукты дорожают неравномерно. Food cost может вырасти с 30% до 40% без предупреждения.',
             'mitigation':'Контракты с поставщиками. Регулярный пересмотр меню.'},
            {'title':'Уход шеф-повара / бариста', 'probability':'СРЕДНЯЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Ключевой повар уходит — качество падает, клиенты замечают.',
             'mitigation':'Документированные рецепты. Сменность. Не один ключевой человек.'},
            {'title':'Зависимость от агрегаторов', 'probability':'ВЫСОКАЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Комиссии 20-30%. Агрегатор может поменять условия.',
             'mitigation':'Развивать собственный канал (соцсети, сайт, колл-центр).'},
            {'title':'СЭС / отзывы о санитарии', 'probability':'СРЕДНЯЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Одна жалоба в 2ГИС о «тухлой еде» режет трафик надолго.',
             'mitigation':'Строгие стандарты. Регулярный аудит. Быстрая работа с негативом.'},
            {'title':'Сезонная просадка / курортность', 'probability':'СРЕДНЯЯ', 'impact':'ТЕРПИМОЕ',
             'text':'Летом — свадьбы, зимой — корпоративы; в другие месяцы провалы 20%.',
             'mitigation':'Планировать запас. Промо в провальные месяцы.'},
        ],
        'C': [
            {'title':'Порча и списания товара', 'probability':'ВЫСОКАЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Для скоропорта — 3-10% потерь. Для непродовольственного — до 5% на бой/порчу.',
             'mitigation':'Ротация запасов FIFO. Скидки на товар к истечению срока.'},
            {'title':'Заморозка оборотного капитала', 'probability':'ВЫСОКАЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Товар лежит — деньги не работают. Плохо оборачивающиеся позиции — яд.',
             'mitigation':'ABC-анализ. Сокращать ассортимент непопулярных позиций.'},
            {'title':'Сезонные пики (цветы, новый год)', 'probability':'СРЕДНЯЯ', 'impact':'ТЕРПИМОЕ',
             'text':'В пиковые даты — дефицит товара, в межсезонье — излишки.',
             'mitigation':'Планирование закупок за 2 мес. Предзаказы.'},
        ],
        'D':[
            {'title':'Высокий churn (отток)', 'probability':'ВЫСОКАЯ', 'impact':'КРИТИЧНОЕ',
             'text':'В абонементных нишах отток 5-15% в месяц — норма, но может взлететь.',
             'mitigation':'Удержание: программы лояльности. CRM. Работа с неактивными.'},
            {'title':'Рост CAC (стоимости привлечения)', 'probability':'СРЕДНЯЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Реклама дорожает, конкуренция растёт — CAC может удвоиться за год.',
             'mitigation':'Развивать органику. Сарафан, реферальные программы.'},
            {'title':'Зависимость от единичных тренеров / преподавателей', 'probability':'СРЕДНЯЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Сильный тренер забирает группу к себе — катастрофа для студии.',
             'mitigation':'Множественные тренеры в каждом направлении. Командная культура.'},
        ],
        'E':[
            {'title':'Кассовый разрыв на проектах', 'probability':'ВЫСОКАЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Клиент платит в конце, а вам платить сегодня. Риск разрыва.',
             'mitigation':'Предоплаты 30-50%. Запас оборотки. Договора с чётким графиком.'},
            {'title':'Клиент уходит не заплатив / претензии', 'probability':'СРЕДНЯЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Спор по качеству → недоплата или возврат.',
             'mitigation':'Акты приёмки на каждом этапе. Юр.договор. Страхование.'},
            {'title':'Колебания маржи на материалы', 'probability':'СРЕДНЯЯ', 'impact':'ТЕРПИМОЕ',
             'text':'Закупочные цены растут быстрее чем вы обновляете прайс.',
             'mitigation':'Фиксация цены при подписании. Пересмотр прайс-листа раз в 3 мес.'},
        ],
        'F':[
            {'title':'Простой мощности', 'probability':'ВЫСОКАЯ', 'impact':'ЗАМЕТНОЕ',
             'text':'Постоянные затраты идут, а мощность простаивает — деньги горят.',
             'mitigation':'Минимум маркетинга на старте. Гибкая занятость персонала.'},
            {'title':'Поломки оборудования', 'probability':'СРЕДНЯЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Ключевой агрегат сломался — бизнес встал.',
             'mitigation':'Запас запчастей. Договор с сервисом. Резервное оборудование.'},
            {'title':'Регуляторные ограничения (экология, санитария)', 'probability':'СРЕДНЯЯ', 'impact':'КРИТИЧНОЕ',
             'text':'Новые требования → доп.инвестиции или закрытие.',
             'mitigation':'Следить за законодательством. Соответствие изначально.'},
        ],
    }

    risks_out = []
    content = load_insight_md(niche_id)
    if content:
        try:
            # Ищем секции рисков по реальным заголовкам insight-файлов.
            # Форматы: `## Финансовые риски и ловушки`, `## Красные флаги`,
            # `## Красные флаги (когда лучше не открывать)`,
            # `## Типичные ошибки новичков`, плюс старые «Риски», «Подводные камни»,
            # «Причины провала». Цифровые префиксы («## 5. Операционные риски»)
            # тоже ловятся, поскольку regex матчит имя заголовка в любом месте строки.
            header_pat = (
                r'#+\s*(?:\d+\.\s*)?'
                r'(Финансовые риски и ловушки'
                r'|Красные флаги(?:\s*\([^)]*\))?'
                r'|Типичные ошибки новичков'
                r'|Операционные риски'
                r'|Риски'
                r'|Подводные камни'
                r'|Причины провала)'
            )
            section_pat = header_pat + r'[\s\S]*?(?=\n#+\s|\Z)'
            sections = re.findall(section_pat, content, re.IGNORECASE)
            # re.findall с одной группой возвращает список групп — нам нужен
            # сам текст блока; возьмём финдитер.
            risks_out_local = []
            for m in re.finditer(section_pat, content, re.IGNORECASE):
                section = m.group(0)
                items = re.findall(
                    r'(?:^|\n)[-*\d.]+\s+\*\*([^*]+)\*\*([\s\S]*?)(?=\n[-*\d.]+|\n#+|\Z)',
                    section,
                )
                for title, body in items:
                    body_text = re.sub(r'\n\s*', ' ', body).strip()[:240]
                    risks_out_local.append({
                        'title': title.strip(),
                        'probability': 'СРЕДНЯЯ', 'impact': 'ЗАМЕТНОЕ',
                        'text': body_text, 'mitigation': '',
                    })
                if len(risks_out_local) >= 5:
                    break
            risks_out = risks_out_local[:5]
        except Exception:
            pass

    if not risks_out:
        risks_out = generic_risks.get(arch, generic_risks['A'])[:5]

    source = 'insight' if len(risks_out) and (not generic_risks.get(arch) or risks_out[0].get('title') != generic_risks[arch][0]['title']) else 'generic'

    # Фильтр по формату: убираем риски про аренду/найм/помещение для HOME.
    format_id = (inp.get('format_id') or '').upper()
    risks_out = _filter_risks_by_format(risks_out, format_id)

    # Для HOME-форматов добавляем специфичные риски сверху (физсостояние,
    # потолок одного мастера, санитария без контроля). Лимит 5 общий.
    if format_id.endswith('_HOME'):
        risks_out = HOME_SPECIFIC_RISKS + risks_out

    risks_out = risks_out[:5]

    return {
        'niche_id': niche_id,
        'source': source,
        'risks': risks_out,
    }


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
    """4 недельных блока чек-листа для Green.
    Если в специфической анкете experience=none и у ниши training_required=True
    (бьюти-сфера), в начало добавляется «Неделя 1-4: Обучение и практика»,
    остальные недели сдвигаются на +4.
    """
    fin = (block2 or {}).get('finance', {})
    capex = fin.get('capex_needed') or 0
    capex_equipment = int(capex * 0.40)
    capex_inventory = int(capex * 0.15)
    capex_rent_setup = int(capex * 0.22)
    format_type = (block2 or {}).get('format_type', '')
    is_solo = (block2 or {}).get('is_solo', False)
    staff_total = ((block2 or {}).get('staff_after_entrepreneur') or {}).get('total', 0)

    # Неделя 1-2: Юридический старт
    plan = [
        {
            'week_range': '1-2',
            'title': 'Юридический старт',
            'actions': [
                'Открыть ИП (Самозанятый / УСН 3%)',
                'Открыть банковский счёт',
                ('Проверить договор аренды (3+ лет, фиксированная индексация)'
                 if format_type in ('STANDARD','KIOSK') else 'Подготовить договора с клиентами / поставщиками'),
            ]
        },
    ]
    # Неделя 3-4: Закупка. Для нишеспецифичных подсказок — заглядываем
    # в result.input.niche_id (минимальный набор для маникюра и пр.).
    niche_id = ((result or {}).get('input') or {}).get('niche_id', '')
    equip_hint_by_niche = {
        'MANICURE': 'минимальный набор: лампа UV/LED, фрезер, стерилизатор, стол',
        'BARBER':   'минимальный набор: кресло, машинка, ножницы, стерилизатор, зеркало',
        'BROW':     'минимальный набор: кушетка, лампа с лупой, кисти, пигменты, стерилизатор',
        'LASH':     'минимальный набор: кушетка, лампа, пинцеты, клей, материалы, стерилизатор',
        'SUGARING': 'минимальный набор: кушетка, подогреватель пасты, материалы, стерилизатор',
    }
    equip_hint = equip_hint_by_niche.get(niche_id)
    if equip_hint:
        equip_action = (
            f'Закупить оборудование ({equip_hint}. Бюджет ≈ {_fmt_kzt(capex_equipment)}. '
            f'Для профессионального качества может понадобиться больше.)'
        )
    else:
        equip_action = f'Закупить оборудование (бюджет ≈ {_fmt_kzt(capex_equipment)})'
    plan.append({
        'week_range': '3-4',
        'title': 'Закупка оборудования и материалов',
        'actions': [
            equip_action,
            f'Первичные закупки материалов (≈ {_fmt_kzt(capex_inventory)})',
        ],
    })
    # Неделя 5-6: Подготовка помещения + найм
    if format_type not in ('HOME', 'SOLO'):
        actions_prep = [f'Ремонт и обустройство (≈ {_fmt_kzt(capex_rent_setup)})', 'Вывеска, брендинг, 2GIS-регистрация']
        if staff_total > 0:
            staff_rus = []
            for s in ((block2 or {}).get('staff_after_entrepreneur', {}).get('masters', []) or []):
                staff_rus.append(f"{s.get('count',0)} {s.get('role','')}")
            for s in ((block2 or {}).get('staff_after_entrepreneur', {}).get('assistants', []) or []):
                staff_rus.append(f"{s.get('count',0)} {s.get('role','')}")
            if staff_rus:
                actions_prep.append('Найм сотрудников: ' + ', '.join(staff_rus))
        plan.append({'week_range': '5-6', 'title': 'Подготовка помещения и команды', 'actions': actions_prep})
    else:
        plan.append({
            'week_range': '5-6', 'title': 'Подготовка рабочего места',
            'actions': ['Обустройство рабочего места', 'Страховка инструментов'],
        })

    # Неделя 7-8: Маркетинг до открытия
    plan.append({
        'week_range': '7-8',
        'title': 'Запуск маркетинга ДО открытия',
        'actions': [
            'Таргетированная реклама (Instagram / TikTok)',
            'Договорённости с блогерами города',
            'Приём предзаписей',
        ],
    })

    # Открытие и дальше
    # Для HOME/SOLO мастер на дому не регистрируется в 2GIS (локация не
    # публичная), отзывы собираются в Instagram + Google Maps.
    reviews_action = (
        'Отзывы в Instagram + Google Maps (если есть геолокация) — просить клиентов с 1-го дня'
        if format_type in ('HOME', 'SOLO', 'MOBILE')
        else 'Отзывы в 2GIS — просить клиентов с 1-го дня'
    )
    plan.append({
        'week_range': 'Запуск',
        'title': 'Первые недели работы',
        'actions': [
            ('Следить за загрузкой мастеров еженедельно'
             if format_type not in ('HOME','SOLO','MOBILE') else 'Отслеживать конверсию заявок в сделки'),
            reviews_action,
            'Еженедельный контроль unit-экономики (выручка/чек/COGS)',
        ],
    })

    # Новичок в бьюти-нише (training_required + experience=none):
    # обучение 4 недели идёт первым блоком, остальные недели сдвигаются.
    training_required = bool(((result or {}).get('input') or {}).get('training_required'))
    experience = ((adaptive or {}).get('experience') or '').lower()
    if training_required and experience == 'none':
        shift = 4
        for block in plan:
            wr = block.get('week_range', '')
            if wr == 'Запуск':
                block['week_range'] = f'{shift+9}-{shift+10}'
            elif '-' in wr:
                a, b = wr.split('-')
                try:
                    block['week_range'] = f'{int(a)+shift}-{int(b)+shift}'
                except ValueError:
                    pass
        plan.insert(0, {
            'week_range': '1-4',
            'title': 'Обучение и практика',
            'actions': [
                'Выбрать школу / курсы по нише',
                'Пройти базовый курс (для маникюра — гель-лак + укрепление)',
                'Практика на моделях (бесплатно / со скидкой)',
                'Собрать первичное портфолио для Instagram',
            ],
        })

    return plan


def _yellow_conditions(block1, block2):
    """3 условия перехода в зелёную зону — из top-3 слабых параметров."""
    weak = (((block1 or {}).get('scoring') or {}).get('weakest') or [])[:3]
    fin = (block2 or {}).get('finance', {})
    conditions = []
    for w in weak:
        label = w.get('label', '')
        if label == 'Капитал vs ориентир':
            gap = -(fin.get('capital_diff') or 0)
            if gap <= 0:
                # капитал достаточен (дефицита нет) — условие не про деньги
                conditions.append({
                    'title': 'Резервный фонд: обеспечить запас оборотки',
                    'options': ['Заложить 3-6 мес расходов как резерв', 'Не вкладывать весь капитал в стартовые вложения', 'Иметь отдельный счёт для резерва'],
                })
            else:
                monthly_credit = int(gap * 0.035)
                conditions.append({
                    'title': f'Найти дополнительные {_fmt_kzt(gap)} капитала',
                    'options': [
                        'Партнёр с долей 15-20%',
                        f'Кредит в банке (платёж ~{_fmt_kzt(monthly_credit)}/мес на 36 мес)',
                        'Грант Astana Hub / Bastau Business',
                    ],
                })
        elif label == 'Точка безубыточности':
            months = w.get('months') or 12
            reserve = int(((fin.get('capex_needed') or 0) * 0.12) * max(months, 6))
            if reserve < 1_000_000: reserve = 1_000_000
            conditions.append({
                'title': f'Обеспечить запас кассы на первые {months} мес',
                'options': [f'Резерв оборотки ≈ {_fmt_kzt(reserve)}', 'Не брать целиком кредит "в дело"', 'Иметь 3-6 мес зарплаты на свою семью'],
            })
        elif label == 'Маркетинговый бюджет':
            conditions.append({
                'title': 'Увеличить маркетинговый бюджет на старте',
                'options': ['Заложить минимум 200-500 тыс ₸ в первые 3 месяца', 'Таргет + локальный офлайн-маркетинг', 'Не экономить на SMM и отзывах'],
            })
        elif label == 'Насыщенность рынка':
            conditions.append({
                'title': 'Разработать сильное УТП перед запуском',
                'options': ['Выделить 2-3 отличия от конкурентов', 'Проработать цена-качество через сегмент', 'Определить «нелёгкую» аудиторию для вас'],
            })
        elif label == 'Опыт предпринимателя':
            conditions.append({
                'title': 'Компенсировать отсутствие опыта',
                'options': ['Найти ментора или партнёра с опытом 3+ лет в нише', 'Начать с SOLO-формата до освоения', 'Пройти курс ZEREK Academy (Архитектор)'],
            })
        elif label == 'Соответствие формата городу':
            conditions.append({
                'title': 'Пересмотреть класс формата под город',
                'options': ['Рассмотреть стандарт-формат вместо премиума', 'Проверить платёжеспособность ЦА', 'Проанализировать успешных конкурентов в регионе'],
            })
        else:
            conditions.append({
                'title': w.get('note', label),
                'options': [w.get('note', 'Требуется внимание')],
            })
    return conditions[:3]


def _red_alternatives(block1, block2, result, db):
    """3 категории альтернатив — формат / город / роль."""
    inp = result.get('input', {}) or {}
    niche_id = inp.get('niche_id', '')
    format_id = inp.get('format_id', '')
    city_name = inp.get('city_name', '') or '—'
    format_name = (block2 or {}).get('format_name_rus', format_id)

    alt_formats = []
    all_formats = _formats_from_fallback_xlsx(db, niche_id)
    current_capex = 0
    for f in all_formats:
        if f.get('format_id') == format_id:
            current_capex = _safe_int(f.get('capex_standard'), 0)
            break
    for f in all_formats:
        if f.get('format_id') == format_id: continue
        cx = _safe_int(f.get('capex_standard'), 0)
        if cx < current_capex:
            alt_formats.append(f"{f.get('format_name')} (~{_fmt_kzt(cx)})")
        if len(alt_formats) >= 2: break

    return [
        {
            'category': 'ФОРМАТ',
            'title': f'Формат {format_name} слишком тяжёл для текущих параметров',
            'options': alt_formats if alt_formats else ['Рассмотрите формат уровнем ниже (эконом вместо стандарта)'],
        },
        {
            'category': 'ГОРОД',
            'title': 'Смена города',
            'options': [
                f'Текущий город — {city_name}. Премиум-форматы работают в Алматы, Астане, Шымкенте',
                'Пересчитайте для города с большей платёжеспособной аудиторией',
            ],
        },
        {
            'category': 'РОЛЬ',
            'title': 'Измените роль предпринимателя',
            'options': [
                'Закройте собой хотя бы одну ставку — снизит ФОТ',
                'Для бьюти-формата: работайте мастером, не только управляйте',
                'Для магазина: закройте роль кассира или менеджера закупок',
            ],
        },
    ]


def _upsell_block(color, block1, block2):
    """Апсейл финмодели + bizplan, текст зависит от вердикта."""
    # Прогресс заполнения финмодели: 8 полей QC / 21 полей всего → ~55-65% с учётом повторов
    fm_pct = 60
    bp_pct = 45
    texts = {
        'green':  'Персональный прогноз на 3 года с денежным потоком, налогами, графиком кредита.',
        'yellow': 'Финмодель поможет точно посчитать сколько нужно партнёру и как распределить дефицит.',
        'red':    'Финмодель объяснит почему не окупается и даст 2-3 альтернативных сценария.',
    }
    return {
        'finmodel': {
            'name_rus': 'Финансовая модель',
            'price_kzt': 9000,
            'description_rus': texts.get(color, texts['green']),
            'prefilled_pct': fm_pct,
        },
        'bizplan': {
            'name_rus': 'Бизнес-план',
            'price_kzt': 15000,
            'description_rus': 'Готовый документ для банка, гранта или инвестора. Персонализирован под цель.',
            'prefilled_pct': bp_pct,
        },
    }


def _final_farewell(color, block2):
    """Финальное напутствие. Шаблонное — AI версию подключим позже."""
    niche = (block2 or {}).get('niche_name_rus', 'бизнес')
    if color == 'green':
        return (f'Ваш {niche.lower()} имеет хорошие шансы окупиться в заявленные сроки. '
                'Главное сейчас — не расслабляться на этапе подготовки и сразу выстраивать сильный маркетинг. '
                'Удачи с запуском — возвращайтесь за финмоделью когда будете готовы проработать детали.')
    if color == 'yellow':
        return ('Ваша идея в зоне перехода — если закроете упомянутые условия, бизнес окупится. '
                'Без этих условий — риск большой. Подумайте неделю, пересчитайте варианты — и возвращайтесь.')
    return ('В текущей конфигурации идея рискованна, но это не значит отказаться от ниши. '
            'Смените формат или город — цифры могут заработать. ZEREK поможет пересчитать любой вариант.')


def compute_block10_next_steps(db, result, adaptive, block1=None, block2=None):
    """Блок 10 — план действий / условия / альтернативы + апсейл + финальное напутствие."""
    color = (block1 or {}).get('color', 'yellow')

    # Город и формат для headline — говорим про направление, не про «вашу идею».
    inp = (result or {}).get('input', {}) or {}
    city_rus = inp.get('city_name') or ''
    city_prefix = f'в {city_rus} ' if city_rus else ''
    format_label = inp.get('format_name') or ''
    format_phrase = f'в формате «{format_label}»' if format_label else ''

    out = {
        'color': color,
        'farewell_rus': _final_farewell(color, block2),
        'upsell': _upsell_block(color, block1, block2),
    }

    if color == 'green':
        out['action_plan'] = _green_action_plan(block2, block1, adaptive=adaptive, result=result)
        out['headline_rus'] = (
            f'✅ Это направление реалистично для заработка {city_prefix}{format_phrase}. '
            f'Можно пробовать.'
        ).replace('  ', ' ').strip()
        out['cta_buttons'] = [
            {'label_rus': 'Купить Финансовую модель — 9 000 ₸', 'action': 'buy_finmodel'},
            {'label_rus': 'Скачать PDF отчёта', 'action': 'download_pdf'},
        ]
    elif color == 'yellow':
        out['conditions'] = _yellow_conditions(block1, block2)
        out['headline_rus'] = (
            '⚠️ Это направление возможно, но с оговорками. Обратите внимание '
            'на пункты выше перед стартом.'
        )
        out['cta_buttons'] = [
            {'label_rus': 'Пересмотреть параметры', 'action': 'restart_survey'},
            {'label_rus': 'Купить Финмодель — 9 000 ₸', 'action': 'buy_finmodel'},
        ]
    else:  # red
        out['alternatives'] = _red_alternatives(block1, block2, result, db)
        out['headline_rus'] = (
            f'🚨 В этом формате{(" и регионе " + city_rus) if city_rus else ""} '
            f'направление даст убыток по базовому сценарию. Пересмотрите параметры или формат.'
        ).replace('  ', ' ').strip()
        out['cta_buttons'] = [
            {'label_rus': 'Пересчитать с другим форматом', 'action': 'change_format'},
            {'label_rus': 'Пересчитать с другим городом', 'action': 'change_city'},
            {'label_rus': 'Подробный анализ провала (9 000 ₸)', 'action': 'buy_finmodel'},
        ]

    return out


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
