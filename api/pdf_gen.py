"""
ZEREK PDF generator — превращает результат quick-check-а в 11-страничный A4 PDF.
Рендер через ReportLab (чистый Python, без системных зависимостей).
Шрифты DejaVu Sans / DejaVu Sans Mono лежат в api/fonts/ и поддерживают кириллицу.
"""

from __future__ import annotations
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from io import BytesIO
from html import escape

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    KeepTogether, PageBreak, NextPageTemplate, Flowable,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.units import mm


# ═══════════════════════════════════════════════════════════
# Шрифты
# ═══════════════════════════════════════════════════════════

_FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONTS_REGISTERED = False


def _register_fonts_once():
    global _FONTS_REGISTERED
    if _FONTS_REGISTERED:
        return
    pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(_FONTS_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", os.path.join(_FONTS_DIR, "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono", os.path.join(_FONTS_DIR, "DejaVuSansMono.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuMono-Bold", os.path.join(_FONTS_DIR, "DejaVuSansMono-Bold.ttf")))
    registerFontFamily("DejaVuSans", normal="DejaVuSans", bold="DejaVuSans-Bold",
                       italic="DejaVuSans", boldItalic="DejaVuSans-Bold")
    registerFontFamily("DejaVuMono", normal="DejaVuMono", bold="DejaVuMono-Bold",
                       italic="DejaVuMono", boldItalic="DejaVuMono-Bold")
    _FONTS_REGISTERED = True


# ═══════════════════════════════════════════════════════════
# Цвета
# ═══════════════════════════════════════════════════════════

COL_BG_DARK = colors.HexColor("#0F172A")
COL_BG_DARK_2 = colors.HexColor("#1E293B")
COL_PRIMARY = colors.HexColor("#6366F1")
COL_PRIMARY_SOFT = colors.HexColor("#EEF2FF")
COL_TEXT = colors.HexColor("#1F2937")
COL_TEXT_MUTED = colors.HexColor("#6B7280")
COL_TEXT_DIM = colors.HexColor("#9CA3AF")
COL_TEXT_HEAD = colors.HexColor("#0F172A")
COL_BG_CARD = colors.HexColor("#F9FAFB")
COL_BORDER = colors.HexColor("#E5E7EB")
COL_GREEN = colors.HexColor("#16A34A")
COL_GREEN_DARK = colors.HexColor("#166534")
COL_GREEN_SOFT = colors.HexColor("#DCFCE7")
COL_YELLOW = colors.HexColor("#CA8A04")
COL_YELLOW_DARK = colors.HexColor("#854D0E")
COL_YELLOW_SOFT = colors.HexColor("#FEF9C3")
COL_RED = colors.HexColor("#DC2626")
COL_RED_DARK = colors.HexColor("#991B1B")
COL_RED_SOFT = colors.HexColor("#FEE2E2")
COL_WHITE = colors.HexColor("#FFFFFF")
COL_BLUE_SOFT = colors.HexColor("#DBEAFE")
COL_BLUE = colors.HexColor("#2563EB")


# ═══════════════════════════════════════════════════════════
# Форматтеры
# ═══════════════════════════════════════════════════════════

def _fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return "—"


def _fmt_k(n) -> str:
    try:
        v = int(n)
    except Exception:
        return "—"
    a = abs(v)
    if a >= 1_000_000:
        s = f"{v/1_000_000:.1f}".replace(".0", "")
        return f"{s} млн"
    if a >= 1_000:
        return f"{round(v/1_000)} тыс"
    return f"{v}"


def _pct_r(n) -> str:
    try:
        return f"{round(float(n))}%"
    except Exception:
        return "—"


def _e(s) -> str:
    if s is None:
        return ""
    return escape(str(s))


def _report_id() -> str:
    return "ZRK-" + uuid.uuid4().hex[:6].upper()


def _today_ru() -> str:
    tz = timezone(timedelta(hours=5))  # UTC+5
    return datetime.now(tz).strftime("%d.%m.%Y")


# ═══════════════════════════════════════════════════════════
# Справочники ниш
# ═══════════════════════════════════════════════════════════

NICHE_NAMES = {
    "AUTOSERVICE": "Автосервис", "BAKERY": "Пекарня", "BARBER": "Барбершоп",
    "BROW": "Брови", "CANTEEN": "Столовая", "CARWASH": "Автомойка",
    "CLEAN": "Клининг", "COFFEE": "Кофейня", "CONFECTION": "Кондитерская",
    "CYBERCLUB": "Компьютерный клуб", "DENTAL": "Стоматология",
    "DONER": "Донерная", "DRYCLEAN": "Химчистка", "FASTFOOD": "Фастфуд",
    "FITNESS": "Фитнес", "FLOWERS": "Цветы", "FRUITSVEGS": "Овощи и фрукты",
    "FURNITURE": "Мебель", "GROCERY": "Продукты", "KINDERGARTEN": "Детский сад",
    "LASH": "Ресницы", "MASSAGE": "Массаж", "NAIL": "Маникюр",
    "PHARMA": "Аптека", "PIZZA": "Пиццерия", "PVZ": "ПВЗ",
    "REPAIR_PHONE": "Ремонт телефонов", "SEMIFOOD": "Полуфабрикаты",
    "SUGARING": "Шугаринг", "SUSHI": "Суши", "TAILOR": "Ателье",
    "TIRE": "Шиномонтаж", "WATER": "Вода",
}


# ═══════════════════════════════════════════════════════════
# Метрики (подготовка плоского словаря)
# ═══════════════════════════════════════════════════════════

def _prep_metrics(result: dict, niche_id: str, ai_risks=None) -> dict:
    inp = result.get("input", {})
    oe = result.get("owner_economics") or {}
    b1 = result.get("block_1", {})
    b4 = result.get("block_4", {})
    b6 = result.get("block_6", {})
    b7 = result.get("block_7", {})
    b9 = result.get("block_9", {})
    b10 = result.get("block_10", {})

    opex_items = result.get("block_3", {}).get("items", [])
    personnel = ""
    for it in opex_items:
        name = (it.get("name") or "").lower()
        if "фот" in name or "зарпл" in name:
            personnel = it.get("note", "")
            break

    aud_match = re.search(r"ЦА:\s*([^\.]+)", b1.get("disclaimer", "") or "")
    audience = aud_match.group(1).strip() if aud_match else ""

    revenue = oe.get("revenue") or b1.get("revenue_monthly", 0)
    cogs = oe.get("cogs") or 0
    gross = oe.get("gross") or 0
    opex_breakdown = oe.get("opex_breakdown") or {}
    profit_before_tax = oe.get("profit_before_tax") or 0
    tax_amount = oe.get("tax_amount") or 0
    social = oe.get("social_payments") or 45000
    net_in_pocket = oe.get("net_in_pocket") or 0
    stress = oe.get("stress_test") or []

    inv_min = b4.get("investment_min") or b4.get("total") or 0
    buffer_total = int((oe.get("opex_total", 0) + social) * 3) if oe else 0

    payback = oe.get("owner_payback_months")

    return {
        "city_name": inp.get("city_name", ""),
        "niche_id": niche_id,
        "niche_name": NICHE_NAMES.get(niche_id, niche_id),
        "format_name": inp.get("format_name") or inp.get("format_id", ""),
        "cls": inp.get("class", ""),
        "area_m2": inp.get("area_m2", ""),
        "loc_type": inp.get("loc_type", ""),
        "personnel": personnel,
        "audience": audience,
        "checkMed": b1.get("check_med", 0),
        "trafficMed": b1.get("traffic_med", 0),
        "locomotive": b1.get("locomotive", ""),
        "revenue": revenue, "cogs": cogs, "gross": gross,
        "opex_breakdown": opex_breakdown,
        "opex_total": oe.get("opex_total", 0),
        "profitBeforeTax": profit_before_tax,
        "tax": tax_amount,
        "taxRatePct": oe.get("tax_rate_pct") or b7.get("rate_pct", 4),
        "taxRegime": b7.get("regime", "Упрощёнка"),
        "social": social,
        "net_in_pocket": net_in_pocket,
        "stress": stress,
        "invMin": inv_min,
        "bufferTotal": buffer_total,
        "capexItems": b4.get("items", []),
        "breakEven": b6.get("tb_revenue", 0),
        "safety_margin": round(b6.get("safety_margin", 0)),
        "tbChecksDay": b6.get("tb_checks_day", 0),
        "payback": payback,
        "verdict_color": b10.get("verdict_color", "yellow"),
        "verdict_text": b10.get("verdict_text", ""),
        "ai_risks": ai_risks or [],
    }


# ═══════════════════════════════════════════════════════════
# Стили
# ═══════════════════════════════════════════════════════════

def _styles():
    return {
        "body": ParagraphStyle(
            "body", fontName="DejaVuSans", fontSize=10.5, leading=15,
            textColor=COL_TEXT, alignment=TA_LEFT, spaceAfter=4,
        ),
        "body_muted": ParagraphStyle(
            "body_muted", fontName="DejaVuSans", fontSize=9.5, leading=14,
            textColor=COL_TEXT_MUTED, alignment=TA_LEFT, spaceAfter=4,
        ),
        "kicker": ParagraphStyle(
            "kicker", fontName="DejaVuSans-Bold", fontSize=8.5, leading=11,
            textColor=COL_PRIMARY, spaceAfter=4,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="DejaVuSans-Bold", fontSize=20, leading=25,
            textColor=COL_TEXT_HEAD, spaceBefore=2, spaceAfter=6,
        ),
        "h3": ParagraphStyle(
            "h3", fontName="DejaVuSans-Bold", fontSize=13, leading=17,
            textColor=COL_TEXT_HEAD, spaceBefore=6, spaceAfter=4,
        ),
        "h4": ParagraphStyle(
            "h4", fontName="DejaVuSans-Bold", fontSize=11, leading=15,
            textColor=colors.HexColor("#374151"), spaceBefore=4, spaceAfter=2,
        ),
        "small": ParagraphStyle(
            "small", fontName="DejaVuSans", fontSize=8.5, leading=12,
            textColor=COL_TEXT_MUTED,
        ),
        "mono": ParagraphStyle(
            "mono", fontName="DejaVuMono-Bold", fontSize=11, leading=14,
            textColor=COL_TEXT_HEAD, alignment=TA_RIGHT,
        ),
        "note": ParagraphStyle(
            "note", fontName="DejaVuSans", fontSize=9.5, leading=14,
            textColor=colors.HexColor("#3730A3"), alignment=TA_LEFT,
        ),
        "cover_brand": ParagraphStyle(
            "cover_brand", fontName="DejaVuSans-Bold", fontSize=13, leading=17,
            textColor=COL_WHITE, alignment=TA_LEFT,
        ),
        "cover_brand_sub": ParagraphStyle(
            "cover_brand_sub", fontName="DejaVuSans", fontSize=9.5, leading=13,
            textColor=colors.HexColor("#A1A1AA"), alignment=TA_LEFT,
        ),
        "cover_badge": ParagraphStyle(
            "cover_badge", fontName="DejaVuSans-Bold", fontSize=10, leading=14,
            textColor=colors.HexColor("#C7D2FE"), alignment=TA_LEFT,
        ),
        "cover_h1": ParagraphStyle(
            "cover_h1", fontName="DejaVuSans-Bold", fontSize=36, leading=42,
            textColor=COL_WHITE, alignment=TA_LEFT, spaceAfter=8,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontName="DejaVuSans", fontSize=13, leading=18,
            textColor=colors.HexColor("#CBD5E1"), alignment=TA_LEFT,
        ),
        "cover_meta": ParagraphStyle(
            "cover_meta", fontName="DejaVuSans", fontSize=10, leading=14,
            textColor=colors.HexColor("#CBD5E1"), alignment=TA_LEFT,
        ),
        "cover_foot": ParagraphStyle(
            "cover_foot", fontName="DejaVuSans", fontSize=9, leading=12,
            textColor=colors.HexColor("#94A3B8"), alignment=TA_LEFT,
        ),
        "hero_num": ParagraphStyle(
            "hero_num", fontName="DejaVuMono-Bold", fontSize=38, leading=44,
            textColor=COL_GREEN, alignment=TA_CENTER,
        ),
        "hero_num_red": ParagraphStyle(
            "hero_num_red", fontName="DejaVuMono-Bold", fontSize=38, leading=44,
            textColor=COL_RED, alignment=TA_CENTER,
        ),
        "hero_label": ParagraphStyle(
            "hero_label", fontName="DejaVuSans-Bold", fontSize=9, leading=12,
            textColor=COL_TEXT_MUTED, alignment=TA_CENTER, spaceAfter=3,
        ),
        "hero_unit": ParagraphStyle(
            "hero_unit", fontName="DejaVuSans", fontSize=11, leading=14,
            textColor=COL_TEXT_MUTED, alignment=TA_CENTER,
        ),
        "verdict_text": ParagraphStyle(
            "verdict_text", fontName="DejaVuSans-Bold", fontSize=12.5, leading=16,
            textColor=COL_TEXT_HEAD, alignment=TA_LEFT,
        ),
    }


# ═══════════════════════════════════════════════════════════
# Page-level декораторы (onPage callbacks)
# ═══════════════════════════════════════════════════════════

PAGE_W, PAGE_H = A4
MARGIN_X = 16 * mm
MARGIN_TOP = 20 * mm
MARGIN_BOTTOM = 22 * mm
DISCLAIMER_TEXT = (
    "Это экспресс-оценка на основе усреднённых данных рынка Казахстана. "
    "Реальные показатели зависят от локации, команды и ситуации. Для запуска — детальная финмодель."
)


def _draw_cover_bg(canv, doc):
    canv.saveState()
    # Весь лист — тёмно-синий градиент-имитация (два сплошных прямоугольника)
    canv.setFillColor(COL_BG_DARK)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Небольшая тёмно-фиолетовая заливка в нижней трети для глубины
    canv.setFillColor(colors.HexColor("#1E1B4B"))
    canv.rect(0, 0, PAGE_W, PAGE_H * 0.35, fill=1, stroke=0)
    canv.setFillColor(colors.HexColor("#312E81"))
    canv.rect(0, 0, PAGE_W * 0.55, PAGE_H * 0.12, fill=1, stroke=0)
    canv.restoreState()


def _draw_content_chrome(canv, doc):
    canv.saveState()
    # Top-left brand, top-right page number
    canv.setFont("DejaVuSans", 8.5)
    canv.setFillColor(COL_TEXT_DIM)
    canv.drawString(MARGIN_X, PAGE_H - 12 * mm, "ZEREK · Экспресс-оценка")
    canv.setFont("DejaVuMono", 8.5)
    canv.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 12 * mm, f"{canv.getPageNumber()}")
    # Thin top rule
    canv.setStrokeColor(COL_BORDER)
    canv.setLineWidth(0.3)
    canv.line(MARGIN_X, PAGE_H - 14 * mm, PAGE_W - MARGIN_X, PAGE_H - 14 * mm)

    # Bottom disclaimer (wrap to 2 lines if needed)
    canv.setFont("DejaVuSans", 7.2)
    canv.setFillColor(COL_TEXT_DIM)
    # Split into two lines for readability
    line1 = "Это экспресс-оценка на основе усреднённых данных рынка Казахстана."
    line2 = "Реальные показатели зависят от локации, команды и ситуации. Для запуска — детальная финмодель."
    canv.drawCentredString(PAGE_W / 2, 12 * mm, line1)
    canv.drawCentredString(PAGE_W / 2, 9 * mm, line2)
    canv.restoreState()


