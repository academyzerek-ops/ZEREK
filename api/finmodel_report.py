"""
ZEREK — HTML-отчёт по финансовой модели
GeoSafe advisory style: Playfair Display + Source Sans 3 + JetBrains Mono
SVG-графики серверные, без JS-библиотек.
"""
import math
from typing import List, Dict, Any, Optional

# ═══════════════════════════════════════
# УТИЛИТЫ
# ═══════════════════════════════════════

def fmt(n) -> str:
    if n is None: return "—"
    return f"{int(round(n)):,}".replace(",", " ")

def fmtM(n) -> str:
    if n is None: return "—"
    n = int(round(n))
    if abs(n) >= 1_000_000: return f"{n/1_000_000:.1f} млн".replace(".0 ", " ")
    if abs(n) >= 1_000: return f"{n/1_000:.0f} тыс"
    return fmt(n)

def fmtPct(n) -> str:
    if n is None: return "—"
    return f"{round(n)}%"

def safe(d: dict, *keys, default=None):
    v = d
    for k in keys:
        if isinstance(v, dict): v = v.get(k, default)
        else: return default
    return v if v is not None else default

def color_for(value, thresholds):
    """thresholds = [(val, color), ...] sorted descending."""
    for thr, clr in thresholds:
        if value >= thr: return clr
    return thresholds[-1][1] if thresholds else "#8a8a8a"

MONTHS_RU = ["Янв","Фев","Мар","Апр","Май","Июн","Июл","Авг","Сен","Окт","Ноя","Дек"]


# ═══════════════════════════════════════
# SVG ГЕНЕРАТОРЫ
# ═══════════════════════════════════════

def svg_bar_chart(data: list, width=560, height=260, show_values=True) -> str:
    if not data: return ""
    n = len(data)
    margin = {"top": 30, "right": 20, "bottom": 40, "left": 70}
    cw = width - margin["left"] - margin["right"]
    ch = height - margin["top"] - margin["bottom"]
    max_val = max(d.get("value", 0) for d in data) or 1
    bar_w = min(cw // n - 12, 80)
    gap = (cw - bar_w * n) / (n + 1)

    s = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">'
    s += f'<rect width="{width}" height="{height}" fill="#faf9f7" rx="8"/>'
    # Grid lines
    for i in range(5):
        y = margin["top"] + ch * i / 4
        val = max_val * (4 - i) / 4
        s += f'<line x1="{margin["left"]}" y1="{y}" x2="{width-margin["right"]}" y2="{y}" stroke="#e0dcd4" stroke-width="0.5"/>'
        s += f'<text x="{margin["left"]-8}" y="{y+4}" text-anchor="end" font-size="10" fill="#8a8a8a" font-family="JetBrains Mono,monospace">{fmtM(val)}</text>'
    # Bars
    for i, d in enumerate(data):
        x = margin["left"] + gap + i * (bar_w + gap)
        v = d.get("value", 0)
        h_bar = (v / max_val) * ch if max_val > 0 else 0
        y = margin["top"] + ch - h_bar
        clr = d.get("color", "#c8a55c")
        s += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h_bar}" fill="{clr}" rx="4"/>'
        if show_values:
            s += f'<text x="{x+bar_w/2}" y="{y-6}" text-anchor="middle" font-size="11" font-weight="600" fill="#1a1a1a" font-family="JetBrains Mono,monospace">{fmtM(v)}</text>'
        s += f'<text x="{x+bar_w/2}" y="{height-10}" text-anchor="middle" font-size="11" fill="#4a4a4a" font-family="Source Sans 3,sans-serif">{d.get("label","")}</text>'
    s += '</svg>'
    return s


def svg_line_chart(series: list, labels: list, width=560, height=280) -> str:
    if not series or not labels: return ""
    margin = {"top": 20, "right": 20, "bottom": 50, "left": 70}
    cw = width - margin["left"] - margin["right"]
    ch = height - margin["top"] - margin["bottom"]
    all_vals = [v for s in series for v in s.get("values", [])]
    if not all_vals: return ""
    mn, mx = min(all_vals), max(all_vals)
    rng = mx - mn or 1
    mn_adj = mn - rng * 0.1
    mx_adj = mx + rng * 0.1
    rng_adj = mx_adj - mn_adj or 1
    n = len(labels)

    def px(i, v):
        x = margin["left"] + (i / max(n - 1, 1)) * cw
        y = margin["top"] + ch - ((v - mn_adj) / rng_adj) * ch
        return x, y

    s = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">'
    s += f'<rect width="{width}" height="{height}" fill="#faf9f7" rx="8"/>'
    # Zero line if range crosses zero
    if mn_adj < 0 < mx_adj:
        _, zy = px(0, 0)
        s += f'<line x1="{margin["left"]}" y1="{zy}" x2="{width-margin["right"]}" y2="{zy}" stroke="#1a1a1a" stroke-width="1" stroke-dasharray="4,3"/>'
        s += f'<text x="{margin["left"]-8}" y="{zy+4}" text-anchor="end" font-size="10" fill="#1a1a1a" font-family="JetBrains Mono,monospace">0</text>'
    # X labels (every 3rd or 6th)
    step = 6 if n > 18 else 3 if n > 9 else 1
    for i in range(0, n, step):
        x, _ = px(i, 0)
        s += f'<text x="{x}" y="{height-8}" text-anchor="middle" font-size="9" fill="#8a8a8a" font-family="Source Sans 3,sans-serif">{labels[i]}</text>'
    # Lines
    for sr in series:
        vals = sr.get("values", [])
        clr = sr.get("color", "#1e3a5f")
        lw = sr.get("width", 2)
        pts = " ".join(f"{px(i,v)[0]},{px(i,v)[1]}" for i, v in enumerate(vals))
        s += f'<polyline points="{pts}" fill="none" stroke="{clr}" stroke-width="{lw}" stroke-linejoin="round"/>'
    # Legend
    lx = margin["left"] + 10
    for i, sr in enumerate(series):
        ly = margin["top"] + 14 + i * 16
        clr = sr.get("color", "#1e3a5f")
        s += f'<line x1="{lx}" y1="{ly}" x2="{lx+16}" y2="{ly}" stroke="{clr}" stroke-width="2"/>'
        s += f'<text x="{lx+22}" y="{ly+4}" font-size="10" fill="#4a4a4a" font-family="Source Sans 3,sans-serif">{sr.get("label","")}</text>'
    s += '</svg>'
    return s


