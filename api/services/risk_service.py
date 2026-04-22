"""api/services/risk_service.py — Block 9: топ-5 рисков ниши.

Источники:
- knowledge/kz/niches/{NICHE}_insight.md (через content_loader)
- generic_risks по архетипу A–F (fallback)
- HOME_SPECIFIC_RISKS (физсостояние, потолок мастера, санитария)

Фильтрация по формату: для HOME исключаются риски про аренду/найм/договор
(не релевантны мастеру на дому).

Извлечено из engine.py в Этапе 3 рефакторинга.
TODO (Этап 7): подключить YAML-источник рисков (data/niches/*.yaml.risks).
"""
import logging
import os
import re
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from loaders.content_loader import load_insight_md  # noqa: E402
from loaders.niche_loader import _archetype_of  # noqa: E402

_log = logging.getLogger("zerek.risk_service")


# ═══════════════════════════════════════════════════════════════════════
# Конфиги фильтров и HOME-specific
# ═══════════════════════════════════════════════════════════════════════

FORMAT_RISK_FILTERS = {
    "MANICURE_HOME": {"exclude_keywords": ["аренд", "помещен", "найм", "договор", "уход мастер", "наём"]},
    "BARBER_HOME":   {"exclude_keywords": ["аренд", "помещен", "найм", "договор", "уход мастер", "наём"]},
    "BROW_HOME":     {"exclude_keywords": ["аренд", "помещен", "найм", "договор", "наём"]},
    "LASH_HOME":     {"exclude_keywords": ["аренд", "помещен", "найм", "договор", "наём"]},
    "SUGARING_HOME": {"exclude_keywords": ["аренд", "помещен", "найм", "договор", "наём"]},
}

HOME_SPECIFIC_RISKS = [
    {"title": "Зависимость от физсостояния", "probability": "СРЕДНЯЯ", "impact": "ВЫСОКОЕ",
     "text": "Болезнь, беременность, травма рук = ноль дохода. Подушка безопасности на 3 мес — must have.",
     "mitigation": "Отложить 3 мес расходов на подушку. Страхование от нетрудоспособности."},
    {"title": "Потолок дохода одного мастера", "probability": "ВЫСОКАЯ", "impact": "СРЕДНЕЕ",
     "text": "Максимум 5-7 клиенток в день физически. Чтобы расти дальше — поднимайте средний чек (дизайн, укрепление, уход) или планируйте переезд в свою студию через 1-2 года.",
     "mitigation": "Апсейл (укрепление, дизайн, уход за кожей рук). План перехода в свою студию через 1-2 года — это даст возможность работать с мастерами и больше клиентов."},
    {"title": "Санитарные нормы без контроля", "probability": "СРЕДНЯЯ", "impact": "ВЫСОКОЕ",
     "text": "Дома проще забить на стерилизацию. Один случай грибка/инфекции — репутация уничтожена.",
     "mitigation": "Автоклав / сухожар. Инструменты одноразовые где можно. Фото стерилизации в сторис."},
]