# ═══════════════════════════════════════════════════════════
# Story builders
# ═══════════════════════════════════════════════════════════

def _content_w() -> float:
    return PAGE_W - 2 * MARGIN_X


def _cover_story(m: dict, report_id: str, date_str: str, st: dict) -> list:
    project = f"{m['niche_name']} · {m['city_name']}"
    sub = (
        "Оценка жизнеспособности бизнес-идеи на основе данных рынка "
        f"{_e(m['city_name'])} и практики малого бизнеса Казахстана."
    )
    # На cover-шаблоне весь фрейм — вся страница, отступы делаем вручную через Spacer+Table.
    # Собираем через одну большую Table с внешними отступами.
    top = Table([[Paragraph("ZEREK", st["cover_brand"])],
                 [Paragraph("AI-платформа бизнес-аналитики · Казахстан", st["cover_brand_sub"])]],
                colWidths=[PAGE_W - 40 * mm])
    top.setStyle(TableStyle([("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
                             ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 2)]))

    middle = Table([
        [Paragraph("ЭКСПРЕСС-ОЦЕНКА НИШИ", st["cover_badge"])],
        [Spacer(1, 10)],
        [Paragraph(_e(project), st["cover_h1"])],
        [Spacer(1, 6)],
        [Paragraph(sub, st["cover_sub"])],
    ], colWidths=[PAGE_W - 40 * mm])
    middle.setStyle(TableStyle([("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
                                ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 0)]))

    meta = Table([
        [Paragraph(f"Дата формирования: <b>{_e(date_str)}</b>", st["cover_meta"])],
        [Paragraph(f"Номер отчёта: <b>{_e(report_id)}</b>", st["cover_meta"])],
        [Spacer(1, 14)],
        [Paragraph("ZEREK.CC · @ZEREKAI_BOT", st["cover_foot"])],
    ], colWidths=[PAGE_W - 40 * mm])
    meta.setStyle(TableStyle([("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
                              ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 0)]))

    # Big outer frame: top-left / middle / bottom-left stacked
    outer = Table([
        [top],
        [Spacer(1, 110)],
        [middle],
        [Spacer(1, 110)],
        [meta],
    ], colWidths=[PAGE_W - 40 * mm])
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0),
        ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    # Spacers to add top/bottom margin within the frame (since cover frame has zero padding)
    return [Spacer(1, 28 * mm), Indenter(outer, left=20 * mm)]


