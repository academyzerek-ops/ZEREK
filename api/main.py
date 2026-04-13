"""
ZEREK API Server v3.1 — FastAPI
33 ниши, 14-листовые шаблоны, report v4, finmodel с полной анкетой.
"""
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os, sys, math, uuid, time
import httpx

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from engine import ZerekDB, run_quick_check_v3
from report import render_report_v4

def clean(obj):
    if isinstance(obj, dict): return {k: clean(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [clean(i) for i in obj]
    elif type(obj).__name__ in ('int64','int32','int16','int8','uint64','uint32'): return int(obj)
    elif type(obj).__name__ in ('float64','float32','float16'):
        v = float(obj); return None if math.isnan(v) or math.isinf(v) else v
    elif type(obj).__name__ == 'bool_': return bool(obj)
    elif type(obj).__name__ == 'ndarray': return obj.tolist()
    elif hasattr(obj, 'item'): return obj.item()
    elif isinstance(obj, str) and obj in ('nan','NaN','inf','-inf'): return None
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)): return None
    return obj

app = FastAPI(title="ZEREK API", version="3.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data", "kz")
db = None; db_error = None
try:
    db = ZerekDB(data_dir=DATA_DIR)
except Exception as e:
    db_error = str(e); print(f"ОШИБКА БД: {e}")

class QCReq(BaseModel):
    city_id: str; niche_id: str; format_id: str; cls: str = "Стандарт"
    area_m2: float = 0; loc_type: str = ""; capital: Optional[int] = 0
    qty: int = 1; founder_works: bool = False
    rent_override: Optional[int] = None; start_month: int = 4
    capex_level: str = "стандарт"

class FMReq(BaseModel):
    """Запрос на генерацию финмодели — все параметры из анкеты."""
    city_id: str; niche_id: str; format_id: str; cls: str = "Стандарт"
    area_m2: float = 0; loc_type: str = ""; capital: Optional[int] = 0
    qty: int = 1; founder_works: bool = False
    rent_override: Optional[int] = None; start_month: int = 4
    # Finmodel-specific
    entity_type: str = "ИП"
    niche_name: str = ""
    format_name: str = ""
    fot_gross: int = 200000
    headcount: int = 2
    check_med: int = 0
    traffic_med: int = 0
    cogs_pct: float = 0.35
    capex: int = 0
    working_cap: int = 1000000
    credit_amount: int = 0
    credit_rate: float = 0.22
    credit_term: int = 36

@app.get("/")
def root():
    return {"service":"ZEREK API","version":"3.1.0","niches":len(db.niche_registry) if db else 0}

@app.get("/health")
def health():
    n = list(db.niche_registry.keys()) if db else []
    return {"status":"ok","db_loaded":db is not None,"db_error":db_error,"niches_count":len(n),"niches":n}

@app.get("/debug")
def debug():
    f1=[]; f2=[]
    try: f1=sorted(os.listdir(DATA_DIR))
    except: pass
    try: f2=sorted(os.listdir(os.path.join(DATA_DIR,"niches")))
    except: pass
    tpl=[]
    try: tpl=sorted(os.listdir(os.path.join(DATA_DIR,"templates")))
    except: pass
    return {"base_dir":BASE_DIR,"data_dir":DATA_DIR,"files":f1,"niche_files":f2,"templates":tpl,"db_loaded":db is not None,"db_error":db_error}

@app.get("/check-env")
def check_env():
    return {
        "GEMINI_API_KEY_exists": bool(os.environ.get("GEMINI_API_KEY")),
        "GEMINI_API_KEY_length": len(os.environ.get("GEMINI_API_KEY", "")),
        "env_count": len(os.environ),
        "railway_env": bool(os.environ.get("RAILWAY_ENVIRONMENT")),
    }

@app.get("/cities")
def get_cities():
    if not db: raise HTTPException(503,"БД не загружена")
    cols=[c for c in ["city_id","Город","Регион","Население всего (чел.)"] if c in db.cities.columns]
    return {"cities":clean(db.cities[cols].dropna(subset=["city_id"]).to_dict("records"))}

@app.get("/niches")
def get_niches():
    if not db: raise HTTPException(503,"БД не загружена")
    return {"niches":clean(db.get_available_niches())}

