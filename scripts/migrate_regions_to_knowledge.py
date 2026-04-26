"""scripts/migrate_regions_to_knowledge.py — R12.6 Фаза 2.1.

Собирает данные по 18 каноническим городам из:
  · config/constants.yaml          → check_coef, legacy_ids, name_rus, region_rus, type, avg_salary_2025, grant_bp_avg_wage
  · data/kz/01_cities.xlsx         → демография (население, муж/жен, возрастные группы, прирост)
  · knowledge/taxes/KZ_2026.md     → tax_rate_ud_pct (через ud_rates_by_city)

Пишет 18 файлов в knowledge/regions/{id}.md в формате R12.6
(YAML frontmatter + текстовое тело).

Запуск:
    python3 scripts/migrate_regions_to_knowledge.py

Идемпотентен — перезапускать безопасно.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import openpyxl
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_REGIONS = REPO_ROOT / "knowledge" / "regions"
CONSTANTS_YAML = REPO_ROOT / "config" / "constants.yaml"
CITIES_XLSX = REPO_ROOT / "data" / "kz" / "01_cities.xlsx"
TAXES_MD = REPO_ROOT / "knowledge" / "taxes" / "KZ_2026.md"


def load_constants():
    with open(CONSTANTS_YAML, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_cities_demography():
    """01_cities.xlsx → {city_id: {total, men, women, ...}}"""
    wb = openpyxl.load_workbook(CITIES_XLSX, data_only=True)
    ws = wb["Города"]
    out = {}
    headers = None
    for i, row in enumerate(ws.iter_rows(values_only=True)):
        if i == 4:
            headers = list(row)
            continue
        if i < 5:
            continue
        if not row[0]:
            continue
        city_id = str(row[0]).strip().lower()
        out[city_id] = {
            "total":              int(row[4]) if row[4] else 0,
            "men":                int(row[5]) if row[5] else 0,
            "women":               int(row[6]) if row[6] else 0,
            "children_0_15":      int(row[8]) if row[8] else 0,
            "working_age_16_62":   int(row[9]) if row[9] else 0,
            "pensioners_63_plus":  int(row[10]) if row[10] else 0,
            "growth_yoy_pct":      float(row[13]) if row[13] is not None else 0.0,
        }
    return out


def load_ud_rates():
    """Извлекает ud_rates_by_city из knowledge/taxes/KZ_2026.md."""
    text = TAXES_MD.read_text(encoding="utf-8")
    # Простой парсер frontmatter (между двух --- )
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    frontmatter = yaml.safe_load(parts[1])
    return (frontmatter or {}).get("ud_rates_by_city") or {}


CITY_DESCRIPTIONS = {
    "astana":      "Столица КЗ. Высокая платёжеспособность, активный рынок beauty/HoReCa, премиум-сегмент в каждой нише.",
    "almaty":      "Экономический центр и культурная столица. Самый зрелый рынок премиум-услуг, высокая конкуренция.",
    "shymkent":    "3-й мегаполис, патриархальный южный город с быстрым ростом среднего класса. Цены ниже Астаны/Алматы на 5-10%.",
    "aktobe":      "Промышленный регион (нефтегаз+металлургия). Высокая концентрация ИТР с устойчивым доходом.",
    "atyrau":      "Нефтегазовая столица. Самые высокие зарплаты в стране (после Мангистау), специфический рынок.",
    "aktau":       "Прикаспийский нефтегазовый город. Рынок узкий, но платёжеспособный.",
    "karaganda":   "Промышленный центр с зрелой инфраструктурой. Стабильный, без резких всплесков.",
    "pavlodar":    "Промышленный регион (Аксу, ЕЭК). Зарплаты выше среднего, рынок умеренный.",
    "kostanay":    "Аграрно-промышленный регион. Чек ниже мегаполисов на 3-5%.",
    "semey":       "Региональный центр Абай. Зарплаты ниже среднего, чек -5%.",
    "oskemen":     "Усть-Каменогорск (ВКО) — горно-металлургический. Рынок зрелый, средний.",
    "uralsk":      "ЗКО — нефтегазовый, но менее зажиточный чем Атырау. Стабильно.",
    "taraz":       "Жамбылская область. Умеренная зарплата, сильная региональная специфика.",
    "turkestan":   "Туркестанская область — самая молодая столица в КЗ. Низкие зарплаты, маленький рынок.",
    "petropavl":   "Петропавловск (СКО) — пограничный с Россией. Зарплаты ниже среднего.",
    "kokshetau":   "Акмолинская область. Близко к Астане, рынок маленький.",
    "kyzylorda":   "Кызылординская область. Аграрный, низкие зарплаты, маленький city.",
    "taldykorgan": "Жетісу (бывшая Алматинская обл.). Региональный центр после переезда столицы области.",
}


def render_region_md(city: dict, demo: dict, ud_rate: int, salary: int) -> str:
    """Сборка markdown файла из dict."""
    cid = city["id"]
    desc = CITY_DESCRIPTIONS.get(cid, "Региональный центр КЗ.")

    legacy_ids = city.get("legacy_ids") or []
    legacy_ids_yaml = ", ".join(legacy_ids) if legacy_ids else ""

    fm_lines = [
        "---",
        f"id: {cid}",
        f"name_rus: {city['name_rus']}",
        f"region_rus: \"{city['region_rus']}\"",
        f"type: {city['type']}",
    ]
    if legacy_ids:
        fm_lines.append(f"legacy_ids: [{legacy_ids_yaml}]")
    fm_lines.append("")
    fm_lines.append("population:")
    fm_lines.append(f"  total: {demo.get('total', 0)}")
    fm_lines.append(f"  men: {demo.get('men', 0)}")
    fm_lines.append(f"  women: {demo.get('women', 0)}")
    fm_lines.append(f"  children_0_15: {demo.get('children_0_15', 0)}")
    fm_lines.append(f"  working_age_16_62: {demo.get('working_age_16_62', 0)}")
    fm_lines.append(f"  pensioners_63_plus: {demo.get('pensioners_63_plus', 0)}")
    fm_lines.append(f"  growth_yoy_pct: {demo.get('growth_yoy_pct', 0.0)}")
    fm_lines.append("")
    fm_lines.append(f"avg_salary_2025: {salary}    # ₸/мес, БНС РК Q4 2025")
    fm_lines.append(f"check_coef: {city['check_coef']}")
    fm_lines.append(f"tax_rate_ud_pct: {ud_rate}")
    if city.get("grant_bp_avg_wage"):
        fm_lines.append(f"grant_bp_avg_wage: {city['grant_bp_avg_wage']}")
    fm_lines.append("")
    fm_lines.append("history:")
    fm_lines.append("  - date: 2026-04-26")
    fm_lines.append(f"    change: создан файл из 01_cities.xlsx + 02_wages_by_city.xlsx + constants.yaml")
    fm_lines.append("    by: Кот")
    fm_lines.append("---")
    fm_lines.append("")
    body = [
        f"# {city['name_rus']}",
        "",
        "## О городе",
        "",
        desc,
        "",
        "## Экономика",
        "",
        f"- Среднемесячная номинальная ЗП (Q4 2025): **{salary:,} ₸**".replace(",", " "),
        f"- Тип города: {city['type']}",
        f"- Ценовой коэффициент к Астане (база 1.00): **×{city['check_coef']}**",
        f"- Ставка УД (УСН): **{ud_rate}%**",
        "",
        "## Замечания",
        "",
        "(Заполняется со временем по мере наблюдений Адиля)",
        "",
    ]
    return "\n".join(fm_lines + body)


def main():
    constants = load_constants()
    demography = load_cities_demography()
    ud_rates = load_ud_rates()
    salaries = constants.get("avg_salary_2025") or {}
    grant_wages = constants.get("grant_bp_avg_wage") or {}

    KNOWLEDGE_REGIONS.mkdir(parents=True, exist_ok=True)

    written = []
    for city in constants.get("cities") or []:
        cid = city["id"]
        # Обогащаем grant_bp_avg_wage из отдельной секции
        if cid in grant_wages:
            city["grant_bp_avg_wage"] = grant_wages[cid]
        salary = salaries.get(cid) or salaries.get("_default") or 473158
        demo = demography.get(cid, {})
        ud_rate = ud_rates.get(cid, 3)
        md = render_region_md(city, demo, ud_rate, salary)
        out_path = KNOWLEDGE_REGIONS / f"{cid}.md"
        out_path.write_text(md, encoding="utf-8")
        written.append(cid)

    print(f"Wrote {len(written)} region files to {KNOWLEDGE_REGIONS}:")
    for cid in written:
        print(f"  · {cid}.md")


if __name__ == "__main__":
    main()
