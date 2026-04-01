"""
ZEREK Report
Генерирует текстовый отчёт Quick Check для Telegram.
PDF отложен — будет добавлен позже.
"""


def fmt(n):
    if n is None: return '—'
    try: return f"{int(n):,}".replace(",", " ")
    except: return str(n)

def pct(n):
    if n is None: return '—'
    return f"{n}%"


def render_text_report(result: dict) -> str:
    inp = result['input']
    cap = result['capex']
    stf = result['staff']
    fin = result['financials']
    be = result['breakeven']
    sc = result['scenarios']
    pb = result['payback']
    tx = result['tax']
    vrd = result['verdict']
    products = result.get('products', [])
    insights = result.get('insights', [])
    marketing = result.get('marketing', [])
    alts = result.get('alternatives', [])
    risks = result.get('risks', {})

    lines = []
    def h1(t): lines.append(f"\n{'='*40}\n  {t}\n{'='*40}")
    def h2(t): lines.append(f"\n-- {t} --")
    def row(k, v): lines.append(f"  {k}: {v}")
    def tip(t): lines.append(f"  -> {t}")
    def warn(t): lines.append(f"  !! {t}")
    def sep(): lines.append("")

    lines.append("ZEREK Quick Check Report")
    lines.append("=" * 40)
    sep()
    row("Бизнес", f"{inp.get('format_name','')} ({inp['class']})")
    row("Город", inp.get('city_name', inp['city_id']))
    if inp.get('qty', 1) > 1:
        row("Кол-во точек/боксов", inp['qty'])
    row("Роль", "Сам работаю" if inp.get('founder_works') else "Нанимаю персонал")
    sep()

    h1("1. НА ЧЕМ ВЫ ЗАРАБАТЫВАЕТЕ")
    row("Средний чек", f"{fmt(fin['check_med'])} тг")
    row("Клиентов в день", fin['traffic_med'])
    row("Валовая маржа", pct(round(fin['margin_pct']*100)))
    sep()
    if products:
        core = [p for p in products if p.get('category') == 'core']
        upsell = [p for p in products if p.get('category') == 'upsell']
        if core[:3]:
            h2("Основные продукты")
            for p in core[:3]:
                name = p.get('product_name','')
                margin = p.get('margin_pct')
                ms = f", маржа {round(margin*100)}%" if margin and margin == margin else ""
                lines.append(f"  - {name}{ms}")
        if upsell[:3]:
            h2("Допродажи (скрытый доход)")
            for p in upsell[:3]:
                name = p.get('product_name','')
                effect = p.get('upsell_check_pct')
                es = f" +{round(effect*100)}% к чеку" if effect and effect == effect else ""
                lines.append(f"  - {name}{es}")
    sep()

    h1("2. РАСХОДЫ")
    row("ФОТ (с налогами)", f"{fmt(stf['fot_full_med'])} тг/мес")
    row("Аренда", f"{fmt(fin['rent_month'])} тг/мес")
    row("OPEX итого", f"{fmt(fin['opex_med'])} тг/мес")
    if fin.get('sez_month', 0) > 0:
        row("СЭЗ расходы", f"{fmt(fin['sez_month'])} тг/мес")
        warn("Общепит: медкнижки, дезинсекция, санпаспорт обязательно!")
    row("Штат", f"{stf['positions']} ({stf['headcount']} чел)")
    sep()

    h1("3. ИНВЕСТИЦИИ (CAPEX)")
    row("Оборудование", f"{fmt(cap['breakdown']['equipment'])} тг")
    row("Ремонт/отделка", f"{fmt(cap['breakdown']['renovation'])} тг")
    if cap['breakdown'].get('furniture'):
        row("Мебель", f"{fmt(cap['breakdown']['furniture'])} тг")
    row("Первый закуп", f"{fmt(cap['breakdown']['first_stock'])} тг")
    row("Разрешения + СЭЗ", f"{fmt(cap['breakdown']['permits_sez'])} тг")
    row("Оборотный капитал", f"{fmt(cap['breakdown']['working_cap'])} тг")
    row("Депозит аренды", f"{fmt(cap['deposit'])} тг")
    sep()
    row("ИТОГО нужно", f"{fmt(cap['total'])} тг")
    row("Ваш капитал", f"{fmt(cap['capital'])} тг")
    lines.append(f"  {cap['signal']}")
    if cap['gap'] > 0:
        row("Запас", f"{fmt(cap['gap'])} тг (~{cap['reserve_months']} мес расходов)")
    sep()

    h1("4. ТОЧКА БЕЗУБЫТОЧНОСТИ")
    row("ТБ в деньгах", f"{fmt(be['тб_₸'])} тг/мес")
    row("ТБ в клиентах", f"{be['тб_чеков_день']} чеков/день")
    row("Запас прочности", pct(be['запас_прочности_%']))
    if be['запас_прочности_%'] < 15:
        warn("Низкий запас прочности!")
    sep()

    h1("5. ТРИ СЦЕНАРИЯ")
    for label, name in [('pess','Пессимистичный'),('base','Базовый'),('opt','Оптимистичный')]:
        s = sc[label]
        lines.append(f"  {name}:")
        lines.append(f"    Трафик {s['трафик_день']}/день, чек {fmt(s['чек'])} тг")
        lines.append(f"    Прибыль: {fmt(s['прибыль_среднемес'])} тг/мес")
        lines.append(f"    {s['окупаемость']['статус']}")
    sep()

    h1("6. НАЛОГИ")
    row("Режим", tx['regime'])
    row("Ставка", f"{tx['rate_pct']}%")
    if tx.get('b2b') == 'Да':
        warn("B2B = риск НДС 16%!")
    sep()

    h1("7. РИСКИ")
    risk_insights = [i for i in insights if i.get('insight_type') == 'risk']
    for ri in risk_insights[:5]:
        txt = str(ri.get('insight_text', ''))
        if txt and txt != 'nan':
            warn(txt)
    newbie = [i for i in insights if i.get('insight_type') == 'newbie_mistake']
    if newbie:
        h2("Ошибки новичков")
        for n in newbie[:3]:
            txt = str(n.get('insight_text', ''))
            if txt and txt != 'nan':
                warn(txt)
    sep()

    if vrd['color'] == 'red' or alts:
        h1("8. ЧТО ДЕЛАТЬ?")
        for alt in alts:
            tip(alt)
        sep()

    h1("9. КАК ПРОДВИГАТЬ")
    main_ch = [m for m in marketing if m.get('priority') == 'основной']
    for ch in main_ch[:5]:
        name = str(ch.get('channel', ''))
        note = str(ch.get('notes', ''))
        lines.append(f"  + {name}")
        if note and note != 'nan':
            lines.append(f"    {note}")
    skip_ch = [m for m in marketing if m.get('priority') == 'не_нужен']
    if skip_ch:
        lines.append(f"\n  НЕ тратьте на:")
        for ch in skip_ch[:3]:
            lines.append(f"  - {ch.get('channel','')}")
    sep()

    h1("10. ИТОГОВАЯ ОЦЕНКА")
    lines.append(f"\n  {vrd['text']}")
    if vrd['reasons']:
        for r in vrd['reasons']:
            lines.append(f"  - {r}")
    sep()

    lifehacks = [i for i in insights if i.get('insight_type') == 'lifehack']
    if lifehacks:
        h2("Полезные советы")
        for lh in lifehacks[:3]:
            txt = str(lh.get('insight_text', ''))
            if txt and txt != 'nan':
                tip(txt)
    sep()

    lines.append("=" * 40)
    lines.append("  @zerekai_bot | zerek.cc")
    lines.append("  Данные: бенчмарки рынка КЗ 2026")
    lines.append("=" * 40)

    return "\n".join(lines)
