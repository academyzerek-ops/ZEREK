"""
ZEREK PDF generator — превращает результат run_quick_check_v3 в 12-страничный A4 PDF.
Рендер через WeasyPrint 65+. Системные зависимости: libpango-1.0-0, libpangoft2-1.0-0,
libharfbuzz-subset0 (см. nixpacks.toml).
"""

from __future__ import annotations
import uuid
from datetime import datetime, timezone, timedelta
from html import escape

# ═══════════════════════════════════════════════════════════
# Форматтеры
# ═══════════════════════════════════════════════════════════

def _fmt(n) -> str:
    try:
        return f"{int(n):,}".replace(",", " ")
    except Exception:
        return "—"


def _fmt_k(n) -> str:
    """Компактное отображение сумм: 1.2 млн / 340 тыс / 900"""
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


def _pct(n) -> str:
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
    tz = timezone(timedelta(hours=5))  # UTC+5 — Казахстан
    return datetime.now(tz).strftime("%d.%m.%Y")


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

NICHE_ICONS = {
    "COFFEE": "☕", "DONER": "🌯", "CARWASH": "🚗", "CLEAN": "🧹",
    "GROCERY": "🛒", "PHARMA": "💊", "BARBER": "💈", "BAKERY": "🥐",
    "PIZZA": "🍕", "SUSHI": "🍣", "FASTFOOD": "🍔", "CANTEEN": "🍽️",
    "CONFECTION": "🎂", "SEMIFOOD": "🥟", "NAIL": "💅", "BROW": "✨",
    "LASH": "👁️", "SUGARING": "🌸", "MASSAGE": "💆", "DENTAL": "🦷",
    "FITNESS": "💪", "AUTOSERVICE": "🔧", "TIRE": "🛞", "FLOWERS": "💐",
    "FRUITSVEGS": "🍎", "WATER": "💧", "FURNITURE": "🪑", "PVZ": "📦",
    "DRYCLEAN": "👔", "TAILOR": "🧵", "REPAIR_PHONE": "📱",
    "KINDERGARTEN": "👶", "CYBERCLUB": "🎮",
}

# ═══════════════════════════════════════════════════════════
# CSS
# ═══════════════════════════════════════════════════════════

