"""
ZEREK Report v3.0
Генерирует отчёт Quick Check в двух форматах:
1. Текст — для Telegram бота
2. PDF — для скачивания (красивый, с цветами ZEREK)

Философия: не калькулятор, а консультация. Риски > успех. Человечный тон.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable, KeepTogether
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# ═══════════════════════════════════════
# ЦВЕТА ZEREK
# ═══════════════════════════════════════
C_PURPLE = HexColor('#6C63FF')
C_DARK = HexColor('#0A0A0F')
C_GREEN = HexColor('#00D4AA')
C_RED = HexColor('#FF4757')
C_YELLOW = HexColor('#FFD93D')
C_GRAY = HexColor('#6B7280')
C_LIGHT = HexColor('#F3F4F6')
C_WHITE = HexColor('#FFFFFF')
C_BG = HexColor('#1F2937')

def fmt(n):
    """Форматирование числа с пробелами."""
    if n is None: return '—'
    try:
        return f"{int(n):,}".replace(",", " ")
    except:
        return str(n)

def pct(n):
    if n is None: return '—'
    return f"{n}%"


# ═══════════════════════════════════════
# 1. ТЕКСТОВЫЙ ОТЧЁТ (для Telegram)
# ═══════════════════════════════════════

def render_text_report(result: dict) -> str:
    """Генерирует текстовый отчёт для Telegram."""
    inp = result['input']
    cap = result['capex']
    stf = result['staff']
    fin = result['financials']
    be = result['breakeven']
    sc = result['scenarios']
    pb = result['payback']
    tx = result['tax']
    vrd = result['verdict']
    mkt = result['market']
    risks = result['risks']
    products = result.get('products', [])
    insights = result.get('insights', [])
    marketing = result.get('marketing', [])
    alts = result.get('alternatives', [])

    lines = []
    def h1(t): lines.append(f"\n{'═'*40}\n  {t}\n{'═'*40}")
    def h2(t): lines.append(f"\n── {t} ──")
    def row(k, v): lines.append(f"  {k}: {v}")
    def tip(t): lines.append(f"  💡 {t}")
    def warn(t): lines.append(f"  ⚠️ {t}")
    def sep(): lines.append("")

    # ── ЗАГОЛОВОК ──
    lines.append("╔══════════════════════════════════════╗")
    lines.append("║     ZEREK · Quick Check Report       ║")
    lines.append("╚══════════════════════════════════════╝")
    sep()
    row("Бизнес", f"{inp.get('format_name','')} ({inp['class']})")
    row("Город", inp.get('city_name', inp['city_id']))
    if inp.get('qty', 1) > 1:
        row("Количество точек/боксов", inp['qty'])
    row("Роль", "Сам работаю" if inp.get('founder_works') else "Нанимаю персонал")
    sep()

    # ── БЛОК 1: НА ЧЁМ ЗАРАБАТЫВАЕТЕ ──
    h1("1. НА ЧЁМ ВЫ ЗАРАБАТЫВАЕТЕ")
    row("Средний чек", f"{fmt(fin['check_med'])} ₸")
    row("Клиентов в день", fin['traffic_med'])
    row("Валовая маржа", pct(round(fin['margin_pct']*100)))
    sep()
    if products:
        h2("Структура выручки")
        core = [p for p in products if p.get('category') == 'core']
        upsell = [p for p in products if p.get('category') == 'upsell']
        if core[:3]:
            for p in core[:3]:
                name = p.get('product_name','')
                margin = p.get('margin_pct')
                margin_str = f", маржа {round(margin*100)}%" if margin else ""
                lines.append(f"  • {name}{margin_str}")
        if upsell[:3]:
            lines.append(f"\n  🔥 Допродажи (ваш скрытый доход):")
            for p in upsell[:3]:
                name = p.get('product_name','')
                effect = p.get('upsell_check_pct')
                effect_str = f" → +{round(effect*100)}% к чеку" if effect else ""
                lines.append(f"  • {name}{effect_str}")
    sep()

    # ── БЛОК 2: РАСХОДЫ ──
    h1("2. СКОЛЬКО ВЫ ТРАТИТЕ")
    row("ФОТ (с налогами)", f"{fmt(stf['fot_full_med'])} ₸/мес")
    row("Аренда", f"{fmt(fin['rent_month'])} ₸/мес")
    row("OPEX итого", f"{fmt(fin['opex_med'])} ₸/мес")
    if fin.get('sez_month', 0) > 0:
        row("СЭЗ расходы", f"{fmt(fin['sez_month'])} ₸/мес")
        warn("Общепит: медкнижки, дезинсекция, санпаспорт — обязательно!")
    sep()
    row("Штат", f"{stf['positions']} ({stf['headcount']} чел)")
    if inp.get('founder_works'):
        tip("Вы работаете сами — ФОТ снижен. Но вы привязаны к точке.")
    sep()

    # ── БЛОК 3: ИНВЕСТИЦИИ ──
    h1("3. ИНВЕСТИЦИИ (CAPEX)")
    row("Оборудование", f"{fmt(cap['breakdown']['equipment'])} ₸")
    row("Ремонт/отделка", f"{fmt(cap['breakdown']['renovation'])} ₸")
    if cap['breakdown'].get('furniture'):
        row("Мебель", f"{fmt(cap['breakdown']['furniture'])} ₸")
    row("Первый закуп", f"{fmt(cap['breakdown']['first_stock'])} ₸")
    row("Разрешения + СЭЗ", f"{fmt(cap['breakdown']['permits_sez'])} ₸")
    row("Оборотный капитал", f"{fmt(cap['breakdown']['working_cap'])} ₸")
    row("Депозит аренды", f"{fmt(cap['deposit'])} ₸")
    sep()
    row("ИТОГО нужно", f"{fmt(cap['total'])} ₸")
    row("Ваш капитал", f"{fmt(cap['capital'])} ₸")
    lines.append(f"  {cap['signal']}")
    if cap['gap'] > 0:
        row("Запас", f"{fmt(cap['gap'])} ₸ (~{cap['reserve_months']} мес расходов)")
    sep()

    # ── БЛОК 4: ТОЧКА БЕЗУБЫТОЧНОСТИ ──
    h1("4. ТОЧКА БЕЗУБЫТОЧНОСТИ")
    row("ТБ в деньгах", f"{fmt(be['тб_₸'])} ₸/мес")
    row("ТБ в клиентах", f"{be['тб_чеков_день']} чеков/день")
    row("Запас прочности", pct(be['запас_прочности_%']))
    if be['запас_прочности_%'] < 15:
        warn("Низкий запас прочности! Любое снижение трафика выведет в минус.")
    sep()

    # ── БЛОК 5: СЦЕНАРИИ ──
    h1("5. ТРИ СЦЕНАРИЯ")
    for label, name in [('pess','Пессимистичный'),('base','Базовый'),('opt','Оптимистичный')]:
        s = sc[label]
        emoji = "🔴" if label == 'pess' else "🟢" if label == 'opt' else "🔵"
        lines.append(f"  {emoji} {name}:")
        lines.append(f"     Трафик {s['трафик_день']}/день, чек {fmt(s['чек'])} ₸")
        lines.append(f"     Прибыль: {fmt(s['прибыль_среднемес'])} ₸/мес")
        lines.append(f"     {s['окупаемость']['статус']}")
    sep()

    # ── БЛОК 6: НАЛОГИ ──
    h1("6. НАЛОГИ")
    row("Режим", tx['regime'])
    row("Ставка", f"{tx['rate_pct']}%")
    if tx.get('b2b') == 'Да':
        warn("B2B клиенты = риск НДС 16%!")
    sep()

    # ── БЛОК 7: РИСКИ (ГЛАВНЫЙ БЛОК) ──
    h1("⚠️  7. РИСКИ — ПРОЧИТАЙТЕ ВНИМАТЕЛЬНО")
    # Инсайты типа risk
    risk_insights = [i for i in insights if i.get('insight_type') == 'risk']
    for ri in risk_insights[:5]:
        warn(ri.get('insight_text', ''))
    # Паттерны закрытий
    fp = risks.get('failure_pattern', {})
    if fp:
        top1 = fp.get('Топ-1 причина', '')
        if top1:
            lines.append(f"\n  🔴 Причина №1 закрытий в этой нише: {top1}")
    sep()
    # Ошибки новичков
    newbie = [i for i in insights if i.get('insight_type') == 'newbie_mistake']
    if newbie:
        h2("Ошибки новичков")
        for n in newbie[:3]:
            warn(n.get('insight_text', ''))
    sep()

    # ── БЛОК 8: ЕСЛИ ПОКАЗАТЕЛИ ОТРИЦАТЕЛЬНЫЕ ──
    if vrd['color'] == 'red' or alts:
        h1("8. ЧТО ДЕЛАТЬ?")
        for alt in alts:
            tip(alt)
        if vrd['color'] == 'red':
            tip("Рассмотрите другой формат с меньшим CAPEX")
            tip("Проконсультируйтесь с нами для детальной финмодели")
        sep()

    # ── БЛОК 9: МАРКЕТИНГ ──
    h1("9. КАК ПРОДВИГАТЬ")
    main_ch = [m for m in marketing if m.get('priority') == 'основной']
    for ch in main_ch[:5]:
        name = ch.get('channel', '')
        note = ch.get('notes', '')
        lines.append(f"  ✅ {name}")
        if note and str(note) != 'nan':
            lines.append(f"     {note}")
    skip_ch = [m for m in marketing if m.get('priority') == 'не_нужен']
    if skip_ch:
        lines.append(f"\n  ❌ НЕ тратьте на:")
        for ch in skip_ch[:3]:
            lines.append(f"     • {ch.get('channel','')} — {ch.get('expected_effect','')}")
    sep()

    # ── БЛОК 10: ВЕРДИКТ ──
    h1("10. ИТОГОВАЯ ОЦЕНКА")
    lines.append(f"\n  {vrd['emoji']} {vrd['text']}")
    if vrd['reasons']:
        for r in vrd['reasons']:
            lines.append(f"  • {r}")
    sep()

    # Лайфхаки
    lifehacks = [i for i in insights if i.get('insight_type') == 'lifehack']
    if lifehacks:
        h2("Полезные советы")
        for lh in lifehacks[:3]:
            tip(lh.get('insight_text', ''))
    sep()

    # ── ПОДВАЛ ──
    lines.append("═" * 40)
    lines.append("  💬 Есть вопросы? @zerekai_bot")
    lines.append("  📈 Хотите точнее? Закажите финмодель")
    lines.append("  🌐 zerek.cc")
    lines.append("═" * 40)
    lines.append("")
    lines.append("  ⚠️ Данный отчёт — экспресс-оценка на основе")
    lines.append("  рыночных бенчмарков КЗ 2026. Цифры ориентировочные.")
    lines.append("  Фактические результаты зависят от управления,")
    lines.append("  локации, качества продукта и маркетинга.")

    return "\n".join(lines)


# ═══════════════════════════════════════
# 2. PDF ОТЧЁТ (для скачивания)
# ═══════════════════════════════════════

def _get_styles():
    """Стили для PDF."""
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(name='ZTitle', fontSize=18, leading=22, textColor=C_PURPLE, 
                              alignment=TA_CENTER, spaceAfter=6))
    styles.add(ParagraphStyle(name='ZSubtitle', fontSize=10, leading=14, textColor=C_GRAY,
                              alignment=TA_CENTER, spaceAfter=12))
    styles.add(ParagraphStyle(name='ZH1', fontSize=14, leading=18, textColor=C_PURPLE,
                              spaceBefore=16, spaceAfter=8, bold=True))
    styles.add(ParagraphStyle(name='ZH2', fontSize=11, leading=14, textColor=C_BG,
                              spaceBefore=10, spaceAfter=6, bold=True))
    styles.add(ParagraphStyle(name='ZBody', fontSize=9, leading=13, textColor=C_DARK))
    styles.add(ParagraphStyle(name='ZTip', fontSize=9, leading=13, textColor=HexColor('#059669'),
                              leftIndent=12))
    styles.add(ParagraphStyle(name='ZWarn', fontSize=9, leading=13, textColor=C_RED,
                              leftIndent=12, bold=True))
    styles.add(ParagraphStyle(name='ZSmall', fontSize=8, leading=11, textColor=C_GRAY))
    styles.add(ParagraphStyle(name='ZVerdict', fontSize=13, leading=17, alignment=TA_CENTER,
                              spaceBefore=8, spaceAfter=8, bold=True))
    return styles


def _kv_table(data, col_widths=None):
    """Таблица ключ-значение."""
    if not col_widths:
        col_widths = [55*mm, 45*mm]
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 9),
        ('TEXTCOLOR', (0,0), (0,-1), C_GRAY),
        ('TEXTCOLOR', (1,0), (1,-1), C_DARK),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('LINEBELOW', (0,0), (-1,-2), 0.5, C_LIGHT),
    ]))
    return t


def render_pdf_report(result: dict, output_path: str):
    """Генерирует PDF отчёт."""
    styles = _get_styles()
    
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        topMargin=15*mm, bottomMargin=15*mm,
        leftMargin=15*mm, rightMargin=15*mm,
    )
    
    story = []
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

    # ── ТИТУЛЬНАЯ СТРАНИЦА ──
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("ZEREK", styles['ZTitle']))
    story.append(Paragraph("Quick Check Report", styles['ZSubtitle']))
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="60%", thickness=2, color=C_PURPLE, spaceAfter=10))
    
    title_data = [
        ['Бизнес:', f"{inp.get('format_name','')} ({inp['class']})"],
        ['Город:', inp.get('city_name', inp['city_id'])],
    ]
    if inp.get('qty', 1) > 1:
        title_data.append(['Кол-во точек:', str(inp['qty'])])
    title_data.append(['Роль:', 'Сам работаю' if inp.get('founder_works') else 'Нанимаю'])
    story.append(_kv_table(title_data))
    
    story.append(Spacer(1, 15*mm))
    
    # Вердикт на титулке
    v_color = C_GREEN if vrd['color'] == 'green' else C_YELLOW if vrd['color'] == 'yellow' else C_RED
    story.append(Paragraph(f"{vrd['emoji']} {vrd['text']}", 
                           ParagraphStyle('VerdictTitle', parent=styles['ZVerdict'], textColor=v_color)))
    
    story.append(Spacer(1, 20*mm))
    story.append(Paragraph("Дата: 2026 | Данные: бенчмарки рынка КЗ", styles['ZSmall']))
    story.append(PageBreak())

    # ── БЛОК 1: НА ЧЁМ ЗАРАБАТЫВАЕТЕ ──
    story.append(Paragraph("1. На чём вы зарабатываете", styles['ZH1']))
    story.append(_kv_table([
        ['Средний чек:', f"{fmt(fin['check_med'])} ₸"],
        ['Клиентов/день:', str(fin['traffic_med'])],
        ['Валовая маржа:', pct(round(fin['margin_pct']*100))],
    ]))
    
    core = [p for p in products if p.get('category') == 'core'][:4]
    upsell = [p for p in products if p.get('category') == 'upsell'][:4]
    if core:
        story.append(Paragraph("Основные продукты/услуги:", styles['ZH2']))
        for p in core:
            m = p.get('margin_pct')
            m_str = f" (маржа {round(m*100)}%)" if m else ""
            story.append(Paragraph(f"• {p.get('product_name','')}{m_str}", styles['ZBody']))
    if upsell:
        story.append(Paragraph("Допродажи — ваш скрытый доход:", styles['ZH2']))
        for p in upsell:
            e = p.get('upsell_check_pct')
            e_str = f" → +{round(e*100)}% к чеку" if e else ""
            story.append(Paragraph(f"• {p.get('product_name','')}{e_str}", styles['ZTip']))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 2: РАСХОДЫ ──
    story.append(Paragraph("2. Ваши расходы", styles['ZH1']))
    story.append(_kv_table([
        ['ФОТ (с налогами):', f"{fmt(stf['fot_full_med'])} ₸/мес"],
        ['Аренда:', f"{fmt(fin['rent_month'])} ₸/мес"],
        ['OPEX итого:', f"{fmt(fin['opex_med'])} ₸/мес"],
        ['Штат:', f"{stf['positions']}"],
    ]))
    if fin.get('sez_month', 0) > 0:
        story.append(Paragraph(f"СЭЗ расходы: {fmt(fin['sez_month'])} ₸/мес (медкнижки, дезинсекция — обязательно для общепита)", styles['ZWarn']))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 3: ИНВЕСТИЦИИ ──
    story.append(Paragraph("3. Инвестиции (CAPEX)", styles['ZH1']))
    capex_rows = [
        ['Оборудование:', f"{fmt(cap['breakdown']['equipment'])} ₸"],
        ['Ремонт/отделка:', f"{fmt(cap['breakdown']['renovation'])} ₸"],
        ['Первый закуп:', f"{fmt(cap['breakdown']['first_stock'])} ₸"],
        ['Разрешения + СЭЗ:', f"{fmt(cap['breakdown']['permits_sez'])} ₸"],
        ['Оборотный капитал:', f"{fmt(cap['breakdown']['working_cap'])} ₸"],
        ['Депозит аренды:', f"{fmt(cap['deposit'])} ₸"],
    ]
    if cap['breakdown'].get('furniture'):
        capex_rows.insert(2, ['Мебель:', f"{fmt(cap['breakdown']['furniture'])} ₸"])
    story.append(_kv_table(capex_rows))
    story.append(Spacer(1, 3*mm))
    story.append(_kv_table([
        ['ИТОГО нужно:', f"{fmt(cap['total'])} ₸"],
        ['Ваш капитал:', f"{fmt(cap['capital'])} ₸"],
    ]))
    gap_style = styles['ZTip'] if cap['gap'] >= 0 else styles['ZWarn']
    story.append(Paragraph(cap['signal'], gap_style))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 4: ТБ ──
    story.append(Paragraph("4. Точка безубыточности", styles['ZH1']))
    story.append(_kv_table([
        ['ТБ в деньгах:', f"{fmt(be['тб_₸'])} ₸/мес"],
        ['ТБ в клиентах:', f"{be['тб_чеков_день']} чеков/день"],
        ['Запас прочности:', pct(be['запас_прочности_%'])],
    ]))
    if be['запас_прочности_%'] < 15:
        story.append(Paragraph("Низкий запас прочности! Любое снижение трафика выведет в минус.", styles['ZWarn']))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 5: СЦЕНАРИИ ──
    story.append(Paragraph("5. Три сценария", styles['ZH1']))
    sc_data = [['', 'Пессимист', 'Базовый', 'Оптимист']]
    sc_data.append(['Трафик/день', str(sc['pess']['трафик_день']), str(sc['base']['трафик_день']), str(sc['opt']['трафик_день'])])
    sc_data.append(['Чек ₸', fmt(sc['pess']['чек']), fmt(sc['base']['чек']), fmt(sc['opt']['чек'])])
    sc_data.append(['Прибыль/мес', fmt(sc['pess']['прибыль_среднемес']), fmt(sc['base']['прибыль_среднемес']), fmt(sc['opt']['прибыль_среднемес'])])
    sc_data.append(['Окупаемость', sc['pess']['окупаемость']['статус'][:15], sc['base']['окупаемость']['статус'][:15], sc['opt']['окупаемость']['статус'][:15]])
    
    sc_table = Table(sc_data, colWidths=[30*mm, 40*mm, 40*mm, 40*mm])
    sc_table.setStyle(TableStyle([
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('BACKGROUND', (0,0), (-1,0), C_PURPLE),
        ('TEXTCOLOR', (0,0), (-1,0), C_WHITE),
        ('BACKGROUND', (1,1), (1,-1), HexColor('#FEE2E2')),
        ('BACKGROUND', (2,1), (2,-1), HexColor('#DBEAFE')),
        ('BACKGROUND', (3,1), (3,-1), HexColor('#DCFCE7')),
        ('ALIGN', (1,0), (-1,-1), 'CENTER'),
        ('GRID', (0,0), (-1,-1), 0.5, C_LIGHT),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(sc_table)
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 6: НАЛОГИ ──
    story.append(Paragraph("6. Налоги", styles['ZH1']))
    story.append(_kv_table([
        ['Режим:', tx['regime']],
        ['Ставка:', f"{tx['rate_pct']}%"],
    ]))
    if tx.get('b2b') == 'Да':
        story.append(Paragraph("B2B клиенты = риск НДС 16%!", styles['ZWarn']))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 7: РИСКИ ──
    story.append(Paragraph("7. РИСКИ — прочитайте внимательно", styles['ZH1']))
    risk_ins = [i for i in insights if i.get('insight_type') == 'risk']
    for ri in risk_ins[:5]:
        txt = ri.get('insight_text', '')
        if txt and str(txt) != 'nan':
            story.append(Paragraph(f"⚠ {txt}", styles['ZWarn']))
            story.append(Spacer(1, 2*mm))
    
    newbie = [i for i in insights if i.get('insight_type') == 'newbie_mistake']
    if newbie:
        story.append(Paragraph("Ошибки новичков:", styles['ZH2']))
        for n in newbie[:3]:
            txt = n.get('insight_text', '')
            if txt and str(txt) != 'nan':
                story.append(Paragraph(f"• {txt}", styles['ZBody']))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 8: АЛЬТЕРНАТИВЫ ──
    if alts:
        story.append(Paragraph("8. Рекомендации по улучшению", styles['ZH1']))
        for alt in alts:
            story.append(Paragraph(f"💡 {alt}", styles['ZTip']))
        story.append(Spacer(1, 5*mm))

    # ── БЛОК 9: МАРКЕТИНГ ──
    story.append(Paragraph("9. Как продвигать ваш бизнес", styles['ZH1']))
    main_ch = [m for m in marketing if m.get('priority') == 'основной'][:5]
    for ch in main_ch:
        name = ch.get('channel', '')
        effect = ch.get('expected_effect', '')
        if str(effect) != 'nan':
            story.append(Paragraph(f"✅ <b>{name}</b> — {effect}", styles['ZBody']))
        else:
            story.append(Paragraph(f"✅ <b>{name}</b>", styles['ZBody']))
    
    skip = [m for m in marketing if m.get('priority') == 'не_нужен'][:3]
    if skip:
        story.append(Paragraph("НЕ тратьте на:", styles['ZH2']))
        for ch in skip:
            story.append(Paragraph(f"❌ {ch.get('channel','')} — не работает для вашего формата", styles['ZSmall']))
    story.append(Spacer(1, 5*mm))

    # ── БЛОК 10: ВЕРДИКТ ──
    story.append(Paragraph("10. Итоговая оценка", styles['ZH1']))
    story.append(Paragraph(f"{vrd['emoji']} {vrd['text']}", 
                           ParagraphStyle('V', parent=styles['ZVerdict'], textColor=v_color)))
    if vrd['reasons']:
        for r in vrd['reasons']:
            story.append(Paragraph(f"• {r}", styles['ZBody']))
    
    # Лайфхаки
    lifehacks = [i for i in insights if i.get('insight_type') == 'lifehack']
    if lifehacks:
        story.append(Spacer(1, 5*mm))
        story.append(Paragraph("Полезные советы:", styles['ZH2']))
        for lh in lifehacks[:3]:
            txt = lh.get('insight_text', '')
            if txt and str(txt) != 'nan':
                story.append(Paragraph(f"💡 {txt}", styles['ZTip']))

    # ── ПОДВАЛ ──
    story.append(Spacer(1, 10*mm))
    story.append(HRFlowable(width="100%", thickness=1, color=C_PURPLE))
    story.append(Spacer(1, 3*mm))
    story.append(Paragraph("ZEREK · AI-аналитика для предпринимателей · @zerekai_bot · zerek.cc", styles['ZSmall']))
    story.append(Paragraph("Данный отчёт — экспресс-оценка на основе рыночных бенчмарков КЗ 2026. "
                           "Цифры ориентировочные и зависят от управления, локации, качества и маркетинга.", styles['ZSmall']))

    # BUILD
    doc.build(story)
    return output_path
