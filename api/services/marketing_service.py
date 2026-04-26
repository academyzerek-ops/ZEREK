"""Marketing service — расчёт помесячного маркетинг-плана по архетипной модели.

Формула:
    Бюджет[месяц] = НовыеКлиенты × CAC × ОпытМножитель × (1 - Органика) + Контент

Где:
- НовыеКлиенты[м] = Клиенты[м] × NCS[м] (ncs интерполируется из YAML m1/m6/m12)
- CAC[м] = BASE_CAC × city_multiplier × experience_multiplier
- Органика[м] = walk_in + (sarafan + referrals + content) × рост_со_временем
- Контент = 0 если self_produced, иначе по архетипу (5K..20K)
"""
from __future__ import annotations
import os
import sys
from typing import Any, Dict, List, Optional

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from loaders import marketing_loader  # noqa: E402


# Experience multiplier: новичок тратит в 2× на CAC в первые 3 мес.
# R12.5: добавлен 3-й уровень "experienced" — опытный мастер с базой
# клиентов, CAC ниже среднего за счёт быстрого включения сарафана.
EXPERIENCE_MULTIPLIER = {
    "none":        {"m1_3": 2.0, "m4_6": 1.3, "m7_12": 1.0},
    "some":        {"m1_3": 1.5, "m4_6": 1.1, "m7_12": 1.0},  # legacy alias "has"
    "has":         {"m1_3": 1.5, "m4_6": 1.1, "m7_12": 1.0},
    "middle":      {"m1_3": 1.5, "m4_6": 1.1, "m7_12": 1.0},  # R12.5 = "some"
    "experienced": {"m1_3": 1.2, "m4_6": 1.0, "m7_12": 1.0},  # R12.5: опытный
    "pro":         {"m1_3": 1.2, "m4_6": 1.0, "m7_12": 1.0},  # legacy alias
    "expert":      {"m1_3": 1.2, "m4_6": 1.0, "m7_12": 1.0},
}

# Content cost в месяц если НЕ сам(а) производит контент.
CONTENT_COST_PER_MONTH = {
    "A1": 15000, "A2": 5000, "A3": 10000, "A4": 5000,
    "A5": 5000, "A6": 0, "A7": 3000, "A8": 20000,
    "A9": 3000, "A10": 5000, "A11": 15000, "A12": 10000,
    "A13": 15000, "A14": 10000, "A15": 10000, "A16": 3000,
}


def get_experience_multiplier(experience: str, month: int) -> float:
    exp = EXPERIENCE_MULTIPLIER.get((experience or "").lower(), EXPERIENCE_MULTIPLIER["none"])
    if month <= 3:
        return exp["m1_3"]
    if month <= 6:
        return exp["m4_6"]
    return exp["m7_12"]


def get_ncs_for_month(niche_id: str, month: int) -> float:
    """Доля новых клиентов в потоке — интерполяция между ncs_m1/m6/m12."""
    metrics = marketing_loader.get_retention_metrics(niche_id)
    if not metrics:
        return _fallback_ncs(month)
    ncs_m1 = float(metrics.get("ncs_m1", 90)) / 100
    ncs_m6 = float(metrics.get("ncs_m6", 50)) / 100
    ncs_m12 = float(metrics.get("ncs_m12", 30)) / 100
    if month <= 1:
        return ncs_m1
    if month <= 6:
        ratio = (month - 1) / 5
        return ncs_m1 + (ncs_m6 - ncs_m1) * ratio
    if month <= 12:
        ratio = (month - 6) / 6
        return ncs_m6 + (ncs_m12 - ncs_m6) * ratio
    return ncs_m12


def _fallback_ncs(month: int) -> float:
    defaults = {1: 0.95, 2: 0.90, 3: 0.80, 4: 0.70, 5: 0.60, 6: 0.55,
                7: 0.45, 8: 0.40, 9: 0.35, 10: 0.35, 11: 0.30, 12: 0.30}
    return defaults.get(month, 0.30)


def get_organic_share_for_month(niche_id: str, month: int) -> float:
    """Доля клиентов приходящих бесплатно (walk-in + сарафан + контент + referrals)."""
    channels = marketing_loader.get_channels_allocation(niche_id)
    if not channels:
        return _fallback_organic(month)
    org = channels.get("organic_flow_allocation", {}) or {}
    sarafan = float(org.get("sarafan", 0)) / 100
    walk_in = float(org.get("walk_in", 0)) / 100
    content = float(org.get("content", 0)) / 100
    referrals = float(org.get("referrals", 0)) / 100
    # walk-in работает с м.1; сарафан/referrals/content растут со временем.
    if month <= 2:
        return walk_in + content * 0.3
    if month <= 6:
        r = (month - 2) / 4
        return walk_in + sarafan * (0.2 + 0.5 * r) + referrals * (0.3 + 0.5 * r) + content * (0.3 + 0.6 * r)
    r = min(1.0, (month - 6) / 6 + 0.7)
    return walk_in + (sarafan + referrals + content) * r