class Indenter(Flowable):
    """Wrap a flowable with horizontal indent (since cover frame is full-bleed)."""
    def __init__(self, child, left=0, right=0):
        super().__init__()
        self.child = child
        self.left = left
        self.right = right

    def wrap(self, aW, aH):
        w, h = self.child.wrap(aW - self.left - self.right, aH)
        self.width = w + self.left + self.right
        self.height = h
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        self.canv.translate(self.left, 0)
        self.child.drawOn(self.canv, 0, 0)
        self.canv.restoreState()


def _verdict_table(m: dict, st: dict) -> Table:
    vc = m["verdict_color"]
    label = {"green": "Бизнес жизнеспособен",
             "yellow": "Бизнес возможен, но есть риски",
             "red": "Высокий риск — рекомендуем пересмотреть"}.get(vc, "Бизнес возможен, но есть риски")
    icon = {"green": "✓", "yellow": "⚠", "red": "✕"}.get(vc, "⚠")
    bg = {"green": COL_GREEN_SOFT, "yellow": COL_YELLOW_SOFT, "red": COL_RED_SOFT}.get(vc, COL_YELLOW_SOFT)
    txt = {"green": COL_GREEN_DARK, "yellow": COL_YELLOW_DARK, "red": COL_RED_DARK}.get(vc, COL_YELLOW_DARK)
    stripe = {"green": COL_GREEN, "yellow": COL_YELLOW, "red": COL_RED}.get(vc, COL_YELLOW)

    icon_cell = Paragraph(
        f'<font size="22" color="{txt.hexval()}">{icon}</font>',
        ParagraphStyle("icon", fontName="DejaVuSans-Bold", fontSize=22, alignment=TA_CENTER),
    )
    label_cell = Paragraph(
        f'<font color="{txt.hexval()}"><b>{_e(label)}</b></font>',
        st["verdict_text"],
    )
    t = Table([[icon_cell, label_cell]], colWidths=[15 * mm, _content_w() - 15 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), bg),
        ("LINEBEFORE", (0, 0), (0, 0), 5, stripe),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


