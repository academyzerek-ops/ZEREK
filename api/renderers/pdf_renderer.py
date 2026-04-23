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
    KeepTogether, PageBreak, NextPageTemplate, Flowable, HRFlowable,
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.lib.units import mm


# ═══════════════════════════════════════════════════════════
# Шрифты
# ═══════════════════════════════════════════════════════════

_FONTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "fonts",
)
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

# ── Palette ───────────────────────────────────────────────
# Основано на бренд-токенах ZEREK: индиго #7C6CFF, зелёный #10B981, амбер #F59E0B,
# красный #EF4444 (CLAUDE.md). Плюс тёплая editorial-нейтраль для фона карточек.
COL_INK = colors.HexColor("#0B0B12")        # почти-чёрный текст на обложке
COL_TEXT_HEAD = colors.HexColor("#111827")  # заголовки
COL_TEXT = colors.HexColor("#1F2937")       # основной текст
COL_TEXT_MUTED = colors.HexColor("#6B7280") # подписи
COL_TEXT_DIM = colors.HexColor("#9CA3AF")   # совсем тихо (header/footer chrome)
COL_LINE = colors.HexColor("#E5E7EB")       # разделители
COL_LINE_SOFT = colors.HexColor("#F1F2F4")  # совсем тонкие
COL_CARD = colors.HexColor("#FAFAF7")       # warm editorial off-white
COL_CARD_COOL = colors.HexColor("#F9FAFB")

COL_ACCENT = colors.HexColor("#7C6CFF")     # бренд
COL_ACCENT_SOFT = colors.HexColor("#EFEDFF")
COL_ACCENT_DARK = colors.HexColor("#4338CA")

COL_GREEN = colors.HexColor("#10B981")
COL_GREEN_DARK = colors.HexColor("#047857")
COL_GREEN_SOFT = colors.HexColor("#ECFDF5")

COL_AMBER = colors.HexColor("#F59E0B")
COL_AMBER_DARK = colors.HexColor("#92400E")
COL_AMBER_SOFT = colors.HexColor("#FFFBEB")

COL_RED = colors.HexColor("#EF4444")
COL_RED_DARK = colors.HexColor("#991B1B")
COL_RED_SOFT = colors.HexColor("#FEF2F2")

COL_WHITE = colors.HexColor("#FFFFFF")

# Обратная совместимость (используются в старом коде — сохраняю алиасы)
COL_PRIMARY = COL_ACCENT
COL_PRIMARY_SOFT = COL_ACCENT_SOFT
COL_BG_CARD = COL_CARD
COL_BORDER = COL_LINE
COL_YELLOW = COL_AMBER
COL_YELLOW_DARK = COL_AMBER_DARK
COL_YELLOW_SOFT = COL_AMBER_SOFT
COL_BG_DARK = COL_INK


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


_MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря",
}


def _report_id() -> str:
    """QC-YYYY-NNNNNN — форматированный ID отчёта."""
    import random
    tz = timezone(timedelta(hours=5))
    year = datetime.now(tz).year
    number = random.randint(100000, 999999)
    return f"QC-{year}-{number}"


def _today_ru() -> str:
    """Дата на русском: «23 апреля 2026» (Астана UTC+5)."""
    tz = timezone(timedelta(hours=5))
    dt = datetime.now(tz)
    return f"{dt.day} {_MONTHS_RU[dt.month]} {dt.year}"


# ═══════════════════════════════════════════════════════════
# Справочники ниш — канон из config/niches.yaml
# ═══════════════════════════════════════════════════════════


def _load_niche_names() -> dict:
    """Читает niche_id → name_rus из config/niches.yaml (репозиторный корень)."""
    import os as _os
    # __file__ = api/renderers/pdf_renderer.py → подняться на 3 уровня до корня
    path = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))),
        "config", "niches.yaml",
    )
    try:
        import yaml as _yaml
        with open(path, "r", encoding="utf-8") as fh:
            cfg = _yaml.safe_load(fh) or {}
        niches = (cfg.get("niches", {}) or {})
        return {nid: meta.get("name_rus", nid) for nid, meta in niches.items() if isinstance(meta, dict)}
    except Exception:
        return {}


NICHE_NAMES = _load_niche_names()