def _fallback_organic(month: int) -> float:
    defaults = {1: 0.05, 2: 0.10, 3: 0.15, 4: 0.20, 5: 0.25, 6: 0.30,
                7: 0.35, 8: 0.40, 9: 0.42, 10: 0.45, 11: 0.48, 12: 0.50}
    return defaults.get(month, 0.50)


def compute_marketing_plan(
    niche_id: str,
    city_id: str,
    total_clients_per_month: List[int],
    experience: str = "none",
    content_self_produced: bool = True,
    legal_form: str = "ip",
    format_id: str = "",       # R12 S2: для format-зависимых фаз A1
    strategy: str = "middle",  # R12.5 S2 хвост: conservative / middle / aggressive
    level: str = None,          # R12.5 калибровка: standard/premium/simple/nice
) -> Dict[str, Any]:
    """Помесячный маркетинг-план + архетипный контекст.

    Возвращает dict. При отсутствии ниши в YAML → {"error": ..., "archetype_id": None}.
    """
    niche_data = marketing_loader.get_niche_marketing(niche_id)
    if not niche_data:
        return {
            "error": f"Ниша {niche_id} не найдена в маркетинговой базе",
            "archetype_id": None,
        }

    archetype_id = niche_data.get("archetype")
    archetype_info = marketing_loader.get_archetype(archetype_id) or {}

    base_cac = marketing_loader.get_base_cac(niche_id)
    city_multiplier = marketing_loader.get_city_cac_multiplier(city_id)
    city_cac = base_cac * city_multiplier

    content_cost_base = 0 if content_self_produced else CONTENT_COST_PER_MONTH.get(archetype_id, 5000)

    channels = niche_data.get("channels", {}) or {}
    platform_comm = channels.get("platform_commission_pct", {}) or {}
    platform_rate = (float(platform_comm.get("delivery", 0)) + float(platform_comm.get("marketplace", 0))) / 100

    monthly_plan: List[Dict[str, Any]] = []
    total_year = 0
    clients_list = list(total_clients_per_month or [])
    while len(clients_list) < 12:
        clients_list.append(clients_list[-1] if clients_list else 0)

    for idx in range(12):
        month = idx + 1
        total_clients = int(clients_list[idx] or 0)
        ncs = get_ncs_for_month(niche_id, month)
        organic = get_organic_share_for_month(niche_id, month)
        new_customers = total_clients * ncs
        paid_customers = max(0.0, new_customers * (1 - organic))
        exp_mult = get_experience_multiplier(experience, month)
        real_cac = city_cac * exp_mult
        paid_budget = int(round(paid_customers * real_cac))
        content_cost = content_cost_base
        total_marketing = paid_budget + content_cost
        monthly_plan.append({
            "month": month,
            "total_clients": total_clients,
            "new_customers": int(round(new_customers)),
            "paid_customers": int(round(paid_customers)),
            "organic_share_pct": round(organic * 100, 1),
            "experience_multiplier": round(exp_mult, 2),
            "real_cac": int(round(real_cac)),
            "paid_budget": paid_budget,
            "content_cost": content_cost,
            "total_marketing": total_marketing,
            "platform_commission_rate_pct": round(platform_rate * 100, 1),
        })
        total_year += total_marketing

    # ── R9 K.1 + R12 S2: фазовый override для соло-beauty (A1) ──
    # Канон по R9: для архетипа A1 маркетинг по явным фазам 3+3+6, не
    # через CAC × clients. R12: фазы зависят от формата — у HOME выкуп
    # инфо-поля дороже (нет пешеходного потока), у STUDIO/SALON_RENT/
    # MALL_SOLO бюджеты ниже (есть локация / трафик ТЦ / трафик салона).
    if archetype_id == "A1":
        # R12 §«Маркетинг разгона М1-М3 / М4-М6 / М7-М12». Под текущие
        # xlsx-суффиксы маппим на R12-канон (см. _FORMAT_SUFFIX_TO_R12).
        # Кривая разгона M1/M2/M3 — лёгкая «волна» с пиком в M2.
        PHASE_BUDGETS_BY_R12 = {
            # HOME: «выкупаем инфо-поле» — выше всех (нет проходящего потока)
            "HOME":       {"ramp_curve": [130_000, 175_000, 152_000],
                           "tuning":      54_000,
                           "mature":      16_000},
            # STUDIO: своя локация даёт первый интерес, но нужен мощный старт
            "STUDIO":     {"ramp_curve": [110_000, 150_000, 130_000],
                           "tuning":      50_000,
                           "mature":      18_000},
            # SALON_RENT: часть трафика идёт от салона — бюджет ниже
            "SALON_RENT": {"ramp_curve": [70_000, 95_000, 75_000],
                           "tuning":      35_000,
                           "mature":      12_000},
            # MALL_SOLO: трафик ТЦ — основной канал, бюджет на оформление
            "MALL_SOLO":  {"ramp_curve": [50_000, 75_000, 55_000],
                           "tuning":      30_000,
                           "mature":      15_000},
        }
        _SUFFIX_TO_R12 = {
            "_HOME": "HOME", "_SOLO": "SALON_RENT",
            "_STANDARD": "STUDIO", "_PREMIUM": None,
        }
        fmt_id_up = (format_id or "").upper()
        _r12_key = None
        for sfx, key in _SUFFIX_TO_R12.items():
            if fmt_id_up.endswith(sfx):
                _r12_key = key
                break
        budgets = PHASE_BUDGETS_BY_R12.get(_r12_key) or PHASE_BUDGETS_BY_R12["HOME"]
        ramp_curve = budgets["ramp_curve"]
        tuning_amt = budgets["tuning"]
        mature_amt = budgets["mature"]
        # R12.5 калибровка: per-level фазы из formats_r12 (если YAML
        # содержит marketing_phases_premium / _standard). Премиум-салон
        # сам приводит клиентов — бюджет ниже стандарта (60K ramp vs 80K).
        try:
            from loaders.niche_loader import load_niche_yaml  # noqa: WPS433
            niche_yaml = load_niche_yaml((niche_id or '').upper()) or {}
            for f in niche_yaml.get('formats_r12') or []:
                if f.get('id') != _r12_key:
                    continue
                lvl_key = (level or '').lower() if level else None
                if lvl_key == 'premium' and f.get('marketing_phases_premium'):
                    mp_lvl = f['marketing_phases_premium']
                elif lvl_key == 'standard' and f.get('marketing_phases_standard'):
                    mp_lvl = f['marketing_phases_standard']
                # SALON_RENT auto: experienced+SALON_RENT → premium
                elif (
                    _r12_key == 'SALON_RENT'
                    and (experience or '').lower() in ('experienced', 'pro', 'expert')
                    and f.get('marketing_phases_premium')
                ):
                    mp_lvl = f['marketing_phases_premium']
                elif _r12_key == 'SALON_RENT' and f.get('marketing_phases_standard'):
                    mp_lvl = f['marketing_phases_standard']
                else:
                    mp_lvl = None
                if mp_lvl:
                    base_ramp = int(mp_lvl.get('ramp_m1_m3_base') or 0)
                    if base_ramp > 0:
                        # Лёгкая «волна» с пиком M2 (как в hardcoded
                        # PHASE_BUDGETS_BY_R12 канон).
                        ramp_curve = [
                            int(round(base_ramp * 0.85)),
                            int(round(base_ramp * 1.15)),
                            base_ramp,
                        ]
                    if mp_lvl.get('tuning_m4_m6_base'):
                        tuning_amt = int(mp_lvl['tuning_m4_m6_base'])
                    if mp_lvl.get('mature_m7_m12_base'):
                        mature_amt = int(mp_lvl['mature_m7_m12_base'])
                break
        except Exception:  # noqa: BLE001
            pass
        # R12.5 S2 хвост: budget_multiplier по стратегии из A1 archetype.
        # conservative ×0.20, middle ×1.00, aggressive ×1.40.
        try:
            from loaders.niche_loader import load_archetype_yaml  # noqa: WPS433
            a1 = load_archetype_yaml('A1') or {}
            strats = a1.get('marketing_strategies') or {}
            strat_data = strats.get((strategy or 'middle').lower()) or strats.get('middle') or {}
            budget_mult = float(strat_data.get('budget_multiplier') or 1.0)
        except Exception:  # noqa: BLE001
            budget_mult = 1.0
        for idx in range(12):
            month = idx + 1
            if month <= 3:
                new_marketing = ramp_curve[month - 1]
            elif month <= 6:
                new_marketing = tuning_amt
            else:
                new_marketing = mature_amt
            new_marketing = int(round(new_marketing * budget_mult))
            monthly_plan[idx]["paid_budget"] = new_marketing
            monthly_plan[idx]["total_marketing"] = new_marketing
        total_year = sum(m["total_marketing"] for m in monthly_plan)

    budgets = [m["total_marketing"] for m in monthly_plan]
    summary = {
        "avg_monthly_budget": int(round(total_year / 12)),
        "total_year_budget": total_year,
        "peak_month": budgets.index(max(budgets)) + 1,
        "peak_budget": max(budgets),
        "lowest_month": budgets.index(min(budgets)) + 1,
        "lowest_budget": min(budgets),
    }

    return {
        "archetype_id": archetype_id,
        "archetype_name": archetype_info.get("name_ru", ""),
        "archetype_formula": archetype_info.get("formula_type", ""),
        "archetype_note": archetype_info.get("note_ru", ""),
        "base_cac": base_cac,
        "city_cac_multiplier": city_multiplier,
        "city_cac": int(round(city_cac)),
        "monthly_plan": monthly_plan,
        "summary": summary,
        "retention_metrics": niche_data.get("retention_metrics", {}),
        "choice_drivers": niche_data.get("choice_drivers", {}),
        "channels_allocation": channels,
        "platform_dependency": niche_data.get("platform_dependency"),
        "demand_type": niche_data.get("demand_type"),
        "frequency": niche_data.get("frequency"),
        "decision_cycle": niche_data.get("decision_cycle"),
        "customer_type": niche_data.get("customer_type"),
        "what_not_to_do_ru": _compose_what_not_to_do(channels, archetype_id),
        "content_advice_ru": _compose_content_advice(niche_data, archetype_id, content_self_produced),
    }