def _hero_number_box(m: dict, st: dict) -> Table:
    pocket = m["net_in_pocket"]
    hero_style = st["hero_num_red"] if pocket < 0 else st["hero_num"]
    if pocket < 0:
        hero_style = st["hero_num_red"]

    t = Table([
        [Paragraph("В КАРМАН СОБСТВЕННИКУ", st["hero_label"])],
        [Paragraph(f"{_fmt_k(pocket)} ₸", hero_style)],
        [Paragraph("в месяц, после всех налогов и соцплатежей", st["hero_unit"])],
    ], colWidths=[_content_w()])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COL_BG_CARD),
        ("BOX", (0, 0), (-1, -1), 0.5, COL_BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (0, 0), 14),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("TOPPADDING", (0, 2), (-1, 2), 2),
        ("BOTTOMPADDING", (0, 2), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, 1), 2),
    ]))
    return t


def _stats_row(m: dict) -> Table:
    def cell(label, value):
        return [
            Paragraph(
                f'<font name="DejaVuSans-Bold" size="8" color="#6B7280">{_e(label).upper()}</font>',
                ParagraphStyle("x", fontName="DejaVuSans", fontSize=8, leading=10, alignment=TA_CENTER),
            ),
            Paragraph(
                f'<font name="DejaVuMono-Bold" size="13" color="#111827">{_e(value)}</font>',
                ParagraphStyle("y", fontName="DejaVuMono-Bold", fontSize=13, leading=16, alignment=TA_CENTER),
            ),
        ]

    payback = f"{m['payback']} мес" if m.get("payback") else "—"
    cells = [
        cell("Окупаемость", payback),
        cell("Старт", f"{_fmt_k(m['invMin'])} ₸"),
        cell("Брейкевен", f"{_fmt_k(m['breakEven'])} ₸"),
        cell("Запас", f"{m['safety_margin']}%"),
    ]

    col_w = (_content_w() - 3 * 4) / 4
    data = [[
        Table([[cells[i][0]], [cells[i][1]]], colWidths=[col_w])
        for i in range(4)
    ]]
    t = Table(data, colWidths=[col_w] * 4)
    # inner style applied to sub-tables via TableStyle on sub-tables
    for inner in [d for row in data for d in row]:
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COL_BG_CARD),
            ("BOX", (0, 0), (-1, -1), 0.5, COL_BORDER),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
    t.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _summary_story(m: dict, st: dict) -> list:
    findings = []
    if m["safety_margin"] < 20:
        findings.append(f"Запас прочности {m['safety_margin']}% — низкий. Любой провал в трафике ведёт к убытку.")
    elif m["safety_margin"] >= 50:
        findings.append(f"Запас прочности {m['safety_margin']}% — хороший. Бизнес устойчив к просадкам.")
    if m.get("payback") and m["payback"] <= 12:
        findings.append(f"Окупаемость ~{m['payback']} мес — быстро. Меньше риска.")
    elif m.get("payback") and m["payback"] > 24:
        findings.append(f"Окупаемость ~{m['payback']} мес — долго. Нужна подушка и терпение.")
    if m["stress"] and m["stress"][0].get("net_in_pocket", 0) < 0:
        findings.append("В плохом сценарии бизнес уходит в минус — нужна дифференциация или снижение аренды.")
    if not findings:
        findings.append("Показатели в пределах нормы для вашей ниши.")

    items = [Paragraph(f"• {_e(t)}", st["body"]) for t in findings[:3]]

    note = Paragraph(
        "<b>Как читать отчёт.</b> Далее — паспорт проекта, экономика одного клиента, месячный P&amp;L, стартовые вложения, стресс-тест и риски ниши. В конце — чек-лист на первый месяц и глоссарий.",
        st["note"],
    )

    return [
        Paragraph("СТРАНИЦА 2 · СВОДКА", st["kicker"]),
        Paragraph("Главное за 60 секунд", st["h2"]),
        Spacer(1, 4),
        _verdict_table(m, st),
        Spacer(1, 10),
        _hero_number_box(m, st),
        Spacer(1, 8),
        _stats_row(m),
        Spacer(1, 12),
        Paragraph("Топ-3 вывода", st["h3"]),
        *items,
        Spacer(1, 10),
        _note_box(note),
    ]


def _note_box(inner_para) -> Table:
    t = Table([[inner_para]], colWidths=[_content_w()])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COL_PRIMARY_SOFT),
        ("LINEBEFORE", (0, 0), (0, 0), 3, COL_PRIMARY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def _kv_table(pairs: list, st: dict, col1_frac=0.4) -> Table:
    cw1 = _content_w() * col1_frac
    cw2 = _content_w() * (1 - col1_frac)
    data = []
    for k, v in pairs:
        data.append([
            Paragraph(_e(k), st["body_muted"]),
            Paragraph(_e(v), ParagraphStyle("kv", parent=st["body"], fontName="DejaVuSans-Bold")),
        ])
    t = Table(data, colWidths=[cw1, cw2])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("BACKGROUND", (0, 0), (-1, -1), COL_BG_CARD),
    ]
    for i in range(len(data) - 1):
        style.append(("LINEBELOW", (0, i), (-1, i), 0.4, COL_BORDER))
    t.setStyle(TableStyle(style))
    return t


def _passport_story(m: dict, st: dict) -> list:
    pairs = [
        ("Город", m["city_name"]),
        ("Ниша", m["niche_name"]),
        ("Формат", m["format_name"]),
        ("Класс оснащения", m["cls"]),
        ("Площадь", f"{m['area_m2']} м²"),
        ("Локация", m["loc_type"]),
    ]
    if m["personnel"]:
        pairs.append(("Штат", m["personnel"]))
    if m["audience"]:
        pairs.append(("Целевая аудитория", m["audience"]))

    portrait_p1 = (
        f"Это {_e(m['niche_name'].lower())} в городе {_e(m['city_name'])}, "
        f"формат «{_e(m['format_name'])}», класс оснащения «{_e(m['cls'])}». "
        f"Площадь {_e(str(m['area_m2']))} м², локация — {_e(m['loc_type'])}."
    )
    portrait_p2 = (
        f"При среднем чеке <b>{_fmt(m['checkMed'])} ₸</b> и трафике "
        f"<b>{_e(str(m['trafficMed']))}</b> клиентов в день расчётная "
        f"месячная выручка — <b>{_fmt_k(m['revenue'])} ₸</b>."
    )
    portrait_p3 = (
        f"Локомотив продаж — <b>{_e(m['locomotive'] or '—')}</b>: "
        f"товар или услуга, которая приводит клиентов и формирует базовую выручку."
    )

    return [
        Paragraph("СТРАНИЦА 3 · ПАСПОРТ ПРОЕКТА", st["kicker"]),
        Paragraph("Что именно оцениваем", st["h2"]),
        _kv_table(pairs, st),
        Spacer(1, 12),
        Paragraph("Портрет проекта", st["h3"]),
        Paragraph(portrait_p1, st["body"]),
        Paragraph(portrait_p2, st["body"]),
        Paragraph(portrait_p3, st["body"]),
    ]