def svg_area_chart(values: list, labels: list, width=560, height=260, payback_month=None) -> str:
    if not values: return ""
    n = len(values)
    margin = {"top": 20, "right": 20, "bottom": 50, "left": 70}
    cw = width - margin["left"] - margin["right"]
    ch = height - margin["top"] - margin["bottom"]
    mn, mx = min(values), max(values)
    rng = mx - mn or 1
    mn_adj = mn - rng * 0.1
    mx_adj = mx + rng * 0.1
    rng_adj = mx_adj - mn_adj or 1

    def px(i, v):
        x = margin["left"] + (i / max(n - 1, 1)) * cw
        y = margin["top"] + ch - ((v - mn_adj) / rng_adj) * ch
        return x, y

    s = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">'
    s += f'<rect width="{width}" height="{height}" fill="#faf9f7" rx="8"/>'
    # Zero line
    _, zy = px(0, 0)
    zy = max(margin["top"], min(margin["top"] + ch, zy))
    s += f'<line x1="{margin["left"]}" y1="{zy}" x2="{width-margin["right"]}" y2="{zy}" stroke="#1a1a1a" stroke-width="1"/>'
    # Area fills
    pts_pos = []
    pts_neg = []
    for i, v in enumerate(values):
        x, y = px(i, v)
        if v >= 0:
            pts_pos.append(f"{x},{y}")
        else:
            pts_neg.append(f"{x},{y}")
    # Full area path
    pts_line = " ".join(f"{px(i,v)[0]},{px(i,v)[1]}" for i, v in enumerate(values))
    x0, _ = px(0, 0)
    xn, _ = px(n - 1, 0)
    s += f'<polygon points="{x0},{zy} {pts_line} {xn},{zy}" fill="rgba(45,80,22,0.08)" stroke="none"/>'
    # Line
    s += f'<polyline points="{pts_line}" fill="none" stroke="#2d5016" stroke-width="2" stroke-linejoin="round"/>'
    # Payback marker
    if payback_month and 0 < payback_month <= n:
        px_m, py_m = px(payback_month - 1, values[payback_month - 1])
        s += f'<circle cx="{px_m}" cy="{py_m}" r="5" fill="#c8a55c" stroke="#fff" stroke-width="2"/>'
        s += f'<text x="{px_m}" y="{py_m-12}" text-anchor="middle" font-size="10" font-weight="700" fill="#c8a55c" font-family="Source Sans 3,sans-serif">Окупаемость: мес. {payback_month}</text>'
    # X labels
    step = 6 if n > 18 else 3
    for i in range(0, n, step):
        x, _ = px(i, 0)
        lbl = labels[i] if i < len(labels) else str(i + 1)
        s += f'<text x="{x}" y="{height-8}" text-anchor="middle" font-size="9" fill="#8a8a8a" font-family="Source Sans 3,sans-serif">{lbl}</text>'
    s += '</svg>'
    return s


def svg_donut_chart(segments: list, width=280, height=280) -> str:
    if not segments: return ""
    total = sum(s.get("value", 0) for s in segments) or 1
    cx, cy, r = width / 2, height / 2, min(width, height) / 2 - 30
    r_inner = r * 0.55
    s = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">'
    angle = -90
    colors = ["#c8a55c", "#2d5016", "#1e3a5f", "#8b6914", "#6b4c11", "#3a6b35", "#4a6fa5", "#8b2500"]
    for i, seg in enumerate(segments):
        pct = seg["value"] / total
        sweep = pct * 360
        end_angle = angle + sweep
        large = 1 if sweep > 180 else 0
        x1 = cx + r * math.cos(math.radians(angle))
        y1 = cy + r * math.sin(math.radians(angle))
        x2 = cx + r * math.cos(math.radians(end_angle))
        y2 = cy + r * math.sin(math.radians(end_angle))
        ix1 = cx + r_inner * math.cos(math.radians(end_angle))
        iy1 = cy + r_inner * math.sin(math.radians(end_angle))
        ix2 = cx + r_inner * math.cos(math.radians(angle))
        iy2 = cy + r_inner * math.sin(math.radians(angle))
        clr = seg.get("color", colors[i % len(colors)])
        path = f"M{x1},{y1} A{r},{r} 0 {large} 1 {x2},{y2} L{ix1},{iy1} A{r_inner},{r_inner} 0 {large} 0 {ix2},{iy2} Z"
        s += f'<path d="{path}" fill="{clr}"/>'
        # Label
        mid = angle + sweep / 2
        lx = cx + (r + 18) * math.cos(math.radians(mid))
        ly = cy + (r + 18) * math.sin(math.radians(mid))
        anchor = "start" if lx > cx else "end"
        if pct >= 0.05:
            s += f'<text x="{lx}" y="{ly+4}" text-anchor="{anchor}" font-size="10" fill="#4a4a4a" font-family="Source Sans 3,sans-serif">{seg.get("label","")} {round(pct*100)}%</text>'
        angle = end_angle
    # Center text
    s += f'<text x="{cx}" y="{cy-4}" text-anchor="middle" font-size="11" fill="#8a8a8a" font-family="Source Sans 3,sans-serif">ИТОГО</text>'
    s += f'<text x="{cx}" y="{cy+14}" text-anchor="middle" font-size="15" font-weight="700" fill="#1a1a1a" font-family="JetBrains Mono,monospace">{fmtM(total)} ₸</text>'
    s += '</svg>'
    return s


