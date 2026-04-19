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

from engine import ZerekDB, run_quick_check_v3, get_niche_config, get_niche_survey
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
    # --- Quick Check v2 adaptive fields (optional, не меняют расчёт) ---
    has_license: Optional[str] = None          # "yes" / "no" / "in_progress"
    staff_mode: Optional[str] = None            # "self" / "hired"
    staff_count: Optional[int] = None
    specific_answers: Optional[dict] = None     # {"Q_CHAIRS": "3-5", ...}

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
    # --- Quick Check v2 adaptive answers (опц.) ---
    specific_answers: Optional[dict] = None
    capex_level: str = "стандарт"

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

CAPEX_TO_CLS = {"эконом":"Эконом","стандарт":"Стандарт","бизнес":"Бизнес","премиум":"Премиум"}

@app.post("/quick-check")
def quick_check(req: QCReq):
    if not db: raise HTTPException(503,f"БД не загружена: {db_error}")
    try:
        cls = CAPEX_TO_CLS.get((req.capex_level or "").strip().lower(), req.cls)
        # v2 adaptive fields (has_license / staff_mode / staff_count / specific_answers)
        # пока просто протаскиваем в ответ для трассировки, не меняя расчёт.
        result = run_quick_check_v3(db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=cls, area_m2=req.area_m2, loc_type=req.loc_type,
            capital=req.capital or 0, qty=req.qty, founder_works=req.founder_works,
            rent_override=req.rent_override, start_month=req.start_month)
        report = render_report_v4(result)
        adaptive = {
            "has_license": req.has_license,
            "staff_mode": req.staff_mode,
            "staff_count": req.staff_count,
            "specific_answers": req.specific_answers,
        }
        # Вставим только если что-то пришло (v1 клиент ничего не меняет)
        if any(v is not None for v in adaptive.values()):
            if isinstance(report, dict):
                report.setdefault("user_inputs", {}).update({k: v for k, v in adaptive.items() if v is not None})
        return {"status":"ok","result":clean(report)}
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("ОШИБКА:",d)
        raise HTTPException(500,str(e)+"\n"+d[-500:])

@app.get("/niche-config/{niche_id}")
def niche_config(niche_id: str):
    """Конфиг адаптивной анкеты Quick Check v2 для указанной ниши."""
    if not db: raise HTTPException(503,"БД не загружена")
    try:
        cfg = get_niche_config(db, niche_id)
        return clean(cfg)
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

@app.get("/niche-survey/{niche_id}")
def niche_survey(niche_id: str, tier: str = "express"):
    """Адаптивная анкета (упорядоченный список вопросов) для ниши и tier'а
    (express|finmodel). Источник: data/kz/09_surveys.xlsx."""
    if not db: raise HTTPException(503,"БД не загружена")
    try:
        return clean(get_niche_survey(db, niche_id, tier))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

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


@app.get("/niche-risks/{niche_id}")
def get_niche_risks(niche_id: str, debug: int = 0):
    """Структурированные риски ниши через Gemini (из knowledge/niches/*_insight.md)."""
    from gemini_rag import extract_niche_risks
    diag = {} if debug else None
    risks = extract_niche_risks(niche_id.upper(), diag=diag)
    out = {"niche_id": niche_id.upper(), "risks": risks}
    if debug:
        out["_diag"] = diag
    return out


@app.get("/pdf-health")
def pdf_health():
    """Diagnostic: is the PDF generator (ReportLab) installed and able to render?"""
    try:
        import reportlab
    except Exception as e:
        return {"status": "not_installed", "engine": "reportlab", "error": str(e)[:300]}
    try:
        from pdf_gen import generate_quick_check_pdf, _register_fonts_once
        _register_fonts_once()
        return {
            "status": "ok",
            "engine": "reportlab",
            "reportlab_version": reportlab.Version,
            "fonts_registered": True,
        }
    except Exception as e:
        import traceback
        return {"status": "fail", "error": str(e)[:400], "trace": traceback.format_exc()[-2000:]}