def _unit_econ_story(m: dict, st: dict) -> list:
    revenue = max(m["revenue"], 1)
    cost_per_tx = round(m["checkMed"] * (m["cogs"] / revenue))
    profit_per_tx = m["checkMed"] - cost_per_tx
    daily = 15 if m["trafficMed"] < 30 else int(m["trafficMed"])
    daily_gross = profit_per_tx * daily

    def row(label, value, color_hex, bold=False, bg=None):
        name = "DejaVuSans-Bold" if bold else "DejaVuSans"
        left = Paragraph(
            f'<font name="{name}" size="11" color="#1F2937">{_e(label)}</font>',
            ParagraphStyle("l", fontName=name, fontSize=11, leading=14),
        )
        right = Paragraph(
            f'<font name="DejaVuMono-Bold" size="14" color="{color_hex}">{_e(value)}</font>',
            ParagraphStyle("r", fontName="DejaVuMono-Bold", fontSize=14, leading=17, alignment=TA_RIGHT),
        )
        t = Table([[left, right]], colWidths=[_content_w() * 0.6, _content_w() * 0.4])
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 0), (-1, -1), bg or COL_BG_CARD),
        ]
        if bold:
            style.append(("BOX", (0, 0), (-1, -1), 1.5, COL_GREEN))
        t.setStyle(TableStyle(style))
        return t

    op = Paragraph(
        '<font size="8" color="#9CA3AF">МИНУС</font>',
        ParagraphStyle("op", fontName="DejaVuSans-Bold", fontSize=8, leading=12, alignment=TA_CENTER),
    )
    op2 = Paragraph(
        '<font size="8" color="#9CA3AF">РАВНО</font>',
        ParagraphStyle("op", fontName="DejaVuSans-Bold", fontSize=8, leading=12, alignment=TA_CENTER),
    )

    note_text = (
        f"<b>Что это значит.</b> Если в день приходит {daily} клиентов — "
        f"это <b>{_fmt(daily_gross)} ₸ в день</b> «наценки после себестоимости». "
        f"Но из неё ещё нужно заплатить аренду, зарплату, налоги, соцплатежи — "
        f"и только потом остаток идёт в карман."
    )

    cogs_pct_of_rev = round(m["cogs"] / revenue * 100)
    gross_pct = 100 - cogs_pct_of_rev
    structure_p1 = (
        f"Себестоимость составляет <b>{cogs_pct_of_rev}%</b> от выручки — "
        f"прямые расходы на товар/сырьё, растут пропорционально продажам."
    )
    structure_p2 = (
        f"Остальное (<b>{gross_pct}%</b>) — это «наценка после себестоимости». "
        f"Из неё покрываются все остальные расходы бизнеса."
    )

    return [
        Paragraph("СТРАНИЦА 4 · ЭКОНОМИКА ОДНОГО КЛИЕНТА", st["kicker"]),
        Paragraph("Сколько вы зарабатываете с одного чека", st["h2"]),
        Spacer(1, 6),
        row("Средний чек", f"{_fmt(m['checkMed'])} ₸", "#111827"),
        Spacer(1, 2), op, Spacer(1, 2),
        row("Себестоимость чека (товар / материалы)", f"−{_fmt(cost_per_tx)} ₸", "#DC2626"),
        Spacer(1, 2), op2, Spacer(1, 2),
        row("Заработок с клиента", f"{_fmt(profit_per_tx)} ₸", "#166534", bold=True, bg=COL_GREEN_SOFT),
        Spacer(1, 10),
        _note_box(Paragraph(note_text, st["note"])),
        Spacer(1, 10),
        Paragraph("Структура себестоимости", st["h3"]),
        Paragraph(structure_p1, st["body"]),
        Paragraph(structure_p2, st["body"]),
    ]


def _pnl_story(m: dict, st: dict) -> list:
    ob = m["opex_breakdown"]
    other = ob.get("other", 0)

    # Собираем таблицу-водопад
    rows = [
        ("Выручка в месяц", m["revenue"], "pos"),
        ("Себестоимость (товар / материалы)", -m["cogs"], "neg"),
        ("Наценка после себестоимости", m["gross"], "sub"),
        ("Аренда", -ob.get("rent", 0), "neg"),
        ("ФОТ (зарплаты + налоги работодателя)", -ob.get("fot", 0), "neg"),
        ("Маркетинг", -ob.get("marketing", 0), "neg"),
        ("Коммуналка", -ob.get("utilities", 0), "neg"),
        ("Расходники, софт, прочее", -other, "neg"),
        ("Прибыль до налогов", m["profitBeforeTax"], "sub"),
        (f"Налог {m['taxRegime']} ({m['taxRatePct']}%)", -m["tax"], "neg"),
        ("Соцплатежи собственника (ОПВ + ОСМС + СО)", -m["social"], "neg"),
        ("В карман собственнику", m["net_in_pocket"], "grand"),
    ]

    # Build data rows (label + value) as Paragraph cells
    data = []
    styles_rows = []
    for idx, (label, val, kind) in enumerate(rows):
        if kind == "grand":
            lbl_font = "DejaVuSans-Bold"; lbl_color = "#166534"; lbl_size = 12
            val_font = "DejaVuMono-Bold"; val_color = "#166534"; val_size = 15
        elif kind == "sub":
            lbl_font = "DejaVuSans-Bold"; lbl_color = "#111827"; lbl_size = 11
            val_font = "DejaVuMono-Bold"; val_color = "#111827"; val_size = 12
        elif kind == "neg":
            lbl_font = "DejaVuSans"; lbl_color = "#374151"; lbl_size = 10
            val_font = "DejaVuMono-Bold"; val_color = "#DC2626"; val_size = 11
        elif kind == "pos":
            lbl_font = "DejaVuSans-Bold"; lbl_color = "#111827"; lbl_size = 11
            val_font = "DejaVuMono-Bold"; val_color = "#15803D"; val_size = 12
        else:
            lbl_font = "DejaVuSans"; lbl_color = "#374151"; lbl_size = 10
            val_font = "DejaVuMono-Bold"; val_color = "#111827"; val_size = 11

        sign = "−" if val < 0 else ""
        val_str = f"{sign}{_fmt(abs(val))} ₸"
        lp = Paragraph(
            f'<font name="{lbl_font}" color="{lbl_color}" size="{lbl_size}">{_e(label)}</font>',
            ParagraphStyle("p", fontName=lbl_font, fontSize=lbl_size, leading=lbl_size + 3),
        )
        vp = Paragraph(
            f'<font name="{val_font}" color="{val_color}" size="{val_size}">{_e(val_str)}</font>',
            ParagraphStyle("v", fontName=val_font, fontSize=val_size, leading=val_size + 3, alignment=TA_RIGHT),
        )
        data.append([lp, vp])

        if kind == "grand":
            styles_rows.append(("BACKGROUND", (0, idx), (-1, idx), COL_GREEN_SOFT))
            styles_rows.append(("BOX", (0, idx), (-1, idx), 1.5, COL_GREEN))
            styles_rows.append(("TOPPADDING", (0, idx), (-1, idx), 12))
            styles_rows.append(("BOTTOMPADDING", (0, idx), (-1, idx), 12))
        elif kind == "sub":
            styles_rows.append(("BACKGROUND", (0, idx), (-1, idx), COL_BG_CARD))
            styles_rows.append(("LINEABOVE", (0, idx), (-1, idx), 0.8, COL_BORDER))
            styles_rows.append(("LINEBELOW", (0, idx), (-1, idx), 0.8, COL_BORDER))
        elif kind == "pos":
            styles_rows.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#F0FDF4")))
        elif kind == "neg":
            styles_rows.append(("BACKGROUND", (0, idx), (-1, idx), colors.HexColor("#FEF2F2")))

    t = Table(data, colWidths=[_content_w() * 0.65, _content_w() * 0.35])
    base_style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(base_style + styles_rows))

    note_text = (
        "<b>Важно.</b> Налог УСН платится с <i>выручки</i>, не с прибыли — даже если "
        "бизнес в минус, налог идёт. Соцплатежи собственника ИП платит за себя независимо "
        "от дохода: это обязательные пенсионные, медстрах и соцотчисления."
    )
    return [
        Paragraph("СТРАНИЦА 5 · МЕСЯЧНАЯ ЭКОНОМИКА", st["kicker"]),
        Paragraph("Куда уходят деньги", st["h2"]),
        Paragraph(
            "Полный P&amp;L вашего бизнеса в базовом сценарии — выручка, расходы, налоги и что остаётся.",
            st["body_muted"],
        ),
        Spacer(1, 6),
        t,
        Spacer(1, 10),
        _note_box(Paragraph(note_text, st["note"])),
    ]