PDF_CSS = r"""
@page {
  size: A4;
  margin: 18mm 16mm 22mm 16mm;
  @top-left  { content: "ZEREK · Экспресс-оценка"; font-family: 'Inter', sans-serif; font-size: 9pt; color: #9ca3af; }
  @top-right { content: counter(page) " / " counter(pages); font-family: 'JetBrains Mono', monospace; font-size: 9pt; color: #9ca3af; }
  @bottom-center {
    content: "Это экспресс-оценка на основе усреднённых данных рынка Казахстана. Реальные показатели зависят от локации, команды и ситуации. Для запуска — детальная финмодель.";
    font-family: 'Inter', sans-serif; font-size: 7.5pt; color: #9ca3af;
    margin-top: 6mm;
  }
}
@page :first {
  margin: 0;
  @top-left { content: none; }
  @top-right { content: none; }
  @bottom-center { content: none; }
}

* { box-sizing: border-box; }
html, body {
  margin: 0; padding: 0;
  font-family: 'Inter', 'Noto Sans', sans-serif;
  font-size: 10.5pt; line-height: 1.55;
  color: #1f2937; background: #ffffff;
}

h1, h2, h3, h4 { margin: 0; font-weight: 700; letter-spacing: -0.01em; color: #0f172a; }
h1 { font-size: 28pt; line-height: 1.15; }
h2 { font-size: 18pt; margin-bottom: 6pt; }
h3 { font-size: 13pt; margin-bottom: 4pt; }
h4 { font-size: 11pt; margin-bottom: 3pt; color: #374151; }
p { margin: 0 0 6pt; }

.num, .mono { font-family: 'JetBrains Mono', 'Noto Mono', monospace; font-weight: 600; }

.page { page-break-after: always; }
.page:last-child { page-break-after: auto; }

/* Cover */
.cover {
  width: 210mm; height: 297mm;
  background: linear-gradient(160deg, #0f172a 0%, #1e293b 60%, #312e81 100%);
  color: #fff;
  padding: 30mm 20mm;
  display: flex; flex-direction: column; justify-content: space-between;
  position: relative;
  page-break-after: always;
}
.cover-brand { font-size: 14pt; letter-spacing: 0.2em; font-weight: 700; text-transform: uppercase; opacity: 0.8; }
.cover-h1 { font-size: 38pt; line-height: 1.1; margin: 18mm 0 8mm; }
.cover-sub { font-size: 14pt; opacity: 0.85; line-height: 1.5; max-width: 140mm; }
.cover-badge {
  display: inline-block; padding: 3mm 6mm; border-radius: 100px;
  background: rgba(255,255,255,0.12); backdrop-filter: blur(10px);
  font-size: 10pt; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 600;
  margin-bottom: 10mm;
}
.cover-meta { font-size: 10pt; opacity: 0.7; margin-top: 20mm; }
.cover-meta span { display: block; margin-bottom: 2mm; }
.cover-foot { font-size: 9pt; opacity: 0.5; letter-spacing: 0.1em; text-transform: uppercase; }

/* Section header */
.kicker { font-size: 9pt; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: #6366f1; margin-bottom: 6pt; }

/* Verdict banner */
.verdict {
  padding: 6mm 8mm; border-radius: 4mm;
  display: flex; align-items: center; gap: 4mm;
  font-size: 13pt; font-weight: 600;
  margin: 6mm 0;
}
.verdict.green  { background: #dcfce7; color: #166534; border-left: 5px solid #22c55e; }
.verdict.yellow { background: #fef9c3; color: #854d0e; border-left: 5px solid #eab308; }
.verdict.red    { background: #fee2e2; color: #991b1b; border-left: 5px solid #ef4444; }
.verdict-icon { font-size: 18pt; }

/* Hero number */
.hero-box {
  background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 4mm;
  padding: 10mm 8mm; text-align: center; margin: 4mm 0 8mm;
}
.hero-label { font-size: 9pt; font-weight: 700; letter-spacing: 0.15em; text-transform: uppercase; color: #6b7280; margin-bottom: 2mm; }
.hero-num { font-size: 36pt; line-height: 1.1; color: #16a34a; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.hero-num.neg { color: #dc2626; }
.hero-unit { font-size: 11pt; color: #6b7280; margin-top: 2mm; }

/* Stats grid */
.stats { display: flex; gap: 4mm; margin: 4mm 0 8mm; }
.stat {
  flex: 1; background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 3mm;
  padding: 4mm 5mm;
}
.stat-label { font-size: 8pt; font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; color: #6b7280; margin-bottom: 1mm; }
.stat-val { font-size: 14pt; font-weight: 700; font-family: 'JetBrains Mono', monospace; color: #111827; }

/* Passport table */
table { width: 100%; border-collapse: collapse; margin: 4mm 0; }
table.key-val td {
  padding: 3mm 4mm; font-size: 10.5pt;
  border-bottom: 1px solid #e5e7eb;
}
table.key-val td:first-child { color: #6b7280; width: 35%; }
table.key-val td:last-child { font-weight: 600; }
table.key-val tr:last-child td { border-bottom: none; }

/* P&L waterfall */
.pl-row {
  display: flex; justify-content: space-between; align-items: center;
  padding: 2.4mm 3mm; font-size: 10pt; border-bottom: 1px solid #f3f4f6;
}
.pl-row.pos { background: rgba(34, 197, 94, 0.06); }
.pl-row.neg { background: rgba(239, 68, 68, 0.05); }
.pl-row.subtotal { background: #f9fafb; font-weight: 700; margin-top: 2mm; border-radius: 2mm; border: 1px solid #e5e7eb; }
.pl-row.grand {
  background: #dcfce7; color: #166534; font-size: 12pt; font-weight: 700;
  margin-top: 3mm; padding: 4mm; border-radius: 2mm;
  border: 2px solid #22c55e; border-bottom: 2px solid #22c55e;
}
.pl-label { color: #374151; }
.pl-row.neg .pl-val { color: #dc2626; }
.pl-row.pos .pl-val { color: #15803d; }
.pl-val { font-family: 'JetBrains Mono', monospace; font-weight: 600; white-space: nowrap; }
.pl-row.grand .pl-val { color: #166534; font-size: 14pt; }

/* Unit economics chain */
.unit-chain { display: flex; flex-direction: column; gap: 2mm; margin: 4mm 0; }
.unit-step {
  display: flex; justify-content: space-between; align-items: center;
  background: #f9fafb; border-radius: 3mm; padding: 4mm 5mm;
}
.unit-step.final { background: #dcfce7; color: #166534; font-weight: 700; border: 2px solid #22c55e; }
.unit-step-val { font-family: 'JetBrains Mono', monospace; font-size: 14pt; font-weight: 700; }
.unit-step.final .unit-step-val { font-size: 18pt; }
.unit-op { font-size: 8pt; color: #9ca3af; text-align: center; text-transform: uppercase; letter-spacing: 0.15em; margin: 1mm 0; }

/* Scenarios */
.scenario {
  background: #f9fafb; border: 1px solid #e5e7eb; border-left: 4px solid; border-radius: 3mm;
  padding: 4mm 5mm; margin-bottom: 3mm;
}
.scenario.bad  { border-left-color: #ef4444; }
.scenario.base { border-left-color: #6366f1; }
.scenario.good { border-left-color: #22c55e; }
.scen-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 1mm; }
.scen-title { font-size: 11pt; font-weight: 700; color: #111827; }
.scen-val { font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 14pt; }
.scenario.bad  .scen-val { color: #dc2626; }
.scenario.base .scen-val { color: #4f46e5; }
.scenario.good .scen-val { color: #15803d; }
.scen-params { font-size: 9pt; color: #6b7280; }

/* Risk cards */
.risk {
  border: 1px solid #e5e7eb; border-left: 4px solid #eab308;
  border-radius: 3mm; padding: 4mm 5mm; margin-bottom: 3mm;
  page-break-inside: avoid;
}
.risk-title { font-size: 11.5pt; font-weight: 700; color: #111827; margin-bottom: 2mm; }
.risk-title::before { content: "⚠️  "; }
.risk-body { font-size: 10pt; color: #374151; margin-bottom: 3mm; }
.risk-protect {
  background: #f0fdf4; border-radius: 2mm; padding: 3mm 4mm;
  font-size: 9.5pt; color: #111827; line-height: 1.55;
}
.risk-protect strong { color: #15803d; }

/* Checklist */
.checklist-week { margin-bottom: 5mm; }
.checklist-week-h { font-size: 11pt; font-weight: 700; color: #4f46e5; margin-bottom: 2mm; letter-spacing: 0.02em; }
.checklist-item {
  display: flex; gap: 3mm; align-items: flex-start;
  padding: 1.5mm 0; font-size: 10pt; color: #374151;
}
.checkbox {
  width: 4mm; height: 4mm; border: 1.5px solid #9ca3af;
  border-radius: 1mm; flex-shrink: 0; margin-top: 0.5mm;
}

/* Hint / commentary */
.note {
  background: #eef2ff; border-left: 3px solid #6366f1;
  padding: 4mm 5mm; border-radius: 2mm; font-size: 9.5pt; color: #3730a3;
  margin: 4mm 0; line-height: 1.6;
}
.note strong { color: #1e1b4b; }

.muted { color: #6b7280; font-size: 9pt; }

/* Glossary */
.glossary dt { font-weight: 700; font-size: 10.5pt; color: #111827; margin-top: 3mm; }
.glossary dd { margin: 0 0 3mm; font-size: 9.5pt; color: #374151; line-height: 1.55; }

/* Section intro */
.section-intro {
  background: linear-gradient(135deg, #eef2ff, #f5f3ff);
  border-radius: 3mm; padding: 5mm 6mm; margin-bottom: 6mm;
}
.section-intro h2 { color: #3730a3; font-size: 20pt; }
.section-intro p { color: #4338ca; font-size: 10pt; margin-top: 2mm; }
"""

