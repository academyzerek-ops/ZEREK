"""
ZEREK API Server v3.1 — FastAPI
33 ниши, 14-листовые шаблоны, report v4, finmodel с полной анкетой.
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os, sys, math

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
    area_m2: float = 0; loc_type: str = ""; capital: int = 5000000
    qty: int = 1; founder_works: bool = False
    rent_override: Optional[int] = None; start_month: int = 4

class FMReq(BaseModel):
    """Запрос на генерацию финмодели — все параметры из анкеты."""
    city_id: str; niche_id: str; format_id: str; cls: str = "Стандарт"
    area_m2: float = 0; loc_type: str = ""; capital: int = 5000000
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
            capital=req.capital, qty=req.qty, founder_works=req.founder_works,
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

from fastapi.responses import FileResponse, Response

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
        safe_name = req.fio.replace(" ", "_")[:30]
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="BP_Grant_{safe_name}_{req.city_id}.docx"'},
        )
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        import traceback; d = traceback.format_exc(); print("GRANT-BP ERROR:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])


# ── Финансовая модель (генерация xlsx) ──

@app.post("/finmodel")
def generate_finmodel_endpoint(req: FMReq):
    """Генерирует xlsx финмодель из шаблона + данные из анкеты."""
    if not db: raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        # 1. Quick Check для базовых данных (рынок, налоги и т.д.)
        result = run_quick_check_v3(db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=req.cls, area_m2=req.area_m2, loc_type=req.loc_type,
            capital=req.capital, qty=req.qty, founder_works=req.founder_works,
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
        
        # 3. Генерируем финмодель
        from gen_finmodel import generate_finmodel
        template = os.path.join(DATA_DIR, 'templates', 'finmodel_template.xlsx')
        if not os.path.exists(template):
            template = os.path.join(DATA_DIR, 'finmodel_template.xlsx')
        if not os.path.exists(template):
            raise HTTPException(404, f"Шаблон не найден: {template}")
        
        output = os.path.join('/tmp', f'ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx')
        generate_finmodel(template, params, output_path=output)
        
        return FileResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f'ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx'
        )
    except HTTPException:
        raise
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("ОШИБКА finmodel:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])