def _invest_story(m: dict, st: dict) -> list:
    # CAPEX строк
    capex_rows = []
    for it in m["capexItems"]:
        capex_rows.append((it.get("name", ""), f"{_fmt(it.get('amount', 0))} ₸"))
    capex_rows.append(("Итого CAPEX", f"{_fmt(m['invMin'])} ₸"))

    buffer_total = m["bufferTotal"]
    buffer_rows = [
        ("Резерв на 3 месяца расходов", f"{_fmt(buffer_total)} ₸"),
        ("Подушка всего", f"{_fmt(buffer_total)} ₸"),
    ]

    grand_total = m["invMin"] + buffer_total
    grand_row = Table(
        [[Paragraph(
            '<font name="DejaVuSans-Bold" color="#3730A3" size="13">Всего на старт (с подушкой)</font>',
            ParagraphStyle("g", fontName="DejaVuSans-Bold", fontSize=13, leading=16)),
          Paragraph(
            f'<font name="DejaVuMono-Bold" color="#3730A3" size="15">{_fmt(grand_total)} ₸</font>',
            ParagraphStyle("gv", fontName="DejaVuMono-Bold", fontSize=15, leading=18, alignment=TA_RIGHT))]],
        colWidths=[_content_w() * 0.65, _content_w() * 0.35],
    )
    grand_row.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), COL_PRIMARY_SOFT),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOX", (0, 0), (-1, -1), 1.5, COL_PRIMARY),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))

    note_text = (
        "<b>Почему подушка критична.</b> 80% закрытий малого бизнеса — в первые 6 месяцев. "
        "Главная причина не «мало клиентов», а <i>кончились деньги до того, как бизнес вышел в плюс</i>. "
        "Резерв на 3 месяца — минимум; 6 месяцев — комфорт."
    )

    return [
        Paragraph("СТРАНИЦА 6 · СТАРТОВЫЕ ВЛОЖЕНИЯ", st["kicker"]),
        Paragraph("Что нужно вложить до открытия", st["h2"]),
        Paragraph("Оборудование и ремонт", st["h3"]),
        _kv_table(capex_rows, st, col1_frac=0.65),
        Spacer(1, 10),
        Paragraph("Подушка безопасности", st["h3"]),
        Paragraph(
            "Деньги сверх CAPEX, которые позволят работать, даже если первые месяцы "
            "выручка будет ниже плана.",
            st["body_muted"],
        ),
        _kv_table(buffer_rows, st, col1_frac=0.65),
        Spacer(1, 12),
        grand_row,
        Spacer(1, 10),
        _note_box(Paragraph(note_text, st["note"])),
    ]


def _stress_story(m: dict, st: dict) -> list:
    stress = m["stress"]
    if len(stress) < 3:
        return []
    s_bad, s_base, s_good = stress[0], stress[1], stress[2]

    def scen_card(kind, s):
        col_map = {"red": (COL_RED, COL_RED_SOFT), "blue": (COL_PRIMARY, COL_PRIMARY_SOFT),
                   "green": (COL_GREEN, COL_GREEN_SOFT)}
        stripe, bg = col_map.get(s.get("color", "blue"), (COL_PRIMARY, COL_PRIMARY_SOFT))
        pocket = s.get("net_in_pocket", 0)
        sign = "−" if pocket < 0 else ""
        val_str = f"{sign}{_fmt_k(abs(pocket))} ₸/мес"
        title_p = Paragraph(
            f'<font name="DejaVuSans-Bold" size="12" color="#0F172A">{_e(s["label"])}</font>',
            ParagraphStyle("tp", fontName="DejaVuSans-Bold", fontSize=12, leading=15),
        )
        val_p = Paragraph(
            f'<font name="DejaVuMono-Bold" size="15" color="{stripe.hexval()}">{_e(val_str)}</font>',
            ParagraphStyle("vp", fontName="DejaVuMono-Bold", fontSize=15, leading=18, alignment=TA_RIGHT),
        )
        params_p = Paragraph(
            f'<font name="DejaVuSans" size="9" color="#6B7280">{_e(s.get("params", ""))}</font>',
            ParagraphStyle("pp", fontName="DejaVuSans", fontSize=9, leading=12),
        )
        inner = Table(
            [[title_p, val_p], [params_p, ""]],
            colWidths=[_content_w() * 0.6, _content_w() * 0.4],
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), COL_BG_CARD),
            ("LINEBEFORE", (0, 0), (0, -1), 4, stripe),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 14),
            ("RIGHTPADDING", (0, 0), (-1, -1), 14),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("SPAN", (0, 1), (-1, 1)),
        ]))
        return inner

    note_text = (
        "<b>Как читать.</b> Если даже в сценарии «всё плохо» вы не уходите в минус — "
        "бизнес устойчив и переживёт плохой квартал. Если уходите в минус — нужна подушка "
        "на покрытие убытков или пересмотр формата (меньше аренда, другой класс, другая локация)."
    )

    return [
        Paragraph("СТРАНИЦА 7 · СТРЕСС-ТЕСТ", st["kicker"]),
        Paragraph("Что будет, если рынок просядет", st["h2"]),
        Paragraph(
            "Проверка устойчивости бизнеса. Каждый сценарий меняет ключевые параметры и пересчитывает «в карман».",
            st["body_muted"],
        ),
        Spacer(1, 8),
        scen_card("red", s_bad),
        Spacer(1, 6),
        scen_card("blue", s_base),
        Spacer(1, 6),
        scen_card("green", s_good),
        Spacer(1, 10),
        _note_box(Paragraph(note_text, st["note"])),
    ]