# ═══════════════════════════════════════════════════════════
# Секции
# ═══════════════════════════════════════════════════════════

def _cover_page(report_id: str, project_name: str, city: str, date_str: str) -> str:
    return f"""
<section class="cover">
  <div>
    <div class="cover-brand">ZEREK</div>
    <div class="cover-foot" style="margin-top: 4mm; opacity: 0.5;">AI-платформа бизнес-аналитики · Казахстан</div>
  </div>
  <div>
    <div class="cover-badge">Экспресс-оценка ниши</div>
    <div class="cover-h1">{_e(project_name)}</div>
    <div class="cover-sub">Оценка жизнеспособности идеи на основе данных рынка {_e(city)} и практики малого бизнеса Казахстана.</div>
  </div>
  <div>
    <div class="cover-meta">
      <span>Дата формирования: <strong>{_e(date_str)}</strong></span>
      <span>Номер отчёта: <strong>{_e(report_id)}</strong></span>
    </div>
    <div class="cover-foot">zerek.cc · @zerekai_bot</div>
  </div>
</section>
"""


def _summary_page(m: dict) -> str:
    verdict_cls = m["verdict_color"]
    verdict_label = {
        "green": "Бизнес жизнеспособен",
        "yellow": "Бизнес возможен, но есть риски",
        "red": "Высокий риск — рекомендуем пересмотреть",
    }.get(verdict_cls, "Бизнес возможен, но есть риски")
    icon = {"green": "✅", "yellow": "⚠️", "red": "🚨"}.get(verdict_cls, "⚠️")

    pocket = m["net_in_pocket"]
    pocket_cls = " neg" if pocket <= 0 else ""

    top_findings = []
    if m["safety_margin"] < 20:
        top_findings.append(f"Запас прочности {m['safety_margin']}% — низкий. Любой провал в трафике ведёт к убытку.")
    elif m["safety_margin"] >= 50:
        top_findings.append(f"Запас прочности {m['safety_margin']}% — хороший. Бизнес устойчив к просадкам.")
    if m.get("payback") and m["payback"] <= 12:
        top_findings.append(f"Окупаемость ~{m['payback']} мес — быстро. Меньше риска.")
    elif m.get("payback") and m["payback"] > 24:
        top_findings.append(f"Окупаемость ~{m['payback']} мес — долго. Нужна подушка и терпение.")
    if m["stress"][0]["net_in_pocket"] < 0:
        top_findings.append("В плохом сценарии бизнес уходит в минус — нужна дифференциация или снижение аренды.")
    if not top_findings:
        top_findings.append("Показатели в пределах нормы для вашей ниши.")

    findings_html = "".join(f"<li>{_e(t)}</li>" for t in top_findings[:3])

    return f"""
<section class="page">
  <div class="kicker">Страница 2 · Сводка</div>
  <h2>Главное за 60 секунд</h2>
  <div class="verdict {verdict_cls}">
    <span class="verdict-icon">{icon}</span>
    <span>{verdict_label}</span>
  </div>

  <div class="hero-box">
    <div class="hero-label">В карман собственнику</div>
    <div class="hero-num{pocket_cls}">{_fmt_k(pocket)} ₸</div>
    <div class="hero-unit">в месяц, после всех налогов и соцплатежей</div>
  </div>

  <div class="stats">
    <div class="stat"><div class="stat-label">Окупаемость</div><div class="stat-val">{str(m.get('payback') or '—')} мес</div></div>
    <div class="stat"><div class="stat-label">Старт</div><div class="stat-val">{_fmt_k(m['invMin'])} ₸</div></div>
    <div class="stat"><div class="stat-label">Брейкевен</div><div class="stat-val">{_fmt_k(m['breakEven'])} ₸</div></div>
    <div class="stat"><div class="stat-label">Запас</div><div class="stat-val">{m['safety_margin']}%</div></div>
  </div>

  <h3>Топ-3 вывода</h3>
  <ul style="padding-left: 4mm; margin-top: 2mm;">{findings_html}</ul>

  <div class="note">
    <strong>Как читать отчёт.</strong> Далее идёт паспорт проекта, экономика одного клиента, месячный P&amp;L, стартовые вложения, стресс-тест и риски ниши. В конце — чек-лист на первый месяц и глоссарий.
  </div>
</section>
"""


