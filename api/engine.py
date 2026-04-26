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

# Базовые константы — источник истины: data/external/kz_tax_constants_2026.yaml.
# Читаем через tax_constants_loader (lru_cache, файл читается один раз за процесс).
# config/constants.yaml оставлен как fallback для обратной совместимости.
def _load_tax_constants():
    """Попытка взять из YAML tax_constants_loader, иначе fallback на constants.yaml."""
    try:
        from loaders.tax_constants_loader import (
            get_mrp, get_mzp, get_nds_rate,
        )
        return int(get_mrp()), int(get_mzp()), float(get_nds_rate())
    except Exception as exc:
        print(f"⚠️ tax_constants_loader недоступен ({exc}); fallback на constants.yaml")
        return (
            int(CONSTANTS.get("mrp_2026", 4325)),
            int(CONSTANTS.get("mzp_2026", 85000)),
            float(CONSTANTS.get("nds_rate", 0.16)),
        )


MRP_2026, MZP_2026, NDS_RATE = _load_tax_constants()

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
    'marketing':   'Открытие и брендинг',
    'deposit':     'Депозит за аренду',
    'legal':       'Юридическое оформление',
    'training':    'Обучение и курсы',
}

# Стоимость обучения по уровню опыта для ниш с training_required=True
# (MANICURE в Round 6; BARBER/BROW/LASH/SUGARING/COSMETOLOGY/MASSAGE/DENTAL
# будут добавлены по мере калибровки wiki-данных).
#
# Round-3 правка: дефолт когда опыт «не указан» / пустой — считаем как
# «с нуля» (прежняя логика .get(exp, 0) выдавала 0 и роняла обучение
# из CAPEX на новичке, который не заполнил поле). Клиенту с опытом в
# шаблоне CAPEX показываем подпись: можно исключить 150 000 ₸.
TRAINING_COSTS_BY_EXPERIENCE = {
    # R12.5 канон (3 уровня из data/archetypes/a1_beauty_solo.yaml):
    'none':          150_000,   # с нуля — полный курс
    'middle':        40_000,    # 1-2 продвинутых курса (= legacy "some")
    'experienced':   20_000,    # повышение квалификации (R12.5 для опытного)
    # Legacy aliases (Mini App до R12.5 использовала some/has/pro/expert):
    'not_specified': 150_000,
    '':              150_000,
    'some':          40_000,    # = middle
    'has':           40_000,
    'pro':           20_000,    # = experienced (раньше 0; R12.5 закладывает курсы 20K)
    'expert':        20_000,
}


# R12.5 Сессия 2: маппинг legacy experience-меток на R12.5-канон.
# Mini App до Сессии 3 присылает 'some'/'has'/'pro'/'expert', движок
# нормализует к 'none'/'middle'/'experienced'.
_EXPERIENCE_TO_R12 = {
    'none': 'none', '': 'none', 'not_specified': 'none',
    'some': 'middle', 'has': 'middle', 'middle': 'middle',
    'pro': 'experienced', 'expert': 'experienced', 'experienced': 'experienced',
}