@app.get("/formats/{niche_id}")
def get_formats(niche_id: str):
    if not db: raise HTTPException(503,"БД не загружена")
    f=db.get_formats_for_niche(niche_id)
    if not f: raise HTTPException(404,f"Ниша {niche_id} не найдена")
    return {"formats":clean(f)}

@app.get("/locations/{niche_id}")
def get_locations(niche_id: str):
    if not db: raise HTTPException(503,"БД не загружена")
    return {"locations":clean(db.get_locations(niche_id))}

@app.get("/classes/{niche_id}/{format_id}")
def get_classes(niche_id: str, format_id: str):
    if not db: raise HTTPException(503,"БД не загружена")
    return {"classes":db.get_classes_for_format(niche_id, format_id)}

@app.get("/tax-rate/{city_id}")
def get_tax_rate(city_id: str):
    if not db: raise HTTPException(503,"БД не загружена")
    from engine import get_city_tax_rate
    return {"city_id":city_id,"ud_rate_pct":get_city_tax_rate(db, city_id)}

@app.post("/quick-check")
def quick_check(req: QCReq):
    if not db: raise HTTPException(503,f"БД не загружена: {db_error}")
    try:
        result = run_quick_check_v3(db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=req.cls, area_m2=req.area_m2, loc_type=req.loc_type,
            capital=req.capital or 0, qty=req.qty, founder_works=req.founder_works,
            rent_override=req.rent_override, start_month=req.start_month)
        report = render_report_v4(result)
        return {"status":"ok","result":clean(report)}
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("ОШИБКА:",d)
        raise HTTPException(500,str(e)+"\n"+d[-500:])

@app.get("/products/{niche_id}/{format_id}")
def get_products(niche_id:str, format_id:str, cls:str="Стандарт"):
    if not db: raise HTTPException(503,"БД не загружена")
    return {"products":clean(db.get_format_all_rows(niche_id,'PRODUCTS',format_id,cls))}

@app.get("/marketing/{niche_id}/{format_id}")
def get_marketing(niche_id:str, format_id:str, cls:str="Стандарт"):
    if not db: raise HTTPException(503,"БД не загружена")
    return {"marketing":clean(db.get_format_all_rows(niche_id,'MARKETING',format_id,cls))}

@app.get("/insights/{niche_id}/{format_id}")
def get_insights(niche_id:str, format_id:str, cls:str="Стандарт"):
    if not db: raise HTTPException(503,"БД не загружена")
    return {"insights":clean(db.get_format_all_rows(niche_id,'INSIGHTS',format_id,cls))}

@app.get("/survey/{niche_id}")
def get_survey(niche_id:str):
    if not db: raise HTTPException(503,"БД не загружена")
    return {"survey":clean(db.get_survey(niche_id))}


# ── Бизнес-план на грант 400 МРП ──

from fastapi.responses import FileResponse, Response, HTMLResponse

# ── Временное хранилище файлов для скачивания ──
_file_store = {}  # token → {bytes, filename, media_type, ts}

def _store_file(content: bytes, filename: str, media_type: str) -> str:
    """Сохраняет файл и возвращает токен для скачивания."""
    # Очистка файлов старше 30 мин
    now = time.time()
    expired = [k for k, v in _file_store.items() if now - v['ts'] > 1800]
    for k in expired:
        del _file_store[k]
    token = uuid.uuid4().hex
    _file_store[token] = {'bytes': content, 'filename': filename, 'media_type': media_type, 'ts': now}
    return token

@app.get("/download/{token}")
def download_file(token: str):
    """Скачивание файла по токену (GET — работает в Telegram WebView)."""
    f = _file_store.get(token)
    if not f:
        raise HTTPException(404, "Файл не найден или истёк срок (30 мин)")
    return Response(
        content=f['bytes'],
        media_type=f['media_type'],
        headers={"Content-Disposition": f'attachment; filename="{f["filename"]}"'},
    )