def _passport_page(m: dict) -> str:
    return f"""
<section class="page">
  <div class="kicker">Страница 3 · Паспорт проекта</div>
  <h2>Что именно оцениваем</h2>
  <table class="key-val">
    <tr><td>📍 Город</td><td>{_e(m['city_name'])}</td></tr>
    <tr><td>🏪 Ниша</td><td>{_e(m['niche_name'])}</td></tr>
    <tr><td>📋 Формат</td><td>{_e(m['format_name'])}</td></tr>
    <tr><td>💎 Класс оснащения</td><td>{_e(m['cls'])}</td></tr>
    <tr><td>📐 Площадь</td><td>{_e(m['area_m2'])} м²</td></tr>
    <tr><td>🏬 Локация</td><td>{_e(m['loc_type'])}</td></tr>
    <tr><td>👨‍💼 Штат</td><td>{_e(m['personnel'] or '—')}</td></tr>
    <tr><td>👥 Целевая аудитория</td><td>{_e(m['audience'] or '—')}</td></tr>
  </table>

  <h3 style="margin-top: 8mm;">Портрет проекта</h3>
  <p>Это {_e(m['niche_name'].lower())} в городе {_e(m['city_name'])}, формат «{_e(m['format_name'])}», класс оснащения «{_e(m['cls'])}». Площадь {_e(m['area_m2'])} м², локация — {_e(m['loc_type'])}.</p>
  <p>При среднем чеке <strong>{_fmt(m['checkMed'])} ₸</strong> и трафике <strong>{_e(m['trafficMed'])}</strong> клиентов в день расчётная месячная выручка составляет <strong>{_fmt_k(m['revenue'])} ₸</strong>.</p>
  <p>Локомотив продаж — <strong>{_e(m['locomotive'] or '—')}</strong>: товар или услуга, которая приводит клиентов и формирует базовую выручку.</p>
</section>
"""