def _apply_r12_5_overrides(fin, niche_id, format_id, experience='none'):
    """R12.5 Сессия 2: переписывает поля `fin` через `formats_r12` блок
    в YAML ниши + experience_levels из A1 архетипа.

    Если ниша не содержит `formats_r12` (или формат не найден в нём) —
    возвращает fin без изменений. Это безопасный fallback для всех
    остальных ниш (BARBER, COFFEE, и т.д.) которые ещё не переехали.

    Override применяет:
      · check_med = base_check_astana × experience.check_multiplier
        (city_check_coef умножится позже в seats_mult ветке —
         мы сохраняем нейтральный масштаб для Астаны).
      · traffic_med = round(experience.avg_clients_per_day_mature)
      · working_days_per_month = formats_r12[fmt].working_days_per_month
        (раньше calc_revenue_monthly использовал × 30 жёстко).
      · cogs_pct из formats_r12 (R12.5: 10% для STUDIO/SALON_RENT/MALL_SOLO,
         12% для HOME).

    Аренда / маркетинг / CAPEX через formats_r12 — НЕ перезаписываем
    в этом коммите (Сессия 2 Commit 2 минимальная). Для HOME это
    не критично (rent=0, marketing уже через marketing_service).
    """
    if not fin:
        return fin
    try:
        from loaders.niche_loader import load_niche_yaml, load_archetype_yaml  # noqa: WPS433
    except ImportError:
        return fin
    niche = (niche_id or '').upper()
    fmt = (format_id or '').upper()
    yaml_data = load_niche_yaml(niche)
    if not yaml_data or 'formats_r12' not in yaml_data:
        return fin

    # Найти формат в formats_r12. Маппим legacy xlsx-суффиксы:
    # _HOME → HOME, _SOLO → SALON_RENT, _STANDARD → STUDIO, _PREMIUM → нет.
    suffix_to_r12 = {
        '_HOME': 'HOME',
        '_SOLO': 'SALON_RENT',
        '_STANDARD': 'STUDIO',
        '_PREMIUM': None,
    }
    r12_id = None
    for sfx, rid in suffix_to_r12.items():
        if fmt.endswith(sfx):
            r12_id = rid
            break
    if not r12_id:
        return fin

    target = None
    for f in yaml_data.get('formats_r12') or []:
        if f.get('id') == r12_id:
            target = f
            break
    if not target:
        return fin

    # Архетип A1 для experience_levels
    a1 = load_archetype_yaml('A1')
    if not a1:
        return fin
    exp_norm = _EXPERIENCE_TO_R12.get((experience or '').lower(), 'none')
    exp_params = (a1.get('experience_levels') or {}).get(exp_norm) or {}

    check_mult = float(exp_params.get('check_multiplier') or 1.0)
    avg_clients = float(exp_params.get('avg_clients_per_day_mature') or 0)

    # Базовый чек берём из formats_r12 (Астана). Если есть уровни —
    # используем simple/standard/single как дефолт (выбор уровня
    # будет в Сессии 3 через анкету).
    base_check_astana = target.get('base_check', {}).get('astana')
    if not base_check_astana:
        # Для STUDIO/SALON_RENT/MALL_SOLO — base_check внутри levels
        levels = target.get('levels') or {}
        if levels:
            default_level_key = (
                'simple' if 'simple' in levels else
                'standard' if 'standard' in levels else
                next(iter(levels))
            )
            base_check_astana = (levels.get(default_level_key) or {}).get('base_check_astana')
            # MALL_SOLO: используем base_check_average_astana если есть
            if not base_check_astana:
                base_check_astana = target.get('base_check_average_astana')

    fin_new = dict(fin)

    if base_check_astana and check_mult:
        # check_med — это база для Астаны до city_check_coef.
        # В коде ниже city_check_coef умножается на check позже
        # (через get_city_check_coef). Astana coef = 1.0, поэтому
        # для неё значение остаётся таким же.
        fin_new['check_med'] = int(round(base_check_astana * check_mult))

    if avg_clients > 0:
        # traffic_med — целое число клиентов в день. Округляем.
        fin_new['traffic_med'] = max(1, int(round(avg_clients)))

    wd = target.get('working_days_per_month')
    if wd:
        fin_new['working_days_per_month'] = int(wd)

    cogs = target.get('cogs_pct')
    if cogs:
        fin_new['cogs_pct'] = float(cogs)

    # R12.5 Сессия 2 хвост: rent_med + deposit_months из formats_r12.
    # HOME: rent=0, deposit=0. STUDIO/SALON_RENT/MALL_SOLO: rent_per_month
    # из YAML, deposit_months обычно 2 (engine: deposit = rent × months).
    # Для SALON_RENT уровень standard/premium хранит rent внутри levels —
    # дефолт на standard. Для STUDIO rent на верхнем уровне формата.
    rent_per_month = target.get('rent_per_month_astana')
    if rent_per_month is None:
        # SALON_RENT — rent внутри levels
        levels = target.get('levels') or {}
        default_level_key = 'standard' if 'standard' in levels else (
            'simple' if 'simple' in levels else None
        )
        if default_level_key:
            rent_per_month = (levels.get(default_level_key) or {}).get('rent_per_month_astana')
    if rent_per_month is not None:
        fin_new['rent_med'] = int(rent_per_month)
    deposit_months = target.get('deposit_months')
    if deposit_months is None:
        levels = target.get('levels') or {}
        default_level_key = 'standard' if 'standard' in levels else (
            'simple' if 'simple' in levels else None
        )
        if default_level_key:
            deposit_months = (levels.get(default_level_key) or {}).get('deposit_months')
    if deposit_months is not None:
        fin_new['deposit_months'] = int(deposit_months)

    return fin_new


