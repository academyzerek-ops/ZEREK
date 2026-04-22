"""api/config.py — Общие константы и справочники.

Создан в Этапе 8.6 рефакторинга для централизации констант,
которые ранее дублировались в engine.py и renderer (OQ-R).

Сейчас содержит:
- LOCATION_TYPES_META — справочник типов локации для UI Mini App
  (был в engine.py + renderers/quick_check_renderer.py)

В будущем сюда переедут (по мере накопления):
- MRP_2026, NDS_RATE, MZP_2026 (сейчас в engine.py)
- DEFAULTS, SCENARIO_*, BLOCK1_THRESHOLDS, SCORING_* (сейчас в engine.py)
- TRAINING_COSTS_BY_EXPERIENCE
- CAPEX_BREAKDOWN_LABELS_RUS
"""


# Типы локаций бизнеса для рендера в анкете v2 (Quick Check).
# Используется: niche_loader (фильтрация в get_niche_config),
# renderer (compute_block2_passport.location_rus).
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