def _unit_econ_page(m: dict) -> str:
    cost_per_tx = round(m['checkMed'] * (m['cogs'] / max(m['revenue'], 1)))
    profit_per_tx = m['checkMed'] - cost_per_tx
    daily = 15 if m['trafficMed'] < 30 else int(m['trafficMed'])
    daily_gross = profit_per_tx * daily
    return f"""
<section class="page">
  <div class="kicker">Страница 4 · Экономика одного клиента</div>
  <h2>Сколько вы зарабатываете с одного чека</h2>

  <div class="unit-chain">
    <div class="unit-step">
      <span>Средний чек</span>
      <span class="unit-step-val">{_fmt(m['checkMed'])} ₸</span>
    </div>
    <div class="unit-op">минус</div>
    <div class="unit-step">
      <span>Себестоимость чека (товар / материалы)</span>
      <span class="unit-step-val" style="color:#dc2626">−{_fmt(cost_per_tx)} ₸</span>
    </div>
    <div class="unit-op">равно</div>
    <div class="unit-step final">
      <span>Заработок с клиента</span>
      <span class="unit-step-val">{_fmt(profit_per_tx)} ₸</span>
    </div>
  </div>

  <div class="note">
    <strong>Что это значит.</strong> Если в день приходит {daily} клиентов — это <strong>{_fmt(daily_gross)} ₸ в день</strong> «наценки после себестоимости». Но из неё ещё нужно заплатить аренду, зарплату, налоги, соцплатежи — и только потом остаток идёт в карман.
  </div>

  <h3>Структура себестоимости</h3>
  <p>По расчётам для вашего формата себестоимость составляет <strong>{round(m['cogs']/max(m['revenue'],1)*100)}%</strong> от выручки. Это прямые расходы на товар/сырьё — они растут пропорционально продажам.</p>
  <p>Остальное ({round((1-m['cogs']/max(m['revenue'],1))*100)}%) — это «наценка после себестоимости» или <em>валовая прибыль</em>. Из неё покрываются все остальные расходы бизнеса.</p>
</section>
"""