def _apply_r12_5_staff_override(staff, niche_id, format_id):
    """R12.5: для R12 ниш все 4 формата — соло (headcount=1, fot=0).

    db.get_format_row для STAFF может возвращать данные из legacy YAML
    formats: блока, где для STANDARD захардкожено headcount=5,
    fot_full_med=1338000 (старая модель «студия 3-4 мастера»).

    R12.5: STUDIO (бывш. STANDARD) — соло-формат с 1 мастером.
    Обнуляем headcount/fot если formats_r12 определён.
    """
    if not staff:
        return staff
    try:
        from loaders.niche_loader import load_niche_yaml  # noqa: WPS433
    except ImportError:
        return staff
    niche = (niche_id or '').upper()
    yaml_data = load_niche_yaml(niche)
    if not yaml_data or 'formats_r12' not in yaml_data:
        return staff
    fmt = (format_id or '').upper()
    suffix_to_r12 = {
        '_HOME': 'HOME', '_SOLO': 'SALON_RENT',
        '_STANDARD': 'STUDIO', '_PREMIUM': None,
    }
    r12_id = None
    for sfx, rid in suffix_to_r12.items():
        if fmt.endswith(sfx):
            r12_id = rid
            break
    if not r12_id:
        return staff
    out = dict(staff)
    out['headcount'] = 1
    out['positions'] = 'Мастер (сам)'
    out['founder_role'] = 'Сам'
    for k in ('fot_net_min', 'fot_net_med', 'fot_net_max',
              'fot_full_min', 'fot_full_med', 'fot_full_max'):
        out[k] = 0
    out['hire_m3'] = 0
    out['hire_m6'] = 0
    return out


def _r12_5_normalize_meta08(meta08, niche_id, format_id):
    """R12.5: для ниш с formats_r12 обнуляем legacy multi-place
    параметры 08-канона. Все 4 формата R12.5 — соло (1 мастер).

    Без этой нормализации:
      · 08.typical_staff = 'мастер:2' даёт seats_mult=2 → revenue×2
      · 08.capex_standard = 2.2M перебивает _apply_r12_5_capex_override
        (см. engine logic «if capex_standard_08 > capex_med * 1.1: override»).

    Возвращает копию meta08 с очищенными полями. Если ниша не имеет
    formats_r12 — возвращает meta08 без изменений.
    """
    if not meta08:
        return meta08
    try:
        from loaders.niche_loader import load_niche_yaml  # noqa: WPS433
    except ImportError:
        return meta08
    niche = (niche_id or '').upper()
    yaml_data = load_niche_yaml(niche)
    if not yaml_data or 'formats_r12' not in yaml_data:
        return meta08
    fmt = (format_id or '').upper()
    suffix_to_r12 = {
        '_HOME': 'HOME', '_SOLO': 'SALON_RENT',
        '_STANDARD': 'STUDIO', '_PREMIUM': None,
    }
    r12_id = None
    for sfx, rid in suffix_to_r12.items():
        if fmt.endswith(sfx):
            r12_id = rid
            break
    if not r12_id:
        return meta08
    out = dict(meta08)
    out['masters_count'] = 1                 # все R12.5 форматы — соло
    out['typical_staff'] = None              # не масштабируем через seats_mult
    out['capex_standard'] = 0                # не перебиваем formats_r12 capex
    return out


def _apply_r12_5_capex_override(capex_data, niche_id, format_id, experience='none'):
    """R12.5 Сессия 2 хвост: переписывает CAPEX-разбивку через
    `formats_r12.capex_items` + `capex_base_total`.

    Engine считает capex_total = capex_med + deposit + working_cap_3m.
    R12.5 capex_base_total УЖЕ включает working_capital, поэтому
    обнуляем `working_cap_3m` чтобы не было double-add.

    Training (по experience) и deposit (×rent_per_month) добавляются
    engine'ом отдельно — это совместимо с R12.5 формулой Адиля:
        capex_total = base_total + training + deposit

    Не меняет capex_data если ниша не содержит formats_r12 — fallback
    на legacy YAML formats: блок (для других ниш).
    """
    if not capex_data:
        return capex_data
    try:
        from loaders.niche_loader import load_niche_yaml  # noqa: WPS433
    except ImportError:
        return capex_data
    niche = (niche_id or '').upper()
    fmt = (format_id or '').upper()
    yaml_data = load_niche_yaml(niche)
    if not yaml_data or 'formats_r12' not in yaml_data:
        return capex_data

    suffix_to_r12 = {
        '_HOME': 'HOME',
        '_SOLO': 'SALON_RENT',
        '_STANDARD': 'STUDIO',
        '_PREMIUM': None,
    }
    r12_id = None
    for sfx, rid in suffix_to_r12.items():
        if fmt.endswith(sfx):
            r12_id = rid
            break
    if not r12_id:
        return capex_data

    target = None
    for f in yaml_data.get('formats_r12') or []:
        if f.get('id') == r12_id:
            target = f
            break
    if not target:
        return capex_data

    # Базовая сумма + items. Для STUDIO/SALON_RENT с уровнями берём
    # дефолт (simple/standard).
    base_total = target.get('capex_base_total')
    if base_total is None:
        # SALON_RENT хранит base_total per-level
        for k in ('capex_base_total_standard', 'capex_base_total_simple'):
            if target.get(k):
                base_total = target[k]
                break
    if base_total is None:
        return capex_data  # нет данных для override

    capex_new = dict(capex_data)
    capex_new['capex_med'] = int(base_total)
    capex_new['capex_min'] = int(base_total * 0.85)
    capex_new['capex_max'] = int(base_total * 1.30)
    # Обнуляем working_cap_3m т.к. он уже внутри base_total через
    # capex_items.working_capital.
    capex_new['working_cap_3m'] = 0

    # Перезаписываем breakdown items для PDF (стр. «Инвестиции»).
    items = target.get('capex_items') or target.get('capex_items_common') or {}
    field_map = {
        'equipment':       'equipment',
        'renovation':      'renovation',
        'furniture':       'furniture',
        'first_stock':     'first_stock',
        'permits':         'permits_sez',
        'working_capital': 'working_cap_3m_breakdown',  # для отображения, не пересчёт
        'marketing_start': 'marketing',
        'legal':           'legal',
        'kiosk_design':    'kiosk_design',
    }
    for yaml_key, capex_key in field_map.items():
        if yaml_key in items:
            med = (items[yaml_key] or {}).get('med')
            if med is not None:
                capex_new[capex_key] = int(med)

    return capex_new