def svg_seasonality(coeffs: list) -> str:
    if not coeffs or len(coeffs) != 12: return ""
    width, height = 500, 180
    margin = {"top": 20, "right": 10, "bottom": 30, "left": 10}
    cw = width - margin["left"] - margin["right"]
    ch = height - margin["top"] - margin["bottom"]
    bar_w = cw / 12 - 4
    max_c = max(coeffs) if coeffs else 1.3
    min_c = min(coeffs) if coeffs else 0.7
    rng = max(max_c - 0.5, 1.5 - 0.5)

    s = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">'
    s += f'<rect width="{width}" height="{height}" fill="#faf9f7" rx="8"/>'
    # 1.0 line
    base_y = margin["top"] + ch * (1 - (1.0 - 0.5) / rng)
    s += f'<line x1="{margin["left"]}" y1="{base_y}" x2="{width-margin["right"]}" y2="{base_y}" stroke="#c8a55c" stroke-width="1" stroke-dasharray="4,3"/>'
    for i, c in enumerate(coeffs):
        x = margin["left"] + i * (bar_w + 4) + 2
        h_bar = abs(c - 0.5) / rng * ch
        y = margin["top"] + ch - h_bar
        if c < 0.9: clr = "#d4a0a0"
        elif c > 1.1: clr = "#a0c8a0"
        else: clr = "#c8c8b0"
        s += f'<rect x="{x}" y="{y}" width="{bar_w}" height="{h_bar}" fill="{clr}" rx="3"/>'
        s += f'<text x="{x+bar_w/2}" y="{y-4}" text-anchor="middle" font-size="9" font-weight="600" fill="#4a4a4a" font-family="JetBrains Mono,monospace">{c:.2f}</text>'
        s += f'<text x="{x+bar_w/2}" y="{height-6}" text-anchor="middle" font-size="9" fill="#8a8a8a" font-family="Source Sans 3,sans-serif">{MONTHS_RU[i]}</text>'
    s += '</svg>'
    return s


def svg_sensitivity_table(changes: list, profits: list, label: str = "Изменение") -> str:
    if not changes or not profits: return ""
    n = len(changes)
    cw = 70
    width = 100 + cw * n
    height = 60
    s = f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="width:100%;max-width:{width}px;">'
    # Header
    s += f'<text x="50" y="18" text-anchor="middle" font-size="10" fill="#8a8a8a" font-family="Source Sans 3,sans-serif">{label}</text>'
    for i, ch_val in enumerate(changes):
        x = 100 + i * cw + cw / 2
        s += f'<text x="{x}" y="18" text-anchor="middle" font-size="10" font-weight="600" fill="#4a4a4a" font-family="JetBrains Mono,monospace">{ch_val:+d}%</text>'
    # Values
    s += f'<text x="50" y="44" text-anchor="middle" font-size="10" fill="#8a8a8a" font-family="Source Sans 3,sans-serif">Прибыль/мес</text>'
    for i, p in enumerate(profits):
        x = 100 + i * cw
        clr = "#e8f5e4" if p > 0 else "#fce8e4" if p < 0 else "#f5f4f1"
        txt_c = "#2d5016" if p > 0 else "#8b2500"
        brd = "2" if changes[i] == 0 else "0.5"
        s += f'<rect x="{x+2}" y="28" width="{cw-4}" height="24" fill="{clr}" stroke="#ddd" stroke-width="{brd}" rx="4"/>'
        s += f'<text x="{x+cw/2}" y="44" text-anchor="middle" font-size="10" font-weight="600" fill="{txt_c}" font-family="JetBrains Mono,monospace">{fmtM(p)}</text>'
    s += '</svg>'
    return s