@app.post("/quick-check/pdf")
def generate_pdf(req: QCReq):
    """
    Генерирует 11-страничный PDF по тем же параметрам, что и /quick-check.
    Возвращает {token, filename, pdf_url, report_id} — клиент открывает pdf_url через openLink.
    """
    if not db: raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        # Defensive import — if weasyprint isn't installed on this deploy, fail gracefully
        try:
            from pdf_gen import generate_quick_check_pdf
        except Exception as e:
            raise HTTPException(503, f"PDF-генератор временно недоступен: {e}")

        cls = CAPEX_TO_CLS.get((req.capex_level or "").strip().lower(), req.cls)
        result = run_quick_check_v3(
            db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=cls, area_m2=req.area_m2, loc_type=req.loc_type,
            capital=req.capital or 0, qty=req.qty, founder_works=req.founder_works,
            rent_override=req.rent_override, start_month=req.start_month,
        )
        rendered = render_report_v4(result)

        from gemini_rag import extract_niche_risks
        ai_risks = extract_niche_risks(req.niche_id.upper())

        pdf_bytes, report_id, filename = generate_quick_check_pdf(rendered, req.niche_id.upper(), ai_risks=ai_risks)
        token = _store_file(pdf_bytes, filename, "application/pdf", disposition="inline")
        return {
            "token": token,
            "report_id": report_id,
            "filename": filename,
            "pdf_url": f"/download/{token}",
            "size_bytes": len(pdf_bytes),
        }
    except HTTPException:
        raise
    except Exception as e:
        import traceback; d = traceback.format_exc(); print("PDF ERROR:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])


# ── Бизнес-план на грант 400 МРП ──

from fastapi.responses import FileResponse, Response, HTMLResponse

# ── Временное хранилище файлов для скачивания ──
_file_store = {}  # token → {bytes, filename, media_type, ts}

_FILE_TTL_SECONDS = 7 * 24 * 3600  # 7 дней для PDF-отчётов

def _store_file(content: bytes, filename: str, media_type: str, disposition: str = 'attachment') -> str:
    """Сохраняет файл и возвращает токен для скачивания."""
    now = time.time()
    expired = [k for k, v in _file_store.items() if now - v['ts'] > _FILE_TTL_SECONDS]
    for k in expired:
        del _file_store[k]
    token = uuid.uuid4().hex
    _file_store[token] = {
        'bytes': content, 'filename': filename, 'media_type': media_type,
        'ts': now, 'disposition': disposition,
    }
    return token

@app.get("/download/{token}")
def download_file(token: str):
    """Скачивание/предпросмотр файла по токену (GET — работает в Telegram WebView)."""
    f = _file_store.get(token)
    if not f:
        raise HTTPException(404, "Файл не найден или истёк срок хранения")
    disp = f.get('disposition', 'attachment')
    filename = f['filename']
    # RFC 5987 — всегда кодируем filename для non-ASCII, оставляем ASCII-дубль для старых клиентов
    from urllib.parse import quote
    ascii_name = filename.encode('ascii', 'ignore').decode('ascii') or 'file'
    encoded = quote(filename, safe='')
    content_disposition = (
        f"{disp}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded}"
    )
    return Response(
        content=f['bytes'],
        media_type=f['media_type'],
        headers={"Content-Disposition": content_disposition},
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


def _parse_pct(val):
    """'30%' / '0.3' / 30 → 0.30. Возвращает None если не парсится."""
    if val is None: return None
    try:
        s = str(val).strip().rstrip('%').replace(',', '.')
        f = float(s)
        return f / 100 if f > 1 else f
    except Exception:
        return None

def _parse_int(val):
    """'3-5' → 4 (midpoint), '200+' → 250, '100' → 100, '10-20' → 15."""
    if val is None: return None
    s = str(val).strip()
    if not s or s.lower() == 'nan': return None
    if s.endswith('+'):
        try:
            base = int(s.rstrip('+').strip())
            return int(base * 1.25)
        except Exception:
            return None
    if '-' in s:
        try:
            a, b = s.split('-', 1)
            return (int(a.strip()) + int(b.strip())) // 2
        except Exception:
            pass
    try:
        return int(float(s))
    except Exception:
        return None

# Маппинг qid → поле FMReq + парсер
_FM_FIELD_MAP = {
    # cogs / fudcost (%)
    'O_FOODCOST': ('cogs_pct', _parse_pct),
    'F_COGS':     ('cogs_pct', _parse_pct),
    'D_COGS':     ('cogs_pct', _parse_pct),
    'A_COGS':     ('cogs_pct', _parse_pct),
    'H_COGS':     ('cogs_pct', _parse_pct),
    # check / средний чек
    'A_CHECK': ('check_med', _parse_int),
    'O_CHECK': ('check_med', _parse_int),
    'D_CHECK': ('check_med', _parse_int),
    'E_CHECK': ('check_med', _parse_int),
    'H_CHECK': ('check_med', _parse_int),
    'P_CHECK_OR_RATE': ('check_med', _parse_int),
    'F_CHECK_OR_UNIT': ('check_med', _parse_int),
    'G_FEE':           ('check_med', _parse_int),
    'B_REP_AVG_PRICE': ('check_med', _parse_int),
    'B_PHOTO_CHECK':   ('check_med', _parse_int),
    'B_FIT_SUB_PRICE': ('check_med', _parse_int),
    'B_CC_RATE':       ('check_med', _parse_int),
    # traffic / volume
    'O_TRAFFIC': ('traffic_med', _parse_int),
    'E_TRAFFIC': ('traffic_med', _parse_int),
    'H_VOLUME':  ('traffic_med', _parse_int),
    'F_VOLUME':  ('traffic_med', _parse_int),
    'D_LOAD':    ('traffic_med', _parse_int),
    'P_CLIENTS_PER_MONTH': ('traffic_med', _parse_int),
    'G_KIDS_COUNT': ('traffic_med', _parse_int),
    # rent
    'A_RENT':     ('rent_override', _parse_int),
    'O_RENT_VAL': ('rent_override', _parse_int),
    'D_RENT':     ('rent_override', _parse_int),
    'E_RENT':     ('rent_override', _parse_int),
    'F_RENT':     ('rent_override', _parse_int),
    'G_RENT':     ('rent_override', _parse_int),
    'H_RENT':     ('rent_override', _parse_int),
    'P_RENT':     ('rent_override', _parse_int),
    # headcount
    'A_CHAIRS':       ('headcount', _parse_int),
    'D_POSTS':        ('headcount', _parse_int),
    'O_STAFF_COUNT':  ('headcount', _parse_int),
    'E_STAFF_COUNT':  ('headcount', _parse_int),
    'G_STAFF_COUNT':  ('headcount', _parse_int),
    'F_STAFF_COUNT':  ('headcount', _parse_int),
    'H_STAFF_COUNT':  ('headcount', _parse_int),
    'D_STAFF_COUNT':  ('headcount', _parse_int),
    # credit
    'U_CREDIT_AMOUNT': ('credit_amount', _parse_int),
    'U_CREDIT_RATE':   ('credit_rate',   _parse_pct),
    'U_CREDIT_TERM':   ('credit_term',   _parse_int),
    # capex / working cap
    'F_EQUIPMENT_CAPEX': ('capex',       _parse_int),
    'E_INITIAL_STOCK':   ('working_cap', _parse_int),
}

def _apply_adaptive_answers(req: FMReq) -> FMReq:
    """Применяет specific_answers к полям FMReq. Возвращает тот же объект."""
    if not req.specific_answers:
        return req
    for qid, raw in (req.specific_answers or {}).items():
        if qid not in _FM_FIELD_MAP:
            continue
        field, parser = _FM_FIELD_MAP[qid]
        parsed = parser(raw)
        if parsed is None:
            continue
        setattr(req, field, parsed)
    return req


@app.post("/finmodel")
def generate_finmodel_endpoint(req: FMReq):
    """Генерирует xlsx финмодель из шаблона + данные из анкеты."""
    if not db: raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        # 0. Применяем адаптивные ответы (specific_answers) к полям FMReq
        _apply_adaptive_answers(req)
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
@app.post("/ai-chat")
async def ai_chat(request: Request):
    body = await request.json()
    question = body.get("question", "")
    context = body.get("context", "")
    if not question:
        return {"answer": "Задайте вопрос."}
    from gemini_rag import get_ai_interpretation
    answer = get_ai_interpretation({"question": question, "lesson_context": context})
    return {"answer": answer}

@app.get("/test-gemini")
def test_gemini():
    try:
        from gemini_rag import get_ai_interpretation
        result = get_ai_interpretation({"test": "Кофейня в Актобе, инвестиции 5 млн, окупаемость 14 мес"})
        return {"status": "ok", "response": result[:500]}
    except Exception as e:
        return {"status": "error", "error": str(e)}


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
   - Экспресс-оценка — 5 000 ₸
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
- Отвечай чистым текстом без Markdown. Не используй звёздочки, решётки, списки с дефисами
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
                from gemini_rag import clean_markdown
                text = clean_markdown(data["candidates"][0]["content"]["parts"][0]["text"])
                return {"reply": text, "status": "ok"}
            else:
                return {"reply": "Не удалось получить ответ. Попробуй ещё раз.", "status": "error"}
    except Exception as e:
        print(f"GEMINI ERROR: {e}")
        return {"reply": "Сервер временно недоступен. Попробуй через минуту.", "status": "error"}
