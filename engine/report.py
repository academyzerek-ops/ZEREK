"""
ZEREK Quick Check — Форматирование отчёта v2.
Принимает dict из engine.run_quick_check() v2 и возвращает текстовый отчёт.
9 блоков: рынок, локация, CAPEX, штат, OPEX, выручка+ТБ, окупаемость, налоги, итоговая оценка.
"""


def fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except:
        return str(n)


def pct(n) -> str:
    try:
        return f"{float(n):.1f}%"
    except:
        return str(n)


def render_report(result: dict) -> str:
    inp = result["input"]
    mkt = result["market"]
    loc = result.get("location", {})
    cap = result["capex"]
    stf = result.get("staff", {})
    opx = result.get("opex", {})
    scn = result.get("scenarios", {})
    be = result["breakeven"]
    pb = result.get("payback", {})
    tax = result.get("tax", {})
    vrd = result.get("verdict", {})
    fin = result["financials"]
    cf = result["cashflow"]
    mac = result["macro"]
    risk = result["risks"]
    tss = mkt["tam_sam_som"]
    comp = mkt["competitors"]

    lines = []

    def h1(t):
        lines.append(f"\n{'═' * 56}\n  {t}\n{'═' * 56}")

    def h2(t):
        lines.append(f"\n── {t} ──")

    def li(t):
        lines.append(f"  • {t}")

    def row(k, v):
        lines.append(f"  {k:<34} {v}")

    def tip(t):
        lines.append(f"\n  💡 {t}")

    def sep():
        lines.append("")

    # ── ШАПКА ──
    lines.append(f"""
╔════════════════════════════════════════════════════════╗
║          ZEREK — QUICK CHECK ОТЧЁТ                    ║
╚════════════════════════════════════════════════════════╝
  Город:    {inp['city_name']}
  Ниша:     {inp['niche_id']}
  Формат:   {inp['format_id']}
  Площадь:  {inp['area_m2']} м²
  Локация:  {inp['loc_type']}
  Капитал:  {fmt(inp['capital'])} ₸
  Уровень:  {inp['capex_level'].upper()}
""")

    # ══════════════════════════════════════════
    # БЛОК 1: ОБЗОР РЫНКА
    # ══════════════════════════════════════════
    h1("1. ОБЗОР РЫНКА")

    h2("Город и население")
    row("Население:", fmt(mkt['population']) + " чел.")
    row("Трудоспособные 16-62:", fmt(mkt['working_age']) + " чел.")
    sep()

    h2("Целевая аудитория")
    row("TAM (весь рынок ниши):", fmt(tss['tam']) + " чел.")
    row("SAM (доступный рынок):", fmt(tss['sam']) + " чел.")
    row("SOM (реалистичная доля):", fmt(tss['som']) + " чел.")
    sep()

    # Поведение потребителей
    cons = mkt.get("consumer_behavior", {})
    if cons:
        h2("Целевая аудитория — поведение")
        if cons.get("Частота визита"):
            row("Частота визита:", str(cons["Частота визита"]))
        if cons.get("Пиковые часы"):
            row("Пиковые часы:", str(cons["Пиковые часы"]))
        if cons.get("Доля повторных клиентов %"):
            row("Повторные клиенты:", str(cons["Доля повторных клиентов %"]) + "%")
        if cons.get("Основной канал поиска"):
            row("Канал привлечения:", str(cons["Основной канал поиска"]))
        sep()

    h2("Конкурентная среда")
    row("Конкурентов в городе:", str(comp.get('кол_во', '?')))
    li(comp.get('сигнал', ''))
    if comp.get('лидеры'):
        li(f"Основные игроки: {comp['лидеры']}")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 2: ЛОКАЦИЯ
    # ══════════════════════════════════════════
    h1("2. ЛОКАЦИЯ И АРЕНДА")

    row("Тип локации:", inp['loc_type'])
    row("Площадь:", str(inp['area_m2']) + " м²")
    row("Аренда / мес:", fmt(loc.get('rent_month', fin['аренда_мес'])) + " ₸")
    if loc.get('rent_benchmark_m2'):
        row("Бенчмарк за м²:", fmt(loc['rent_benchmark_m2']) + " ₸")
    if loc.get('rent_per_m2'):
        row("Ваша ставка за м²:", fmt(loc['rent_per_m2']) + " ₸")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 3: ИНВЕСТИЦИИ
    # ══════════════════════════════════════════
    h1("3. ИНВЕСТИЦИИ (CAPEX)")

    all_levels = cap.get("все_уровни", {})
    if all_levels:
        row("🟢 Эконом (б/у оборуд.):", fmt(all_levels.get("эконом", 0)) + " ₸")
        row("🔵 Стандарт (новое среднее):", fmt(all_levels.get("стандарт", 0)) + " ₸")
        row("🟡 Премиум (топ-бренды):", fmt(all_levels.get("премиум", 0)) + " ₸")
        sep()

    row(f"Выбранный уровень ({cap['уровень']}):", fmt(cap['оборудование_и_ремонт']) + " ₸")
    row("+ Депозит аренды (2 мес.):", fmt(cap['депозит_аренды']) + " ₸")
    row("ИТОГО нужно:", fmt(cap['итого']) + " ₸")
    sep()
    row("Ваш капитал:", fmt(cap['капитал_пользователя']) + " ₸")
    lines.append(f"  {cap['сигнал']}")

    if cap.get('разница', 0) > 0:
        row("Запас:", fmt(cap['разница']) + " ₸")
        if cap.get('запас_месяцев'):
            row("Хватит на:", str(cap['запас_месяцев']) + " мес. расходов")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 4: ШТАТ
    # ══════════════════════════════════════════
    h1("4. ШТАТНОЕ РАСПИСАНИЕ")

    for stage_key, stage_label in [("start", "Старт"), ("growth", "Рост"), ("scale", "Масштаб")]:
        stage_data = stf.get(stage_key, {})
        if not stage_data or not stage_data.get("staff"):
            continue
        h2(f"{stage_label}")
        for s in stage_data["staff"]:
            role = s.get("role", "?")
            count = s.get("headcount", 0)
            salary = s.get("salary", 0)
            owner = " (вы сами)" if s.get("is_owner") else ""
            salary_str = "без оклада" if s.get("is_owner") else fmt(salary) + " ₸"
            li(f"{role}{owner} × {count} — {salary_str}")
        fot = stage_data.get("total_fot_with_taxes", 0)
        if fot:
            row("  ФОТ с налогами:", fmt(fot) + " ₸/мес")
        sep()

    tip("Налоги работодателя 2026: ОПВР 3.5% + СО 5% + ООСМС 3% = 11.5% сверх оклада. Соцналог для упрощёнки отменён.")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 5: РАСХОДЫ (OPEX)
    # ══════════════════════════════════════════
    h1("5. ЕЖЕМЕСЯЧНЫЕ РАСХОДЫ (OPEX)")

    row("Аренда:", fmt(opx.get('аренда', fin['аренда_мес'])) + " ₸")
    row("ФОТ с налогами:", fmt(opx.get('фот', fin['fot_мес'])) + " ₸")

    bench = opx.get("benchmarks", {})
    if bench:
        cons_pct = bench.get("consumables_pct", 0)
        if cons_pct:
            row("Расходники/себестоимость:", pct(float(cons_pct) * 100) + " от выручки")
        util = bench.get("utilities_fixed_kzt", 0)
        if util:
            row("Коммунальные:", fmt(util) + " ₸")
        mkt_f = bench.get("marketing_fixed_kzt", 0)
        mkt_p = bench.get("marketing_pct", 0)
        if mkt_f or mkt_p:
            mkt_str = fmt(mkt_f) + " ₸" if mkt_f else ""
            if mkt_p:
                mkt_str += f" + {pct(float(mkt_p) * 100)} от выручки"
            row("Маркетинг:", mkt_str.strip(" +"))
        soft = bench.get("software_kzt", 0)
        if soft:
            row("ПО и касса:", fmt(soft) + " ₸")
        trans = bench.get("transport_kzt", 0)
        if trans:
            row("Транспорт:", fmt(trans) + " ₸")
    else:
        row("Себестоимость (COGS):", pct(fin['cogs_pct']) + " от выручки")
        li("Маркетинг: ~3% от выручки")
        li("Коммунальные: ~4% от выручки")

    sep()
    opex_growth = opx.get("рост_opex_прогноз_%", mac.get("рост_opex_прогноз_%", 0))
    if opex_growth:
        li(f"Прогноз роста расходов: {pct(opex_growth)}/год (инфляция по нише)")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 6: ВЫРУЧКА И БЕЗУБЫТОЧНОСТЬ
    # ══════════════════════════════════════════
    h1("6. ВЫРУЧКА И БЕЗУБЫТОЧНОСТЬ")

    h2("Прогноз выручки — 3 сценария")

    for label, emoji, key in [("Пессимист.", "🔴", "pess"), ("Базовый", "🔵", "base"), ("Оптимист.", "🟢", "opt")]:
        sc = scn.get(key, {})
        if sc:
            rev = fmt(sc.get("выручка_мес", 0))
            traf = sc.get("трафик_день", "?")
            chk = fmt(sc.get("чек", 0))
            profit = fmt(sc.get("прибыль_среднемес", 0))
            lines.append(f"  {emoji} {label:12} выр. {rev:>12} ₸  |  {traf} кл/день  |  приб. {profit} ₸/мес")

    sep()

    h2("Точка безубыточности")
    row("ТБ по выручке:", fmt(be['тб_выручка']) + " ₸/мес")
    row("ТБ в клиентах (день):", str(be['тб_единиц_день']) + " чел./день")
    safety = be.get('запас_прочности_%', 0)
    if safety > 0:
        row("Запас прочности:", pct(safety) + " ✅")
    else:
        row("Запас прочности:", pct(abs(safety)) + " ниже ТБ 🔴")

    tip(f"Чтобы не работать в убыток, нужно минимум {be['тб_единиц_день']} клиентов в день со средним чеком {fmt(fin['чек'])} ₸.")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 7: ОКУПАЕМОСТЬ
    # ══════════════════════════════════════════
    h1("7. ОКУПАЕМОСТЬ")

    row("CAPEX всего:", fmt(cap['итого']) + " ₸")
    sep()

    for label, emoji, key in [("Пессимист.", "🔴", "pess"), ("Базовый", "🔵", "base"), ("Оптимист.", "🟢", "opt")]:
        p = pb.get(key, {})
        m = p.get("месяц", "—")
        lines.append(f"  {emoji} {label:12} {m} мес.")

    sep()
    base_pb = pb.get("base", {})
    if base_pb:
        lines.append(f"  {base_pb.get('статус', '')}")
    sep()

    # ══════════════════════════════════════════
    # БЛОК 8: НАЛОГИ
    # ══════════════════════════════════════════
    h1("8. НАЛОГОВЫЙ РЕЖИМ")

    if tax:
        row("Рекомендация:", tax.get("рекомендация", "—"))
        row("Ставка в вашем городе:", pct(tax.get("ставка_города_%", 4)))
        row("Примерный налог за год:", fmt(tax.get("налог_примерный_год", 0)) + " ₸")
        sep()
        if tax.get("объяснение"):
            lines.append(f"  {tax['объяснение']}")
            sep()

        # B2B предупреждение
        if tax.get("b2b_likelihood") == "high":
            lines.append(f"  ⚠️ ВАЖНО: {tax.get('b2b_предупреждение', '')}")
            lines.append(f"  👉 {tax.get('b2b_рекомендация', '')}")
            sep()
        elif tax.get("b2b_likelihood") == "medium":
            lines.append(f"  ℹ️ {tax.get('b2b_предупреждение', '')}")
            sep()

        row("Порог регистрации по НДС:", fmt(tax.get("порог_ндс", 43250000)) + " ₸")
        row("МРП 2026:", fmt(tax.get("мрп_2026", MRP_2026)) + " ₸")
    else:
        # Fallback на старый формат
        rec = result.get("recommendations", {})
        tax_old = rec.get("налоговый_режим", {})
        row("Режим:", str(tax_old.get("Рекомендуемый режим", "?")))
        row("Регистрация:", str(tax_old.get("Регистрация", "?")))
    sep()

    # ══════════════════════════════════════════
    # БЛОК 9: ИТОГОВАЯ ОЦЕНКА
    # ══════════════════════════════════════════
    h1("9. ИТОГОВАЯ ОЦЕНКА")

    if vrd:
        lines.append(f"\n  {vrd.get('emoji', '')} {vrd.get('text', '')}")
        sep()
        reasons = vrd.get("reasons", [])
        if reasons:
            h2("На что обратить внимание")
            for r in reasons:
                li(r)
            sep()

    # Риски
    h2("Основные риски по нише")
    failure = risk.get('паттерн_закрытий', {})
    if failure:
        top1 = failure.get('Топ-1 причина', '')
        top2 = failure.get('Топ-2 причина', '')
        if top1:
            li(f"Причина №1 закрытий: {top1}")
        if top2:
            li(f"Причина №2 закрытий: {top2}")
        phrase = failure.get('Фраза для отчёта Quick Check', '')
        if phrase:
            tip(phrase)
    sep()

    # Разрешения — чеклист
    h2("Чеклист: что нужно до открытия")
    li("Зарегистрировать ИП (онлайн на eGov)")
    permits = risk.get('разрешения', [])
    for p in permits[:5]:
        must = "‼️" if p.get("Обязательность") == "Обязательно" else "ℹ️"
        name = p.get("Документ / разрешение", "")
        li(f"{must} {name}")
    li("Открыть расчётный счёт")
    li("Подключить онлайн-кассу")
    sep()

    # ── ПОДВАЛ ──
    lines.append("═" * 56)
    lines.append("")
    lines.append("  💬 Есть вопросы? Обсудите с AI-консультантом ZEREK")
    lines.append("  📈 Хотите точнее? Закажите финансовое моделирование")
    lines.append("")
    lines.append("  @zerekai_bot | zerek.cc")
    lines.append("═" * 56)
    lines.append("")
    lines.append("  ⚠️ Дисклеймер: данный отчёт — экспресс-оценка на основе")
    lines.append("  рыночных бенчмарков. Цифры ориентировочные и не являются")
    lines.append("  гарантией финансового результата.")
    lines.append("")

    return "\n".join(lines)


# Обратная совместимость — MRP для fallback
MRP_2026 = 4325