# ═══════════════════════════════════════
# HTML ШАБЛОН
# ═══════════════════════════════════════

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700;800;900&family=Source+Sans+3:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');
:root{--bg:#faf9f7;--bg2:#f5f4f1;--card:#fff;--t1:#1a1a1a;--t2:#4a4a4a;--t3:#8a8a8a;--ac:#c8a55c;--ac-bg:rgba(200,165,92,.08);--ok:#2d5016;--ok-bg:rgba(45,80,22,.06);--wrn:#8b6914;--wrn-bg:rgba(139,105,20,.06);--err:#8b2500;--err-bg:rgba(139,37,0,.06);--blue:#1e3a5f;--brd:rgba(0,0,0,.08);--r:12px;--rs:8px}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Source Sans 3',sans-serif;background:var(--bg);color:var(--t1);line-height:1.7;-webkit-font-smoothing:antialiased;max-width:800px;margin:0 auto;padding:0 20px}
h1,h2,h3{font-family:'Playfair Display',serif;line-height:1.3}
h1{font-size:28px;font-weight:800}h2{font-size:22px;font-weight:700;margin-bottom:16px}h3{font-size:17px;font-weight:600;margin:20px 0 10px}
.mono{font-family:'JetBrains Mono',monospace}
.section{padding:32px 0;border-bottom:1px solid var(--brd)}
.section-num{display:inline-block;width:28px;height:28px;background:var(--ac);color:#fff;border-radius:50%;text-align:center;line-height:28px;font-size:12px;font-weight:700;margin-right:10px;font-family:'JetBrains Mono',monospace}
.card{background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:20px;margin:16px 0}
.kpi-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.kpi{background:var(--card);border:1px solid var(--brd);border-radius:var(--r);padding:16px;text-align:center}
.kpi-value{font-size:24px;font-weight:700;font-family:'JetBrains Mono',monospace;margin:6px 0}
.kpi-label{font-size:12px;color:var(--t3);font-weight:600;text-transform:uppercase;letter-spacing:1px}
.kpi-hint{font-size:11px;color:var(--t3);margin-top:6px;line-height:1.4}
.kpi.green .kpi-value{color:var(--ok)}.kpi.yellow .kpi-value{color:var(--wrn)}.kpi.red .kpi-value{color:var(--err)}
table{width:100%;border-collapse:collapse;font-size:13px;margin:12px 0}
th{background:var(--bg2);text-align:left;padding:10px 12px;font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:var(--t3);border-bottom:2px solid var(--brd)}
td{padding:10px 12px;border-bottom:1px solid var(--brd)}
tr:last-child td{border-bottom:none}
.total td,.total th{font-weight:700;border-top:2px solid var(--t1);background:var(--bg2)}
.disclaimer{font-size:12px;color:var(--t3);border-top:1px solid var(--brd);padding-top:12px;margin-top:16px;line-height:1.6}
.explain{background:var(--ac-bg);border-left:3px solid var(--ac);border-radius:0 var(--rs) var(--rs) 0;padding:16px 18px;margin:16px 0;font-size:13px;color:var(--t2);line-height:1.75}
.explain strong{color:var(--t1)}
.explain-title{font-size:11px;font-weight:700;color:var(--ac);letter-spacing:1px;text-transform:uppercase;margin-bottom:8px}
.verdict{text-align:center;padding:28px;border-radius:var(--r);margin:20px 0}
.verdict.green{background:var(--ok-bg);border:1px solid rgba(45,80,22,.15)}.verdict .v-icon{font-size:40px;margin-bottom:10px}
.verdict.yellow{background:var(--wrn-bg);border:1px solid rgba(139,105,20,.15)}
.verdict.red{background:var(--err-bg);border:1px solid rgba(139,37,0,.15)}
.verdict .v-title{font-size:18px;font-weight:700;margin-bottom:8px;font-family:'Playfair Display',serif}
.verdict .v-text{font-size:14px;color:var(--t2);max-width:600px;margin:0 auto;line-height:1.6}
.risk-card{display:flex;gap:10px;padding:12px;background:var(--card);border:1px solid var(--brd);border-radius:var(--rs);margin:8px 0;font-size:13px;line-height:1.5}
.risk-icon{font-size:18px;flex-shrink:0}
.cover{text-align:center;padding:60px 20px 40px}
.cover .logo{font-family:'Playfair Display',serif;font-size:18px;font-weight:800;color:var(--ac);letter-spacing:4px;margin-bottom:32px}
.cover h1{font-size:32px;margin-bottom:8px}
.cover .sub{font-size:16px;color:var(--t2);margin-bottom:24px}
.cover-kpis{display:grid;grid-template-columns:1fr 1fr;gap:10px;max-width:400px;margin:24px auto}
.cover-kpi{padding:12px;border-radius:var(--rs);text-align:center}
.cover-kpi.green{background:var(--ok-bg)}.cover-kpi.yellow{background:var(--wrn-bg)}.cover-kpi.red{background:var(--err-bg)}
.cover-kpi .ck-val{font-size:20px;font-weight:700;font-family:'JetBrains Mono',monospace}
.cover-kpi .ck-label{font-size:10px;color:var(--t3);text-transform:uppercase;letter-spacing:1px}
details{margin:12px 0}summary{cursor:pointer;font-weight:600;color:var(--ac);font-size:14px;padding:8px 0}
.scroll-table{overflow-x:auto;-webkit-overflow-scrolling:touch}
.footer{text-align:center;padding:40px 0;font-size:12px;color:var(--t3);line-height:1.8;border-top:1px solid var(--brd);margin-top:32px}
.footer strong{color:var(--ac);letter-spacing:2px}
.btn{display:block;width:100%;padding:14px;border-radius:var(--rs);font-size:14px;font-weight:700;font-family:inherit;cursor:pointer;text-align:center;text-decoration:none;margin:8px 0}
.btn-primary{background:var(--ac);color:#fff;border:none}.btn-secondary{background:var(--card);color:var(--t1);border:1px solid var(--brd)}
@media(max-width:600px){.kpi-grid{grid-template-columns:1fr 1fr}.cover-kpis{grid-template-columns:1fr 1fr}h1{font-size:24px}h2{font-size:19px}.kpi-value{font-size:20px}}
"""


# ═══════════════════════════════════════
# ГЛАВНАЯ ФУНКЦИЯ
# ═══════════════════════════════════════

def render_finmodel_report(data: dict) -> str:
    inp = data.get("input", {})
    capex = data.get("capex", {})
    dash = data.get("dashboard", {})
    pl = data.get("pl_monthly", [])
    cf = data.get("cashflow_monthly", [])
    sens = data.get("sensitivity", {})
    season = data.get("seasonality", [])
    staff = data.get("staff", [])
    opex_bd = data.get("opex_breakdown", {})
    risks = data.get("risks", [])
    recs = data.get("recommendations", [])

    biz = inp.get("business_name", "Бизнес-проект")
    city = inp.get("city", "")
    horizon = inp.get("horizon_months", 36)
    start = inp.get("start_date", "2026")

    # KPI colors
    def kpi_c(val, thresholds):
        for thr, c in thresholds:
            if val is not None and val >= thr: return c
        return "red"

    npv_c = kpi_c(dash.get("npv", 0), [(0, "green"), (-1e9, "red")])
    irr_c = kpi_c(dash.get("irr", 0), [(20, "green"), (10, "yellow"), (-1e9, "red")])
    pb_v = dash.get("payback_months")
    pb_c = kpi_c(100 - (pb_v or 99), [(100 - 12, "green"), (100 - 24, "yellow"), (-1e9, "red")]) if pb_v else "red"
    roi_c = kpi_c(dash.get("roi", 0), [(50, "green"), (20, "yellow"), (-1e9, "red")])

    h = f"""<!DOCTYPE html><html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ZEREK — Финансовая модель: {biz}</title>
<style>{CSS}</style></head><body>
"""

    # ═══ ОБЛОЖКА ═══
    h += '<div class="cover">'
    h += '<div class="logo">ZEREK</div>'
    h += f'<h1>{biz}</h1>'
    h += f'<div class="sub">{city} &middot; {horizon} месяцев &middot; {start}</div>'
    h += '<div class="cover-kpis">'
    h += f'<div class="cover-kpi {roi_c}"><div class="ck-val">{fmtPct(dash.get("roi"))}</div><div class="ck-label">ROI за 3 года</div></div>'
    h += f'<div class="cover-kpi {pb_c}"><div class="ck-val">{pb_v or "—"} мес</div><div class="ck-label">Окупаемость</div></div>'
    h += f'<div class="cover-kpi {npv_c}"><div class="ck-val">{fmtM(dash.get("profit_year1"))}</div><div class="ck-label">Прибыль год 1</div></div>'
    h += f'<div class="cover-kpi {npv_c}"><div class="ck-val">{fmtM(dash.get("npv"))}</div><div class="ck-label">NPV</div></div>'
    h += '</div>'
    h += '<p class="disclaimer" style="border:none;padding-top:24px;">Финансовая модель подготовлена на основе рыночных бенчмарков БНС РК. Все цифры — прогнозные.</p>'
    h += '</div>'

    # ═══ БЛОК 1: ДАШБОРД ═══
    h += '<div class="section"><h2><span class="section-num">1</span>Ключевые показатели</h2>'
    h += '<div class="kpi-grid">'
    kpis = [
        ("NPV", fmtM(dash.get("npv")), "₸", npv_c, "Если > 0 — проект создаёт стоимость"),
        ("IRR", fmtPct(dash.get("irr")), "", irr_c, "Сравните с депозитом (~15%)"),
        ("Окупаемость", str(pb_v or "—"), "мес", pb_c, "Когда вернутся вложения"),
        ("ROI", fmtPct(dash.get("roi")), "", roi_c, "Прибыль на вложенный тенге"),
        ("Безубыточность", fmt(dash.get("bep_clients_day", 0)), "кл/день", "green", f'Мин. {dash.get("bep_clients_day",0)} клиентов/день'),
        ("Средний чек", fmt(dash.get("avg_check", 0)), "₸", "green", "Типовая сумма покупки"),
    ]
    for label, val, unit, clr, hint in kpis:
        h += f'<div class="kpi {clr}"><div class="kpi-label">{label}</div><div class="kpi-value">{val} {unit}</div><div class="kpi-hint">{hint}</div></div>'
    h += '</div>'
    h += '<p class="disclaimer">Показатели рассчитаны при условии выполнения плановых объёмов продаж.</p>'
    h += '</div>'

    # ═══ БЛОК 2: ВЫРУЧКА ═══
    h += '<div class="section"><h2><span class="section-num">2</span>Сколько заработаете</h2>'
    rev_data = [
        {"label": "Год 1", "value": dash.get("revenue_year1", 0), "color": "#c8a55c"},
        {"label": "Год 2", "value": dash.get("revenue_year2", 0), "color": "#b8944a"},
        {"label": "Год 3", "value": dash.get("revenue_year3", 0), "color": "#a07c30"},
    ]
    h += svg_bar_chart(rev_data)
    h += '<table><tr><th>Показатель</th><th>Год 1</th><th>Год 2</th><th>Год 3</th></tr>'
    h += f'<tr><td>Выручка</td><td class="mono">{fmtM(dash.get("revenue_year1"))}</td><td class="mono">{fmtM(dash.get("revenue_year2"))}</td><td class="mono">{fmtM(dash.get("revenue_year3"))}</td></tr>'
    h += f'<tr><td>Чистая прибыль</td><td class="mono">{fmtM(dash.get("profit_year1"))}</td><td class="mono">{fmtM(dash.get("profit_year2"))}</td><td class="mono">{fmtM(dash.get("profit_year3"))}</td></tr>'
    h += f'<tr><td>Маржа</td><td class="mono">{fmtPct(dash.get("margin_year1"))}</td><td class="mono">{fmtPct(dash.get("margin_year2"))}</td><td class="mono">{fmtPct(dash.get("margin_year3"))}</td></tr>'
    h += '</table>'
    h += '<p class="disclaimer">Год 2 и 3 учитывают инфляцию расходов и рост трафика. Реальный рост зависит от качества сервиса и маркетинга.</p>'
    h += '</div>'

    # ═══ БЛОК 3: P&L ═══
    h += '<div class="section"><h2><span class="section-num">3</span>Прибыли и убытки по месяцам</h2>'
    if pl:
        labels_pl = [p.get("label", str(p.get("month", ""))) for p in pl]
        h += svg_line_chart([
            {"label": "Выручка", "values": [p.get("revenue", 0) for p in pl], "color": "#1e3a5f", "width": 2},
            {"label": "Расходы", "values": [p.get("opex", 0) + p.get("cogs", 0) for p in pl], "color": "#8b2500", "width": 1.5},
            {"label": "Чистая прибыль", "values": [p.get("net_profit", 0) for p in pl], "color": "#2d5016", "width": 2},
        ], labels_pl)
        h += '<details><summary>Показать таблицу P&L</summary><div class="scroll-table"><table>'
        h += '<tr><th>Месяц</th><th>Выручка</th><th>Себестоимость</th><th>Валовая</th><th>OPEX</th><th>Налог</th><th>Чистая</th></tr>'
        for p in pl:
            np_c = 'color:var(--ok)' if p.get("net_profit", 0) >= 0 else 'color:var(--err)'
            h += f'<tr><td>{p.get("label","")}</td><td class="mono">{fmtM(p.get("revenue"))}</td><td class="mono">{fmtM(p.get("cogs"))}</td><td class="mono">{fmtM(p.get("gross_profit"))}</td><td class="mono">{fmtM(p.get("opex"))}</td><td class="mono">{fmtM(p.get("tax"))}</td><td class="mono" style="{np_c}">{fmtM(p.get("net_profit"))}</td></tr>'
        h += '</table></div></details>'
    h += '<p class="disclaimer">P&L — начисленные показатели. Реальное движение денег см. Cash Flow.</p>'
    h += '</div>'

    # ═══ БЛОК 4: CASH FLOW ═══
    h += '<div class="section"><h2><span class="section-num">4</span>Движение денег и окупаемость</h2>'
    if cf:
        cum_vals = [c.get("cumulative_cf", 0) for c in cf]
        labels_cf = [c.get("label", str(c.get("month", ""))) for c in cf]
        h += svg_area_chart(cum_vals, labels_cf, payback_month=pb_v)
        h += '<div class="explain"><div class="explain-title">Что это значит?</div>'
        loss_months = sum(1 for v in cum_vals if v < 0)
        h += f'<p>Cash Flow — реальные деньги на вашем счёте. Первые <strong>{loss_months} месяцев</strong> вы будете «в минусе» — это нормальный период разгона.</p>'
        if pb_v:
            h += f'<p>На <strong>{pb_v}-м месяце</strong> накопленный денежный поток выходит в плюс — стартовые вложения полностью вернулись.</p>'
        h += '</div>'
    h += '<p class="disclaimer">Учитывает только операционные потоки. Не учитывает привлечение внешнего финансирования.</p>'
    h += '</div>'

    # ═══ БЛОК 5: CAPEX ═══
    h += '<div class="section"><h2><span class="section-num">5</span>Стартовые вложения</h2>'
    capex_items = [
        ("Оборудование", capex.get("equipment", 0)),
        ("Ремонт", capex.get("renovation", 0)),
        ("Мебель и интерьер", capex.get("furniture", 0)),
        ("Первая закупка", capex.get("first_stock", 0)),
        ("Разрешения и СЭЗ", capex.get("permits", 0)),
        ("Депозит аренды", capex.get("deposit", 0)),
    ]
    capex_items = [(n, v) for n, v in capex_items if v]
    if capex_items:
        donut_segs = [{"label": n, "value": v} for n, v in capex_items]
        h += '<div style="text-align:center;">' + svg_donut_chart(donut_segs) + '</div>'
    capex_total = capex.get("total", sum(v for _, v in capex_items))
    h += '<table><tr><th>Статья</th><th style="text-align:right">Сумма</th><th style="text-align:right">%</th></tr>'
    for name, val in capex_items:
        pct = round(val / capex_total * 100) if capex_total else 0
        h += f'<tr><td>{name}</td><td class="mono" style="text-align:right">{fmt(val)} ₸</td><td class="mono" style="text-align:right">{pct}%</td></tr>'
    h += f'<tr class="total"><td>ИТОГО</td><td class="mono" style="text-align:right">{fmt(capex_total)} ₸</td><td class="mono" style="text-align:right">100%</td></tr>'
    h += '</table>'
    biggest = max(capex_items, key=lambda x: x[1])[0] if capex_items else "оборудование"
    h += f'<div class="explain"><div class="explain-title">Совет</div><p>Самая большая статья — <strong>{biggest}</strong>. На оборудовании можно сэкономить 20–30%, купив б/у. На ремонте экономить не стоит — это первое впечатление клиента.</p></div>'
    h += '</div>'

    # ═══ БЛОК 6: OPEX ═══
    h += '<div class="section"><h2><span class="section-num">6</span>Ежемесячные расходы</h2>'
    opex_items = [
        ("Аренда", opex_bd.get("rent", 0)),
        ("ФОТ с налогами", opex_bd.get("fot", 0)),
        ("Себестоимость", opex_bd.get("cogs_avg", 0)),
        ("Маркетинг", opex_bd.get("marketing", 0)),
        ("Коммунальные", opex_bd.get("utilities", 0)),
        ("ПО и касса", opex_bd.get("software", 0)),
        ("Транспорт", opex_bd.get("transport", 0)),
        ("Прочие", opex_bd.get("other", 0)),
    ]
    opex_items = [(n, v) for n, v in opex_items if v]
    opex_total = sum(v for _, v in opex_items)
    if opex_items:
        donut_segs2 = [{"label": n, "value": v} for n, v in opex_items]
        h += '<div style="text-align:center;">' + svg_donut_chart(donut_segs2) + '</div>'
    h += '<table><tr><th>Статья</th><th style="text-align:right">Сумма/мес</th><th style="text-align:right">%</th></tr>'
    for name, val in opex_items:
        pct = round(val / opex_total * 100) if opex_total else 0
        h += f'<tr><td>{name}</td><td class="mono" style="text-align:right">{fmt(val)} ₸</td><td class="mono" style="text-align:right">{pct}%</td></tr>'
    h += f'<tr class="total"><td>ИТОГО</td><td class="mono" style="text-align:right">{fmt(opex_total)} ₸</td><td class="mono" style="text-align:right">100%</td></tr>'
    h += '</table>'
    top2 = sorted(opex_items, key=lambda x: -x[1])[:2]
    top2_pct = sum(v for _, v in top2) / opex_total * 100 if opex_total else 0
    h += f'<div class="explain"><div class="explain-title">Что это значит?</div><p>Самые тяжёлые статьи: <strong>{top2[0][0]}</strong> и <strong>{top2[1][0] if len(top2)>1 else ""}</strong> ({round(top2_pct)}% всех расходов). Это ваш «минимум выживания» — если выручка ниже <strong>{fmt(opex_total)} ₸</strong>, вы теряете деньги.</p></div>'
    h += '</div>'

    # ═══ БЛОК 7: КОМАНДА ═══
    if staff:
        h += '<div class="section"><h2><span class="section-num">7</span>Команда</h2>'
        h += '<table><tr><th>Роль</th><th style="text-align:center">Кол-во</th><th style="text-align:right">Зарплата</th></tr>'
        fot_total = 0
        for s in staff:
            sal = s.get("salary", 0) * s.get("count", 1)
            fot_total += sal
            owner = " (вы)" if s.get("is_owner") else ""
            h += f'<tr><td>{s.get("role","")}{owner}</td><td class="mono" style="text-align:center">{s.get("count",1)}</td><td class="mono" style="text-align:right">{fmt(sal)} ₸</td></tr>'
        h += f'<tr class="total"><td>ИТОГО ФОТ</td><td></td><td class="mono" style="text-align:right">{fmt(fot_total)} ₸</td></tr>'
        h += '</table>'
        h += '<p class="disclaimer">ФОТ включает налоги работодателя 2026: ОПВР 3.5% + СО 5% + ООСМС 3% = 11.5% сверху.</p>'
        h += '</div>'

    # ═══ БЛОК 8: СЕЗОННОСТЬ ═══
    if season and len(season) == 12:
        h += '<div class="section"><h2><span class="section-num">8</span>Сезонность</h2>'
        h += svg_seasonality(season)
        peak = MONTHS_RU[season.index(max(season))]
        low = MONTHS_RU[season.index(min(season))]
        h += f'<div class="explain"><div class="explain-title">Что это значит?</div><p>Пик спроса — <strong>{peak}</strong>, провал — <strong>{low}</strong>. Коэффициент 0.8 = выручка на 20% ниже среднего. 1.2 = на 20% выше. Учитывайте при планировании закупок и графика сотрудников.</p></div>'
        h += '<p class="disclaimer">Коэффициенты основаны на среднеотраслевых данных. Реальная сезонность может отличаться.</p>'
        h += '</div>'

    # ═══ БЛОК 9: ЧУВСТВИТЕЛЬНОСТЬ ═══
    rev_ch = sens.get("revenue_change", [])
    rev_p = sens.get("profit_at_change", [])
    rent_ch = sens.get("rent_change", [])
    rent_p = sens.get("profit_at_rent_change", [])
    if rev_ch and rev_p:
        h += '<div class="section"><h2><span class="section-num">9</span>Что будет, если что-то пойдёт не так</h2>'
        h += '<h3>Изменение выручки</h3>'
        h += svg_sensitivity_table(rev_ch, rev_p, "Выручка")
        if rent_ch and rent_p:
            h += '<h3 style="margin-top:20px;">Изменение аренды</h3>'
            h += svg_sensitivity_table(rent_ch, rent_p, "Аренда")
        # Find critical point
        crit = None
        for i, p in enumerate(rev_p):
            if p < 0:
                crit = rev_ch[i]; break
        h += '<div class="explain"><div class="explain-title">Что это значит?</div>'
        if crit is not None:
            h += f'<p>Если выручка упадёт на <strong>{abs(crit)}%</strong> — бизнес уходит в убыток. '
        else:
            h += '<p>Даже при падении выручки на 30% бизнес остаётся прибыльным — хороший запас прочности. '
        h += 'Это помогает понять: где самое уязвимое место вашего бизнеса.</p></div>'
        h += '<p class="disclaimer">Анализ показывает влияние одного фактора при прочих равных.</p>'
        h += '</div>'

    # ═══ БЛОК 10: НАЛОГИ ═══
    h += '<div class="section"><h2><span class="section-num">10</span>Налоги</h2>'
    regime = inp.get("tax_regime", "УСН")
    rate = inp.get("tax_rate", 0.03)
    h += f'<div class="card"><p><strong>Режим:</strong> {regime}</p><p><strong>Ставка:</strong> {round(rate*100)}%</p></div>'
    h += f'<div class="explain"><div class="explain-title">Простыми словами</div><p>Упрощённая декларация — самый выгодный режим. Вы платите <strong>{round(rate*100)}% от выручки</strong>, подаёте форму 910.00 раз в полгода. Без НДС до порога.</p></div>'
    h += '</div>'

    # ═══ БЛОК 11: РИСКИ ═══
    if risks or recs:
        h += '<div class="section"><h2><span class="section-num">11</span>На что обратить внимание</h2>'
        if risks:
            h += '<h3>Риски</h3>'
            for r in risks:
                h += f'<div class="risk-card"><div class="risk-icon">⚠️</div><div>{r}</div></div>'
        if recs:
            h += '<h3>Рекомендации</h3>'
            for r in recs:
                h += f'<div class="risk-card"><div class="risk-icon">✅</div><div>{r}</div></div>'
        h += '</div>'

    # ═══ БЛОК 12: ВЕРДИКТ ═══
    h += '<div class="section"><h2><span class="section-num">12</span>Наше заключение</h2>'
    npv_v = dash.get("npv", 0) or 0
    irr_v = dash.get("irr", 0) or 0
    pb_v2 = dash.get("payback_months") or 99
    if npv_v > 0 and irr_v > 15 and pb_v2 <= 18:
        vc, vi = "green", "✅"
        vt = f"Проект финансово состоятелен. Инвестиции окупаются за {pb_v2} месяцев, ROI за 3 года — {fmtPct(dash.get('roi'))}. Рекомендуем к запуску при наличии резерва."
    elif npv_v > 0 and pb_v2 <= 30:
        vc, vi = "yellow", "⚠️"
        vt = f"Проект может быть прибыльным, но окупаемость {pb_v2} месяцев — нужен резерв и терпение. Рекомендуем детальный анализ локации."
    else:
        vc, vi = "red", "🔴"
        vt = "При текущих параметрах проект рискован. Рекомендуем пересмотреть формат, локацию или снизить расходы."
    h += f'<div class="verdict {vc}"><div class="v-icon">{vi}</div><div class="v-title">{"Рекомендуем к запуску" if vc=="green" else "Требует доработки" if vc=="yellow" else "Высокий риск"}</div><div class="v-text">{vt}</div></div>'
    h += '</div>'

    # ═══ БЛОК 13: CTA ═══
    h += '<div class="section" style="border:none;">'
    h += '<a class="btn btn-secondary" href="#" onclick="alert(\'Бизнес-план скоро будет доступен\');return false;">📋 Заказать бизнес-план — 15 000 ₸</a>'
    h += '<a class="btn btn-secondary" href="#" onclick="alert(\'AI-чат скоро будет доступен\');return false;">💬 Обсудить с AI-консультантом</a>'
    h += '</div>'

    # ═══ ПОДВАЛ ═══
    h += '<div class="footer">'
    h += '<p><strong>ZEREK</strong></p>'
    h += '<p>Финансовая аналитика для каждого предпринимателя</p>'
    h += '<p>zerek.cc &middot; @zerekai_bot &middot; Актобе, Казахстан &middot; 2026</p>'
    h += '<p style="margin-top:16px;">Данный отчёт подготовлен автоматически на основе рыночных бенчмарков БНС РК. Все прогнозные цифры носят ориентировочный характер.</p>'
    h += '</div>'

    h += '</body></html>'
    return h


# ═══════════════════════════════════════
# ТЕСТ С MOCK-ДАННЫМИ
# ═══════════════════════════════════════

if __name__ == "__main__":
    import json
    mock = {
        "input": {"business_name": "Кофейня-кафе", "city": "Астана", "format_id": "COFFEE_FULL", "niche_id": "COFFEE", "entity_type": "ИП", "tax_regime": "УСН", "tax_rate": 0.03, "horizon_months": 36, "start_date": "2026-04"},
        "capex": {"equipment": 3200000, "renovation": 1500000, "furniture": 400000, "first_stock": 200000, "permits": 100000, "deposit": 960000, "total": 6360000},
        "dashboard": {"npv": 4500000, "irr": 28, "payback_months": 14, "roi": 72, "bep_monthly": 1800000, "bep_clients_day": 22, "avg_check": 1400, "revenue_year1": 19800000, "revenue_year2": 22680000, "revenue_year3": 25200000, "profit_year1": 3200000, "profit_year2": 5100000, "profit_year3": 6800000, "margin_year1": 16, "margin_year2": 22, "margin_year3": 27, "opex_monthly_avg": 1350000},
        "pl_monthly": [{"month": i+1, "label": f"{'Апр Май Июн Июл Авг Сен Окт Ноя Дек Янв Фев Мар'.split()[i%12]} {'2026' if i<9 else '2027' if i<21 else '2028'}", "revenue": int(1650000*(0.5+i*0.02)), "cogs": int(580000*(0.5+i*0.02)), "gross_profit": int(1070000*(0.5+i*0.02)), "opex": 680000, "ebitda": int(390000*(0.5+i*0.02)-200000), "tax": int(50000*(0.5+i*0.02)), "net_profit": int(340000*(0.5+i*0.02)-200000)} for i in range(36)],
        "cashflow_monthly": [{"month": i+1, "label": f"М{i+1}", "inflow": int(1650000*(0.5+i*0.02)), "outflow": int(1300000 if i>0 else 7600000), "net_cf": int(350000*(0.5+i*0.02)-200000 if i>0 else -6000000), "cumulative_cf": int(-6000000+sum(350000*(0.5+j*0.02)-200000 for j in range(1,i+1)))} for i in range(36)],
        "sensitivity": {"revenue_change": [-30,-20,-10,0,10,20,30], "profit_at_change": [-180000,-40000,100000,260000,420000,580000,740000], "rent_change": [-30,-20,-10,0,10,20,30], "profit_at_rent_change": [400000,350000,300000,260000,210000,160000,110000]},
        "seasonality": [0.85, 0.80, 0.90, 1.00, 1.05, 0.90, 0.85, 0.80, 0.95, 1.10, 1.15, 1.20],
        "staff": [{"role": "Бариста", "count": 2, "salary": 180000, "is_owner": False}, {"role": "Управляющий (вы)", "count": 1, "salary": 0, "is_owner": True}],
        "opex_breakdown": {"rent": 480000, "fot": 360000, "cogs_avg": 580000, "marketing": 50000, "utilities": 35000, "software": 15000, "transport": 0, "other": 20000},
        "risks": ["Высокая конкуренция — в Астане 200+ кофеен", "Рост аренды в ТЦ (5-10%/год)", "Сезонное падение спроса летом"],
        "recommendations": ["Выберите локацию с трафиком 500+ чел/день", "Запустите Instagram за 2 месяца до открытия", "Держите резерв на 3 месяца расходов"],
    }
    html = render_finmodel_report(mock)
    import tempfile, os
    outpath = os.path.join(tempfile.gettempdir(), "zerek_finmodel_test.html")
    with open(outpath, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Generated: {len(html)} chars -> {outpath}")