class GrantBPReq(BaseModel):
    fio: str; iin: str; phone: str; address: str
    legal_status: str = "безработный"; legal_address: str = ""
    experience_years: int = 0; family_status: str = ""
    city_id: str; niche_id: str; format_id: str
    project_name: str; location_description: str = ""
    loc_type: str = "ТЦ"; own_funds: int = 0
    grant_amount: int = 1730000; start_month: int = 1

@app.post("/grant-bp")
def grant_bp_endpoint(req: GrantBPReq):
    """Генерирует заполненный бизнес-план на грант 400 МРП (.docx)."""
    from grant_bp import generate_grant_bp
    template = os.path.join(os.path.dirname(BASE_DIR), "templates", "bizplan", "grant_400mrp_template.docx")
    if not os.path.exists(template):
        template = os.path.join(DATA_DIR, "templates", "grant_400mrp_template.docx")
    if not os.path.exists(template):
        raise HTTPException(404, f"Шаблон БП не найден: {template}")
    try:
        docx_bytes = generate_grant_bp(
            template_path=template,
            fio=req.fio, iin=req.iin, phone=req.phone, address=req.address,
            legal_status=req.legal_status, legal_address=req.legal_address or req.address,
            experience_years=req.experience_years, family_status=req.family_status,
            city_id=req.city_id, niche_id=req.niche_id, format_id=req.format_id,
            project_name=req.project_name, location_description=req.location_description,
            loc_type=req.loc_type, own_funds=req.own_funds,
            grant_amount=req.grant_amount, start_month=req.start_month,
        )
        fname = f"BP_Grant_{req.city_id}_{req.niche_id}.docx"
        token = _store_file(docx_bytes, fname, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        return {"status": "ok", "token": token, "filename": fname}
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        import traceback; d = traceback.format_exc(); print("GRANT-BP ERROR:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])


# ── Финансовая модель (генерация xlsx) ──

def _compute_finmodel_data(params: dict) -> dict:
    """Вычисляет месячные P&L/CF из параметров (зеркало Excel-формул)."""
    from datetime import datetime
    seasonality = [0.85, 0.85, 0.90, 1.00, 1.05, 1.10, 1.10, 1.05, 1.00, 0.95, 0.95, 1.20]
    horizon = params.get('horizon', 36)
    check0 = params.get('check_med', 1400)
    traffic0 = params.get('traffic_med', 70)
    work_days = params.get('work_days', 30)
    tg = params.get('traffic_growth', 0.07)
    cg = params.get('check_growth', 0.08)
    cogs_pct = params.get('cogs_pct', 0.35)
    loss_pct = params.get('loss_pct', 0.03)
    rent = params.get('rent', 70000)
    fot = params.get('fot_gross', 200000) * params.get('headcount', 2)
    utilities = params.get('utilities', 15000)
    marketing = params.get('marketing', 50000)
    consumables = params.get('consumables', 3500)
    software = params.get('software', 5000)
    other = params.get('other', 10000)
    capex = params.get('capex', 1500000)
    deposit = rent * params.get('deposit_months', 2)
    working_cap = params.get('working_cap', 1000000)
    amort_monthly = capex / (params.get('amort_years', 7) * 12)
    tax_rate = params.get('tax_rate', 0.03)
    credit_amt = params.get('credit_amount', 0)
    credit_rate = params.get('credit_rate', 0.22)
    credit_term = params.get('credit_term', 36)
    wacc = params.get('wacc', 0.20)
    # Credit annuity
    credit_pmt = 0
    if credit_amt > 0 and credit_term > 0:
        mr = credit_rate / 12
        if mr > 0:
            credit_pmt = credit_amt * mr / (1 - (1 + mr) ** -credit_term)
        else:
            credit_pmt = credit_amt / credit_term
    total_investment = capex + deposit + working_cap
    fixed_opex = rent + fot + utilities + marketing + consumables + software + other
    pl_monthly = []
    cf_monthly = []
    cumulative_profit = 0
    cumulative_cf = -total_investment
    payback_month = None
    for m in range(horizon):
        year_factor = (1 + tg) ** (m // 12) * (1 + cg) ** (m // 12)
        s_idx = m % 12
        check_m = check0 * (1 + cg) ** (m / 12)
        traffic_m = traffic0 * (1 + tg) ** (m / 12)
        season_coef = seasonality[s_idx]
        revenue = check_m * traffic_m * work_days * season_coef
        cogs = revenue * cogs_pct
        loss = revenue * loss_pct
        gross = revenue - cogs - loss
        opex = fixed_opex
        ebitda = gross - opex
        depreciation = amort_monthly
        ebt = ebitda - depreciation
        tax = max(0, revenue * tax_rate)
        net_profit = ebt - tax
        cumulative_profit += net_profit
        # Cash flow
        cf_ops = net_profit + depreciation
        cf_inv = -total_investment if m == 0 else 0
        cf_fin = -credit_pmt if credit_amt > 0 and m < credit_term else 0
        cf_net = cf_ops + cf_inv + cf_fin
        cumulative_cf += cf_ops + cf_fin  # exclude initial invest double-count
        if m == 0:
            cumulative_cf = -total_investment + cf_ops + cf_fin
        if payback_month is None and cumulative_cf >= 0:
            payback_month = m + 1
        pl_monthly.append({
            'month': m + 1, 'revenue': round(revenue), 'cogs': round(cogs),
            'gross_profit': round(gross), 'opex': round(opex), 'ebitda': round(ebitda),
            'net_profit': round(net_profit), 'cumulative': round(cumulative_profit)
        })
        cf_monthly.append({
            'month': m + 1, 'operating': round(cf_ops), 'investing': round(cf_inv),
            'financing': round(cf_fin), 'net': round(cf_net), 'cumulative': round(cumulative_cf)
        })
    # Dashboard KPIs
    profit_y1 = sum(p['net_profit'] for p in pl_monthly[:12])
    profit_y2 = sum(p['net_profit'] for p in pl_monthly[12:24]) if horizon > 12 else 0
    profit_y3 = sum(p['net_profit'] for p in pl_monthly[24:36]) if horizon > 24 else 0
    total_profit = sum(p['net_profit'] for p in pl_monthly)
    roi = (total_profit / total_investment * 100) if total_investment > 0 else 0
    # NPV
    npv = -total_investment
    for m, p in enumerate(pl_monthly):
        npv += p['net_profit'] / (1 + wacc / 12) ** (m + 1)
    # IRR approximation
    irr = (total_profit / total_investment / (horizon / 12) * 100) if total_investment > 0 else 0
    # Breakeven
    be_revenue = fixed_opex / (1 - cogs_pct - loss_pct) if (1 - cogs_pct - loss_pct) > 0 else 0
    return {
        'input': {
            'business_name': params.get('business_name', 'Бизнес'),
            'city': params.get('city', ''),
            'horizon_months': horizon,
            'start_date': datetime.now().strftime('%Y'),
        },
        'capex': {
            'equipment': capex, 'deposit': deposit,
            'working_capital': working_cap, 'total': total_investment,
        },
        'dashboard': {
            'npv': round(npv), 'irr': round(irr),
            'roi': round(roi), 'payback_months': payback_month,
            'profit_year1': round(profit_y1), 'profit_year2': round(profit_y2),
            'profit_year3': round(profit_y3),
            'revenue_month1': pl_monthly[0]['revenue'] if pl_monthly else 0,
            'breakeven_revenue': round(be_revenue),
        },
        'pl_monthly': pl_monthly,
        'cashflow_monthly': cf_monthly,
        'seasonality': seasonality,
        'opex_breakdown': {
            'rent': rent, 'fot': fot, 'utilities': utilities,
            'marketing': marketing, 'consumables': consumables,
            'software': software, 'other': other,
        },
        'staff': [{'role': 'Сотрудник', 'count': params.get('headcount', 2), 'salary': params.get('fot_gross', 200000)}],
        'risks': [
            {'name': 'Снижение трафика на 30%', 'impact': 'Убыток в первый год'},
            {'name': 'Рост аренды на 20%', 'impact': 'Снижение маржи'},
            {'name': 'Сезонный спад', 'impact': 'Кассовый разрыв зимой'},
        ],
        'recommendations': [
            'Контролируйте юнит-экономику ежемесячно',
            'Формируйте резерв минимум на 3 месяца',
            'Оптимизируйте маркетинг по ROI каналов',
        ],
    }


@app.post("/finmodel")
def generate_finmodel_endpoint(req: FMReq):
    """Генерирует xlsx финмодель из шаблона + данные из анкеты."""
    if not db: raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        # 1. Quick Check для базовых данных (рынок, налоги и т.д.)
        result = run_quick_check_v3(db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=req.cls, area_m2=req.area_m2, loc_type=req.loc_type,
            capital=req.capital or 0, qty=req.qty, founder_works=req.founder_works,
            rent_override=req.rent_override, start_month=req.start_month)

        # 2. Собираем параметры из анкеты (приоритет) + fallback на QC
        fin = result.get('financials', {})
        tx = result.get('tax', {})

        params = {
            'entity_type': req.entity_type,
            'tax_regime': tx.get('regime', 'УСН'),
            'nds_payer': 'Нет',
            'tax_rate': (tx.get('rate_pct', 3) or 3) / 100,
            'check_med': req.check_med if req.check_med > 0 else fin.get('check_med', 1400),
            'traffic_med': req.traffic_med if req.traffic_med > 0 else fin.get('traffic_med', 70),
            'work_days': 30,
            'traffic_growth': 0.07,
            'check_growth': 0.08,
            'cogs_pct': req.cogs_pct if req.cogs_pct > 0 else fin.get('cogs_pct', 0.35),
            'loss_pct': fin.get('loss_pct', 0.03),
            'rent': req.rent_override or fin.get('rent_month', 70000),
            'fot_gross': req.fot_gross,
            'headcount': req.headcount,
            'utilities': fin.get('utilities', 15000),
            'marketing': fin.get('marketing', 50000),
            'consumables': fin.get('consumables', 3500),
            'software': fin.get('software', 5000),
            'other': fin.get('transport', 10000),
            'capex': req.capex if req.capex > 0 else result.get('capex', {}).get('capex_med', 1500000),
            'deposit_months': 2,
            'working_cap': req.working_cap,
            'amort_years': 7,
            'credit_amount': req.credit_amount,
            'credit_rate': req.credit_rate,
            'credit_term': req.credit_term,
            'wacc': 0.20,
            # Для заголовков
            'business_name': (req.niche_name + ': ' + req.format_name) if req.niche_name else req.format_id,
            'city': result.get('input', {}).get('city_name', req.city_id),
        }

        # 3. Генерируем финмодель (xlsx)
        from gen_finmodel import generate_finmodel
        template = os.path.join(os.path.dirname(BASE_DIR), 'templates', 'finmodel', 'finmodel_template.xlsx')
        if not os.path.exists(template):
            template = os.path.join(DATA_DIR, 'templates', 'finmodel_template.xlsx')
        if not os.path.exists(template):
            raise HTTPException(404, f"Шаблон не найден: {template}")

        output = os.path.join('/tmp', f'ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx')
        generate_finmodel(template, params, output_path=output)

        with open(output, 'rb') as fh:
            xlsx_bytes = fh.read()
        fname = f'ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx'
        token = _store_file(xlsx_bytes, fname, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

        # 4. Генерируем HTML-отчёт
        report_token = None
        try:
            from finmodel_report import render_finmodel_report
            report_data = _compute_finmodel_data(params)
            report_html = render_finmodel_report(report_data)
            report_fname = f'ZEREK_FinReport_{req.niche_id}_{req.city_id}.html'
            report_token = _store_file(report_html.encode('utf-8'), report_fname, 'text/html; charset=utf-8')
        except Exception as re:
            print(f"WARN: finmodel report failed: {re}")

        return {"status": "ok", "token": token, "filename": fname, "report_token": report_token}
    except HTTPException:
        raise
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("ОШИБКА finmodel:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])


@app.post("/finmodel/report")
def finmodel_html_report(data: dict):
    """Генерирует HTML-отчёт по финансовой модели."""
    from finmodel_report import render_finmodel_report
    try:
        html = render_finmodel_report(data)
        return HTMLResponse(content=html)
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("FINMODEL REPORT ERROR:", d)
        raise HTTPException(500, str(e))


# ============================================
# GEMINI RAG — AI-интерпретация отчётов
# ============================================
@app.get("/test-gemini")
def test_gemini():
    key = os.getenv("GEMINI_API_KEY", "")
    # Check all env vars that contain GEMINI or KEY
    env_matches = {k: v[:8]+"..." for k, v in os.environ.items() if "GEMINI" in k.upper() or "API_KEY" in k.upper()}
    info = {"has_key": bool(key), "key_len": len(key), "env_matches": env_matches, "total_env": len(os.environ)}
    if not key:
        return {"status": "no_key", **info}
    try:
        from gemini_rag import get_ai_interpretation
        result = get_ai_interpretation({"test": "Кофейня в Актобе, инвестиции 5 млн, окупаемость 14 мес"})
        return {"status": "ok", **info, "response": result[:500]}
    except Exception as e:
        import traceback
        return {"status": "error", **info, "error": str(e), "trace": traceback.format_exc()[-300:]}


# ============================================
# GEMINI FLASH CHAT
# ============================================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"

SYSTEM_PROMPT = """
Ты — ZEREK, AI-ассистент для предпринимателей Казахстана.

## Кто ты
- Ты не инфоцыган и не кричишь про «успешный успех»
- Ты показываешь реальность: риски, подводные камни, реальные причины банкротств
- Ты заботливый, но жёсткий — не обманываешь клиента розовыми очками
- Ты финансовый консультант с глубокой экспертизой в малом бизнесе Казахстана
- Говоришь просто, без финансового жаргона — твоя аудитория не финансисты

## Платформа ZEREK
ZEREK — edtech + AI-аналитика для предпринимателей. Включает:

1. **ZEREK Academy** — бесплатное обучение бизнесу:
   - Фундамент (12-15 лет): финграмотность с нуля
   - Архитектор (16+): от идеи до запуска

2. **Обзоры рынка** — 50 ниш малого бизнеса × 14 городов КЗ. Бесплатно.

3. **Кейсы (Чужие грабли)** — реальные истории провалов и успехов.

4. **Расчёты:**
   - Экспресс-оценка — 3 000 ₸
   - Финансовая модель — 9 000 ₸: Excel на 60 месяцев
   - Бизнес-план — 15 000 ₸ (скоро)

## Данные Казахстана 2026
- МРП 2026 = 4 325 ₸, НДС = 16%, Ставка НБРК 18%, Инфляция ~12%
- Патент отменён с 01.01.2026 → заменён на «Самозанятый»
- Упрощёнка (УСН): Астана 3%, Алматы 3%, Шымкент 2%, Актобе 3%, Караганда 2%, Атырау 2%

## Как отвечать
- Кратко и по делу, без воды
- Используй конкретные цифры когда знаешь
- Если не знаешь точно — скажи честно
- Всегда предупреждай о рисках
- Тон: как умный друг который шарит в бизнесе и не хочет чтобы ты прогорел
- Отвечай на русском языке
- Никогда не упоминай город Актобе как базу ZEREK
"""

@app.post("/chat")
async def chat_endpoint(request: Request):
    if not GEMINI_API_KEY:
        return {"reply": "AI-чат временно недоступен. Попробуй позже.", "status": "error"}

    body = await request.json()
    user_message = body.get("message", "")
    context = body.get("context", {})
    history = body.get("history", [])

    context_note = ""
    if context.get("screen") and context["screen"] != "chat":
        context_note = f"\n\n[Контекст: пользователь на экране '{context['screen']}'"
        if context.get("title"):
            context_note += f", читает: {context['title']}"
        context_note += "]"

    contents = []
    for msg in history[-20:]:
        role = "user" if msg.get("role") == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg.get("content", "")}]})

    contents.append({"role": "user", "parts": [{"text": user_message + context_note}]})

    payload = {
        "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": contents,
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024, "topP": 0.9}
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GEMINI_URL, json=payload)
            data = resp.json()
            if "candidates" in data and len(data["candidates"]) > 0:
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                return {"reply": text, "status": "ok"}
            else:
                return {"reply": "Не удалось получить ответ. Попробуй ещё раз.", "status": "error"}
    except Exception as e:
        print(f"GEMINI ERROR: {e}")
        return {"reply": "Сервер временно недоступен. Попробуй через минуту.", "status": "error"}
