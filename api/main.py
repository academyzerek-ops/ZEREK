"""
ZEREK API Server — FastAPI v2
Эндпоинты для Quick Check расчётов.
Обновлено: НК РК 2026, 3 сценария, ставки маслихатов.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from engine import ZerekDB, run_quick_check, get_inflation_region
from engine.report import render_report


def clean_for_json(obj):
    """Рекурсивно конвертирует numpy типы в стандартные Python типы."""
    import math
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(i) for i in obj]
    elif type(obj).__name__ in ('int64', 'int32', 'int16', 'int8', 'uint64', 'uint32'):
        return int(obj)
    elif type(obj).__name__ in ('float64', 'float32', 'float16'):
        v = float(obj)
        return None if math.isnan(v) or math.isinf(v) else v
    elif type(obj).__name__ == 'bool_':
        return bool(obj)
    elif type(obj).__name__ == 'ndarray':
        return obj.tolist()
    elif hasattr(obj, 'item'):
        return obj.item()
    elif str(obj) in ('nan', 'NaN', 'inf', '-inf'):
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
    description="Quick Check расчётный движок для предпринимателей Казахстана. НК РК 2026.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "data")
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
    area_m2: float
    loc_type: str
    capital: int
    rent_override: Optional[int] = None
    start_month: int = 4
    capex_level: str = "стандарт"


# ─────────────────────────────────────────────
# ЭНДПОИНТЫ
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "ZEREK API",
        "version": "2.0.0",
        "status": "running",
        "docs": "/docs",
        "tax_code": "НК РК 2026",
    }


@app.get("/health")
def health():
    return {
        "status": "ok",
        "db_loaded": db is not None,
        "db_error": db_error,
        "version": "2.0.0",
    }


@app.get("/debug")
def debug():
    data_dir = os.path.join(BASE_DIR, "data")
    files = []
    try:
        files = sorted(os.listdir(data_dir))
    except Exception as e:
        files = [f"ERROR: {e}"]
    return {
        "base_dir": BASE_DIR,
        "data_dir": data_dir,
        "data_dir_exists": os.path.exists(data_dir),
        "files_count": len(files),
        "files": files,
        "db_loaded": db is not None,
        "db_error": db_error,
    }


@app.get("/cities")
def get_cities():
    cols = ["city_id", "Город", "Регион", "Тип города", "Население всего (чел.)"]
    df = db.cities[cols].dropna(subset=["city_id"])
    return {"cities": df.to_dict("records")}


@app.get("/niches")
def get_niches():
    cols = ["niche_id", "Название", "Группа", "Статус обзора", "Приоритет"]
    df = db.niches[cols].dropna(subset=["niche_id"])
    return {"niches": df.to_dict("records")}


@app.get("/formats/{niche_id}")
def get_formats(niche_id: str):
    df = db.formats[db.formats["niche_id"] == niche_id]
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Ниша {niche_id} не найдена")
    cols = ["format_id", "niche_id", "Название формата", "Площадь типовая (м²)",
            "Тип локации", "CAPEX min (₸)", "CAPEX стандарт (₸)", "CAPEX премиум (₸)",
            "Порог входа", "Примечания"]
    return {"formats": df[cols].to_dict("records")}


@app.get("/capex/{format_id}")
def get_capex(format_id: str):
    rows = db.capex_totals[db.capex_totals["format_id"] == format_id]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Формат {format_id} не найден")
    return {"capex": rows.iloc[0].to_dict()}


@app.get("/rent/{city_id}")
def get_rent(city_id: str):
    df = db.rent[db.rent["city_id"] == city_id]
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Город {city_id} не найден")
    return {"rent": df.to_dict("records")}


@app.get("/tax-rate/{city_id}")
def get_tax_rate(city_id: str):
    """Ставка УД по городу (решение маслихата 2026)."""
    if db is None:
        raise HTTPException(status_code=503, detail="БД не загружена")
    from engine import get_city_tax_rate
    rate = get_city_tax_rate(db, city_id)
    return {
        "city_id": city_id,
        "ud_rate_pct": rate,
        "base_rate_pct": 4.0,
        "note": "Базовая ставка 4% (НК РК ст.726). Маслихат может ±50%.",
    }


@app.post("/quick-check")
def quick_check(req: QuickCheckRequest):
    """Главный эндпоинт — полный расчёт Quick Check v2."""
    if db is None:
        raise HTTPException(status_code=503, detail=f"База данных не загружена: {db_error}")
    try:
        result = run_quick_check(
            db=db,
            city_id=req.city_id,
            niche_id=req.niche_id,
            format_id=req.format_id,
            area_m2=req.area_m2,
            loc_type=req.loc_type,
            capital=req.capital,
            rent_override=req.rent_override,
            start_month=req.start_month,
            capex_level=req.capex_level,
        )
        return {"status": "ok", "result": clean_for_json(result)}
    except Exception as e:
        import traceback
        detail = traceback.format_exc()
        print("ОШИБКА quick-check:", detail)
        raise HTTPException(status_code=500, detail=str(e) + "\n" + detail[-500:])


@app.post("/quick-check/report")
def quick_check_report(req: QuickCheckRequest):
    """Текстовый отчёт Quick Check v2 (для Telegram)."""
    if db is None:
        raise HTTPException(status_code=503, detail=f"База данных не загружена: {db_error}")
    try:
        result = run_quick_check(
            db=db,
            city_id=req.city_id,
            niche_id=req.niche_id,
            format_id=req.format_id,
            area_m2=req.area_m2,
            loc_type=req.loc_type,
            capital=req.capital,
            rent_override=req.rent_override,
            start_month=req.start_month,
            capex_level=req.capex_level,
        )
        report_text = render_report(result)
        return {"status": "ok", "report": report_text}
    except Exception as e:
        import traceback
        raise HTTPException(status_code=500, detail=str(e) + "\n" + traceback.format_exc()[-500:])


@app.get("/competitors/{niche_id}/{city_id}")
def get_competitors(niche_id: str, city_id: str):
    df = db.competitors[
        (db.competitors["niche_id"] == niche_id) &
        (db.competitors["city_id"] == city_id)
    ]
    if df.empty:
        df = db.competitors[db.competitors["niche_id"] == niche_id]
    if df.empty:
        raise HTTPException(status_code=404, detail="Данные не найдены")
    return {"competitors": df.to_dict("records")}


@app.get("/failure-patterns/{niche_id}")
def get_failure_patterns(niche_id: str):
    rows = db.failure_patterns[db.failure_patterns["niche_id"] == niche_id]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Ниша {niche_id} не найдена")
    return {"pattern": rows.iloc[0].to_dict()}


@app.get("/permits/{niche_id}")
def get_permits(niche_id: str):
    df = db.permits[
        db.permits["niche_id"].str.contains(niche_id, na=False) |
        (db.permits["niche_id"] == "ALL")
    ]
    return {"permits": df.to_dict("records")}


@app.get("/macro/{city_id}")
def get_macro(city_id: str):
    from engine import get_inflation_region
    inflation = get_inflation_region(db, city_id)
    return {
        "city_id": city_id,
        "inflation_pct": inflation,
        "inflation_label": f"{inflation}% годовых (февраль 2026)",
    }
