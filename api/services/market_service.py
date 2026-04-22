"""api/services/market_service.py — Block 3: рынок и конкуренты.

Согласно спеке: насыщенность рынка, платёжеспособность, список конкурентов.
Для HOME-форматов — упрощённая «note» (конкуренты в Instagram, не в 2GIS).

Извлечено из engine.py в Этапе 3 рефакторинга.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    BENCHMARK_RETAIL_DENSITY_10K,
    _safe_float,
    _safe_int,
)
from loaders.city_loader import get_city_check_coef  # noqa: E402

_log = logging.getLogger("zerek.market_service")


def compute_block3_market(result):
    """Block 3 — рынок и конкуренты. HOME-форматы получают заметку."""
    inp = result.get("input", {}) or {}
    risks = result.get("risks", {}) or {}
    comp = risks.get("competitors") or {}

    # HOME-форматы: 2GIS и агрегаторы не отражают реального рынка мастеров
    # на дому (точки не публичные). Показываем ориентир, а не нули.
    format_id_up = (inp.get("format_id") or "").upper()
    if format_id_up.endswith("_HOME"):
        return {
            "type": "home_market_note",
            "message": ("Для мастера на дому конкуренция формируется в "
                        "Instagram и TikTok. 2GIS и агрегаторы не отражают "
                        "реального рынка домашних мастеров. Ищите конкурентов "
                        "через хэштеги Instagram по вашему городу и району."),
        }

    competitors_count = _safe_int(comp.get("competitors_count")) or _safe_int(comp.get("n")) or 0
    city_name = inp.get("city_name", "") or inp.get("city_id", "")
    city_pop = _safe_int(inp.get("city_population"), 0)

    # Приоритет — готовый density_per_10k из xlsx (через get_competitors).
    # Фолбэк — пересчёт competitors_count / (population / 10000).
    density_raw = _safe_float(comp.get("density_per_10k"), 0.0)
    if density_raw > 0:
        density = density_raw
    else:
        density = (competitors_count / (city_pop / 10000)) if city_pop else 0
    benchmark_density = BENCHMARK_RETAIL_DENSITY_10K
    saturation_pct = (density / benchmark_density * 100) if benchmark_density else 0

    if saturation_pct <= 60:
        sat_color = "green"
        sat_text = "Рынок недонасыщен — есть пространство для входа даже без сильного УТП"
    elif saturation_pct <= 110:
        sat_color = "yellow"
        sat_text = "Рынок умеренно насыщен — есть пространство для входа при сильном УТП"
    elif saturation_pct <= 150:
        sat_color = "orange"
        sat_text = "Рынок насыщен — для успеха нужен чёткий отличительный фактор (локация, сервис, цена)"
    else:
        sat_color = "red"
        sat_text = "Рынок перенасыщен — высокий риск долгой окупаемости из-за конкуренции"

    city_coef = get_city_check_coef(inp.get("city_id", "")) or 1.0
    affordability_index = city_coef
    if affordability_index >= 1.15:
        afford_text = f"Платёжеспособность на {int((affordability_index-1)*100)}% выше средней по РК — можно закладывать премиум-чек"
    elif affordability_index >= 1.0:
        afford_text = "Платёжеспособность на уровне средней по РК — стандартные цены рынка работают хорошо"
    elif affordability_index >= 0.85:
        afford_text = f"Платёжеспособность на {int((1-affordability_index)*100)}% ниже средней по РК — учтите при ценообразовании"
    else:
        afford_text = f"Платёжеспособность на {int((1-affordability_index)*100)}% ниже средней по РК — премиум-форматы рискованны"

    competitors_list = []
    if isinstance(comp.get("top"), list):
        for c in comp["top"][:5]:
            competitors_list.append({
                "name": c.get("name") or c.get("title") or "—",
                "rating": c.get("rating"),
                "reviews": c.get("reviews") or c.get("reviews_count"),
                "district": c.get("district") or "",
            })

    return {
        "city": city_name,
        "saturation": {
            "competitors_count": competitors_count,
            "density_city": round(density, 2),
            "density_benchmark": benchmark_density,
            "pct_of_benchmark": int(saturation_pct),
            "color": sat_color,
            "text_rus": sat_text,
        },
        "competitors_list": competitors_list,
        "affordability": {
            "city_coef": round(affordability_index, 2),
            "text_rus": afford_text,
        },
    }
