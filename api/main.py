"""
ZEREK API Server v3 — FastAPI
33 ниши, 14-листовые шаблоны, report v4 с 14 блоками.
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

app = FastAPI(title="ZEREK API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data") if not os.path.exists(os.path.join(BASE_DIR, "data")) else os.path.join(BASE_DIR, "data")
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

@app.get("/")
def root():
    return {"service":"ZEREK API","version":"3.0.0","niches":len(db.niche_registry) if db else 0}

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
    return {"base_dir":BASE_DIR,"data_dir":DATA_DIR,"files":f1,"niche_files":f2,"db_loaded":db is not None,"db_error":db_error}

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


# ── Финансовая модель (генерация xlsx) ──

from fastapi.responses import FileResponse

@app.post("/finmodel")
def generate_finmodel_endpoint(req: QCReq):
    """Генерирует xlsx финмодель из шаблона + данные Quick Check."""
    if not db: raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        # 1. Считаем Quick Check
        result = run_quick_check_v3(db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=req.cls, area_m2=req.area_m2, loc_type=req.loc_type,
            capital=req.capital, qty=req.qty, founder_works=req.founder_works,
            rent_override=req.rent_override, start_month=req.start_month)
        
        # 2. Генерируем финмодель
        from gen_finmodel import generate_from_quickcheck
        template = os.path.join(BASE_DIR, 'templates', 'finmodel_template.xlsx')
        if not os.path.exists(template):
            template = os.path.join(DATA_DIR, 'finmodel_template.xlsx')
        
        output = os.path.join('/tmp', f'ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx')
        generate_from_quickcheck(template, result, output_path=output)
        
        return FileResponse(
            output,
            media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            filename=f'ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx'
        )
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("ОШИБКА finmodel:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])
