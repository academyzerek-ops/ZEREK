"""
ZEREK Report v4 — Генератор структурированных данных для отчёта Quick Check.
14 блоков, дисклеймеры, пояснения, связка сценариев с маркетингом.
Принимает dict из engine.run_quick_check_v3() и возвращает dict для фронтенда.
"""


def fmt(n) -> str:
    try: return f"{int(n):,}".replace(",", " ")
    except: return str(n) if n else "—"


def render_report_v4(result: dict) -> dict:
    inp = result.get("input", {})
    fin = result.get("financials", {})
    sf = result.get("staff", {})
    cap = result.get("capex", {})
    be = result.get("breakeven", {})
    sc = result.get("scenarios", {})
    tx = result.get("tax", {})
    vd = result.get("verdict", {})
    pr = result.get("products", [])
    ins = result.get("insights", [])
    mk = result.get("marketing", [])
    al = result.get("alternatives", [])
    mkt = result.get("market", {})
    comp = result.get("competitors", {})
    cf = result.get("cashflow", [])

    check_med = fin.get("check_med", 0)
    traffic_med = fin.get("traffic_med", 0)
    cogs_pct = fin.get("cogs_pct", 0.35)
    margin_pct = fin.get("margin_pct", 0.65)
    rent_month = fin.get("rent_month", 0)
    niche_id = inp.get("niche_id", "")
    format_id = inp.get("format_id", "")
    cls = inp.get("class", "") or inp.get("cls", "")
    city_name = inp.get("city_name", "")
    revenue_med = check_med * traffic_med * 30

    core_products = [p for p in pr if p.get("category") == "core"]
    upsell_products = [p for p in pr if p.get("category") == "upsell"]
    locomotive = core_products[0].get("product_name", "") if core_products else "Основная услуга"

    # Структура выручки 100%
    rev_struct = []
    for p in core_products:
        s = p.get("share_pct", 0)
        if s: rev_struct.append({"name": p.get("product_name",""), "share": round(float(s)*100), "type": "core"})
    ups_total = sum(float(p.get("upsell_check_pct",0)) for p in upsell_products)
    if ups_total > 0:
        rev_struct.append({"name": "Допродажи", "share": round(ups_total*100), "type": "upsell", "note": f"+{round(ups_total*100)}% к чеку"})

    # Прямые расходы
    cogs_m = int(revenue_med * cogs_pct)
    loss_m = int(revenue_med * fin.get("loss_pct", 0.03))

    # Постоянные расходы
    fot_full = sf.get("fot_full_med", 0) or int(sf.get("fot_net_med", 0) * 1.175)
    utils = fin.get("utilities", 0); mkt_b = fin.get("marketing", 0)
    cons = fin.get("consumables", 0); soft = fin.get("software", 0)
    trans = fin.get("transport", 0); sez = fin.get("sez_month", 0)
    fixed = fot_full + rent_month + utils + mkt_b + cons + soft + trans + sez

    # CAPEX
    bk = cap.get("breakdown", {})
    capital = inp.get("capital", 0) or 0; capex_total = cap.get("total", 0)
    inv_range = cap.get("investment_range", {})
    gap = capital - capex_total if capital > 0 else 0

    eq_notes = {
        'COFFEE':'Кофемашина, кофемолка, холодильная витрина, блендер',
        'BAKERY':'Печь конвекционная, тестомес, расстоечный шкаф, витрина',
        'DONER':'Гриль вертикальный, фритюрница, холодильник, вытяжка',
        'PIZZA':'Печь для пиццы, тестомес, холодильный стол',
        'SUSHI':'Рисоварка, холодильная витрина, проф. ножи',
        'FASTFOOD':'Гриль, фритюрница, тепловая витрина, вытяжка',
        'CANTEEN':'Плита промышленная, пароконвектомат, мармит',
        'BARBER':'Кресла барберские, зеркала, инструменты, стерилизатор',
        'NAIL':'Маникюрный стол, лампа UV/LED, фрезер',
        'LASH':'Кушетка, лампа, пинцеты, материалы',
        'SUGARING':'Кушетка, воскоплав, паста, расходники',
        'BROW':'Кресло, лампа, инструменты, краски',
        'MASSAGE':'Массажный стол, масла, полотенца',
        'DENTAL':'Стом. кресло, бормашина, автоклав, рентген',
        'FITNESS':'Тренажёры, свободные веса, кардио, зеркала',
        'CARWASH':'АВД Kärcher, пылесос, пеногенератор, химия',
        'AUTOSERVICE':'Подъёмник, компрессор, инструмент, диагностика',
        'TIRE':'Шиномонтажный станок, балансировочный, компрессор',
        'GROCERY':'Холодильники, стеллажи, касса, весы',
        'PHARMA':'Витрины, холодильник, касса, софт учёта',
        'FLOWERS':'Холодильная камера, вёдра, упаковка',
        'FRUITSVEGS':'Стеллажи, весы, холодильник, ящики',
        'CLEAN':'Проф. пылесос Kärcher, парогенератор, моющий пылесос',
        'DRYCLEAN':'Стиральная проф., сушильная, гладильный пресс',
        'REPAIR_PHONE':'Паяльная станция, микроскоп, инструменты, запчасти',
        'KINDERGARTEN':'Детская мебель, игрушки, посуда, спальное',
        'PVZ':'Стеллажи, сканер, ПК, принтер этикеток',
        'SEMIFOOD':'Тестомес, формовочный аппарат, морозильная камера',
        'CONFECTION':'Миксер планетарный, духовой шкаф, формы',
        'WATER':'Система обратного осмоса, бутыли, помпы',
        'TAILOR':'Швейная машина, оверлок, утюг, манекен',
        'CYBERCLUB':'Игровые ПК, мониторы 144Hz, кресла, сеть',
        'FURNITURE':'Форматно-раскроечный, фрезер, кромочник, дрели',
    }

    capex_items = []
    if bk.get("equipment"): capex_items.append({"name":"Оборудование","amount":bk["equipment"],"note":eq_notes.get(niche_id,"Проф. оборудование")})
    if bk.get("renovation"): capex_items.append({"name":"Ремонт помещения","amount":bk["renovation"]})
    if bk.get("furniture"): capex_items.append({"name":"Мебель и интерьер","amount":bk["furniture"]})
    if bk.get("first_stock"): capex_items.append({"name":"Первый закуп","amount":bk["first_stock"]})
    if bk.get("permits_sez"): capex_items.append({"name":"Разрешения и СЭЗ","amount":bk["permits_sez"]})
    if bk.get("working_cap"): capex_items.append({"name":"Оборотный капитал","amount":bk["working_cap"]})

    inv_min = inv_range.get("min", capex_total)
    inv_max = inv_range.get("max", capex_total)
    if capital > 0 and gap >= 0:
        budget_txt = f"Ваш бюджет {fmt(capital)} ₸ покрывает стартовые вложения {fmt(capex_total)} ₸. Остаток {fmt(gap)} ₸ рекомендуем сохранить как резерв."
    elif capital > 0:
        budget_txt = f"Стартовые вложения {fmt(capex_total)} ₸, ваш бюджет {fmt(capital)} ₸. Рассмотрите снижение класса или формат с меньшими вложениями."
    else:
        budget_txt = f"Потребуется инвестиций: от {fmt(inv_min)} до {fmt(inv_max)} ₸ (оборудование, ремонт, депозит аренды + резерв 3 мес.)."

    # Сценарии
    sc_descs = {
        "pess": {"label":"Пессимистичный","color":"red","mkt_desc":"Минимум: Instagram сами + сарафан. Без вложений.","mkt_budget":"0–15 тыс ₸/мес"},
        "base": {"label":"Базовый","color":"blue","mkt_desc":"Таргет, Reels, ведение соцсетей, базовый 2ГИС.","mkt_budget":"30–80 тыс ₸/мес"},
        "opt": {"label":"Оптимистичный","color":"green","mkt_desc":"Полный SMM, платный 2ГИС, продакшн, акции.","mkt_budget":"80–150 тыс ₸/мес"},
    }
    scenarios_out = []
    for k in ["pess","base","opt"]:
        s = sc.get(k, {}); d = sc_descs[k]; pb = s.get("окупаемость", {})
        scenarios_out.append({"key":k,"label":d["label"],"color":d["color"],"traffic":s.get("трафик_день",0),"check":s.get("чек",0),"revenue_year":s.get("выручка_год",0),"profit_monthly":s.get("прибыль_среднемес",0),"payback":pb.get("статус",""),"mkt_desc":d["mkt_desc"],"mkt_budget":d["mkt_budget"]})

    # Налоги
    tax_rate = tx.get("rate_pct", 3); tax_oked = tx.get("oked", "")
    tax_txt = f"Рекомендуем {tx.get('regime','Упрощённую')}. ОКЭД {tax_oked} входит в перечень разрешённых. Для г. {city_name} ставка {tax_rate}%."
    if tx.get("nds_risk") and str(tx.get("nds_risk")) not in ['nan','Нет','']:
        tax_txt += " При работе с юрлицами — они не смогут принять НДС к вычету."

    # Маркетинг
    main_ch = [{"channel":m.get("channel",""),"effect":m.get("expected_effect",""),"budget_month":m.get("budget_month",0),"notes":m.get("notes","")} for m in mk if m.get("priority")=="основной"]
    skip_ch = [m.get("channel","") for m in mk if m.get("priority")=="не_нужен"]

    # Советы
    tips_inc = [t.get("insight_text","") for t in ins if t.get("insight_type")=="lifehack" and str(t.get("insight_text",""))!="nan"][:3]
    tips_risk = [t.get("insight_text","") for t in ins if t.get("insight_type")=="risk" and str(t.get("insight_text",""))!="nan"][:3]
    tips_err = [t.get("insight_text","") for t in ins if t.get("insight_type")=="newbie_mistake" and str(t.get("insight_text",""))!="nan"][:3]

    # Здоровье проекта
    health = []
    pb_m = sc.get("base",{}).get("окупаемость",{}).get("месяц")
    health.append({"name":"Окупаемость","status":"green" if pb_m and pb_m<=18 else "yellow" if pb_m and pb_m<=30 else "red","value":f"{pb_m} мес" if pb_m else ">30 мес"})
    gm = round((1-cogs_pct)*100)
    health.append({"name":"Маржинальность","status":"green" if gm>=60 else "yellow" if gm>=40 else "red","value":f"{gm}%"})
    cl = comp.get("уровень",3)
    health.append({"name":"Конкуренция","status":"green" if cl<=2 else "yellow" if cl<=3 else "red","value":["","Низкая","Низкая","Средняя","Высокая","Очень высокая"][min(cl,5)]})
    sp = be.get("запас_прочности_%",0)
    health.append({"name":"Запас прочности","status":"green" if sp>=30 else "yellow" if sp>=10 else "red","value":f"{sp}%"})
    if capital > 0:
        health.append({"name":"Капитал","status":"green" if gap>=0 else "red","value":"Достаточно" if gap>=0 else f"Нехватка {fmt(abs(gap))} ₸"})
    else:
        health.append({"name":"Инвестиции","status":"yellow","value":f"от {fmt(inv_min)} ₸"})

    # Сезонность
    season = [{"month":c.get("кал_месяц",""),"revenue":c.get("выручка",0),"profit":c.get("прибыль",0)} for c in cf[:12]]

    # Чеклист
    checklist = [{"item":"Регистрация ИП/ТОО","done":False},{"item":f"ОКЭД {tax_oked}","done":False}]
    if sez > 0:
        checklist.append({"item":"СЭЗ (санитарное заключение)","done":False})
        checklist.append({"item":"Медкнижки персонала","done":False})

    return {
        "input": inp,
        "owner_economics": result.get("owner_economics", {}),
        "health": {"title":"Здоровье проекта","indicators":health},
        "block_1": {
            "title":"На чём зарабатываете","subtitle":"Структура выручки",
            "check_med":check_med,"traffic_med":traffic_med,"revenue_monthly":revenue_med,
            "locomotive":locomotive,"revenue_structure":rev_struct,
            "disclaimer":f"Средний чек {fmt(check_med)} ₸ — типовая корзина для класса «{cls}» в г. {city_name}. Локомотив: {locomotive}. ЦА: {mkt.get('target_audience','массовый потребитель')}, {mkt.get('age_range','18-50')}, доход {mkt.get('income_level','средний')}.",
        },
        "block_2": {
            "title":"Прямые расходы","subtitle":"Зависят от объёма продаж",
            "cogs_pct":round(cogs_pct*100),"cogs_monthly":cogs_m,"loss_monthly":loss_m,
            "gross_profit":revenue_med-cogs_m,"gross_margin_pct":round((1-cogs_pct)*100),
            "disclaimer":f"Себестоимость ~{round(cogs_pct*100)}% от выручки. Валовая маржа {round((1-cogs_pct)*100)}% — это ДО вычета аренды, зарплат, налогов.",
        },
        "block_3": {
            "title":"Постоянные расходы","subtitle":"Платите каждый месяц",
            "items":[
                {"name":"ФОТ (зарплаты+налоги)","amount":fot_full,"note":sf.get("positions","")},
                {"name":"Аренда","amount":rent_month},
                {"name":"Коммунальные","amount":utils},
                {"name":"Маркетинг","amount":mkt_b},
                {"name":"Расходники","amount":cons},
                {"name":"Софт/касса","amount":soft},
            ] + ([{"name":"СЭЗ","amount":sez}] if sez>0 else []),
            "total":fixed,
            "disclaimer":f"ФОТ включает чистую зарплату + налоги работодателя. Штат: {sf.get('positions','')}.",
        },
        "block_4": {
            "title":"Стартовые вложения","subtitle":"До открытия",
            "items":capex_items,"total":capex_total,"budget":capital,"gap":gap,
            "budget_text":budget_txt,"reserve_months":cap.get("reserve_months",0),
            "investment_min":inv_min,"investment_max":inv_max,
        },
        "block_5": {
            "title":"Три сценария","subtitle":"Прогноз на 12 месяцев",
            "scenarios":scenarios_out,
            "disclaimer":"Маркетинговый бюджет и качество продвижения определяют сценарий. Реклама играет огромную роль наряду с качеством продукта.",
        },
        "block_6": {
            "title":"Точка безубыточности","subtitle":"Минимум чтобы выйти в ноль",
            "tb_revenue":be.get("тб_₸",0),"tb_checks_day":be.get("тб_чеков_день",0),
            "safety_margin":be.get("запас_прочности_%",0),
            "disclaimer":f"При чеке {fmt(check_med)} ₸ нужно минимум {be.get('тб_чеков_день',0)} клиентов/день чтобы покрыть все расходы ({fmt(fixed)} ₸/мес).",
        },
        "block_7": {"title":"Налоги","text":tax_txt,"regime":tx.get("regime",""),"rate_pct":tax_rate},
        "block_8": {
            "title":"Как продвигать","main":main_ch,"skip":skip_ch,
            "disclaimer":"Бюджет на маркетинг определяет сценарий. Пессимист = 0. Базовый = 30-80 тыс. Оптимист = 80-150 тыс.",
        },
        "block_9": {"title":"Полезные советы","income":tips_inc,"risks":tips_risk,"mistakes":tips_err},
        "block_10": {
            "title":"Выводы","verdict_color":vd.get("color","yellow"),"verdict_text":vd.get("text",""),
            "reasons":vd.get("reasons",[]),"alternatives":al,
            "next_steps":["Проверьте локацию лично в часы пик","Получите 3 предложения по аренде","Уточните стоимость оборудования у 2-3 поставщиков"],
        },
        "block_11_season": {"title":"Сезонность","data":season},
        "block_12_checklist": {"title":"Что оформить","items":checklist},
    }
