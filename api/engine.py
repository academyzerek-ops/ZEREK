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
}


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
    """Приводит любой (legacy или canonical) city_id к канонической форме.

    Если id не найден — возвращает как есть, чтобы не ломать вызывающий код.
    """
    if city_id is None:
        return city_id
    s = str(city_id).strip()
    return CITY_LEGACY_TO_CANON.get(s, s)


def get_city_check_coef(city_id: str) -> float:
    """Ценовой коэффициент города. База = 1.00 (Актобе)."""
    canon = normalize_city_id(city_id)
    return CITY_CHECK_COEF.get(canon, 1.00)

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
    """Читает канонические атрибуты формата из 08_niche_formats.xlsx.

    Возвращает {capex_standard, typical_staff, masters_count, area_m2,
    format_type, format_name}. Если запись не найдена — пустой dict.

    Источник истины для (a) CAPEX-бенчмарка и (b) «эталонного» кол-ва мастеров:
    per-niche xlsx может содержать несколько строк под одним format_id
    (разные варианты класса), и `get_format_row` всегда берёт первую.
    08_niche_formats.xlsx даёт один канонический ориентир.
    """
    try:
        df = getattr(db, 'niches_formats_fallback', None)
    except Exception:
        df = None
    if df is None or getattr(df, 'empty', True):
        return {}
    try:
        rows = df[(df['niche_id'].astype(str) == niche_id)
                  & (df['format_id'].astype(str) == format_id)]
    except Exception:
        return {}
    if rows.empty:
        return {}
    r = rows.iloc[0]
    ts_raw = str(r.get('typical_staff', '') or '').strip()
    # Кол-во «мастеров» = первая группа в typical_staff (основная роль,
    # админы/ассистенты не считаются). Формат: 'роль:N|роль2:M'.
    masters_count = 0
    if ts_raw and ts_raw.lower() != 'nan':
        first = ts_raw.split('|')[0]
        if ':' in first:
            try:
                masters_count = int(first.split(':', 1)[1].strip())
            except Exception:
                masters_count = 0
    return {
        'niche_id': niche_id,
        'format_id': format_id,
        'format_name': str(r.get('format_name', '') or ''),
        'capex_standard': _safe_int(r.get('capex_standard'), 0),
        'typical_staff': ts_raw if ts_raw.lower() != 'nan' else '',
        'masters_count': masters_count,
        'area_m2': _safe_int(r.get('area_m2'), 0),
        'format_type': str(r.get('format_type', '') or ''),
    }


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
    cid = normalize_city_id(city_id)
    if db.cities.empty or "city_id" not in db.cities.columns:
        return {"city_id": cid, "Город": cid, "Население всего (чел.)": 0}
    rows = db.cities[db.cities["city_id"] == cid]
    if rows.empty:
        return {"city_id": cid, "Город": cid, "Население всего (чел.)": 0}
    return rows.iloc[0].to_dict()

def get_city_tax_rate(db: ZerekDB, city_id: str) -> float:
    cid = normalize_city_id(city_id)
    if db.city_tax_rates.empty:
        return FALLBACK_TAX_RATE_PCT
    rows = db.city_tax_rates[db.city_tax_rates["city_id"] == cid]
    if rows.empty:
        return FALLBACK_TAX_RATE_PCT
    return float(rows.iloc[0].get("ud_rate_pct", FALLBACK_TAX_RATE_PCT))

def get_rent_median(db: ZerekDB, city_id: str, loc_type: str) -> tuple:
    cid = normalize_city_id(city_id)
    if db.rent.empty:
        return (3000, 500)
    try:
        df = db.rent
        rows = df[(df["city_id"] == cid) & (df["loc_type"] == loc_type)]
        if rows.empty:
            rows = df[df["city_id"] == cid]
        if rows.empty:
            return (3000, 500)
        r = rows.iloc[0]
        return (int(r.get("rent_per_m2_median", 3000)), int(r.get("utilities_per_m2", 500)))
    except KeyError:
        return (3000, 500)

def get_competitors(db: ZerekDB, niche_id: str, city_id: str) -> dict:
    """Возвращает словарь с уровнем насыщения, числом конкурентов и плотностью.

    Добавлены поля `competitors_count` (int, нижняя граница диапазона из xlsx)
    и `density_per_10k` (float, сырое значение из колонки «на 10 000»), чтобы
    Block 1 и Block 3 могли работать с числами без повторного парсинга.
    """
    cid = normalize_city_id(city_id)
    fallback = {
        "уровень": 3,
        "сигнал": "Нет данных о конкуренции",
        "кол_во": "н/д",
        "competitors_count": 0,
        "density_per_10k": 0.0,
        "лидеры": "",
    }
    if db.competitors.empty:
        return fallback
    try:
        rows = db.competitors[(db.competitors["niche_id"] == niche_id) & (db.competitors["city_id"] == cid)]
    except KeyError:
        return fallback
    if rows.empty:
        return fallback
    row = rows.iloc[0]
    sat = _safe_int(row.get("Уровень насыщения (1-5)"), 3)
    signals = {1:"🟢 Рынок свободен",2:"🟢 Есть место",3:"🟡 Нужна дифференциация",4:"🟠 Высокая конкуренция",5:"🔴 Рынок насыщен"}
    # «Кол-во конкурентов (оценка)» в xlsx — обычно диапазон «20-30» или число.
    # Берём нижнюю границу как числовое значение.
    raw_count = row.get("Кол-во конкурентов (оценка)", "")
    count_int = 0
    try:
        s = str(raw_count).strip()
        if s and s.lower() != "nan":
            # если «20-30» — берём «20», иначе пробуем как число
            count_int = int(s.split("-")[0].strip()) if "-" in s else int(float(s))
    except Exception:
        count_int = 0
    # «Кол-во на 10 000 жителей» — готовый float из xlsx
    density = _safe_float(row.get("Кол-во на 10 000 жителей"), 0.0)
    return {
        "уровень": sat,
        "сигнал": signals.get(sat, ""),
        "кол_во": raw_count,
        "competitors_count": count_int,
        "density_per_10k": density,
        "лидеры": row.get("Лидеры рынка", ""),
    }

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
# Пороги и ставки — из constants.yaml (OWNER_CLOSURE_POCKET,
# OWNER_GROWTH_POCKET, OWNER_SOCIAL_RATE, OWNER_SOCIAL_BASE_MRP).
# ═══════════════════════════════════════════════