def _pnl_page(m: dict) -> str:
    ob = m["opex_breakdown"]
    other = ob.get("other", 0)
    return f"""
<section class="page">
  <div class="kicker">Страница 5 · Месячная экономика</div>
  <h2>Куда уходят деньги</h2>
  <p class="muted">Полный P&amp;L вашего бизнеса в базовом сценарии — выручка, расходы, налоги и что остаётся вам.</p>

  <div class="pl-row pos"><span class="pl-label">Выручка в месяц</span><span class="pl-val">{_fmt(m['revenue'])} ₸</span></div>
  <div class="pl-row neg"><span class="pl-label">Себестоимость (товар / материалы)</span><span class="pl-val">−{_fmt(m['cogs'])} ₸</span></div>
  <div class="pl-row subtotal"><span class="pl-label">Наценка после себестоимости</span><span class="pl-val">{_fmt(m['gross'])} ₸</span></div>

  <div class="pl-row neg"><span class="pl-label">Аренда</span><span class="pl-val">−{_fmt(ob['rent'])} ₸</span></div>
  <div class="pl-row neg"><span class="pl-label">ФОТ (зарплаты + налоги работодателя)</span><span class="pl-val">−{_fmt(ob['fot'])} ₸</span></div>
  <div class="pl-row neg"><span class="pl-label">Маркетинг</span><span class="pl-val">−{_fmt(ob['marketing'])} ₸</span></div>
  <div class="pl-row neg"><span class="pl-label">Коммуналка</span><span class="pl-val">−{_fmt(ob['utilities'])} ₸</span></div>
  <div class="pl-row neg"><span class="pl-label">Расходники, софт, прочее</span><span class="pl-val">−{_fmt(other)} ₸</span></div>
  <div class="pl-row subtotal"><span class="pl-label">Прибыль до налогов</span><span class="pl-val">{_fmt(m['profitBeforeTax'])} ₸</span></div>

  <div class="pl-row neg"><span class="pl-label">Налог {_e(m['taxRegime'])} ({m['taxRatePct']}%)</span><span class="pl-val">−{_fmt(m['tax'])} ₸</span></div>
  <div class="pl-row neg"><span class="pl-label">Соцплатежи собственника (ОПВ + ОСМС + СО)</span><span class="pl-val">−{_fmt(m['social'])} ₸</span></div>

  <div class="pl-row grand"><span class="pl-label">В карман собственнику</span><span class="pl-val">{_fmt(m['net_in_pocket'])} ₸</span></div>

  <div class="note" style="margin-top: 6mm;">
    <strong>Важно.</strong> Налог УСН платится с <em>выручки</em>, не с прибыли — даже если бизнес в минус, налог идёт. Соцплатежи собственника ИП платит за себя независимо от дохода: это обязательные пенсионные, медстрах и соцотчисления.
  </div>
</section>
"""


def _invest_page(m: dict) -> str:
    capex_rows = "".join(
        f'<tr><td>{_e(it.get("name", ""))}</td><td class="num" style="text-align:right">{_fmt(it.get("amount", 0))} ₸</td></tr>'
        for it in m["capexItems"]
    )
    buffer_total = m["bufferTotal"]
    grand_total = m["invMin"] + buffer_total
    return f"""
<section class="page">
  <div class="kicker">Страница 6 · Стартовые вложения</div>
  <h2>Что нужно вложить до открытия</h2>

  <h3>Оборудование и ремонт</h3>
  <table class="key-val">{capex_rows}
    <tr><td><strong>Итого CAPEX</strong></td><td class="num" style="text-align:right"><strong>{_fmt(m['invMin'])} ₸</strong></td></tr>
  </table>

  <h3 style="margin-top: 6mm;">🛡️ Подушка безопасности</h3>
  <p>Деньги сверх CAPEX, которые позволят работать, даже если первые месяцы выручка будет ниже плана.</p>
  <table class="key-val">
    <tr><td>Резерв на 3 месяца расходов</td><td class="num" style="text-align:right">{_fmt(buffer_total)} ₸</td></tr>
  </table>

  <div class="pl-row grand" style="margin-top: 6mm;">
    <span class="pl-label">Всего на старт (с подушкой)</span>
    <span class="pl-val">{_fmt(grand_total)} ₸</span>
  </div>

  <div class="note">
    <strong>Почему подушка критична.</strong> 80% закрытий малого бизнеса — в первые 6 месяцев, и главная причина не «мало клиентов», а <em>кончились деньги до того, как бизнес вышел в плюс</em>. Резерв на 3 месяца — минимум; 6 месяцев — комфорт.
  </div>
</section>
"""


def _stress_page(m: dict) -> str:
    stress = m["stress"]
    s_bad, s_base, s_good = stress[0], stress[1], stress[2]

    def _scen(kind: str, s: dict) -> str:
        neg = s["net_in_pocket"] < 0
        sign = "−" if neg else ""
        val = f"{sign}{_fmt(abs(s['net_in_pocket']))} ₸"
        return f"""
  <div class="scenario {kind}">
    <div class="scen-head">
      <span class="scen-title">{_e(s['label'])}</span>
      <span class="scen-val">{val}/мес</span>
    </div>
    <div class="scen-params">{_e(s['params'])}</div>
  </div>"""

    return f"""
<section class="page">
  <div class="kicker">Страница 7 · Стресс-тест</div>
  <h2>Что будет, если рынок просядет</h2>
  <p class="muted">Проверка устойчивости бизнеса. Каждый сценарий меняет ключевые параметры и пересчитывает «в карман».</p>

  {_scen('bad', s_bad)}
  {_scen('base', s_base)}
  {_scen('good', s_good)}

  <div class="note">
    <strong>Как читать.</strong> Если даже в сценарии «всё плохо» вы не уходите в минус — бизнес устойчив и переживёт плохой квартал. Если уходите в минус — нужна подушка на покрытие убытков или пересмотр формата (меньше аренда, другой класс, другая локация).
  </div>
</section>
"""


