"""
ZEREK API Server v3
Работает с engine_v3 — данные из data/niches/*.xlsx (13 листов).
НК РК 2026. Динамические анкеты. Контентные блоки.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os, sys, math

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from engine_v3 import ZerekDB, run_quick_check_v3
from report_v3 import render_text_report


def clean_for_json(obj):
    """Рекурсивно чистит numpy/pandas типы для JSON."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(i) for i in obj]
    elif type(obj).__name__ in ('int64','int32','int16','int8','uint64','uint32'):
        return int(obj)
    elif type(obj).__name__ in ('float64','float32','float16'):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    elif type(obj).__name__ == 'bool_':
        return bool(obj)
    elif type(obj).__name__ == 'ndarray':
        return obj.tolist()
    elif hasattr(obj, 'item'):
        return obj.item()
    elif str(obj) in ('nan','NaN','inf','-inf'):
        return None
    else:
        try:
            if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
                return None
        except:
            pass
        return obj


app = FastAPI(
    title="ZEREK API",
    description="Quick Check v3 — AI-аналитика для предпринимателей КЗ. НК РК 2026.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(BASE_DIR, "data")
db_error = None
db = None
try:
    db = ZerekDB(data_dir=DATA_DIR)
except Exception as e:
    db_error = str(e)
    print(f"ОШИБКА ЗАГРУЗКИ БД: {e}")


# ─────────────────────────────────────────────
# МОДЕЛИ ЗАПРОСОВ
# ─────────────────────────────────────────────

class QuickCheckRequest(BaseModel):
    city_id: str
    niche_id: str
    format_id: str
    cls: str = "Стандарт"           # Эконом/Стандарт/Бизнес/Премиум
    area_m2: float = 0
    loc_type: str = "улица"
    capital: int = 5000000
    qty: int = 1                     # кол-во боксов/точек
    founder_works: bool = False
    rent_override: Optional[int] = None
    start_month: int = 4


# ─────────────────────────────────────────────
# СЛУЖЕБНЫЕ ЭНДПОИНТЫ
# ─────────────────────────────────────────────

@app.get("/")
def root():
    niches_count = len(db.get_available_niches()) if db else 0
    return {
        "service": "ZEREK API",
        "version": "3.0.0",
        "status": "running",
        "niches_loaded": niches_count,
        "docs": "/docs",
    }

@app.get("/health")
def health():
    return {
        "status": "ok",
        "db_loaded": db is not None,
        "db_error": db_error,
        "version": "3.0.0",
        "niches": [n['niche_id'] for n in db.get_available_niches()] if db else [],
    }

@app.get("/debug")
def debug():
    niches_dir = os.path.join(DATA_DIR, "niches")
    niche_files = sorted(os.listdir(niches_dir)) if os.path.exists(niches_dir) else []
    common_files = [f for f in sorted(os.listdir(DATA_DIR)) if f.endswith('.xlsx')] if os.path.exists(DATA_DIR) else []
    return {
        "base_dir": BASE_DIR,
        "data_dir": DATA_DIR,
        "niches_dir": niches_dir,
        "niche_files": niche_files,
        "common_files": common_files,
        "db_loaded": db is not None,
        "db_error": db_error,
    }


# ─────────────────────────────────────────────
# ДАННЫЕ — Города, Ниши, Форматы, Анкеты
# ─────────────────────────────────────────────

@app.get("/cities")
def get_cities():
    if db is None: raise HTTPException(503, "БД не загружена")
    if db.cities.empty:
        return {"cities": []}
    cols = [c for c in ["city_id","Город","Регион","Тип города","Население всего (чел.)"] if c in db.cities.columns]
    return {"cities": db.cities[cols].dropna(subset=["city_id"]).to_dict("records")}

@app.get("/niches")
def get_niches():
    """Список ниш — генерируется из файлов в data/niches/."""
    if db is None: raise HTTPException(503, "БД не загружена")
    return {"niches": db.get_available_niches()}

@app.get("/formats/{niche_id}")
def get_formats(niche_id: str):
    """Форматы бизнеса внутри ниши."""
    if db is None: raise HTTPException(503, "БД не загружена")
    formats = db.get_formats_for_niche(niche_id)
    if not formats:
        raise HTTPException(404, f"Ниша {niche_id} не найдена")
    return {"niche_id": niche_id, "formats": formats}

@app.get("/survey/{niche_id}")
def get_survey(niche_id: str):
    """Динамическая анкета для ниши (из листа SURVEY)."""
    if db is None: raise HTTPException(503, "БД не загружена")
    survey = db.get_survey(niche_id)
    if not survey:
        raise HTTPException(404, f"Анкета для {niche_id} не найдена")
    return {"niche_id": niche_id, "steps": clean_for_json(survey)}

@app.get("/products/{niche_id}/{format_id}/{cls}")
def get_products(niche_id: str, format_id: str, cls: str):
    """Ассортимент и допродажи по формату и классу."""
    if db is None: raise HTTPException(503, "БД не загружена")
    products = db.get_format_all_rows(niche_id, 'PRODUCTS', format_id, cls)
    return {"products": clean_for_json(products.to_dict("records")) if not products.empty else []}

@app.get("/marketing/{niche_id}/{format_id}/{cls}")
def get_marketing(niche_id: str, format_id: str, cls: str):
    """Маркетинг-каналы по формату и классу."""
    if db is None: raise HTTPException(503, "БД не загружена")
    marketing = db.get_format_all_rows(niche_id, 'MARKETING', format_id, cls)
    return {"marketing": clean_for_json(marketing.to_dict("records")) if not marketing.empty else []}

@app.get("/insights/{niche_id}/{format_id}/{cls}")
def get_insights(niche_id: str, format_id: str, cls: str):
    """Риски и советы по формату и классу."""
    if db is None: raise HTTPException(503, "БД не загружена")
    insights = db.get_format_all_rows(niche_id, 'INSIGHTS', format_id, cls)
    return {"insights": clean_for_json(insights.to_dict("records")) if not insights.empty else []}


# ─────────────────────────────────────────────
# ОБЩИЕ ДАННЫЕ
# ─────────────────────────────────────────────

@app.get("/rent/{city_id}")
def get_rent(city_id: str):
    if db is None: raise HTTPException(503, "БД не загружена")
    if db.rent.empty:
        return {"rent": [], "note": "Данные аренды не загружены"}
    df = db.rent[db.rent["city_id"] == city_id]
    return {"rent": df.to_dict("records") if not df.empty else []}

@app.get("/tax-rate/{city_id}")
def get_tax_rate(city_id: str):
    """Ставка УД по городу (решение маслихата 2026)."""
    if db is None: raise HTTPException(503, "БД не загружена")
    from engine_v3 import get_city_tax_rate
    rate = get_city_tax_rate(db, city_id)
    return {"city_id": city_id, "ud_rate_pct": rate, "base_rate_pct": 4.0}

@app.get("/competitors/{niche_id}/{city_id}")
def get_competitors(niche_id: str, city_id: str):
    if db is None: raise HTTPException(503, "БД не загружена")
    from engine_v3 import get_competitors as gc
    return {"competitors": gc(db, niche_id, city_id)}

@app.get("/permits/{niche_id}")
def get_permits(niche_id: str):
    if db is None: raise HTTPException(503, "БД не загружена")
    from engine_v3 import get_permits as gp
    return {"permits": gp(db, niche_id)}


# ─────────────────────────────────────────────
# ГЛАВНЫЙ ЭНДПОИНТ — QUICK CHECK v3
# ─────────────────────────────────────────────

@app.post("/quick-check")
def quick_check(req: QuickCheckRequest):
    """Полный расчёт Quick Check v3 → JSON."""
    if db is None:
        raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        result = run_quick_check_v3(
            db=db,
            city_id=req.city_id,
            niche_id=req.niche_id,
            format_id=req.format_id,
            cls=req.cls,
            area_m2=req.area_m2,
            loc_type=req.loc_type,
            capital=req.capital,
            qty=req.qty,
            founder_works=req.founder_works,
            rent_override=req.rent_override,
            start_month=req.start_month,
        )
        return {"status": "ok", "result": clean_for_json(result)}
    except Exception as e:
        import traceback
        detail = traceback.format_exc()
        print("ОШИБКА quick-check:", detail)
        raise HTTPException(500, str(e) + "\n" + detail[-500:])

@app.post("/quick-check/report")
def quick_check_report(req: QuickCheckRequest):
    """Текстовый отчёт Quick Check v3 (для Telegram)."""
    if db is None:
        raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        result = run_quick_check_v3(
            db=db,
            city_id=req.city_id,
            niche_id=req.niche_id,
            format_id=req.format_id,
            cls=req.cls,
            area_m2=req.area_m2,
            loc_type=req.loc_type,
            capital=req.capital,
            qty=req.qty,
            founder_works=req.founder_works,
            rent_override=req.rent_override,
            start_month=req.start_month,
        )
        report_text = render_text_report(result)
        return {"status": "ok", "report": report_text}
    except Exception as e:
        import traceback
        raise HTTPException(500, str(e) + "\n" + traceback.format_exc()[-500:])