def calc_owner_social_payments(declared_monthly_base: int = None) -> int:
    """
    Обязательные соцплатежи собственника-ИП на Упрощёнке (РК 2026):
    ОПВ 10% + ОПВР 3.5% + ОСМС ~5% от 1.4 МРП + СО 3.5% ≈ 18-22% от базы.
    База и ставка читаются из constants.yaml (owner.social_base_mrp × МРП;
    owner.social_rate). Возвращает ₸/мес.
    """
    cap = MRP_2026 * OWNER_SOCIAL_BASE_MRP
    if declared_monthly_base is None:
        declared_monthly_base = cap
    base = min(declared_monthly_base, cap)
    return int(base * OWNER_SOCIAL_RATE)


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
    """Настоящий стресс-тест: плохо / база / хорошо. «В карман» по каждому сценарию.

    Коэффициенты читаются из config/defaults.yaml (quick_check.scenario_coefficients).
    Для стрессового плохого сценария используется stress_bad (с rent_k > 1).
    """
    # Человекочитаемые описания для UI — построим из коэффициентов
    def _desc(sc):
        parts = []
        t = sc.get('traffic_k', 1.0)
        c = sc.get('check_k', 1.0)
        r = sc.get('rent_k', 1.0)
        if t != 1.0:
            parts.append(f"трафик {'+' if t > 1 else '−'}{abs(int(round((t-1)*100)))}%")
        if c != 1.0:
            parts.append(f"чек {'+' if c > 1 else '−'}{abs(int(round((c-1)*100)))}%")
        if r != 1.0:
            parts.append(f"аренда {'+' if r > 1 else '−'}{abs(int(round((r-1)*100)))}%")
        return ', '.join(parts).capitalize() if parts else 'Расчётные показатели'

    scenarios = [
        {'key': 'bad',  'label': 'Если всё плохо',   'color': 'red',
         'params': _desc(SCENARIO_STRESS),
         **SCENARIO_STRESS},
        {'key': 'base', 'label': 'Базовый сценарий', 'color': 'blue',
         'params': _desc(SCENARIO_BASE),
         **SCENARIO_BASE},
        {'key': 'good', 'label': 'Если всё хорошо',  'color': 'green',
         'params': _desc(SCENARIO_OPT),
         **SCENARIO_OPT},
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
        return {'score': 1, 'label': 'Капитал vs бенчмарк',
                'note': 'Нет данных по CAPEX бенчмарку'}
    if capital_own is None or capital_own == 0:
        return {'score': 2, 'label': 'Капитал vs бенчмарк',
                'note': f'Капитал не указан — расчёт условный. Бенчмарк CAPEX {int(capex_needed):,} ₸.'.replace(',', ' ')}
    ratio = capital_own / capex_needed
    t_excel, t_match, t_low = SCORING_CAPITAL  # пороги: профицит / норма / терпимо
    if ratio >= t_excel:
        return {'score': 3, 'label': 'Капитал vs бенчмарк',
                'note': f'Капитал с запасом: на {int((ratio-1)*100)}% выше бенчмарка',
                'ratio': ratio}
    if ratio >= t_match:
        return {'score': 2, 'label': 'Капитал vs бенчмарк',
                'note': 'Капитал соответствует бенчмарку',
                'ratio': ratio}
    if ratio >= t_low:
        return {'score': 1, 'label': 'Капитал vs бенчмарк',
                'note': f'Капитал на грани: дефицит {int((1-ratio)*100)}%',
                'ratio': ratio,
                'gap_kzt': int(capex_needed - capital_own)}
    return {'score': 0, 'label': 'Капитал vs бенчмарк',
            'note': f'Критический дефицит капитала: {int((1-ratio)*100)}%',
            'ratio': ratio,
            'gap_kzt': int(capex_needed - capital_own)}


def _score_roi(profit_year, total_investment):
    """Скоринг годового ROI.

    - total_investment < 500K → 1 балл «недостаточно данных».
    - roi > 3.0 (300%) → sanity-cap: ROI=300%, 1 балл «проверьте капитал».
    - пороги из defaults.yaml (SCORING_ROI = [hi, mid, lo] = [0.45, 0.30, 0.15]).
    """
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
    breakeven_months = payback.get('месяц') or breakeven.get('месяц')
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

    scoring_items = [
        _score_capital(capital_own, capex_needed),
        _score_roi(profit_year, total_investment),
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


# ═══════════════════════════════════════════════
# BLOCK 3 — РЫНОК И КОНКУРЕНТЫ
# ═══════════════════════════════════════════════

def compute_block3_market(db, result, adaptive):
    inp = result.get('input', {}) or {}
    risks = result.get('risks', {}) or {}
    comp = risks.get('competitors') or {}

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
        afford_text = f'Платёжеспособность на {int((affordability_index-1)*100)}% выше средней КЗ — можно закладывать премиум-чек'
    elif affordability_index >= 1.0:
        afford_text = 'Платёжеспособность на уровне средней КЗ — стандартные цены рынка работают хорошо'
    elif affordability_index >= 0.85:
        afford_text = f'Платёжеспособность на {int((1-affordability_index)*100)}% ниже средней КЗ — учтите при ценообразовании'
    else:
        afford_text = f'Платёжеспособность на {int((1-affordability_index)*100)}% ниже средней КЗ — премиум-форматы рискованны'

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
    configs = getattr(db, 'configs', {}) or {}
    return ((configs.get('niches', {}) or {}).get('niches', {}) or {}).get(niche_id, {}).get('archetype', '')


def compute_block4_unit_economics(db, result, adaptive, block2=None):
    inp = result.get('input', {}) or {}
    fin = result.get('financials', {}) or {}
    staff = result.get('staff', {}) or {}
    tax = result.get('tax', {}) or {}
    arch = _archetype_of(db, inp.get('niche_id', ''))

    avg_check = _safe_int(fin.get('check_med'), 0) or 3000
    traffic = _safe_int(fin.get('traffic_med'), 0) or 30
    cogs_pct = _safe_float(fin.get('cogs_pct'), 0.30)
    tax_rate = (tax.get('rate_pct', 3) or 3) / 100
    rent_month = _safe_int(fin.get('rent_month'), 0)
    fot_month = _safe_int(staff.get('fot_full_med'), 0)
    opex_month = _safe_int(fin.get('opex_med'), 0)

    # Количество юнитов
    staff_total = 0
    if block2:
        staff_total = ((block2.get('typical_staff') or {}).get('total')) or 0
    if staff_total == 0:
        staff_total = max(1, _safe_int(staff.get('headcount'), 1))

    work_days = 26

    # SOLO-режим: мастер = сам предприниматель (HOME/SOLO форматы).
    # В этом случае «Мастеру (сдельно)» и «Бизнесу» — это одно и то же лицо,
    # разбивку упрощаем: материалы / аренда / налог → «В карман вам».
    is_solo_unit = bool(inp.get('founder_works')) and (
        (block2 or {}).get('is_solo') or
        (inp.get('format_id') or '').upper().endswith(('_HOME', '_SOLO'))
    )

    # Архетип-специфичный unit
    if arch == 'A':  # услуги с мастерами
        unit_label = 'мастер в месяц'
        masters_count = max(staff_total, 1)
        checks_per_day = max(int(traffic / masters_count), 1)
        load_pct = 0.80
        gross_rev_per_unit = int(checks_per_day * avg_check * work_days * load_pct)
        # распределение одного чека
        materials = int(avg_check * 0.12)
        rent_share = int(rent_month / masters_count / (checks_per_day * work_days)) if masters_count else 0
        overhead_share = int(opex_month * 0.5 / masters_count / (checks_per_day * work_days)) if masters_count else 0
        tax_per_check = int(avg_check * tax_rate)
        if is_solo_unit:
            # Без сдельной — мастер и предприниматель одно лицо.
            in_pocket = max(0, avg_check - materials - rent_share - overhead_share - tax_per_check)
            breakdown = [
                {'label':'Материалы', 'amount':materials, 'pct': round(materials/avg_check*100)},
                {'label':'Аренда (доля)', 'amount':rent_share, 'pct': round(rent_share/avg_check*100)},
                {'label':'Прочие OPEX', 'amount':overhead_share, 'pct': round(overhead_share/avg_check*100)},
                {'label':'Налог', 'amount':tax_per_check, 'pct': round(tax_per_check/avg_check*100)},
                {'label':'В карман вам', 'amount':in_pocket, 'pct': round(in_pocket/avg_check*100)},
            ]
            piece_rate = 0
        else:
            piece_rate = int(avg_check * 0.40)
            business = max(0, avg_check - piece_rate - materials - rent_share - overhead_share - tax_per_check)
            breakdown = [
                {'label':'Мастеру (сдельно)', 'amount':piece_rate, 'pct': round(piece_rate/avg_check*100)},
                {'label':'Материалы', 'amount':materials, 'pct': round(materials/avg_check*100)},
                {'label':'Аренда (доля)', 'amount':rent_share, 'pct': round(rent_share/avg_check*100)},
                {'label':'Прочие OPEX', 'amount':overhead_share, 'pct': round(overhead_share/avg_check*100)},
                {'label':'Налог', 'amount':tax_per_check, 'pct': round(tax_per_check/avg_check*100)},
                {'label':'Бизнесу', 'amount':business, 'pct': round(business/avg_check*100)},
            ]
        # breakeven по загрузке
        fixed_per_master = int((rent_month + opex_month * 0.5) / masters_count) if masters_count else 0
        var_margin = avg_check - piece_rate - materials - tax_per_check
        min_checks_month = int(fixed_per_master / var_margin) if var_margin > 0 else 9999
        min_load = min_checks_month / max(checks_per_day * work_days, 1)
        planned_checks = int(checks_per_day * work_days * load_pct)
        safety = planned_checks / max(min_checks_month, 1)
        metrics = {
            'checks_per_day': checks_per_day, 'avg_check': avg_check,
            'load_pct': int(load_pct*100), 'work_days': work_days,
            'gross_revenue_per_unit': gross_rev_per_unit,
            'breakeven_value': min_checks_month,
            'breakeven_label': f'{min_checks_month} услуг/мес на мастера',
            'planned_value': planned_checks,
            'planned_label': f'{planned_checks} услуг планируется',
            'safety_margin': round(safety, 1),
            'min_load_pct': int(min_load*100),
        }
    elif arch == 'B':  # общепит — один чек
        unit_label = 'один чек'
        food_cost = int(avg_check * cogs_pct)
        fot_per_check = int(fot_month / max(traffic*work_days, 1))
        rent_per_check = int(rent_month / max(traffic*work_days, 1))
        overhead_per_check = int(opex_month * 0.4 / max(traffic*work_days, 1))
        tax_per_check = int(avg_check * tax_rate)
        business = max(0, avg_check - food_cost - fot_per_check - rent_per_check - overhead_per_check - tax_per_check)
        breakdown = [
            {'label':'Food cost', 'amount':food_cost, 'pct': round(food_cost/avg_check*100)},
            {'label':'ФОТ на чек', 'amount':fot_per_check, 'pct': round(fot_per_check/avg_check*100)},
            {'label':'Аренда (доля)', 'amount':rent_per_check, 'pct': round(rent_per_check/avg_check*100)},
            {'label':'Прочие OPEX', 'amount':overhead_per_check, 'pct': round(overhead_per_check/avg_check*100)},
            {'label':'Налог', 'amount':tax_per_check, 'pct': round(tax_per_check/avg_check*100)},
            {'label':'Бизнесу', 'amount':business, 'pct': round(business/avg_check*100)},
        ]
        fixed_costs = fot_month + rent_month + int(opex_month * 0.6)
        var_margin = avg_check - food_cost - tax_per_check
        be_checks_day = int(fixed_costs / max(var_margin * work_days, 1)) if var_margin > 0 else 0
        safety = traffic / max(be_checks_day, 1)
        metrics = {
            'avg_check': avg_check,
            'breakeven_value': be_checks_day,
            'breakeven_label': f'{be_checks_day} чеков/день',
            'planned_value': traffic,
            'planned_label': f'{traffic} чеков/день',
            'safety_margin': round(safety, 1),
        }
    elif arch == 'C':  # retail
        unit_label = '100 ₸ выручки'
        markup_pct = 50
        cogs_pct_r = 100 / (100 + markup_pct) if markup_pct else 0.5
        c_cogs = int(100 * cogs_pct_r)
        c_fot = int(100 * 0.10)
        c_rent = int(100 * 0.12)
        c_over = int(100 * 0.08)
        c_tax = int(100 * tax_rate)
        c_loss = int(100 * 0.05)
        c_bus = max(0, 100 - c_cogs - c_fot - c_rent - c_over - c_tax - c_loss)
        breakdown = [
            {'label':'Закупка (COGS)', 'amount':c_cogs, 'pct':c_cogs},
            {'label':'ФОТ', 'amount':c_fot, 'pct':c_fot},
            {'label':'Аренда', 'amount':c_rent, 'pct':c_rent},
            {'label':'Прочие OPEX', 'amount':c_over, 'pct':c_over},
            {'label':'Налог', 'amount':c_tax, 'pct':c_tax},
            {'label':'Списания/порча', 'amount':c_loss, 'pct':c_loss},
            {'label':'Бизнесу', 'amount':c_bus, 'pct':c_bus},
        ]
        metrics = {
            'markup_pct': markup_pct, 'inventory_turnover_days': 28, 'gross_margin_pct': 100-c_cogs,
            'breakeven_label': 'По обороту запасов',
            'planned_label': f'Средний чек ~{_fmt_kzt(avg_check)}',
            'safety_margin': 2.0,
        }
    elif arch == 'D':  # абонементы
        unit_label = 'один клиент (LTV)'
        monthly_fee = avg_check  # в D-архетипе это абонемент
        churn_pct = 0.08
        lifetime = 1 / churn_pct
        ltv = int(monthly_fee * lifetime * 0.6)  # с учётом gross_margin
        marketing = int(opex_month * 0.25) or 150_000
        new_per_month = max(int(marketing / 12000), 1)
        cac = int(marketing / new_per_month)
        ltv_cac = round(ltv / max(cac, 1), 2)
        payback = round(cac / (monthly_fee * 0.6), 1) if monthly_fee else 0
        breakdown = [
            {'label':'LTV клиента', 'amount':ltv, 'pct':100},
        ]
        metrics = {
            'monthly_fee': monthly_fee, 'churn_pct': int(churn_pct*100), 'lifetime_months': round(lifetime,1),
            'ltv': ltv, 'cac': cac, 'ltv_cac_ratio': ltv_cac, 'payback_months': payback,
            'breakeven_label': 'LTV/CAC > 3', 'planned_label': f'LTV/CAC = {ltv_cac}',
            'safety_margin': round(ltv_cac/3, 1),
        }
    elif arch == 'E':  # проектный
        unit_label = 'один проект'
        project = avg_check  # для E avg_check = средний чек проекта
        mat = int(project * 0.40); fotp = int(project * 0.20)
        rent_p = int(project * 0.10); over = int(project * 0.05); taxp = int(project * tax_rate)
        bus = max(0, project - mat - fotp - rent_p - over - taxp)
        breakdown = [
            {'label':'Материалы', 'amount':mat, 'pct':40},
            {'label':'ФОТ', 'amount':fotp, 'pct':20},
            {'label':'Аренда (доля)', 'amount':rent_p, 'pct':10},
            {'label':'Прочие OPEX', 'amount':over, 'pct':5},
            {'label':'Налог', 'amount':taxp, 'pct':round(taxp/project*100)},
            {'label':'Бизнесу', 'amount':bus, 'pct':round(bus/project*100)},
        ]
        projects_per_month = max(1, int(traffic))  # traffic проксирует projects/month
        min_projects = max(1, int((rent_month + fot_month) / max(bus, 1)))
        safety = projects_per_month / max(min_projects, 1)
        metrics = {
            'avg_project': project, 'projects_per_month': projects_per_month,
            'breakeven_value': min_projects,
            'breakeven_label': f'{min_projects} проектов/мес',
            'planned_value': projects_per_month,
            'planned_label': f'{projects_per_month} проектов/мес',
            'safety_margin': round(safety, 1),
        }
    else:  # F — мощность
        unit_label = 'одна единица мощности'
        capacity = max(staff_total, 1)
        per_unit_revenue = int((fin.get('revenue_year1') or 0) / 12 / capacity) if capacity else 0
        occupancy = 0.65
        breakdown = [
            {'label':'Переменные затраты', 'amount':int(avg_check*0.30), 'pct':30},
            {'label':'ФОТ (сдельно)', 'amount':int(avg_check*0.25), 'pct':25},
            {'label':'Аренда (доля)', 'amount':int(avg_check*0.14), 'pct':14},
            {'label':'Коммуналка', 'amount':int(avg_check*0.08), 'pct':8},
            {'label':'Прочие', 'amount':int(avg_check*0.05), 'pct':5},
            {'label':'Налог', 'amount':int(avg_check*tax_rate), 'pct':round(tax_rate*100)},
            {'label':'Бизнесу', 'amount':int(avg_check*0.18), 'pct':18},
        ]
        metrics = {
            'capacity_units': capacity,
            'avg_check': avg_check,
            'occupancy_pct': int(occupancy*100),
            'per_unit_revenue_month': per_unit_revenue,
            'breakeven_label': 'Заполняемость ≥35%',
            'planned_label': f'Заполняемость {int(occupancy*100)}%',
            'safety_margin': round(occupancy/0.35, 1),
        }

    return {
        'archetype': arch,
        'unit_label': unit_label,
        'avg_check': avg_check,
        'breakdown': breakdown,
        'metrics': metrics,
    }


# ═══════════════════════════════════════════════
# BLOCK 6 — СТАРТОВЫЙ КАПИТАЛ (CAPEX)
# ═══════════════════════════════════════════════

def compute_block6_capital(db, result, adaptive, block2=None):
    capex = result.get('capex', {}) or {}
    capex_needed = _safe_int(capex.get('capex_med')) or _safe_int(capex.get('capex_total'))
    if capex_needed < 500_000 and block2:
        capex_needed = (block2.get('finance') or {}).get('capex_needed') or capex_needed
    capital_own = _safe_int(adaptive.get('capital_own')) if adaptive.get('capital_own') else None

    # Структура CAPEX — из breakdown если есть
    breakdown_src = capex.get('breakdown') or {}
    if isinstance(breakdown_src, dict) and breakdown_src:
        capex_structure = [
            {'label':CAPEX_BREAKDOWN_LABELS_RUS.get(k, k), 'amount':_safe_int(v, 0),
             'pct':int(_safe_int(v, 0)/max(capex_needed,1)*100)}
            for k,v in breakdown_src.items() if _safe_int(v, 0) > 0
        ]
    else:
        # синтетика по типовому распределению
        items = [
            ('Оборудование', 0.32),
            ('Ремонт / обустройство', 0.22),
            ('Первичные закупки', 0.15),
            ('Маркетинг на старт', 0.10),
            ('Оборотный капитал (3 мес)', 0.12),
            ('Депозит + 1-я аренда', 0.04),
            ('Юр.расходы, лицензии', 0.05),
        ]
        capex_structure = [{'label':l, 'amount':int(capex_needed*p), 'pct':int(p*100)} for l,p in items]

    # Дефицит / профицит
    if capital_own is None:
        diff_status = 'not_specified'; diff = None; diff_pct = None; actions = []
    else:
        diff = capital_own - capex_needed
        diff_pct = (diff / capex_needed * 100) if capex_needed else 0
        if diff >= 0:
            diff_status = 'surplus' if diff_pct > 5 else 'match'
            actions = ['Отложить профицит в резервный фонд (3-6 мес OPEX)', 'Увеличить маркетинговый бюджет на старт'] if diff_status == 'surplus' else []
        else:
            diff_status = 'critical_deficit' if abs(diff_pct) > 30 else 'deficit'
            gap = abs(diff)
            credit_monthly = int(gap * 0.035)  # 22% / 36 мес аннуитет
            actions = [
                f'Урезать формат до эконом-класса (бюджет ≈ {_fmt_kzt(int(capex_needed*0.5))})',
                f'Кредит {_fmt_kzt(gap)} на 24 мес (платёж ~{_fmt_kzt(credit_monthly)}/мес)',
                'Найти партнёра с долей 20%',
                'Грант Astana Hub / Bastau Business до 5 млн ₸',
            ]

    return {
        'capex_needed': capex_needed,
        'capital_own': capital_own,
        'diff': diff,
        'diff_pct': round(diff_pct, 1) if diff_pct is not None else None,
        'diff_status': diff_status,
        'capex_structure': capex_structure,
        'actions': actions,
    }


# ═══════════════════════════════════════════════
# BLOCK 7 — ТРАЕКТОРИЯ БИЗНЕСА НА 24 МЕСЯЦА
# ═══════════════════════════════════════════════

def compute_block7_scenarios(db, result, adaptive):
    scenarios = result.get('scenarios', {}) or {}
    cashflow = result.get('cashflow') or []

    # Помесячная траектория для каждого сценария (24 мес)
    def build_traj(scale):
        arr = []
        cumulative = 0
        for m in range(24):
            # Берём базовый cashflow, применяем множитель; если cashflow < 12 — экстраполируем
            if m < len(cashflow):
                mp = _safe_int(cashflow[m].get('прибыль'), 0) * scale
            elif cashflow:
                # Второй год — берём средний последнего кв. × рост 7%
                last_q_avg = sum(_safe_int(cashflow[-i].get('прибыль'), 0) for i in range(1, min(4, len(cashflow))+1)) / min(3, len(cashflow))
                mp = int(last_q_avg * scale * (1.07 ** ((m-12)/12)))
            else:
                mp = 0
            cumulative += int(mp)
            arr.append({'month': m+1, 'profit': int(mp), 'cumulative': cumulative})
        return arr

    pess = build_traj(B7_SCALE_PESS)
    base = build_traj(B7_SCALE_BASE)
    opt  = build_traj(B7_SCALE_OPT)

    # Ключевые точки
    def find_points(arr, capex_total):
        breakeven = None  # первый месяц где profit > 0
        roi_back = None   # первый месяц где cumulative >= capex_total
        for p in arr:
            if breakeven is None and p['profit'] > 0:
                breakeven = p['month']
            if roi_back is None and p['cumulative'] >= capex_total:
                roi_back = p['month']
            if breakeven and roi_back: break
        return {'breakeven_month': breakeven, 'roi_month': roi_back}

    capex_total = _safe_int((result.get('capex') or {}).get('capex_med'), 0) or _safe_int((result.get('capex') or {}).get('capex_total'), 0)
    return {
        'scenarios': {
            'pess': {'traj': pess, **find_points(pess, capex_total)},
            'base': {'traj': base, **find_points(base, capex_total)},
            'opt':  {'traj': opt,  **find_points(opt,  capex_total)},
        },
        'capex_total': capex_total,
    }


# ═══════════════════════════════════════════════
# BLOCK 8 — СТРЕСС-ТЕСТ
# ═══════════════════════════════════════════════

def compute_block8_stress_test(db, result, adaptive):
    """Анализ чувствительности к параметрам. Считаем импакт падения/роста на прибыль."""
    fin = result.get('financials', {}) or {}
    scenarios = result.get('scenarios', {}) or {}
    base_profit_year = _safe_int((scenarios.get('base') or {}).get('прибыль_год'), 0) or _safe_int(fin.get('profit_year1'), 0) or 1
    base_profit_month = base_profit_year // 12

    # Оцениваем импакт каждого параметра на -20%
    avg_check = _safe_int(fin.get('check_med'), 0) or 3000
    traffic = _safe_int(fin.get('traffic_med'), 0) or 30
    rent = _safe_int(fin.get('rent_month'), 0) or 150_000
    fot = _safe_int(result.get('staff', {}).get('fot_full_med'), 0) or 300_000
    cogs_pct = _safe_float(fin.get('cogs_pct'), 0.30)

    # Простой расчёт чувствительности (операционная прибыль = rev - cogs - opex)
    base_rev = avg_check * traffic * 26
    base_cogs = base_rev * cogs_pct
    base_opex = rent + fot + int((fin.get('opex_med') or 0) * 0.5)
    base_op_profit = max(base_rev - base_cogs - base_opex, 1)

    def impact(new_rev=None, new_cogs=None, new_opex=None):
        r = new_rev if new_rev is not None else base_rev
        c = new_cogs if new_cogs is not None else base_cogs
        o = new_opex if new_opex is not None else base_opex
        new_profit = r - c - o
        return round((new_profit - base_op_profit) / base_op_profit * 100)

    sensitivities = [
        {'param':'Загрузка / трафик', 'change':-20, 'impact_pct': impact(new_rev=base_rev*0.80, new_cogs=base_cogs*0.80)},
        {'param':'Средний чек',        'change':-20, 'impact_pct': impact(new_rev=base_rev*0.80, new_cogs=base_cogs*0.80)},
        {'param':'ФОТ (рост)',         'change':+20, 'impact_pct': impact(new_opex=base_opex + fot*0.20)},
        {'param':'Аренда (рост)',      'change':+30, 'impact_pct': impact(new_opex=base_opex + rent*0.30)},
        {'param':'Маркетинг (нет)',    'change':-100,'impact_pct': impact(new_rev=base_rev*0.90, new_cogs=base_cogs*0.90)},
        {'param':'Налог (рост)',       'change':+50, 'impact_pct': impact(new_opex=base_opex + int(base_rev*0.015))},
    ]
    # Порядок по абсолютному импакту
    sensitivities.sort(key=lambda x: x['impact_pct'])

    # Точки смерти
    var_margin = base_rev - base_cogs
    death_points = [
        {'param':'Загрузка / трафик', 'threshold': f'падение до <{int(base_opex/var_margin*100)}% ведёт в минус' if var_margin else '—'},
        {'param':'Средний чек',        'threshold': f'падение на >{int((1 - base_opex/(base_rev*(1-cogs_pct)))*100)}% ведёт в минус' if base_rev else '—'},
        {'param':'ФОТ',                'threshold': f'рост на >{int((base_op_profit)/(fot or 1)*100)}% ведёт в минус' if fot else '—'},
    ]

    # Критичный параметр — с наибольшим отрицательным импактом
    critical = sensitivities[0]

    recommendations_by_param = {
        'Загрузка / трафик': [
            'Минимум 3 первых месяца — фокус на маркетинге',
            'Следите за загрузкой еженедельно с 1-й недели',
            'Если загрузка <45% к 3-му мес — срочно пересматривайте маркетинг',
        ],
        'Средний чек': [
            'Разработать upsell / апсейлы (пакеты, комплексные услуги)',
            'Регулярно пересматривать прайс раз в 3 мес',
            'Не бояться поднимать цену на 5-10% после набора базы',
        ],
        'ФОТ (рост)': [
            'Сдельная система мотивации — привязана к выручке',
            'Не брать сотрудников про запас',
            'Готовить замену ключевым мастерам',
        ],
    }
    recs = recommendations_by_param.get(critical['param'], ['Следите за параметром ежемесячно'])

    return {
        'base_profit_month': base_profit_month,
        'base_profit_year': base_profit_year,
        'sensitivities': sensitivities,
        'death_points': death_points,
        'critical_param': critical,
        'recommendations': recs,
    }


# ═══════════════════════════════════════════════
# BLOCK 9 — РИСКИ НИШИ
# ═══════════════════════════════════════════════

def compute_block9_risks(db, result, adaptive):
    """Читает insight-файл ниши и извлекает топ-5 рисков. Fallback — generic риски по архетипу."""
    import os, re
    inp = result.get('input', {}) or {}
    niche_id = inp.get('niche_id', '')

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    insight_path = os.path.join(repo_root, 'knowledge', 'kz', 'niches', f'{niche_id}_insight.md')

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
    if os.path.exists(insight_path):
        try:
            with open(insight_path, 'r', encoding='utf-8') as f:
                content = f.read()
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

    return {
        'niche_id': niche_id,
        'source': 'insight' if len(risks_out) and (not generic_risks.get(arch) or risks_out[0].get('title') != generic_risks[arch][0]['title']) else 'generic',
        'risks': risks_out,
    }


# ═══════════════════════════════════════════════
# BLOCK 5 — P&L ЗА ГОД (Quick Check report, стр. 5)
# Три сценария + ключевые мультипликаторы + доход предпринимателя
# ═══════════════════════════════════════════════

def _cogs_label_by_archetype(archetype):
    return {
        'A': 'Расходные материалы',
        'B': 'Food cost',
        'C': 'Себестоимость товара',
        'D': 'Расходники',
        'E': 'Материалы проектов',
        'F': 'Переменные материалы',
    }.get(archetype, 'Материалы / COGS')


def _scenario_pnl_row(revenue_y, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate):
    """Собирает годовую P&L строку для одного сценария."""
    cogs_y = int(revenue_y * (cogs_pct or 0.30))
    fot_y = int(fot_monthly * 12)
    rent_y = int(rent_monthly * 12)
    marketing_y = int(marketing_monthly * 12)
    other_y = int(other_opex_monthly * 12)
    tax_y = int(revenue_y * (tax_rate or 0.03))
    net_profit = revenue_y - cogs_y - fot_y - rent_y - marketing_y - other_y - tax_y
    return {
        'revenue':   revenue_y,
        'cogs':      cogs_y,
        'fot':       fot_y,
        'rent':      rent_y,
        'marketing': marketing_y,
        'other_opex':other_y,
        'tax':       tax_y,
        'net_profit':net_profit,
    }


def compute_block5_pnl(db, result, adaptive):
    """Блок 5 — P&L за год по 3 сценариям + ключевые мультипликаторы."""
    adaptive = adaptive or {}
    fin = result.get('financials', {}) or {}
    scenarios = result.get('scenarios', {}) or {}
    staff = result.get('staff', {}) or {}
    tax = result.get('tax', {}) or {}
    inp = result.get('input', {}) or {}
    capex_block = result.get('capex', {}) or {}
    owner_eco = result.get('owner_economics', {}) or {}

    # Получаем архетип ниши
    archetype = ''
    configs = getattr(db, 'configs', {}) or {}
    niches_cfg = (configs.get('niches', {}) or {}).get('niches', {}) or {}
    niche_id = inp.get('niche_id', '')
    if niche_id:
        archetype = (niches_cfg.get(niche_id, {}) or {}).get('archetype', '')

    # Базовые месячные параметры
    # ВАЖНО: result.staff уже «подрезан» в run_quick_check_v3 на одну ставку
    # если owner_plus_* (через founder_works_eff в main.py). Здесь НЕ
    # вычитаем повторно, иначе ФОТ уйдёт в отрицательный двойной учёт.
    fot_monthly_full = _safe_int(staff.get('fot_full_med'), 0) or _safe_int(staff.get('fot_net_med'), 0)
    # Эффективное число ставок: masters_canon из 08 (4 барбера), либо row.headcount
    # с учётом seats_mult если тот применён. Это уже «полное» число, не нужно
    # множить повторно на seats_mult.
    row_hc = _safe_int(staff.get('headcount'), 1) or 1
    masters_canon = _safe_int(inp.get('masters_canon'), 0) or 0
    seats_mult_in = float(_safe_float(inp.get('seats_mult'), 1.0) or 1.0)
    effective_hc = max(masters_canon, int(round(row_hc * max(seats_mult_in, 1.0))), row_hc, 1)
    ent_role_id = adaptive.get('entrepreneur_role') or 'owner_only'
    # Доля одной ставки в полном (ещё не подрезанном) ФОТ.
    # Если ФОТ уже подрезан (owner_plus_*), восстанавливаем full
    # по соотношению: fot_unadj = fot_adj * hc / (hc - 1).
    if ent_role_id not in ('owner_only', 'owner_multi') and fot_monthly_full > 0 and effective_hc > 1:
        fot_unadj = int(fot_monthly_full * effective_hc / max(effective_hc - 1, 1))
        one_role_salary_full = int(fot_unadj / effective_hc)
    else:
        fot_unadj = fot_monthly_full
        one_role_salary_full = int(fot_unadj / effective_hc) if effective_hc else 0
    # Для PNL используем ФОТ как есть (уже корректно учитывает owner_plus_*).
    fot_monthly = fot_monthly_full
    rent_monthly = _safe_int(fin.get('rent_month'), 0)
    opex_total = _safe_int(fin.get('opex_med'), 0)
    # marketing + прочее — делим opex
    marketing_monthly = int(opex_total * 0.2) if opex_total else 100_000
    other_opex_monthly = max(0, opex_total - rent_monthly - marketing_monthly) if opex_total else 100_000
    cogs_pct = _safe_float(fin.get('cogs_pct'), 0.30)
    tax_rate = (tax.get('rate_pct', 3) or 3) / 100

    # Выручка по сценариям (годовая)
    rev_year_base = _safe_int((scenarios.get('base') or {}).get('выручка_год'), 0)
    rev_year_pess = _safe_int((scenarios.get('pess') or {}).get('выручка_год'), 0)
    rev_year_opt  = _safe_int((scenarios.get('opt')  or {}).get('выручка_год'), 0)

    if rev_year_base == 0:
        # Фолбэк из financials
        rev_year_base = _safe_int(fin.get('revenue_year1'), 0)
        rev_year_pess = int(rev_year_base * 0.75)
        rev_year_opt  = int(rev_year_base * 1.25)

    # ВАЖНО: ФОТ и аренда фиксированы; COGS пропорционально; маркетинг — как базовый
    pnl_base = _scenario_pnl_row(rev_year_base, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)
    pnl_pess = _scenario_pnl_row(rev_year_pess, cogs_pct, fot_monthly, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)
    # Оптимист: ФОТ чуть выше (сдельщики получают больше)
    fot_opt = int(fot_monthly * 1.15)
    pnl_opt  = _scenario_pnl_row(rev_year_opt, cogs_pct, fot_opt, rent_monthly, marketing_monthly, other_opex_monthly, tax_rate)

    # Мультипликаторы (по базовому сценарию)
    def _safe_div(a, b):
        return (a / b) if b else 0
    gross_margin = _safe_div(rev_year_base - pnl_base['cogs'], rev_year_base)
    op_margin = _safe_div(rev_year_base - pnl_base['cogs'] - pnl_base['fot'] - pnl_base['rent'] - pnl_base['marketing'] - pnl_base['other_opex'], rev_year_base)
    net_margin = _safe_div(pnl_base['net_profit'], rev_year_base)

    # ROI годовой
    # total_investment = capital_own (если указан) или capex_standard из 08
    # (правильный знаменатель, см. баг #2). Фолбэк — capex_med из per-niche
    # (часто занижен). Если < 500K или ROI > 300% — отдельная ветка.
    capital_own = _safe_int(adaptive.get('capital_own')) if adaptive.get('capital_own') else 0
    capex_standard_08 = _safe_int(inp.get('capex_standard'), 0)
    total_investment = (capital_own
                        or capex_standard_08
                        or _safe_int(capex_block.get('capex_med'), 0)
                        or _safe_int(capex_block.get('capex_total'), 0))
    if total_investment < 500_000:
        for k in ('capex_high', 'total', 'capital'):
            v = _safe_int(capex_block.get(k), 0)
            if v >= 500_000:
                total_investment = v; break
    if total_investment < 500_000:
        annual_roi = None  # нечего считать
    else:
        raw_roi = _safe_div(pnl_base['net_profit'], total_investment)
        # Sanity-cap на абсурдные ROI (обычно признак неверного знаменателя).
        annual_roi = min(raw_roi, 3.0) if raw_roi > 3.0 else raw_roi

    # Доход предпринимателя
    # Ставка роли = одна позиция из ФОТ (уже вычтена выше из pnl_base.fot, так
    # что удвоения нет: profit_monthly + role_salary_monthly = чистый доход
    # владельца без пересечений).
    role_salary_monthly = 0
    role_breakdown = []
    if ent_role_id not in ('owner_only', 'owner_multi'):
        role_salary_monthly = one_role_salary_full
        if role_salary_monthly == 0:
            role_salary_monthly = 200_000
        role_breakdown.append({'role': ent_role_id.replace('owner_plus_', ''),
                               'salary_monthly': role_salary_monthly})
    elif ent_role_id == 'owner_multi':
        role_salary_monthly = max(int(fot_monthly_full * 0.35), 300_000)
        role_breakdown.append({'role': 'multi', 'salary_monthly': role_salary_monthly})

    profit_monthly_base = pnl_base['net_profit'] // 12
    income_from_business = profit_monthly_base
    entrepreneur_income_monthly = role_salary_monthly + income_from_business

    return {
        'archetype': archetype,
        'cogs_label_rus': _cogs_label_by_archetype(archetype),
        'scenarios': {
            'pess': pnl_pess,
            'base': pnl_base,
            'opt':  pnl_opt,
        },
        'margins': {
            'gross':     gross_margin,
            'operating': op_margin,
            'net':       net_margin,
        },
        'annual_roi': annual_roi,
        'total_investment': total_investment,
        'entrepreneur_income': {
            'role_salary_monthly': role_salary_monthly,
            'profit_monthly':       income_from_business,
            'total_monthly':        entrepreneur_income_monthly,
            'total_yearly':         entrepreneur_income_monthly * 12,
            'role_breakdown':       role_breakdown,
        },
    }


# ═══════════════════════════════════════════════
# BLOCK 10 — СЛЕДУЮЩИЕ ШАГИ (Quick Check report, финал)
# План действий / условия / альтернативы по вердикту + CTA upsell
# ═══════════════════════════════════════════════

def _green_action_plan(block2, block1):
    """4 недельных блока чек-листа для Green."""
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
    # Неделя 3-4: Закупка
    plan.append({
        'week_range': '3-4',
        'title': 'Закупка оборудования и материалов',
        'actions': [
            f'Закупить оборудование (бюджет ≈ {_fmt_kzt(capex_equipment)})',
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
    plan.append({
        'week_range': 'Запуск',
        'title': 'Первые недели работы',
        'actions': [
            ('Следить за загрузкой мастеров еженедельно'
             if format_type not in ('HOME','SOLO','MOBILE') else 'Отслеживать конверсию заявок в сделки'),
            'Отзывы в 2GIS — просить клиентов с 1-го дня',
            'Еженедельный контроль unit-экономики (выручка/чек/COGS)',
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
        if label == 'Капитал vs бенчмарк':
            gap = -(fin.get('capital_diff') or 0)
            if gap <= 0:
                # капитал достаточен (дефицита нет) — условие не про деньги
                conditions.append({
                    'title': 'Резервный фонд: обеспечить запас оборотки',
                    'options': ['Заложить 3-6 мес OPEX как резерв', 'Не вкладывать весь капитал в CAPEX', 'Иметь отдельный счёт для резерва'],
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

    out = {
        'color': color,
        'farewell_rus': _final_farewell(color, block2),
        'upsell': _upsell_block(color, block1, block2),
    }

    if color == 'green':
        out['action_plan'] = _green_action_plan(block2, block1)
        out['headline_rus'] = '✅ Ваша идея реалистична. Можете входить.'
        out['cta_buttons'] = [
            {'label_rus': 'Купить Финансовую модель — 9 000 ₸', 'action': 'buy_finmodel'},
            {'label_rus': 'Скачать PDF отчёта', 'action': 'download_pdf'},
        ]
    elif color == 'yellow':
        out['conditions'] = _yellow_conditions(block1, block2)
        out['headline_rus'] = f'⚠️ Идея возможна при устранении {len(out["conditions"])} условий.'
        out['cta_buttons'] = [
            {'label_rus': 'Пересмотреть параметры', 'action': 'restart_survey'},
            {'label_rus': 'Купить Финмодель — 9 000 ₸', 'action': 'buy_finmodel'},
        ]
    else:  # red
        out['alternatives'] = _red_alternatives(block1, block2, result, db)
        out['headline_rus'] = '🚨 В текущей конфигурации бизнес не окупится.'
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