def _risks_story(m: dict, st: dict) -> list:
    risks = m.get("ai_risks") or []
    if not risks:
        return []

    story = [
        Paragraph("СТРАНИЦА 8 · РИСКИ НИШИ", st["kicker"]),
        Paragraph("Почему закрываются такие бизнесы", st["h2"]),
        Paragraph(
            "7 самых денежно-критичных рисков для вашей ниши — из практики закрывшихся бизнесов. "
            "Для каждого: описание + действие, как защититься.",
            st["body_muted"],
        ),
        Spacer(1, 8),
    ]

    for idx, r in enumerate(risks[:7]):
        title_p = Paragraph(
            f'<font name="DejaVuSans-Bold" size="12" color="#111827">⚠ {_e(r.get("title", ""))}</font>',
            ParagraphStyle("rt", fontName="DejaVuSans-Bold", fontSize=12, leading=15),
        )
        body_p = Paragraph(
            f'<font name="DejaVuSans" size="10" color="#374151">{_e(r.get("body", ""))}</font>',
            ParagraphStyle("rb", fontName="DejaVuSans", fontSize=10, leading=14),
        )
        protect_text = r.get("protect", "")
        if protect_text:
            protect_p = Paragraph(
                f'<font name="DejaVuSans-Bold" size="9.5" color="#15803D">Как защититься:</font> '
                f'<font name="DejaVuSans" size="9.5" color="#111827">{_e(protect_text)}</font>',
                ParagraphStyle("rp", fontName="DejaVuSans", fontSize=9.5, leading=13),
            )
            rows_data = [[title_p], [body_p], [protect_p]]
        else:
            rows_data = [[title_p], [body_p]]

        card = Table(rows_data, colWidths=[_content_w()])
        cstyle = [
            ("BACKGROUND", (0, 0), (-1, -1), COL_BG_CARD),
            ("LINEBEFORE", (0, 0), (0, -1), 4, COL_YELLOW),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, 0), 10),
            ("TOPPADDING", (0, 1), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, -1), (-1, -1), 10),
        ]
        if protect_text:
            cstyle.append(("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#F0FDF4")))
            cstyle.append(("TOPPADDING", (0, 2), (-1, 2), 6))
            cstyle.append(("BOTTOMPADDING", (0, 2), (-1, 2), 8))
        card.setStyle(TableStyle(cstyle))

        story.append(KeepTogether([card, Spacer(1, 6)]))

    return story


def _checklist_story(st: dict) -> list:
    weeks = [
        ("Неделя 1 · Локация и рынок", [
            "Проверить локацию лично в часы пик (среда 18:00–20:00, выходные)",
            "Сосчитать трафик вручную в 2-3 часовых слота",
            "Обойти 5 конкурентов в радиусе 2 км — цены, ассортимент, загрузка",
            "Получить 3 коммерческих предложения по аренде",
        ]),
        ("Неделя 2 · Поставщики и операционка", [
            "Созвониться с 2–3 поставщиками, получить прайс и условия",
            "Рассчитать бюджет на первый закуп с учётом ассортимента",
            "Уточнить минимальные партии и сроки поставки",
            "Обсудить возврат/обмен нераспроданного товара",
        ]),
        ("Неделя 3 · Регистрация и финансы", [
            "Зарегистрировать ИП или получить статус Самозанятого",
            "Уточнить ставку УСН в вашем городе у налогового консультанта",
            "Открыть счёт в Kaspi Business или Halyk Business",
            "Подключить Kaspi Pay/QR для приёма платежей",
        ]),
        ("Неделя 4 · Маркетинг и запуск", [
            "Создать Instagram-страницу с первыми 9 постами",
            "Завести профиль в 2ГИС и на Google Maps",
            "Собрать чек-лист открытия: меню, ценники, кассовое ПО, медкнижки",
            "Тестовый день — открыться в режиме «мягкий запуск» для друзей",
        ]),
    ]
    story = [
        Paragraph("СТРАНИЦА 9 · ПЛАН ДЕЙСТВИЙ", st["kicker"]),
        Paragraph("Чек-лист на первый месяц", st["h2"]),
        Paragraph(
            "Распечатайте и отмечайте по мере выполнения. Порядок имеет значение — "
            "неделя 1 важнее всего, 80% провалов происходит из-за плохой локации.",
            st["body_muted"],
        ),
        Spacer(1, 8),
    ]
    for title, items in weeks:
        story.append(Paragraph(
            f'<font name="DejaVuSans-Bold" size="11" color="#4F46E5">{_e(title)}</font>',
            ParagraphStyle("wh", fontName="DejaVuSans-Bold", fontSize=11, leading=14, spaceAfter=4),
        ))
        for it in items:
            story.append(Paragraph(
                f'<font name="DejaVuSans" size="10" color="#1F2937">☐  {_e(it)}</font>',
                ParagraphStyle("ci", fontName="DejaVuSans", fontSize=10, leading=14, spaceAfter=2, leftIndent=8),
            ))
        story.append(Spacer(1, 8))
    return story