def _compose_what_not_to_do(channels: Dict[str, Any], archetype_id: str) -> str:
    paid = (channels or {}).get("paid_budget_allocation", {}) or {}
    not_working: List[str] = []
    if paid.get("gis_paid", 0) <= 5 and archetype_id in {"A1", "A11", "A13"}:
        not_working.append("2GIS (для вашей ниши не работает)")
    if paid.get("google_yandex", 0) <= 5 and archetype_id in {"A1", "A2", "A8", "A15"}:
        not_working.append("Google Ads / Яндекс.Директ (клиенты не ищут в поисковике)")
    if paid.get("olx_krisha", 0) == 0:
        not_working.append("OLX / Krisha (это не ваша площадка)")
    not_working.append("ВКонтакте (в Казахстане не работает)")
    if not_working:
        return "Не тратьте бюджет на: " + ", ".join(not_working) + "."
    return ""


def _compose_content_advice(niche_data: Dict[str, Any], archetype_id: str, self_produced: bool) -> str:
    """R8 I.4: для визуальных ниш не делаем допущение «вы умеете снимать»
    (это никто не спрашивал в анкете). Вместо этого даём два честных
    пути с цифрами: сам или с помощниками. Шаблон видит «\\n\\n» как
    разделитель параграфов и рендерит расширенный блок.
    """
    visual_score = int((niche_data.get("choice_drivers") or {}).get("visual", 0))
    if visual_score >= 4:
        return (
            "Бюджет рассчитан на самостоятельное ведение контента. "
            "Если у вас иначе — адаптируйте.\n\n"
            "<strong>Путь 1 — сам</strong> (для соло-старта). Capcut/Inshot, "
            "таргет в Meta самостоятельно. Весь бюджет идёт на рекламу — "
            "это текущий расчёт. 1-2 часа в день.\n\n"
            "<strong>Путь 2 — с помощниками.</strong> Мобилограф 50-100К/мес, "
            "таргетолог 30-60К/мес или 10-15% от рекламного бюджета. "
            "Закладывайте +80-160К/мес сверх плана; иначе придётся "
            "урезать рекламу — а контент без трафика не работает."
        )
    if archetype_id in {"A4", "A5", "A13"}:
        return (
            "Ваша ниша — про доверие и отзывы. Фокус: собирайте отзывы на 2GIS, "
            "Google Maps, Instagram. Один положительный кейс окупает месяц таргета."
        )
    if archetype_id in {"A6", "A7"}:
        return (
            "Ваша ниша — про локацию и скорость. Фокус: правильный профиль 2GIS "
            "с фото, часами работы, описанием. Контент не критичен."
        )
    return ""