def _risks_page(m: dict) -> str:
    risks = m.get("ai_risks") or []
    if not risks:
        return ""
    cards = "".join(
        f"""<div class="risk">
      <div class="risk-title">{_e(r.get('title', ''))}</div>
      <div class="risk-body">{_e(r.get('body', ''))}</div>
      <div class="risk-protect"><strong>Как защититься: </strong>{_e(r.get('protect', ''))}</div>
    </div>"""
        for r in risks[:7]
    )
    return f"""
<section class="page">
  <div class="kicker">Страница 8 · Риски ниши</div>
  <h2>Почему закрываются такие бизнесы</h2>
  <p class="muted">Ниже — 7 самых денежно-критичных рисков для вашей ниши, основанных на практике закрывшихся бизнесов. Для каждого — описание и действие, как защититься.</p>
  {cards}
</section>
"""


def _checklist_page() -> str:
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

    weeks_html = ""
    for title, items in weeks:
        items_html = "".join(f'<div class="checklist-item"><div class="checkbox"></div><div>{_e(it)}</div></div>' for it in items)
        weeks_html += f'<div class="checklist-week"><div class="checklist-week-h">{_e(title)}</div>{items_html}</div>'

    return f"""
<section class="page">
  <div class="kicker">Страница 9 · План действий</div>
  <h2>Чек-лист на первый месяц</h2>
  <p class="muted">Распечатайте и отмечайте по мере выполнения. Порядок имеет значение — неделя 1 важнее всего, 80% провалов происходит из-за плохой локации.</p>
  {weeks_html}
</section>
"""


def _glossary_page() -> str:
    terms = [
        ("В карман собственнику", "Деньги, которые остаются лично вам после всех налогов и обязательных соцплатежей. Не путать с выручкой и не с прибылью до налогов."),
        ("Выручка", "Все деньги, которые пришли от клиентов за месяц. Из неё ничего ещё не вычли."),
        ("Наценка после себестоимости", "То же, что «валовая прибыль». Выручка минус прямые расходы на товар/материалы. Показывает, сколько остаётся на аренду, зарплаты, налоги."),
        ("Окупаемость", "Сколько месяцев нужно, чтобы вернуть стартовые вложения за счёт прибыли. Норма: 12–24 месяца."),
        ("Подушка безопасности", "Деньги сверх CAPEX на покрытие расходов в первые месяцы, пока выручка не достигла плана. Минимум 3 месяца расходов."),
        ("Соцплатежи собственника", "Обязательные платежи ИП за себя: ОПВ (пенсия), ОСМС (медстрах), СО (соцотчисления). Платятся независимо от прибыли."),
        ("Стартовые вложения", "То же, что CAPEX. Деньги на оборудование, ремонт, первый закуп, разрешения — всё до открытия."),
        ("Точка безубыточности", "Минимальная выручка в месяц, при которой бизнес не теряет деньги. Ниже — убыток, выше — прибыль."),
        ("Точка закрытия", "Когда собственник зарабатывает меньше наёмного продавца — смысла вести бизнес нет. Ориентир: ~200 тыс ₸ в карман."),
        ("Точка роста", "Когда прибыль позволяет финансировать найм или новую точку из текущего потока. ~600 тыс ₸ в карман и выше."),
        ("Упрощёнка / УСН", "Налоговый режим для ИП и ТОО с оборотом до ≈ 2,6 млрд ₸/год. Платится процент (2–4%) от выручки."),
    ]
    dt_html = "".join(f"<dt>{_e(t)}</dt><dd>{_e(d)}</dd>" for t, d in terms)
    return f"""
<section class="page">
  <div class="kicker">Страница 10 · Глоссарий</div>
  <h2>Термины простым языком</h2>
  <dl class="glossary">{dt_html}</dl>
</section>
"""