def _glossary_story(st: dict) -> list:
    terms = [
        ("В карман собственнику", "Деньги, которые остаются лично вам после всех налогов и обязательных соцплатежей. Не выручка и не прибыль до налогов."),
        ("Выручка", "Все деньги от клиентов за месяц. Из неё ещё ничего не вычли."),
        ("Наценка после себестоимости", "То же, что «валовая прибыль». Выручка минус прямые расходы на товар/материалы."),
        ("Окупаемость", "Сколько месяцев нужно, чтобы вернуть стартовые вложения за счёт прибыли. Норма: 12–24 месяца."),
        ("Подушка безопасности", "Деньги сверх CAPEX на покрытие расходов в первые месяцы. Минимум 3 месяца расходов."),
        ("Соцплатежи собственника", "Обязательные платежи ИП за себя: ОПВ (пенсия), ОСМС (медстрах), СО (соцотчисления)."),
        ("Стартовые вложения", "Деньги на оборудование, ремонт, первый закуп, разрешения — всё до открытия."),
        ("Точка безубыточности", "Минимальная выручка в месяц, при которой бизнес не теряет и не зарабатывает."),
        ("Точка закрытия", "Когда собственник зарабатывает меньше наёмного продавца — смысла вести бизнес нет."),
        ("Точка роста", "Когда прибыль позволяет финансировать найм или новую точку из потока. От 600 тыс ₸ в карман."),
        ("Упрощёнка / УСН", "Налоговый режим для ИП и ТОО. Платится 2–4% от выручки."),
    ]
    story = [
        Paragraph("СТРАНИЦА 10 · ГЛОССАРИЙ", st["kicker"]),
        Paragraph("Термины простым языком", st["h2"]),
        Spacer(1, 6),
    ]
    for t, d in terms:
        story.append(Paragraph(
            f'<font name="DejaVuSans-Bold" size="10.5" color="#111827">{_e(t)}</font>',
            ParagraphStyle("gt", fontName="DejaVuSans-Bold", fontSize=10.5, leading=13, spaceBefore=4),
        ))
        story.append(Paragraph(
            f'<font name="DejaVuSans" size="9.5" color="#374151">{_e(d)}</font>',
            ParagraphStyle("gd", fontName="DejaVuSans", fontSize=9.5, leading=13, spaceAfter=4),
        ))
    return story


def _methodology_story(st: dict) -> list:
    products = [
        ("📊 Финансовая модель", "9 000 ₸ — помесячный расчёт на 36 месяцев, сезонность, кредит"),
        ("📋 Бизнес-план", "15 000 ₸ — для банка/гранта, шаблон Bastau Biznes"),
        ("🎯 Pitch Deck", "По запросу — презентация для инвестора"),
    ]
    contacts = [
        ("Telegram-бот", "@zerekai_bot"),
        ("Сайт", "zerek.cc"),
        ("Email", "hello@zerek.cc"),
    ]

    note_text = (
        "<b>Что делать дальше.</b> Если оценка показала хороший потенциал — "
        "переходите к финмодели (помесячный расчёт, сезонность, кассовые разрывы). "
        "Если красный вердикт — рассмотрите другой формат, класс или локацию; "
        "или получите бизнес-план для подачи на грант «Бастау Бизнес» (400 МРП)."
    )

    return [
        Paragraph("СТРАНИЦА 11 · МЕТОДОЛОГИЯ", st["kicker"]),
        Paragraph("На чём основан этот отчёт", st["h2"]),
        Paragraph("Источники данных", st["h3"]),
        Paragraph(
            "Расчёты собраны из открытых и внутренних источников: БНС РК (статистика), "
            "Национальный банк РК (макро), 2ГИС (конкуренция), база ZEREK (33 ниши × 15 городов, "
            "усреднённые показатели малого бизнеса 2024–2026).",
            st["body"],
        ),
        Paragraph("Актуальность ставок 2026", st["h3"]),
        Paragraph(
            "МРП 2026: 4 325 ₸. Патент <b>отменён с 01.01.2026</b> — заменён на статус «Самозанятый». "
            "УСН: от 2% до 4% в зависимости от города. Соцплатежи ИП: "
            "ОПВ 10% + ОПВР 3,5% + ОСМС ~5% от 1,4 МРП + СО 3,5%.",
            st["body"],
        ),
        Paragraph("Ограничения экспресс-оценки", st["h3"]),
        Paragraph(
            "Это усреднённая модель. Реальные показатели зависят от локации (±30% к выручке), "
            "команды, маркетинга и ситуации. Для запуска бизнеса — детальная финансовая модель.",
            st["body"],
        ),
        Spacer(1, 8),
        _note_box(Paragraph(note_text, st["note"])),
        Spacer(1, 10),
        Paragraph("Следующие продукты ZEREK", st["h3"]),
        _kv_table(products, st, col1_frac=0.35),
        Spacer(1, 10),
        Paragraph("Контакты", st["h3"]),
        _kv_table(contacts, st, col1_frac=0.35),
    ]


# ═══════════════════════════════════════════════════════════
# Сборка + рендер
# ═══════════════════════════════════════════════════════════

def generate_quick_check_pdf(result: dict, niche_id: str, ai_risks=None) -> tuple:
    """
    Рендерит PDF в bytes.
    Возвращает (pdf_bytes, report_id, filename).
    """
    _register_fonts_once()
    m = _prep_metrics(result, niche_id, ai_risks=ai_risks)
    report_id = _report_id()
    date_str = _today_ru()
    st = _styles()

    buf = BytesIO()
    doc = BaseDocTemplate(
        buf, pagesize=A4, title=f"ZEREK — {m['niche_name']} · {m['city_name']}",
        leftMargin=MARGIN_X, rightMargin=MARGIN_X,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
    )

    cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover",
                        leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
                        showBoundary=0)
    content_frame = Frame(
        MARGIN_X, MARGIN_BOTTOM,
        PAGE_W - 2 * MARGIN_X,
        PAGE_H - MARGIN_TOP - MARGIN_BOTTOM,
        id="content", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
    )

    doc.addPageTemplates([
        PageTemplate(id="cover", frames=cover_frame, onPage=_draw_cover_bg),
        PageTemplate(id="content", frames=content_frame, onPage=_draw_content_chrome),
    ])

    story = []
    story.append(NextPageTemplate("cover"))
    story.extend(_cover_story(m, report_id, date_str, st))

    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    sections = [
        _summary_story(m, st),
        _passport_story(m, st),
        _unit_econ_story(m, st),
        _pnl_story(m, st),
        _invest_story(m, st),
        _stress_story(m, st),
        _risks_story(m, st),
        _checklist_story(st),
        _glossary_story(st),
        _methodology_story(st),
    ]

    for i, sec in enumerate(sections):
        if not sec:
            continue
        story.extend(sec)
        if i < len(sections) - 1:
            story.append(PageBreak())

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()

    # ASCII-safe filename — кириллица в Content-Disposition ломает HTTP
    filename = f"ZEREK_{niche_id}_{report_id}.pdf"
    return pdf_bytes, report_id, filename
