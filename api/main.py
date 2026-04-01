"""
ZEREK API Server
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os, sys, math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")
if not os.path.exists(DATA_DIR):
    DATA_DIR = os.path.join(BASE_DIR, "data")
sys.path.insert(0, BASE_DIR)

from engine import ZerekDB, run_quick_check_v3, get_city_tax_rate, get_competitors, get_permits
from report import render_text_report

def clean_for_json(obj):
    if isinstance(obj, dict): return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list): return [clean_for_json(i) for i in obj]
    elif type(obj).__name__ in ('int64','int32','int16','int8','uint64','uint32'): return int(obj)
    elif type(obj).__name__ in ('float64','float32','float16'):
        v = float(obj); return None if math.isnan(v) or math.isinf(v) else v
    elif type(obj).__name__ == 'bool_': return bool(obj)
    elif type(obj).__name__ == 'ndarray': return obj.tolist()
    elif hasattr(obj, 'item'): return obj.item()
    elif str(obj) in ('nan','NaN','inf','-inf'): return None
    else:
        try:
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)): return None
        except: pass
        return obj

db_error = None; db = None
try:
    print(f"DATA_DIR: {DATA_DIR}")
    db = ZerekDB(data_dir=DATA_DIR)
except Exception as e:
    db_error = str(e); import traceback; print(f"ОШИБКА: {e}\n{traceback.format_exc()}")

app = FastAPI(title="ZEREK API", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class QuickCheckRequest(BaseModel):
    city_id: str; niche_id: str; format_id: str
    cls: str = "Стандарт"; area_m2: float = 0; loc_type: str = "улица"
    capital: int = 5000000; qty: int = 1; founder_works: bool = False
    rent_override: Optional[int] = None; start_month: int = 4

# === СЛУЖЕБНЫЕ ===
@app.get("/")
def root():
    n = len(db.get_available_niches()) if db else 0
    return {"service":"ZEREK API","version":"3.0.0","status":"running","niches_loaded":n}

@app.get("/health")
def health():
    return {"status":"ok","db_loaded":db is not None,"db_error":db_error,"version":"3.0.0",
            "niches":[n['niche_id'] for n in db.get_available_niches()] if db else [],"data_dir":DATA_DIR}

@app.get("/debug")
def debug():
    nd = os.path.join(DATA_DIR,"niches")
    nf = sorted(os.listdir(nd)) if os.path.exists(nd) else []
    cf = [f for f in sorted(os.listdir(DATA_DIR)) if f.endswith('.xlsx')] if os.path.exists(DATA_DIR) else []
    return {"base_dir":BASE_DIR,"root_dir":ROOT_DIR,"data_dir":DATA_DIR,"data_exists":os.path.exists(DATA_DIR),
            "niches_dir":nd,"niches_exists":os.path.exists(nd),"niche_files":nf,"common_files":cf,
            "db_loaded":db is not None,"db_error":db_error}

# === ДАННЫЕ ===
@app.get("/cities")
def ep_cities():
    if db is None: raise HTTPException(503, f"БД не загружена: {db_error}")
    if db.cities.empty: return {"cities":[]}
    cols = [c for c in ["city_id","Город","Регион","Тип города","Население всего (чел.)"] if c in db.cities.columns]
    return {"cities":db.cities[cols].dropna(subset=["city_id"]).to_dict("records")}

@app.get("/niches")
def ep_niches():
    if db is None: raise HTTPException(503, f"БД не загружена: {db_error}")
    return {"niches":db.get_available_niches()}

@app.get("/formats/{niche_id}")
def ep_formats(niche_id: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    f = db.get_formats_for_niche(niche_id)
    if not f: raise HTTPException(404,f"Ниша {niche_id} не найдена")
    return {"niche_id":niche_id,"formats":f}

@app.get("/locations/{niche_id}")
def ep_locations(niche_id: str):
    """Типы локации для ниши (индивидуальные)."""
    if db is None: raise HTTPException(503,"БД не загружена")
    locs = db.get_locations(niche_id)
    return {"niche_id":niche_id,"locations":clean_for_json(locs)}

@app.get("/classes/{niche_id}/{format_id}")
def ep_classes(niche_id: str, format_id: str):
    """Доступные классы для формата."""
    if db is None: raise HTTPException(503,"БД не загружена")
    classes = db.get_classes_for_format(niche_id, format_id)
    return {"niche_id":niche_id,"format_id":format_id,"classes":classes}

@app.get("/survey/{niche_id}")
def ep_survey(niche_id: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    s = db.get_survey(niche_id)
    if not s: raise HTTPException(404,f"Анкета для {niche_id} не найдена")
    return {"niche_id":niche_id,"steps":clean_for_json(s)}

@app.get("/products/{niche_id}/{format_id}/{cls}")
def ep_products(niche_id: str, format_id: str, cls: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    p = db.get_format_all_rows(niche_id,'PRODUCTS',format_id,cls)
    return {"products":clean_for_json(p.to_dict("records")) if not p.empty else []}

@app.get("/marketing/{niche_id}/{format_id}/{cls}")
def ep_marketing(niche_id: str, format_id: str, cls: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    m = db.get_format_all_rows(niche_id,'MARKETING',format_id,cls)
    return {"marketing":clean_for_json(m.to_dict("records")) if not m.empty else []}

@app.get("/insights/{niche_id}/{format_id}/{cls}")
def ep_insights(niche_id: str, format_id: str, cls: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    i = db.get_format_all_rows(niche_id,'INSIGHTS',format_id,cls)
    return {"insights":clean_for_json(i.to_dict("records")) if not i.empty else []}

@app.get("/rent/{city_id}")
def ep_rent(city_id: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    if db.rent.empty: return {"rent":[]}
    df = db.rent[db.rent["city_id"]==city_id]
    return {"rent":df.to_dict("records") if not df.empty else []}

@app.get("/tax-rate/{city_id}")
def ep_tax(city_id: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    return {"city_id":city_id,"ud_rate_pct":get_city_tax_rate(db,city_id),"base_rate_pct":4.0}

@app.get("/competitors/{niche_id}/{city_id}")
def ep_competitors(niche_id: str, city_id: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    return {"competitors":get_competitors(db,niche_id,city_id)}

@app.get("/permits/{niche_id}")
def ep_permits(niche_id: str):
    if db is None: raise HTTPException(503,"БД не загружена")
    return {"permits":get_permits(db,niche_id)}

# === QUICK CHECK ===
@app.post("/quick-check")
def quick_check(req: QuickCheckRequest):
    if db is None: raise HTTPException(503,f"БД не загружена: {db_error}")
    try:
        result = run_quick_check_v3(db=db,city_id=req.city_id,niche_id=req.niche_id,format_id=req.format_id,
            cls=req.cls,area_m2=req.area_m2,loc_type=req.loc_type,capital=req.capital,
            qty=req.qty,founder_works=req.founder_works,rent_override=req.rent_override,start_month=req.start_month)
        return {"status":"ok","result":clean_for_json(result)}
    except Exception as e:
        import traceback; d=traceback.format_exc(); print("ОШИБКА:",d)
        raise HTTPException(500,str(e)+"\n"+d[-500:])

@app.post("/quick-check/report")
def quick_check_report(req: QuickCheckRequest):
    if db is None: raise HTTPException(503,f"БД не загружена: {db_error}")
    try:
        result = run_quick_check_v3(db=db,city_id=req.city_id,niche_id=req.niche_id,format_id=req.format_id,
            cls=req.cls,area_m2=req.area_m2,loc_type=req.loc_type,capital=req.capital,
            qty=req.qty,founder_works=req.founder_works,rent_override=req.rent_override,start_month=req.start_month)
        return {"status":"ok","report":render_text_report(result)}
    except Exception as e:
        import traceback
        raise HTTPException(500,str(e)+"\n"+traceback.format_exc()[-500:])