def _normalize_capex_items(items: list) -> list:
    """Приводит CAPEX-записи к единому виду {name, amount, note?}.

    block6.capex_structure использует 'label', legacy block_4.items — 'name'.
    """
    out = []
    for it in items or []:
        if not isinstance(it, dict):
            continue
        name = it.get("name") or it.get("label") or ""
        amount = it.get("amount", 0)
        out.append({"name": name, "amount": amount, "note": it.get("note", "")})
    return out


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

    # Новый формат — источник истины (calculator).
    nb1 = result.get("block1") or {}
    nb4 = result.get("block4") or {}
    nb5 = result.get("block5") or {}
    nb6 = result.get("block6") or {}
    nb10 = result.get("block10") or {}
    ei = nb5.get("entrepreneur_income") or {}
    b4_metrics = nb4.get("metrics") or {}

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

    # CAPEX — источник истины из block6 (с обучением по experience).
    # Fallback: block_4 (legacy) если нового формата нет.
    inv_min = nb6.get("capex_needed") or b4.get("investment_min") or b4.get("total") or 0
    buffer_total = int((oe.get("opex_total", 0) + social) * 3) if oe else 0

    # Payback — из block5 (новый формат), fallback на owner_economics (legacy).
    payback = nb5.get("payback_months") or oe.get("owner_payback_months")

    return {
        "city_name": inp.get("city_name", ""),
        "niche_id": niche_id,
        "niche_name": NICHE_NAMES.get(niche_id, niche_id),
        "format_name": inp.get("format_name") or inp.get("format_id", ""),
        "cls": inp.get("class", ""),
        "area_m2": inp.get("area_m2", ""),
        "loc_type": inp.get("loc_type", ""),
        "experience": inp.get("experience") or (
            (result.get("user_inputs") or {}).get("specific_answers") or {}
        ).get("experience"),
        "personnel": personnel,
        "audience": audience,
        # Трафик/чек — приоритет новому формату (block4.metrics), fallback legacy.
        "checkMed": b4_metrics.get("avg_check") or b1.get("check_med", 0),
        "trafficMed": b4_metrics.get("checks_per_day") or b1.get("traffic_med", 0),
        "trafficMax": b4_metrics.get("max_checks_per_day") or 0,
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
        # Доход предпринимателя из block5 (новый формат): средний год + зрелая.
        "avg_monthly_yr1": ei.get("total_monthly"),
        "mature_monthly": ei.get("mature_monthly"),
        "stress": stress,
        "invMin": inv_min,
        "bufferTotal": buffer_total,
        # CAPEX items — нормализация ключей (block6 использует 'label', legacy — 'name').
        "capexItems": _normalize_capex_items(nb6.get("capex_structure") or b4.get("items", [])),
        "breakEven": b6.get("tb_revenue", 0),
        "safety_margin": round(b6.get("safety_margin", 0)),
        "tbChecksDay": b6.get("tb_checks_day", 0),
        "payback": payback,
        # Вердикт — из block1 (новый, калькулятор). Fallback legacy block_10.
        "verdict_color": nb1.get("color") or b10.get("verdict_color", "yellow"),
        "verdict_text": nb1.get("verdict_statement") or b10.get("verdict_text", ""),
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
            "cover_brand", fontName="DejaVuSans-Bold", fontSize=28, leading=32,
            textColor=COL_WHITE, alignment=TA_CENTER,
        ),
        "cover_brand_sub": ParagraphStyle(
            "cover_brand_sub", fontName="DejaVuSans", fontSize=9, leading=13,
            textColor=colors.HexColor("#A1A1AA"), alignment=TA_CENTER,
        ),
        "cover_kicker": ParagraphStyle(
            "cover_kicker", fontName="DejaVuSans-Bold", fontSize=11, leading=16,
            textColor=colors.HexColor("#C7D2FE"), alignment=TA_CENTER,
            spaceAfter=18,
        ),
        "cover_h1": ParagraphStyle(
            "cover_h1", fontName="DejaVuSans-Bold", fontSize=48, leading=56,
            textColor=COL_WHITE, alignment=TA_CENTER, spaceAfter=10,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub", fontName="DejaVuSans", fontSize=13, leading=18,
            textColor=colors.HexColor("#CBD5E1"), alignment=TA_CENTER,
        ),
        "cover_meta_label": ParagraphStyle(
            "cover_meta_label", fontName="DejaVuSans", fontSize=10, leading=14,
            textColor=colors.HexColor("#9CA3AF"), alignment=TA_LEFT,
        ),
        "cover_meta_value": ParagraphStyle(
            "cover_meta_value", fontName="DejaVuSans-Bold", fontSize=10, leading=14,
            textColor=colors.HexColor("#E5E7EB"), alignment=TA_LEFT,
        ),
        "cover_report_id": ParagraphStyle(
            "cover_report_id", fontName="DejaVuMono", fontSize=10, leading=14,
            textColor=colors.HexColor("#9CA3AF"), alignment=TA_RIGHT,
        ),
        "cover_foot": ParagraphStyle(
            "cover_foot", fontName="DejaVuSans", fontSize=9, leading=13,
            textColor=colors.HexColor("#94A3B8"), alignment=TA_CENTER,
        ),
        "hero_num": ParagraphStyle(
            "hero_num", fontName="DejaVuMono-Bold", fontSize=44, leading=50,
            textColor=COL_GREEN_DARK, alignment=TA_CENTER,
        ),
        "hero_num_red": ParagraphStyle(
            "hero_num_red", fontName="DejaVuMono-Bold", fontSize=44, leading=50,
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
    # Чистый холст: тёмный фон + тонкая акцентная линия сверху.
    canv.setFillColor(COL_INK)
    canv.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    # Акцентная горизонтальная полоса в верхней части
    canv.setFillColor(COL_ACCENT)
    canv.rect(0, PAGE_H - 4 * mm, 40 * mm, 2 * mm, fill=1, stroke=0)
    canv.restoreState()


def _draw_content_chrome(canv, doc):
    canv.saveState()
    # Header: brand слева, номер страницы справа, тонкая линия под ними
    canv.setFont("DejaVuSans-Bold", 8)
    canv.setFillColor(COL_TEXT_DIM)
    canv.drawString(MARGIN_X, PAGE_H - 11 * mm, "ZEREK")
    canv.setFont("DejaVuSans", 8)
    canv.drawString(MARGIN_X + 14, PAGE_H - 11 * mm, "·  Экспресс-оценка")
    canv.setFont("DejaVuMono", 8)
    canv.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 11 * mm, f"стр. {canv.getPageNumber():02d}")
    canv.setStrokeColor(COL_LINE)
    canv.setLineWidth(0.3)
    canv.line(MARGIN_X, PAGE_H - 13 * mm, PAGE_W - MARGIN_X, PAGE_H - 13 * mm)

    # Footer: одна компактная строка
    canv.setStrokeColor(COL_LINE)
    canv.setLineWidth(0.3)
    canv.line(MARGIN_X, 14 * mm, PAGE_W - MARGIN_X, 14 * mm)
    canv.setFont("DejaVuSans", 7.2)
    canv.setFillColor(COL_TEXT_DIM)
    canv.drawString(MARGIN_X, 10 * mm,
                    "Экспресс-оценка на основе усреднённых данных рынка РК. Для запуска — детальная финмодель.")
    canv.drawRightString(PAGE_W - MARGIN_X, 10 * mm, "zerek.cc")
    canv.restoreState()


