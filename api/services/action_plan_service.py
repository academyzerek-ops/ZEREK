"""api/services/action_plan_service.py — Block 10: план действий.

Адаптивный план по цвету вердикта (green/yellow/red):
- green: 4-6 недельных блоков чек-листа (с обучением для experience=none)
- yellow: 3 условия перехода в зелёную зону
- red: 3 категории альтернатив (формат / город / роль)
- + апсейл на FinModel/BizPlan
- + финальное напутствие

Извлечено из engine.py в Этапе 3 рефакторинга.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import _safe_int  # noqa: E402
from loaders.niche_loader import _formats_from_fallback_xlsx  # noqa: E402
from renderers.quick_check_renderer import _fmt_kzt  # noqa: E402

_log = logging.getLogger("zerek.action_plan_service")


def _green_action_plan(block2, block1, adaptive=None, result=None):
    """4-6 недельных блоков чек-листа для Green-вердикта.

    Если experience=none и training_required=True (бьюти) — добавляется
    «Неделя 1-4: Обучение и практика» в начало.
    """
    fin = (block2 or {}).get("finance", {})
    capex = fin.get("capex_needed") or 0
    capex_equipment = int(capex * 0.40)
    capex_inventory = int(capex * 0.15)
    capex_rent_setup = int(capex * 0.22)
    format_type = (block2 or {}).get("format_type", "")
    is_solo = (block2 or {}).get("is_solo", False)
    staff_total = ((block2 or {}).get("staff_after_entrepreneur") or {}).get("total", 0)

    plan = [
        {
            "week_range": "1-2",
            "title": "Юридический старт",
            "actions": [
                "Открыть ИП (Самозанятый / УСН 3%)",
                "Открыть банковский счёт",
                ("Проверить договор аренды (3+ лет, фиксированная индексация)"
                 if format_type in ("STANDARD", "KIOSK") else "Подготовить договора с клиентами / поставщиками"),
            ]
        },
    ]
    niche_id = ((result or {}).get("input") or {}).get("niche_id", "")
    equip_hint_by_niche = {
        "MANICURE": "минимальный набор: лампа UV/LED, фрезер, стерилизатор, стол",
        "BARBER":   "минимальный набор: кресло, машинка, ножницы, стерилизатор, зеркало",
        "BROW":     "минимальный набор: кушетка, лампа с лупой, кисти, пигменты, стерилизатор",
        "LASH":     "минимальный набор: кушетка, лампа, пинцеты, клей, материалы, стерилизатор",
        "SUGARING": "минимальный набор: кушетка, подогреватель пасты, материалы, стерилизатор",
    }
    equip_hint = equip_hint_by_niche.get(niche_id)
    if equip_hint:
        equip_action = (
            f"Закупить оборудование ({equip_hint}. Бюджет ≈ {_fmt_kzt(capex_equipment)}. "
            f"Для профессионального качества может понадобиться больше.)"
        )
    else:
        equip_action = f"Закупить оборудование (бюджет ≈ {_fmt_kzt(capex_equipment)})"
    plan.append({
        "week_range": "3-4",
        "title": "Закупка оборудования и материалов",
        "actions": [
            equip_action,
            f"Первичные закупки материалов (≈ {_fmt_kzt(capex_inventory)})",
        ],
    })
    if format_type not in ("HOME", "SOLO"):
        actions_prep = [f"Ремонт и обустройство (≈ {_fmt_kzt(capex_rent_setup)})", "Вывеска, брендинг, 2GIS-регистрация"]
        if staff_total > 0:
            staff_rus = []
            for s in ((block2 or {}).get("staff_after_entrepreneur", {}).get("masters", []) or []):
                staff_rus.append(f"{s.get('count', 0)} {s.get('role', '')}")
            for s in ((block2 or {}).get("staff_after_entrepreneur", {}).get("assistants", []) or []):
                staff_rus.append(f"{s.get('count', 0)} {s.get('role', '')}")
            if staff_rus:
                actions_prep.append("Найм сотрудников: " + ", ".join(staff_rus))
        plan.append({"week_range": "5-6", "title": "Подготовка помещения и команды", "actions": actions_prep})
    else:
        plan.append({
            "week_range": "5-6", "title": "Подготовка рабочего места",
            "actions": ["Обустройство рабочего места", "Страховка инструментов"],
        })

    plan.append({
        "week_range": "7-8",
        "title": "Запуск маркетинга ДО открытия",
        "actions": [
            "Таргетированная реклама (Instagram / TikTok)",
            "Договорённости с блогерами города",
            "Приём предзаписей",
        ],
    })

    reviews_action = (
        "Отзывы в Instagram + Google Maps (если есть геолокация) — просить клиентов с 1-го дня"
        if format_type in ("HOME", "SOLO", "MOBILE")
        else "Отзывы в 2GIS — просить клиентов с 1-го дня"
    )
    plan.append({
        "week_range": "Запуск",
        "title": "Первые недели работы",
        "actions": [
            ("Следить за загрузкой мастеров еженедельно"
             if format_type not in ("HOME", "SOLO", "MOBILE") else "Отслеживать конверсию заявок в сделки"),
            reviews_action,
            "Еженедельный контроль unit-экономики (выручка/чек/COGS)",
        ],
    })

    # Новичок в бьюти-нише: обучение 4 недели в начале, остальные сдвигаются.
    training_required = bool(((result or {}).get("input") or {}).get("training_required"))
    experience = ((adaptive or {}).get("experience") or "").lower()
    if training_required and experience == "none":
        shift = 4
        for block in plan:
            wr = block.get("week_range", "")
            if wr == "Запуск":
                block["week_range"] = f"{shift+9}-{shift+10}"
            elif "-" in wr:
                a, b = wr.split("-")
                try:
                    block["week_range"] = f"{int(a)+shift}-{int(b)+shift}"
                except ValueError:
                    pass
        plan.insert(0, {
            "week_range": "1-4",
            "title": "Обучение и практика",
            "actions": [
                "Выбрать школу / курсы по нише",
                "Пройти базовый курс (для маникюра — гель-лак + укрепление)",
                "Практика на моделях (бесплатно / со скидкой)",
                "Собрать первичное портфолио для Instagram",
            ],
        })

    return plan


def _yellow_conditions(block1, block2):
    """3 условия перехода в зелёную зону — из top-3 слабых параметров."""
    weak = (((block1 or {}).get("scoring") or {}).get("weakest") or [])[:3]
    fin = (block2 or {}).get("finance", {})
    conditions = []
    for w in weak:
        label = w.get("label", "")
        if label == "Капитал vs ориентир":
            gap = -(fin.get("capital_diff") or 0)
            if gap <= 0:
                conditions.append({
                    "title": "Резервный фонд: обеспечить запас оборотки",
                    "options": ["Заложить 3-6 мес расходов как резерв", "Не вкладывать весь капитал в стартовые вложения", "Иметь отдельный счёт для резерва"],
                })
            else:
                monthly_credit = int(gap * 0.035)
                conditions.append({
                    "title": f"Найти дополнительные {_fmt_kzt(gap)} капитала",
                    "options": [
                        "Партнёр с долей 15-20%",
                        f"Кредит в банке (платёж ~{_fmt_kzt(monthly_credit)}/мес на 36 мес)",
                        "Грант Astana Hub / Bastau Business",
                    ],
                })
        elif label == "Точка безубыточности":
            months = w.get("months") or 12
            reserve = int(((fin.get("capex_needed") or 0) * 0.12) * max(months, 6))
            if reserve < 1_000_000:
                reserve = 1_000_000
            conditions.append({
                "title": f"Обеспечить запас кассы на первые {months} мес",
                "options": [f"Резерв оборотки ≈ {_fmt_kzt(reserve)}", "Не брать целиком кредит \"в дело\"", "Иметь 3-6 мес зарплаты на свою семью"],
            })
        elif label == "Маркетинговый бюджет":
            conditions.append({
                "title": "Увеличить маркетинговый бюджет на старте",
                "options": ["Заложить минимум 200-500 тыс ₸ в первые 3 месяца", "Таргет + локальный офлайн-маркетинг", "Не экономить на SMM и отзывах"],
            })
        elif label == "Насыщенность рынка":
            conditions.append({
                "title": "Разработать сильное УТП перед запуском",
                "options": ["Выделить 2-3 отличия от конкурентов", "Проработать цена-качество через сегмент", "Определить «нелёгкую» аудиторию для вас"],
            })
        elif label == "Опыт предпринимателя":
            conditions.append({
                "title": "Компенсировать отсутствие опыта",
                "options": ["Найти ментора или партнёра с опытом 3+ лет в нише", "Начать с SOLO-формата до освоения", "Пройти курс ZEREK Academy (Архитектор)"],
            })
        elif label == "Соответствие формата городу":
            conditions.append({
                "title": "Пересмотреть класс формата под город",
                "options": ["Рассмотреть стандарт-формат вместо премиума", "Проверить платёжеспособность ЦА", "Проанализировать успешных конкурентов в регионе"],
            })
        else:
            conditions.append({
                "title": w.get("note", label),
                "options": [w.get("note", "Требуется внимание")],
            })
    return conditions[:3]


def _red_alternatives(block1, block2, result, db):
    """3 категории альтернатив — формат / город / роль.

    db нужен для _formats_from_fallback_xlsx (список форматов ниши).
    """
    inp = result.get("input", {}) or {}
    niche_id = inp.get("niche_id", "")
    format_id = inp.get("format_id", "")
    city_name = inp.get("city_name", "") or "—"
    format_name = (block2 or {}).get("format_name_rus", format_id)

    alt_formats = []
    all_formats = _formats_from_fallback_xlsx(db, niche_id)
    current_capex = 0
    for f in all_formats:
        if f.get("format_id") == format_id:
            current_capex = _safe_int(f.get("capex_standard"), 0)
            break
    for f in all_formats:
        if f.get("format_id") == format_id:
            continue
        cx = _safe_int(f.get("capex_standard"), 0)
        if cx < current_capex:
            alt_formats.append(f"{f.get('format_name')} (~{_fmt_kzt(cx)})")
        if len(alt_formats) >= 2:
            break

    return [
        {
            "category": "ФОРМАТ",
            "title": f"Формат {format_name} слишком тяжёл для текущих параметров",
            "options": alt_formats if alt_formats else ["Рассмотрите формат уровнем ниже (эконом вместо стандарта)"],
        },
        {
            "category": "ГОРОД",
            "title": "Смена города",
            "options": [
                f"Текущий город — {city_name}. Премиум-форматы работают в Алматы, Астане, Шымкенте",
                "Пересчитайте для города с большей платёжеспособной аудиторией",
            ],
        },
        {
            "category": "РОЛЬ",
            "title": "Измените роль предпринимателя",
            "options": [
                "Закройте собой хотя бы одну ставку — снизит ФОТ",
                "Для бьюти-формата: работайте мастером, не только управляйте",
                "Для магазина: закройте роль кассира или менеджера закупок",
            ],
        },
    ]


def _upsell_block(color, block1, block2):
    """Апсейл на FinModel/BizPlan, текст зависит от вердикта."""
    fm_pct = 60
    bp_pct = 45
    texts = {
        "green":  "Персональный прогноз на 3 года с денежным потоком, налогами, графиком кредита.",
        "yellow": "Финмодель поможет точно посчитать сколько нужно партнёру и как распределить дефицит.",
        "red":    "Финмодель объяснит почему не окупается и даст 2-3 альтернативных сценария.",
    }
    return {
        "finmodel": {
            "name_rus": "Финансовая модель",
            "price_kzt": 9000,
            "description_rus": texts.get(color, texts["green"]),
            "prefilled_pct": fm_pct,
        },
        "bizplan": {
            "name_rus": "Бизнес-план",
            "price_kzt": 15000,
            "description_rus": "Готовый документ для банка, гранта или инвестора. Персонализирован под цель.",
            "prefilled_pct": bp_pct,
        },
    }


def _final_farewell(color, block2):
    """Финальное напутствие, шаблонное (AI версия позже)."""
    niche = (block2 or {}).get("niche_name_rus", "бизнес")
    if color == "green":
        return (f"Ваш {niche.lower()} имеет хорошие шансы окупиться в заявленные сроки. "
                "Главное сейчас — не расслабляться на этапе подготовки и сразу выстраивать сильный маркетинг. "
                "Удачи с запуском — возвращайтесь за финмоделью когда будете готовы проработать детали.")
    if color == "yellow":
        return ("Ваша идея в зоне перехода — если закроете упомянутые условия, бизнес окупится. "
                "Без этих условий — риск большой. Подумайте неделю, пересчитайте варианты — и возвращайтесь.")
    return ("В текущей конфигурации идея рискованна, но это не значит отказаться от ниши. "
            "Смените формат или город — цифры могут заработать. ZEREK поможет пересчитать любой вариант.")


def compute_block10_next_steps(db, result, adaptive, block1=None, block2=None):
    """Block 10 — план действий / условия / альтернативы + апсейл + напутствие."""
    color = (block1 or {}).get("color", "yellow")

    inp = (result or {}).get("input", {}) or {}
    city_rus = inp.get("city_name") or ""
    city_prefix = f"в {city_rus} " if city_rus else ""
    format_label = inp.get("format_name") or ""
    format_phrase = f"в формате «{format_label}»" if format_label else ""

    out = {
        "color": color,
        "farewell_rus": _final_farewell(color, block2),
        "upsell": _upsell_block(color, block1, block2),
    }

    if color == "green":
        out["action_plan"] = _green_action_plan(block2, block1, adaptive=adaptive, result=result)
        out["headline_rus"] = (
            f"✅ Это направление реалистично для заработка {city_prefix}{format_phrase}. "
            f"Можно пробовать."
        ).replace("  ", " ").strip()
        out["cta_buttons"] = [
            {"label_rus": "Купить Финансовую модель — 9 000 ₸", "action": "buy_finmodel"},
            {"label_rus": "Скачать PDF отчёта", "action": "download_pdf"},
        ]
    elif color == "yellow":
        out["conditions"] = _yellow_conditions(block1, block2)
        out["headline_rus"] = (
            "⚠️ Это направление возможно, но с оговорками. Обратите внимание "
            "на пункты выше перед стартом."
        )
        out["cta_buttons"] = [
            {"label_rus": "Пересмотреть параметры", "action": "restart_survey"},
            {"label_rus": "Купить Финмодель — 9 000 ₸", "action": "buy_finmodel"},
        ]
    else:  # red
        out["alternatives"] = _red_alternatives(block1, block2, result, db)
        out["headline_rus"] = (
            f"🚨 В этом формате{(' и регионе ' + city_rus) if city_rus else ''} "
            f"направление даст убыток по базовому сценарию. Пересмотрите параметры или формат."
        ).replace("  ", " ").strip()
        out["cta_buttons"] = [
            {"label_rus": "Пересчитать с другим форматом", "action": "change_format"},
            {"label_rus": "Пересчитать с другим городом", "action": "change_city"},
            {"label_rus": "Подробный анализ провала (9 000 ₸)", "action": "buy_finmodel"},
        ]

    return out