_MONTH_NAMES_RUS_FULL = ['Янв','Фев','Мар','Апр','Май','Июн',
                         'Июл','Авг','Сен','Окт','Ноя','Дек']
_MONTH_NAMES_RUS_LONG = ['Январь','Февраль','Март','Апрель','Май','Июнь',
                         'Июль','Август','Сентябрь','Октябрь','Ноябрь','Декабрь']


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

        # Налоги 2026 (справочник режимов). Ставки УСН по городам теперь в
        # data/external/kz_tax_constants_2026.yaml — читаются через
        # tax_constants_loader.get_usn_rate_for_city().
        self.tax_regimes = self._xl("05_tax_regimes.xlsx", "tax_regimes_2026", 0)

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


# ═══════════════════════════════════════════════
# 3. РАСЧЁТНЫЕ ФУНКЦИИ
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# PHASE 2 — OWNER ECONOMICS
# «В карман собственнику» + точки закрытия/роста + стресс-тест
# Пороги и ставки — из constants.yaml (OWNER_CLOSURE_POCKET,
# OWNER_GROWTH_POCKET, OWNER_SOCIAL_RATE, OWNER_SOCIAL_BASE_MRP).
# ═══════════════════════════════════════════════


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
    experience: str = 'none',  # R12.5: уровень опыта для override fin/capex
) -> dict:
    """
    Quick Check v3 — полный расчёт из новых шаблонов (12 листов).
    Возвращает структурированный dict для отчёта.
    """
    # Lazy import — после Этапа 8 cleanup wrappers удалены, чтобы избежать
    # циклов (services импортируют константы из engine на module-level).
    from loaders.city_loader import (
        get_city, get_city_check_coef, normalize_city_id,
    )
    from loaders.competitor_loader import get_competitors
    from loaders.content_loader import get_failure_pattern, get_permits
    from loaders.niche_loader import _get_canonical_format_meta
    from loaders.rent_loader import get_rent_median
    from loaders.tax_constants_loader import get_usn_rate_for_city
    from services.economics_service import (
        calc_breakeven, calc_cashflow, calc_closure_growth_points,
        calc_owner_economics, calc_payback,
    )

    # Нормализуем city_id на входе: legacy (ALA/ALMATY/almaty) → canonical.
    city_id = normalize_city_id(city_id)

    # ── Данные из шаблона ниши ──
    fmt = db.get_format_row(niche_id, 'FORMATS', format_id, cls)
    fin = db.get_format_row(niche_id, 'FINANCIALS', format_id, cls)
    staff = db.get_format_row(niche_id, 'STAFF', format_id, cls)
    capex_data = db.get_format_row(niche_id, 'CAPEX', format_id, cls)
    tax_data = db.get_format_row(niche_id, 'TAXES', format_id, cls)

    # R12.5 Сессия 2: override fin + capex_data через formats_r12 +
    # A1 archetype. Канон R12.5 — base_check / avg_clients_per_day_mature /
    # working_days_per_month / rent_per_month / capex_base_total +
    # capex_items по формату и уровню опыта. Применяется только если
    # YAML содержит formats_r12 для этой ниши и archetype = A1.
    # Иначе fin/capex_data используются как были (legacy R8/R9).
    fin = _apply_r12_5_overrides(
        fin, niche_id, format_id, experience=experience,
    )
    capex_data = _apply_r12_5_capex_override(
        capex_data, niche_id, format_id, experience=experience,
    )
    staff = _apply_r12_5_staff_override(staff, niche_id, format_id)

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
    # R12.5: 08-канон для R12 ниш всё ещё может содержать legacy
    # multi-place параметры (typical_staff: 'мастер:2', capex 2.2M).
    # Обнуляем их если formats_r12 определён — все 4 формата R12.5 = соло.
    meta08 = _r12_5_normalize_meta08(meta08, niche_id, format_id)

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
    # Источник: data/external/kz_tax_constants_2026.yaml (решения маслихатов 2026).
    tax_rate = get_usn_rate_for_city(city_id) / 100

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
            # R12.5 Сессия 2: working_days_per_month — приходит из
            # formats_r12 через _apply_r12_5_overrides. Используется
            # в compute_pnl_aggregates Шаг 3 (rev_mature_m).
            "working_days_per_month": _safe_int(fin.get('working_days_per_month'), 30),
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
# QUICK CHECK v2 — Adaptive Survey Config
# ═══════════════════════════════════════════════