# ═══════════════════════════════════════════════════════════
# Story builders
# ═══════════════════════════════════════════════════════════

def _content_w() -> float:
    return PAGE_W - 2 * MARGIN_X


def _cover_story(m: dict, report_id: str, date_str: str, st: dict) -> list:
    niche_upper = _e(m["niche_name"].upper())
    format_label = _e(m.get("format_name") or "")
    city_name = _e(m.get("city_name") or "")

    content_w = PAGE_W - 40 * mm
    divider_col = colors.HexColor("#27272A")
    divider = HRFlowable(width=content_w, thickness=0.5, color=divider_col,
                         spaceBefore=0, spaceAfter=0)

    brand = Table([
        [Paragraph("ZEREK", st["cover_brand"])],
        [Spacer(1, 4)],
        [Paragraph("AI-ПЛАТФОРМА БИЗНЕС-АНАЛИТИКИ", st["cover_brand_sub"])],
    ], colWidths=[content_w])
    brand.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    middle = Table([
        [Paragraph("АНАЛИЗ&nbsp;&nbsp;БИЗНЕС-ИДЕИ", st["cover_kicker"])],
        [Paragraph(niche_upper, st["cover_h1"])],
        [Spacer(1, 10)],
        [Paragraph("Quick Check · 2026", st["cover_sub"])],
    ], colWidths=[content_w])
    middle.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    # Меta: две колонки (label | value) с равномерным выравниванием.
    meta_rows = []
    if format_label:
        meta_rows.append(("Формат", format_label))
    if city_name:
        meta_rows.append(("Город", city_name))
    meta_rows.append(("Подготовлено", _e(date_str)))

    meta_data = [
        [Paragraph(lbl + ":", st["cover_meta_label"]),
         Paragraph(val, st["cover_meta_value"])]
        for lbl, val in meta_rows
    ]
    meta_tbl = Table(meta_data, colWidths=[content_w * 0.35, content_w * 0.65])
    meta_tbl.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 3), ("BOTTOMPADDING", (0,0), (-1,-1), 3),
        ("VALIGN", (0,0), (-1,-1), "TOP"),
    ]))

    report_id_p = Paragraph(f"№ {_e(report_id)}", st["cover_report_id"])
    footer = Paragraph(
        "ZEREK — AI-платформа бизнес-аналитики для предпринимателей Казахстана<br/>"
        "zerek.cc  ·  @ZEREKAI_BOT",
        st["cover_foot"],
    )

    outer = Table([
        [brand],
        [Spacer(1, 24)],
        [divider],
        [Spacer(1, 80)],
        [middle],
        [Spacer(1, 80)],
        [divider],
        [Spacer(1, 32)],
        [meta_tbl],
        [Spacer(1, 16)],
        [report_id_p],
        [Spacer(1, 36)],
        [footer],
    ], colWidths=[content_w])
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0,0), (-1,-1), 0), ("RIGHTPADDING", (0,0), (-1,-1), 0),
        ("TOPPADDING", (0,0), (-1,-1), 0), ("BOTTOMPADDING", (0,0), (-1,-1), 0),
    ]))

    return [Spacer(1, 34 * mm), Indenter(outer, left=20 * mm)]


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


class BarRow(Flowable):
    """
    Строка с подписью слева, моно-значением справа и пропорциональным баром-подложкой.
    Используется в P&L и стресс-тесте. Бар = цветная заливка ширины proportion×label_w,
    на прозрачном фоне строки.
    """
    def __init__(self, label, value_str, fraction, bar_color,
                 label_font="DejaVuSans", label_size=10, label_color=None,
                 value_font="DejaVuMono-Bold", value_size=11, value_color=None,
                 row_h=20, total_w=None, bold_label=False, emphasize=False):
        super().__init__()
        self.label = label
        self.value_str = value_str
        self.fraction = max(0.0, min(1.0, fraction))
        self.bar_color = bar_color
        self.label_font = "DejaVuSans-Bold" if bold_label else label_font
        self.label_size = label_size
        self.label_color = label_color or COL_TEXT
        self.value_font = value_font
        self.value_size = value_size
        self.value_color = value_color or COL_TEXT
        self.row_h = row_h
        self.width_override = total_w
        self.emphasize = emphasize  # рамка + жирнее

    def wrap(self, aW, aH):
        self.width = self.width_override or aW
        self.height = self.row_h
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        # Колонки: label 65%, value 35%
        label_w = w * 0.65
        value_w = w - label_w
        pad_x = 8
        # Фон самой подложки под бар
        c.setFillColor(COL_LINE_SOFT)
        c.rect(0, 0, label_w, h, fill=1, stroke=0)
        # Бар
        if self.fraction > 0:
            c.setFillColor(self.bar_color)
            c.rect(0, 0, label_w * self.fraction, h, fill=1, stroke=0)
        # Подпись
        c.setFillColor(self.label_color)
        c.setFont(self.label_font, self.label_size)
        text_y = (h - self.label_size) / 2 + 2
        c.drawString(pad_x, text_y, self.label)
        # Значение справа
        c.setFillColor(self.value_color)
        c.setFont(self.value_font, self.value_size)
        c.drawRightString(w - pad_x, text_y, self.value_str)
        # Акцентная рамка (для grand-row)
        if self.emphasize:
            c.setStrokeColor(COL_GREEN)
            c.setLineWidth(1.4)
            c.rect(0, 0, w, h, fill=0, stroke=1)