def _methodology_page() -> str:
    return f"""
<section class="page">
  <div class="kicker">Страница 11 · Методология</div>
  <h2>На чём основан этот отчёт</h2>

  <h3>Источники данных</h3>
  <p>Расчёты собраны из открытых и внутренних источников: БНС РК (статистика), Национальный банк РК (макро), 2ГИС (конкуренция), база ZEREK (33 ниши × 15 городов, усреднённые показатели малого бизнеса 2024–2026).</p>

  <h3>Актуальность ставок</h3>
  <p>МРП 2026: 4 325 ₸. Патент ОТМЕНЁН с 01.01.2026 — заменён на статус «Самозанятый». УСН: от 2% до 4% в зависимости от города и ОКЭД. Соцплатежи ИП: ОПВ 10% + ОПВР 3,5% + ОСМС ~5% от 1,4 МРП + СО 3,5% от декларируемой базы.</p>

  <h3>Ограничения экспресс-оценки</h3>
  <p>Это усреднённая модель. Реальные показатели зависят от локации (±30% к выручке), команды, маркетинга и рыночной ситуации. Для запуска бизнеса мы рекомендуем заказать детальную финансовую модель с индивидуальными параметрами.</p>

  <div class="note" style="margin-top: 8mm;">
    <strong>Что делать дальше.</strong> Если оценка показала хороший потенциал — переходите к финансовой модели: помесячный расчёт на 36 месяцев, учёт сезонности, кассовые разрывы, 5 сценариев. Если красный вердикт — рассмотрите другой формат, класс или локацию; или получите бизнес-план для подачи на грант «Бастау Бизнес» (400 МРП).
  </div>

  <h3 style="margin-top: 8mm;">Следующие продукты ZEREK</h3>
  <table class="key-val">
    <tr><td>📊 Финансовая модель</td><td><strong>9 000 ₸</strong> — помесячный расчёт, сезонность, кредит</td></tr>
    <tr><td>📋 Бизнес-план</td><td><strong>15 000 ₸</strong> — для банка/гранта, шаблон Bastau Biznes</td></tr>
    <tr><td>🎯 Pitch Deck</td><td>По запросу — презентация для инвестора</td></tr>
  </table>

  <h3 style="margin-top: 8mm;">Контакты</h3>
  <table class="key-val">
    <tr><td>Telegram-бот</td><td>@zerekai_bot</td></tr>
    <tr><td>Сайт</td><td>zerek.cc</td></tr>
    <tr><td>Email</td><td>hello@zerek.cc</td></tr>
  </table>
</section>
"""

# ═══════════════════════════════════════════════════════════
# Сборка + рендер
# ═══════════════════════════════════════════════════════════

def _prep_metrics(result: dict, niche_id: str, ai_risks: list = None) -> dict:
    """Соберёт плоский dict для всех секций из quick-check результата."""
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
        if "фот" in (it.get("name") or "").lower() or "зарпл" in (it.get("name") or "").lower():
            personnel = it.get("note", "")
            break

    import re
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
        "payback": payback,
        "verdict_color": b10.get("verdict_color", "yellow"),
        "verdict_text": b10.get("verdict_text", ""),
        "ai_risks": ai_risks or [],
    }


def render_quick_check_html(result: dict, niche_id: str, ai_risks: list = None) -> tuple[str, str]:
    """
    Собирает финальный HTML для PDF.
    Возвращает (html_str, report_id).
    """
    m = _prep_metrics(result, niche_id, ai_risks=ai_risks)
    report_id = _report_id()
    date_str = _today_ru()
    project_name = f"{m['niche_name']} · {m['city_name']}"

    sections = [
        _cover_page(report_id, project_name, m["city_name"], date_str),
        _summary_page(m),
        _passport_page(m),
        _unit_econ_page(m),
        _pnl_page(m),
        _invest_page(m),
        _stress_page(m),
        _risks_page(m),
        _checklist_page(),
        _glossary_page(),
        _methodology_page(),
    ]

    body = "\n".join(s for s in sections if s)

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<title>ZEREK · Экспресс-оценка · {_e(project_name)}</title>
<style>{PDF_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""
    return html, report_id


def generate_quick_check_pdf(result: dict, niche_id: str, ai_risks: list = None) -> tuple[bytes, str, str]:
    """
    Рендерит PDF в bytes.
    Возвращает (pdf_bytes, report_id, filename).
    """
    from weasyprint import HTML

    html, report_id = render_quick_check_html(result, niche_id, ai_risks=ai_risks)
    pdf_bytes = HTML(string=html).write_pdf()
    m_niche = NICHE_NAMES.get(niche_id, niche_id)
    filename = f"ZEREK_{m_niche}_{report_id}.pdf".replace(" ", "_")
    return pdf_bytes, report_id, filename