# Справочник типов локации для рендера в анкете v2.
# LOCATION_TYPES_META переехал в api/config.py (Этап 8.6).
# Re-export для обратной совместимости (niche_loader импортирует отсюда).
from config import LOCATION_TYPES_META  # noqa: F401, E402


# ───────────────────────────────────────────────────────────────────────────
# Quick Check v2 — Survey (per-niche question list)
# ───────────────────────────────────────────────────────────────────────────


# ═══════════════════════════════════════════════
# BLOCK 1 — ВЕРДИКТ (Quick Check report, первая страница)
# Согласно спецификации «ZEREK Quick Check — Блок 1» v1.0
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# BLOCK 3 — РЫНОК И КОНКУРЕНТЫ
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# BLOCK 4 — ЮНИТ-ЭКОНОМИКА
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# BLOCK 6 — СТАРТОВЫЙ КАПИТАЛ (CAPEX)
# ═══════════════════════════════════════════════


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


# ═══════════════════════════════════════════════
# BLOCK 9 — РИСКИ НИШИ
# ═══════════════════════════════════════════════


# Constants and filter helpers переехали в services/risk_service.py.
# Здесь только тонкая обёртка для совместимости с импортами engine.


# ═══════════════════════════════════════════════
# BLOCK 5 — P&L ЗА ГОД (Quick Check report, стр. 5)
# Три сценария + ключевые мультипликаторы + доход предпринимателя
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# BLOCK 10 — СЛЕДУЮЩИЕ ШАГИ (Quick Check report, финал)
# План действий / условия / альтернативы по вердикту + CTA upsell
# ═══════════════════════════════════════════════


# ═══════════════════════════════════════════════
# BLOCK 2 — ПАСПОРТ БИЗНЕСА (Quick Check report, стр. 2)
# Спецификация «ZEREK Quick Check — Блок 2» v1.0
# ═══════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════
# YAML overlay для get_format_row (Этап 7 рефакторинга)
#
# Для MANICURE — после xlsx-чтения накладываем YAML значения из
# data/niches/MANICURE_data.yaml. MANICURE_HOME пропускается (xlsx
# калиброван за 7 раундов и в baseline регрессии). Остальные форматы
# (SOLO/STANDARD/PREMIUM) получают YAML-overlay чтобы открыть ранее
# недоступные расчёты (xlsx часто NaN для marketing_med/other_opex_med).
# ═══════════════════════════════════════════════════════════════════════

_original_get_format_row = ZerekDB.get_format_row


def _get_format_row_with_yaml_overlay(self, niche_id: str, sheet: str,
                                       format_id: str, cls: str) -> dict:
    xlsx_row = _original_get_format_row(self, niche_id, sheet, format_id, cls)
    if niche_id != "MANICURE":
        return xlsx_row
    from loaders.niche_loader import overlay_yaml_on_xlsx
    return overlay_yaml_on_xlsx(xlsx_row, niche_id, sheet, format_id, cls)


ZerekDB.get_format_row = _get_format_row_with_yaml_overlay


# ───────────────────────────────────────────────────────────────────────────
# v1.0 spec — formats from 08_niche_formats.xlsx with extended fields
# ───────────────────────────────────────────────────────────────────────────