class RuleDivider(Flowable):
    """Тонкая горизонтальная линия-разделитель на всю ширину контента."""
    def __init__(self, color=None, thickness=0.4, space_before=3, space_after=3):
        super().__init__()
        self.color = color or COL_LINE
        self.thickness = thickness
        self.space_before = space_before
        self.space_after = space_after

    def wrap(self, aW, aH):
        self.width = aW
        self.height = self.space_before + self.thickness + self.space_after
        return self.width, self.height

    def draw(self):
        c = self.canv
        y = self.space_after + self.thickness / 2
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line(0, y, self.width, y)


def _verdict_table(m: dict, st: dict) -> Table:
    vc = m["verdict_color"]
    label = {"green": "Бизнес жизнеспособен",
             "yellow": "Бизнес возможен, но есть риски",
             "red": "Высокий риск — рекомендуем пересмотреть"}.get(vc, "Бизнес возможен, но есть риски")
    status_tag = {"green": "ВЕРДИКТ · ЗЕЛЁНЫЙ",
                  "yellow": "ВЕРДИКТ · ЖЁЛТЫЙ",
                  "red": "ВЕРДИКТ · КРАСНЫЙ"}.get(vc, "ВЕРДИКТ")
    stripe = {"green": COL_GREEN, "yellow": COL_AMBER, "red": COL_RED}.get(vc, COL_AMBER)
    txt_col = {"green": COL_GREEN_DARK, "yellow": COL_AMBER_DARK, "red": COL_RED_DARK}.get(vc, COL_AMBER_DARK)

    tag_p = Paragraph(
        f'<font name="DejaVuSans-Bold" size="8" color="{stripe.hexval()}">{status_tag}</font>',
        ParagraphStyle("vt", fontName="DejaVuSans-Bold", fontSize=8, leading=12),
    )
    label_p = Paragraph(
        f'<font name="DejaVuSans-Bold" size="14" color="{txt_col.hexval()}">{_e(label)}</font>',
        ParagraphStyle("vl", fontName="DejaVuSans-Bold", fontSize=14, leading=18),
    )
    inner = Table([[tag_p], [label_p]], colWidths=[_content_w() - 8])
    inner.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (0, 0), 0), ("BOTTOMPADDING", (0, 0), (0, 0), 2),
        ("TOPPADDING", (0, 1), (0, 1), 0), ("BOTTOMPADDING", (0, 1), (0, 1), 0),
    ]))
    t = Table([[inner]], colWidths=[_content_w()])
    t.setStyle(TableStyle([
        ("LINEBEFORE", (0, 0), (0, 0), 3, stripe),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _hero_number_box(m: dict, st: dict) -> Table:
    """Две карточки — средняя за первый год + на мощности (синхронно с Mini App).

    Источник данных: block5.entrepreneur_income.{total_monthly, mature_monthly}.
    """
    avg_yr1 = m.get("avg_monthly_yr1") or 0
    mature = m.get("mature_monthly") or 0
    avg_s = f"{_fmt(avg_yr1)} ₸"
    mat_s = f"{_fmt(mature)} ₸"

    def card(label, sub, val):
        return Table([
            [Paragraph(f'<font name="DejaVuSans" size="9" color="#6B7280">{_e(label).upper()}</font>',
                       ParagraphStyle("hl", fontName="DejaVuSans", fontSize=9, leading=11, alignment=TA_CENTER))],
            [Paragraph(f'<font name="DejaVuMono-Bold" size="20" color="{COL_GREEN_DARK.hexval()}">{_e(val)}</font>',
                       ParagraphStyle("hv", fontName="DejaVuMono-Bold", fontSize=20, leading=24, alignment=TA_CENTER))],
            [Paragraph(f'<font name="DejaVuSans" size="9" color="#9CA3AF">{_e(sub)}</font>',
                       ParagraphStyle("hs", fontName="DejaVuSans", fontSize=9, leading=12, alignment=TA_CENTER))],
        ], colWidths=[_content_w() / 2])

    col_w = _content_w() / 2
    left = card("Средняя за первый год", "с учётом разгона", avg_s)
    right = card("Когда выйдете на мощность", "после месяца 4", mat_s)
    for c in (left, right):
        c.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, 0), 12), ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
            ("TOPPADDING", (0, 1), (-1, 1), 0), ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
            ("TOPPADDING", (0, 2), (-1, 2), 0), ("BOTTOMPADDING", (0, 2), (-1, 2), 12),
        ]))

    t = Table([[left, right]], colWidths=[col_w, col_w])
    t.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 0), (-1, 0), 0.4, COL_LINE),
        ("LINEBELOW", (0, 0), (-1, 0), 0.4, COL_LINE),
        ("LINEBEFORE", (1, 0), (1, 0), 0.3, COL_LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    return t


def _stats_row(m: dict) -> Table:
    payback = f"{m['payback']} мес" if m.get("payback") else "—"
    items = [
        ("Окупаемость", payback),
        ("Стартовые", f"{_fmt_k(m['invMin'])} ₸"),
        ("Брейкевен", f"{_fmt_k(m['breakEven'])} ₸"),
        ("Запас", f"{m['safety_margin']}%"),
    ]

    col_w = _content_w() / 4
    row = []
    for label, value in items:
        stack = Table(
            [
                [Paragraph(
                    f'<font name="DejaVuSans" size="8" color="#9CA3AF">{_e(label).upper()}</font>',
                    ParagraphStyle("x", fontName="DejaVuSans", fontSize=8, leading=10, alignment=TA_LEFT),
                )],
                [Paragraph(
                    f'<font name="DejaVuMono-Bold" size="15" color="#111827">{_e(value)}</font>',
                    ParagraphStyle("y", fontName="DejaVuMono-Bold", fontSize=15, leading=18, alignment=TA_LEFT),
                )],
            ],
            colWidths=[col_w],
        )
        stack.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        row.append(stack)

    t = Table([row], colWidths=[col_w] * 4)
    style = [
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    # Тонкие вертикальные линии-разделители между колонками
    for col in range(1, 4):
        style.append(("LINEBEFORE", (col, 0), (col, 0), 0.3, COL_LINE))
    t.setStyle(TableStyle(style))
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
        Paragraph("СВОДКА", st["kicker"]),
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


def _kv_table(pairs: list, st: dict, col1_frac=0.4, numeric_right=True) -> Table:
    cw1 = _content_w() * col1_frac
    cw2 = _content_w() * (1 - col1_frac)
    data = []
    for k, v in pairs:
        label_p = Paragraph(
            f'<font name="DejaVuSans" color="#6B7280" size="10">{_e(k)}</font>',
            ParagraphStyle("kl", fontName="DejaVuSans", fontSize=10, leading=14),
        )
        # Определяем: число это или текст (числа в моно, справа)
        v_str = _e(v)
        is_numeric = any(ch.isdigit() for ch in v_str) and ("₸" in v_str or "%" in v_str or "мес" in v_str or "м²" in v_str)
        if is_numeric and numeric_right:
            value_p = Paragraph(
                f'<font name="DejaVuMono-Bold" color="#111827" size="11">{v_str}</font>',
                ParagraphStyle("kvn", fontName="DejaVuMono-Bold", fontSize=11, leading=14, alignment=TA_RIGHT),
            )
        else:
            value_p = Paragraph(
                f'<font name="DejaVuSans-Bold" color="#111827" size="10.5">{v_str}</font>',
                ParagraphStyle("kvt", fontName="DejaVuSans-Bold", fontSize=10.5, leading=14),
            )
        data.append([label_p, value_p])
    t = Table(data, colWidths=[cw1, cw2])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]
    for i in range(len(data)):
        style.append(("LINEBELOW", (0, i), (-1, i), 0.3, COL_LINE))
    # Убираем нижнюю линию у последней строки (выглядит как дублированный разрыв)
    if data:
        style.append(("LINEBELOW", (0, len(data) - 1), (-1, len(data) - 1), 0, COL_WHITE))
    # Верхняя линия над первой строкой для акцента
    style.insert(0, ("LINEABOVE", (0, 0), (-1, 0), 0.3, COL_LINE))
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
        Paragraph("ПАСПОРТ ПРОЕКТА", st["kicker"]),
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
    # Реальный трафик из block4.metrics.checks_per_day (не fallback 15!).
    daily = int(m.get("trafficMed") or 0)
    daily_max = int(m.get("trafficMax") or 0)
    daily_gross = profit_per_tx * daily

    # Три строки формулы: чек / минус себест. / равно прибыль
    def chain_row(label, value_str, value_color, emphasize=False):
        lbl_size = 12 if emphasize else 11
        val_size = 20 if emphasize else 13
        lbl_weight = "DejaVuSans-Bold" if emphasize else "DejaVuSans"
        lbl_color = "#111827" if emphasize else "#374151"
        left = Paragraph(
            f'<font name="{lbl_weight}" size="{lbl_size}" color="{lbl_color}">{_e(label)}</font>',
            ParagraphStyle("l", fontName=lbl_weight, fontSize=lbl_size, leading=lbl_size + 3),
        )
        right = Paragraph(
            f'<font name="DejaVuMono-Bold" size="{val_size}" color="{value_color}">{_e(value_str)}</font>',
            ParagraphStyle("r", fontName="DejaVuMono-Bold", fontSize=val_size, leading=val_size + 3, alignment=TA_RIGHT),
        )
        t = Table([[left, right]], colWidths=[_content_w() * 0.58, _content_w() * 0.42])
        style = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, 0), 0.3, COL_LINE),
        ]
        if emphasize:
            style.append(("LINEABOVE", (0, 0), (-1, 0), 1.5, COL_GREEN))
            style.append(("LINEBELOW", (0, 0), (-1, 0), 1.5, COL_GREEN))
            style.append(("TOPPADDING", (0, 0), (-1, -1), 14))
            style.append(("BOTTOMPADDING", (0, 0), (-1, -1), 14))
        t.setStyle(TableStyle(style))
        return t

    max_tail = f" (максимум {daily_max})" if daily_max and daily_max > daily else ""
    note_text = (
        f"<b>Что это значит.</b> В среднем <b>{daily} клиентов в день</b>{max_tail} "
        f"дают <b>{_fmt(daily_gross)} ₸ в день</b> «наценки после себестоимости». "
        f"Из неё ещё нужно заплатить аренду, зарплату, налоги, соцплатежи — "
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
        Paragraph("ЭКОНОМИКА ОДНОГО КЛИЕНТА", st["kicker"]),
        Paragraph("Сколько вы зарабатываете с одного чека", st["h2"]),
        Paragraph(
            "Формула простая: чек минус себестоимость равно заработок с клиента.",
            st["body_muted"],
        ),
        Spacer(1, 10),
        chain_row("Средний чек", f"{_fmt(m['checkMed'])} ₸", "#111827"),
        chain_row("Минус себестоимость (товар / материалы)",
                  f"−{_fmt(cost_per_tx)} ₸", COL_RED.hexval()),
        Spacer(1, 6),
        chain_row("Заработок с клиента", f"{_fmt(profit_per_tx)} ₸",
                  COL_GREEN_DARK.hexval(), emphasize=True),
        Spacer(1, 14),
        _note_box(Paragraph(note_text, st["note"])),
        Spacer(1, 10),
        Paragraph("Структура себестоимости", st["h3"]),
        Paragraph(structure_p1, st["body"]),
        Paragraph(structure_p2, st["body"]),
    ]