# Generic риски по архетипу (fallback если insight.md не нашёлся)
GENERIC_RISKS_BY_ARCHETYPE = {
    "A": [
        {"title": "Уход мастера с клиентской базой", "probability": "ВЫСОКАЯ", "impact": "КРИТИЧНОЕ",
         "text": "В нишах услуг клиенты привязаны к мастеру. Уход мастера может забрать 40-60% его клиентов.",
         "mitigation": "Программа удержания мастеров. CRM салона, не личная. Минимум 2 мастера на 1 позицию."},
        {"title": "Открытие конкурента в радиусе 300м", "probability": "СРЕДНЯЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Бьюти-ниши стадно растут. Новый конкурент в районе может забрать 20-30% трафика.",
         "mitigation": "Долгосрочный договор аренды. Программа лояльности. Работа с соцсетями."},
        {"title": "Сезонная просадка янв-фев", "probability": "ВЫСОКАЯ", "impact": "ТЕРПИМОЕ",
         "text": "После новогодних расходов спрос падает. Просадка до −25%.",
         "mitigation": "Запас оборотки на 2 мес. Сезонные акции и пакеты."},
        {"title": "Проблемы с аксессуарами / расходниками", "probability": "СРЕДНЯЯ", "impact": "ТЕРПИМОЕ",
         "text": "Курс, логистика, импорт — срывы поставок материалов.",
         "mitigation": "Запас расходников на 2 мес. 2-3 поставщика вместо одного."},
        {"title": "Регулирование (СЭС, лицензии)", "probability": "НИЗКАЯ", "impact": "КРИТИЧНОЕ",
         "text": "Проверки СЭС, претензии по документам, особенно для мед.ниш.",
         "mitigation": "Проверить все разрешения ДО открытия. Договор с юристом."},
    ],
    "B": [
        {"title": "Скачок food cost", "probability": "ВЫСОКАЯ", "impact": "КРИТИЧНОЕ",
         "text": "Продукты дорожают неравномерно. Food cost может вырасти с 30% до 40% без предупреждения.",
         "mitigation": "Контракты с поставщиками. Регулярный пересмотр меню."},
        {"title": "Уход шеф-повара / бариста", "probability": "СРЕДНЯЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Ключевой повар уходит — качество падает, клиенты замечают.",
         "mitigation": "Документированные рецепты. Сменность. Не один ключевой человек."},
        {"title": "Зависимость от агрегаторов", "probability": "ВЫСОКАЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Комиссии 20-30%. Агрегатор может поменять условия.",
         "mitigation": "Развивать собственный канал (соцсети, сайт, колл-центр)."},
        {"title": "СЭС / отзывы о санитарии", "probability": "СРЕДНЯЯ", "impact": "КРИТИЧНОЕ",
         "text": "Одна жалоба в 2ГИС о «тухлой еде» режет трафик надолго.",
         "mitigation": "Строгие стандарты. Регулярный аудит. Быстрая работа с негативом."},
        {"title": "Сезонная просадка / курортность", "probability": "СРЕДНЯЯ", "impact": "ТЕРПИМОЕ",
         "text": "Летом — свадьбы, зимой — корпоративы; в другие месяцы провалы 20%.",
         "mitigation": "Планировать запас. Промо в провальные месяцы."},
    ],
    "C": [
        {"title": "Порча и списания товара", "probability": "ВЫСОКАЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Для скоропорта — 3-10% потерь. Для непродовольственного — до 5% на бой/порчу.",
         "mitigation": "Ротация запасов FIFO. Скидки на товар к истечению срока."},
        {"title": "Заморозка оборотного капитала", "probability": "ВЫСОКАЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Товар лежит — деньги не работают. Плохо оборачивающиеся позиции — яд.",
         "mitigation": "ABC-анализ. Сокращать ассортимент непопулярных позиций."},
        {"title": "Сезонные пики (цветы, новый год)", "probability": "СРЕДНЯЯ", "impact": "ТЕРПИМОЕ",
         "text": "В пиковые даты — дефицит товара, в межсезонье — излишки.",
         "mitigation": "Планирование закупок за 2 мес. Предзаказы."},
    ],
    "D": [
        {"title": "Высокий churn (отток)", "probability": "ВЫСОКАЯ", "impact": "КРИТИЧНОЕ",
         "text": "В абонементных нишах отток 5-15% в месяц — норма, но может взлететь.",
         "mitigation": "Удержание: программы лояльности. CRM. Работа с неактивными."},
        {"title": "Рост CAC (стоимости привлечения)", "probability": "СРЕДНЯЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Реклама дорожает, конкуренция растёт — CAC может удвоиться за год.",
         "mitigation": "Развивать органику. Сарафан, реферальные программы."},
        {"title": "Зависимость от единичных тренеров / преподавателей", "probability": "СРЕДНЯЯ", "impact": "КРИТИЧНОЕ",
         "text": "Сильный тренер забирает группу к себе — катастрофа для студии.",
         "mitigation": "Множественные тренеры в каждом направлении. Командная культура."},
    ],
    "E": [
        {"title": "Кассовый разрыв на проектах", "probability": "ВЫСОКАЯ", "impact": "КРИТИЧНОЕ",
         "text": "Клиент платит в конце, а вам платить сегодня. Риск разрыва.",
         "mitigation": "Предоплаты 30-50%. Запас оборотки. Договора с чётким графиком."},
        {"title": "Клиент уходит не заплатив / претензии", "probability": "СРЕДНЯЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Спор по качеству → недоплата или возврат.",
         "mitigation": "Акты приёмки на каждом этапе. Юр.договор. Страхование."},
        {"title": "Колебания маржи на материалы", "probability": "СРЕДНЯЯ", "impact": "ТЕРПИМОЕ",
         "text": "Закупочные цены растут быстрее чем вы обновляете прайс.",
         "mitigation": "Фиксация цены при подписании. Пересмотр прайс-листа раз в 3 мес."},
    ],
    "F": [
        {"title": "Простой мощности", "probability": "ВЫСОКАЯ", "impact": "ЗАМЕТНОЕ",
         "text": "Постоянные затраты идут, а мощность простаивает — деньги горят.",
         "mitigation": "Минимум маркетинга на старте. Гибкая занятость персонала."},
        {"title": "Поломки оборудования", "probability": "СРЕДНЯЯ", "impact": "КРИТИЧНОЕ",
         "text": "Ключевой агрегат сломался — бизнес встал.",
         "mitigation": "Запас запчастей. Договор с сервисом. Резервное оборудование."},
        {"title": "Регуляторные ограничения (экология, санитария)", "probability": "СРЕДНЯЯ", "impact": "КРИТИЧНОЕ",
         "text": "Новые требования → доп.инвестиции или закрытие.",
         "mitigation": "Следить за законодательством. Соответствие изначально."},
    ],
}