def _pnl_story(m: dict, st: dict) -> list:
    ob = m["opex_breakdown"]
    other = ob.get("other", 0)

    revenue = max(m["revenue"], 1)
    rows = [
        ("Выручка в месяц", m["revenue"], "pos"),
        ("Себестоимость (товар / материалы)", m["cogs"], "neg"),
        ("Наценка после себестоимости", m["gross"], "sub_pos"),
        ("Аренда", ob.get("rent", 0), "neg"),
        ("ФОТ (зарплаты + налоги работодателя)", ob.get("fot", 0), "neg"),
        ("Маркетинг", ob.get("marketing", 0), "neg"),
        ("Коммуналка", ob.get("utilities", 0), "neg"),
        ("Расходники, софт, прочее", other, "neg"),
        ("Прибыль до налогов", m["profitBeforeTax"], "sub_pos"),
        (f"Налог {m['taxRegime']} ({m['taxRatePct']}%)", m["tax"], "neg"),
        ("Соцплатежи собственника (ОПВ + ОСМС + СО)", m["social"], "neg"),
        ("В карман собственнику", max(m["net_in_pocket"], 0), "grand"),
    ]

    flowables = []
    for label, abs_val, kind in rows:
        frac = abs_val / revenue if revenue else 0
        if kind == "pos":
            bar = COL_GREEN_SOFT; val_color = COL_GREEN_DARK; label_color = COL_TEXT_HEAD
            bold = True; emphasize = False; sign = ""
        elif kind == "sub_pos":
            bar = COL_ACCENT_SOFT; val_color = COL_ACCENT_DARK; label_color = COL_TEXT_HEAD
            bold = True; emphasize = False; sign = ""
        elif kind == "neg":
            bar = COL_RED_SOFT; val_color = COL_RED; label_color = COL_TEXT
            bold = False; emphasize = False; sign = "−"
        elif kind == "grand":
            bar = COL_GREEN_SOFT; val_color = COL_GREEN_DARK; label_color = COL_GREEN_DARK
            bold = True; emphasize = True; sign = ""
        else:
            bar = COL_LINE_SOFT; val_color = COL_TEXT; label_color = COL_TEXT
            bold = False; emphasize = False; sign = ""

        val_str = f"{sign}{_fmt(abs_val)} ₸"
        row_h = 28 if kind == "grand" else (22 if kind in ("pos", "sub_pos") else 18)
        val_size = 14 if kind == "grand" else (12 if kind in ("pos", "sub_pos") else 11)
        label_size = 11 if kind in ("grand", "pos", "sub_pos") else 10

        flowables.append(BarRow(
            label=label, value_str=val_str, fraction=frac, bar_color=bar,
            label_color=label_color, value_color=val_color,
            label_size=label_size, value_size=val_size,
            row_h=row_h, bold_label=bold, emphasize=emphasize,
        ))
        flowables.append(Spacer(1, 2))

    note_text = (
        "<b>Важно.</b> Налог УСН платится с <i>выручки</i>, не с прибыли — даже если "
        "бизнес в минус, налог идёт. Соцплатежи собственника ИП платит за себя независимо "
        "от дохода: это обязательные пенсионные, медстрах и соцотчисления."
    )
    return [
        Paragraph("МЕСЯЧНАЯ ЭКОНОМИКА", st["kicker"]),
        Paragraph("Куда уходят деньги", st["h2"]),
        Paragraph(
            "Длина бара — доля от месячной выручки. Сначала минусы (расходы, налоги), потом что остаётся вам.",
            st["body_muted"],
        ),
        Spacer(1, 8),
        *flowables,
        Spacer(1, 10),
        _note_box(Paragraph(note_text, st["note"])),
    ]


def _invest_story(m: dict, st: dict) -> list:
    # CAPEX строк
    capex_rows = []
    for it in m["capexItems"]:
        capex_rows.append((it.get("name", ""), f"{_fmt(it.get('amount', 0))} ₸"))
    capex_rows.append(("Итого CAPEX", f"{_fmt(m['invMin'])} ₸"))

    # Раскрываем состав подушки: 3 × (OPEX-компоненты + соцплатежи ИП).
    ob = m.get("opex_breakdown") or {}
    social_m = m.get("social", 0)
    breakdown_labels = [
        ("rent",       "Аренда × 3 мес"),
        ("fot",        "ФОТ × 3 мес"),
        ("marketing",  "Маркетинг × 3 мес"),
        ("utilities",  "Коммуналка × 3 мес"),
        ("other",      "Прочее (расходники, софт) × 3 мес"),
    ]
    buffer_rows = []
    computed_total = 0
    for key, label in breakdown_labels:
        monthly = int(ob.get(key) or 0)
        if monthly <= 0:
            continue
        three_m = monthly * 3
        buffer_rows.append((label, f"{_fmt(three_m)} ₸"))
        computed_total += three_m
    if social_m > 0:
        social_3m = int(social_m) * 3
        buffer_rows.append(("Соцплатежи ИП × 3 мес", f"{_fmt(social_3m)} ₸"))
        computed_total += social_3m
    # Предпочитаем посчитанную сумму (бит-в-бит к компонентам).
    # Fallback: m['bufferTotal'] если opex_breakdown пуст.
    buffer_total = computed_total if buffer_rows else m.get("bufferTotal", 0)
    buffer_rows.append(("Подушка всего", f"{_fmt(buffer_total)} ₸"))

    grand_total = m["invMin"] + buffer_total
    grand_row = Table(
        [[Paragraph(
            '<font name="DejaVuSans-Bold" color="#111827" size="13">Всего на старт (с подушкой)</font>',
            ParagraphStyle("g", fontName="DejaVuSans-Bold", fontSize=13, leading=16)),
          Paragraph(
            f'<font name="DejaVuMono-Bold" color="{COL_ACCENT_DARK.hexval()}" size="18">{_fmt(grand_total)} ₸</font>',
            ParagraphStyle("gv", fontName="DejaVuMono-Bold", fontSize=18, leading=22, alignment=TA_RIGHT))]],
        colWidths=[_content_w() * 0.55, _content_w() * 0.45],
    )
    grand_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LINEABOVE", (0, 0), (-1, 0), 1.5, COL_ACCENT),
        ("LINEBELOW", (0, 0), (-1, 0), 1.5, COL_ACCENT),
    ]))

    note_text = (
        "<b>Почему подушка критична.</b> 80% закрытий малого бизнеса — в первые 6 месяцев. "
        "Главная причина не «мало клиентов», а <i>кончились деньги до того, как бизнес вышел в плюс</i>. "
        "Резерв на 3 месяца — минимум; 6 месяцев — комфорт."
    )

    return [
        Paragraph("СТАРТОВЫЕ ВЛОЖЕНИЯ", st["kicker"]),
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

    # Максимальное |pocket| для нормализации ширины бара
    max_abs = max((abs(s.get("net_in_pocket", 0)) for s in stress), default=1) or 1

    def scen_block(s):
        color_key = s.get("color", "blue")
        bar_color = {"red": COL_RED_SOFT, "blue": COL_ACCENT_SOFT, "green": COL_GREEN_SOFT}.get(color_key, COL_ACCENT_SOFT)
        stripe = {"red": COL_RED, "blue": COL_ACCENT, "green": COL_GREEN}.get(color_key, COL_ACCENT)
        val_color = {"red": COL_RED, "blue": COL_ACCENT_DARK, "green": COL_GREEN_DARK}.get(color_key, COL_ACCENT_DARK)
        pocket = s.get("net_in_pocket", 0)
        sign = "−" if pocket < 0 else ""
        val_str = f"{sign}{_fmt_k(abs(pocket))} ₸/мес"
        frac = abs(pocket) / max_abs

        # Заголовок сценария + параметры слева, значение справа
        title_p = Paragraph(
            f'<font name="DejaVuSans-Bold" size="12" color="#111827">{_e(s["label"])}</font><br/>'
            f'<font name="DejaVuSans" size="9" color="#6B7280">{_e(s.get("params", ""))}</font>',
            ParagraphStyle("tp", fontName="DejaVuSans", fontSize=12, leading=15),
        )
        val_p = Paragraph(
            f'<font name="DejaVuMono-Bold" size="16" color="{val_color.hexval()}">{_e(val_str)}</font>',
            ParagraphStyle("vp", fontName="DejaVuMono-Bold", fontSize=16, leading=19, alignment=TA_RIGHT),
        )
        head = Table([[title_p, val_p]], colWidths=[_content_w() * 0.58, _content_w() * 0.42])
        head.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))

        # Бар-подложка с левой stripe
        bar = BarRow(
            label="", value_str="", fraction=frac, bar_color=bar_color,
            row_h=10, label_size=10, label_color=COL_TEXT, value_color=COL_TEXT,
        )

        # Вставляем левую цветную полоску через обёртку Table с LINEBEFORE
        wrap = Table([[head], [bar]], colWidths=[_content_w()])
        wrap.setStyle(TableStyle([
            ("LINEBEFORE", (0, 0), (0, -1), 3, stripe),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        return wrap

    note_text = (
        "<b>Как читать.</b> Длина бара — сравнительная величина «в карман» между сценариями. "
        "Если в сценарии «всё плохо» цифра в минус — нужна подушка на покрытие или пересмотр формата."
    )

    return [
        Paragraph("СТРЕСС-ТЕСТ", st["kicker"]),
        Paragraph("Что будет, если рынок просядет", st["h2"]),
        Paragraph(
            "Проверка устойчивости бизнеса. Каждый сценарий меняет ключевые параметры и пересчитывает «в карман».",
            st["body_muted"],
        ),
        Spacer(1, 10),
        scen_block(stress[0]),
        Spacer(1, 8),
        scen_block(stress[1]),
        Spacer(1, 8),
        scen_block(stress[2]),
        Spacer(1, 10),
        _note_box(Paragraph(note_text, st["note"])),
    ]


def _risks_story(m: dict, st: dict) -> list:
    risks = m.get("ai_risks") or []
    if not risks:
        return []

    story = [
        Paragraph("РИСКИ НИШИ", st["kicker"]),
        Paragraph("Почему закрываются такие бизнесы", st["h2"]),
        Paragraph(
            "7 самых денежно-критичных рисков для вашей ниши — из практики закрывшихся бизнесов. "
            "Для каждого: описание + действие, как защититься.",
            st["body_muted"],
        ),
        Spacer(1, 8),
    ]

    for idx, r in enumerate(risks[:7]):
        num = f"{idx + 1:02d}"
        # Номер слева, заголовок и текст — справа
        num_p = Paragraph(
            f'<font name="DejaVuMono-Bold" size="14" color="{COL_AMBER.hexval()}">{num}</font>',
            ParagraphStyle("rn", fontName="DejaVuMono-Bold", fontSize=14, leading=17, alignment=TA_LEFT),
        )
        title_p = Paragraph(
            f'<font name="DejaVuSans-Bold" size="12" color="#111827">{_e(r.get("title", ""))}</font>',
            ParagraphStyle("rt", fontName="DejaVuSans-Bold", fontSize=12, leading=16),
        )
        body_p = Paragraph(
            f'<font name="DejaVuSans" size="10" color="#374151">{_e(r.get("body", ""))}</font>',
            ParagraphStyle("rb", fontName="DejaVuSans", fontSize=10, leading=14),
        )
        protect_text = r.get("protect", "")
        right_rows = [[title_p], [body_p]]
        if protect_text:
            protect_p = Paragraph(
                f'<font name="DejaVuSans-Bold" size="9.5" color="{COL_GREEN_DARK.hexval()}">Как защититься.</font> '
                f'<font name="DejaVuSans" size="9.5" color="#111827">{_e(protect_text)}</font>',
                ParagraphStyle("rp", fontName="DejaVuSans", fontSize=9.5, leading=13),
            )
            right_rows.append([protect_p])

        right_stack = Table(right_rows, colWidths=[_content_w() - 14 * mm])
        right_stack.setStyle(TableStyle([
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (0, 0), 0),
            ("TOPPADDING", (0, 1), (0, 1), 2),
            ("BOTTOMPADDING", (0, 0), (0, 0), 2),
            ("BOTTOMPADDING", (0, 1), (0, 1), 2),
            ("TOPPADDING", (0, -1), (0, -1), 4),
            ("BOTTOMPADDING", (0, -1), (0, -1), 0),
        ]))

        card = Table([[num_p, right_stack]], colWidths=[14 * mm, _content_w() - 14 * mm])
        card.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LINEBELOW", (0, 0), (-1, 0), 0.3, COL_LINE),
        ]))
        story.append(KeepTogether([card]))

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
        Paragraph("ПЛАН ДЕЙСТВИЙ", st["kicker"]),
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
        ("Подушка безопасности", "Деньги сверх стартовых вложений — на покрытие расходов в первые месяцы. Минимум 3 месяца."),
        ("Соцплатежи собственника", "Обязательные платежи ИП за себя: ОПВ (пенсия), ОСМС (медстрах), СО (соцотчисления)."),
        ("Стартовые вложения", "Деньги на оборудование, ремонт, первый закуп, разрешения — всё до открытия."),
        ("Точка безубыточности", "Минимальная выручка в месяц, при которой бизнес не теряет и не зарабатывает."),
        ("Точка закрытия", "Когда собственник зарабатывает меньше наёмного продавца — смысла вести бизнес нет."),
        ("Точка роста", "Прибыль позволяет финансировать найм или новую точку из потока. От 600 тыс ₸ в карман."),
        ("Упрощёнка / УСН", "Налоговый режим для ИП и ТОО. Платится 2–4% от выручки."),
    ]
    rows = []
    for t, d in terms:
        rows.append([
            Paragraph(
                f'<font name="DejaVuSans-Bold" size="10" color="#111827">{_e(t)}</font>',
                ParagraphStyle("gt", fontName="DejaVuSans-Bold", fontSize=10, leading=13),
            ),
            Paragraph(
                f'<font name="DejaVuSans" size="9.5" color="#374151">{_e(d)}</font>',
                ParagraphStyle("gd", fontName="DejaVuSans", fontSize=9.5, leading=13),
            ),
        ])
    col1 = _content_w() * 0.32
    col2 = _content_w() * 0.68
    tbl = Table(rows, colWidths=[col1, col2])
    style = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LINEABOVE", (0, 0), (-1, 0), 0.3, COL_LINE),
    ]
    for i in range(len(rows)):
        style.append(("LINEBELOW", (0, i), (-1, i), 0.3, COL_LINE))
    tbl.setStyle(TableStyle(style))
    return [
        Paragraph("ГЛОССАРИЙ", st["kicker"]),
        Paragraph("Термины простым языком", st["h2"]),
        Spacer(1, 8),
        tbl,
    ]


def _methodology_story(st: dict) -> list:
    products = [
        ("Финансовая модель", "9 000 ₸ — помесячный расчёт на 36 месяцев, сезонность, кредит"),
        ("Бизнес-план", "15 000 ₸ — для банка или гранта «Бастау Бизнес»"),
        ("Pitch Deck", "По запросу — презентация для инвестора"),
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
        Paragraph("МЕТОДОЛОГИЯ", st["kicker"]),
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

    filename = generate_pdf_filename(
        m.get("niche_name") or niche_id,
        m.get("city_name") or "",
        m.get("format_name") or "",
    )
    return pdf_bytes, report_id, filename


def generate_pdf_filename(niche_name: str, city_name: str, format_label: str) -> str:
    """Имя PDF: ZEREK_Анализ_{Ниша}_{Формат}_{Город}_{YYYY-MM-DD}.pdf.

    Кириллица сохраняется — download-эндпоинт кодирует filename* по RFC 5987.
    """
    from datetime import date
    today = date.today().isoformat()
    parts = ["ZEREK", "Анализ"]
    for part in (niche_name, format_label, city_name):
        p = (part or "").strip().replace(" ", "_")
        if p:
            parts.append(p)
    parts.append(today)
    return "_".join(parts) + ".pdf"