# ═══════════════════════════════════════════════════════════════════════
# Функции
# ═══════════════════════════════════════════════════════════════════════


def _filter_risks_by_format(risks_list, format_id):
    """Исключает риски, чей title/text содержит exclude_keywords формата."""
    flt = FORMAT_RISK_FILTERS.get(format_id or "")
    if not flt:
        return risks_list
    kws = [k.lower() for k in flt.get("exclude_keywords") or []]
    if not kws:
        return risks_list
    out = []
    for r in risks_list:
        blob = ((r.get("title") or "") + " " + (r.get("text") or "")).lower()
        if any(k in blob for k in kws):
            continue
        out.append(r)
    return out


def compute_block9_risks(db, result, adaptive):
    """Block 9 — топ-5 рисков ниши.

    Источник: insight.md (через content_loader) → парсинг секций.
    Фолбэк: GENERIC_RISKS_BY_ARCHETYPE[arch] (5 общих рисков на архетип).
    Затем фильтр по формату + добавление HOME_SPECIFIC_RISKS для HOME.

    db нужен для _archetype_of (в Этапе 4+ архетип будет в result).
    """
    inp = result.get("input", {}) or {}
    niche_id = inp.get("niche_id", "")

    arch = _archetype_of(db, niche_id)

    risks_out = []
    content = load_insight_md(niche_id)
    if content:
        try:
            header_pat = (
                r"#+\s*(?:\d+\.\s*)?"
                r"(Финансовые риски и ловушки"
                r"|Красные флаги(?:\s*\([^)]*\))?"
                r"|Типичные ошибки новичков"
                r"|Операционные риски"
                r"|Риски"
                r"|Подводные камни"
                r"|Причины провала)"
            )
            section_pat = header_pat + r"[\s\S]*?(?=\n#+\s|\Z)"
            risks_out_local = []
            for m in re.finditer(section_pat, content, re.IGNORECASE):
                section = m.group(0)
                items = re.findall(
                    r"(?:^|\n)[-*\d.]+\s+\*\*([^*]+)\*\*([\s\S]*?)(?=\n[-*\d.]+|\n#+|\Z)",
                    section,
                )
                for title, body in items:
                    body_text = re.sub(r"\n\s*", " ", body).strip()[:240]
                    risks_out_local.append({
                        "title": title.strip(),
                        "probability": "СРЕДНЯЯ", "impact": "ЗАМЕТНОЕ",
                        "text": body_text, "mitigation": "",
                    })
                if len(risks_out_local) >= 5:
                    break
            risks_out = risks_out_local[:5]
        except Exception:
            pass

    if not risks_out:
        risks_out = GENERIC_RISKS_BY_ARCHETYPE.get(arch, GENERIC_RISKS_BY_ARCHETYPE["A"])[:5]

    source = (
        "insight" if len(risks_out) and (
            not GENERIC_RISKS_BY_ARCHETYPE.get(arch)
            or risks_out[0].get("title") != GENERIC_RISKS_BY_ARCHETYPE[arch][0]["title"]
        ) else "generic"
    )

    format_id = (inp.get("format_id") or "").upper()
    risks_out = _filter_risks_by_format(risks_out, format_id)

    if format_id.endswith("_HOME"):
        risks_out = HOME_SPECIFIC_RISKS + risks_out

    risks_out = risks_out[:5]

    return {
        "niche_id": niche_id,
        "source": source,
        "risks": risks_out,
    }
