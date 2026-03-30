"""
ZEREK API Server — FastAPI
Эндпоинты для Quick Check расчётов.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import os
import sys

# Путь к движку и данным
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from engine import ZerekDB, run_quick_check, get_inflation_region
from engine.report import render_report

app = FastAPI(
    title="ZEREK API",
    description="Quick Check расчётный движок для предпринимателей Казахстана",
    version="1.0.0"
)

# CORS — разрешаем запросы из Telegram Mini App и браузера
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Загружаем базу данных один раз при старте
DATA_DIR = os.path.join(BASE_DIR, "data")
db = ZerekDB(data_dir=DATA_DIR)


# ─────────────────────────────────────────────
# МОДЕЛИ ЗАПРОСОВ
# ─────────────────────────────────────────────

class QuickCheckRequest(BaseModel):
    city_id: str               # "AKT", "ALA", "AST" и т.д.
    niche_id: str              # "COFFEE", "BARBER", "CARWASH" и т.д.
    format_id: str             # "COFFEE_KIOSK", "BARBER_STD" и т.д.
    area_m2: float             # площадь в м²
    loc_type: str              # "Спальный район стрит" / "Центр стрит 1 лин" / "ТЦ" / "Отдельное здание/бокс"
    capital: int               # стартовый капитал в ₸
    rent_override: Optional[int] = None   # аренда в ₸/мес если знает
    start_month: int = 4       # месяц открытия (1-12)
    capex_level: str = "стандарт"  # "эконом" / "стандарт" / "премиум"


# ─────────────────────────────────────────────
# ЭНДПОИНТЫ
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "service": "ZEREK API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/cities")
def get_cities():
    """Список городов с населением."""
    cols = ["city_id", "Город", "Регион", "Тип города", "Население всего (чел.)"]
    df = db.cities[cols].dropna(subset=["city_id"])
    return {"cities": df.to_dict("records")}


@app.get("/niches")
def get_niches():
    """Список ниш с приоритетами."""
    cols = ["niche_id", "Название", "Группа", "Статус обзора", "Приоритет"]
    df = db.niches[cols].dropna(subset=["niche_id"])
    return {"niches": df.to_dict("records")}


@app.get("/formats/{niche_id}")
def get_formats(niche_id: str):
    """Форматы для конкретной ниши."""
    df = db.formats[db.formats["niche_id"] == niche_id]
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Ниша {niche_id} не найдена")
    cols = ["format_id", "niche_id", "Название формата", "Площадь типовая (м²)",
            "Тип локации", "CAPEX min (₸)", "CAPEX стандарт (₸)", "CAPEX премиум (₸)",
            "Порог входа", "Примечания"]
    return {"formats": df[cols].to_dict("records")}


@app.get("/capex/{format_id}")
def get_capex(format_id: str):
    """CAPEX итоги по формату."""
    rows = db.capex_totals[db.capex_totals["format_id"] == format_id]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Формат {format_id} не найден")
    return {"capex": rows.iloc[0].to_dict()}


@app.get("/rent/{city_id}")
def get_rent(city_id: str):
    """Ставки аренды для города."""
    df = db.rent[db.rent["city_id"] == city_id]
    if df.empty:
        raise HTTPException(status_code=404, detail=f"Город {city_id} не найден")
    return {"rent": df.to_dict("records")}


@app.post("/quick-check")
def quick_check(req: QuickCheckRequest):
    """
    Главный эндпоинт — полный расчёт Quick Check.
    Возвращает структурированный JSON со всеми блоками отчёта.
    """
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
        return {"status": "ok", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/quick-check/report")
def quick_check_report(req: QuickCheckRequest):
    """
    Возвращает текстовый отчёт Quick Check (для отображения в Telegram).
    """
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/competitors/{niche_id}/{city_id}")
def get_competitors(niche_id: str, city_id: str):
    """Конкурентная среда по нише и городу."""
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
    """Паттерны закрытий по нише."""
    rows = db.failure_patterns[db.failure_patterns["niche_id"] == niche_id]
    if rows.empty:
        raise HTTPException(status_code=404, detail=f"Ниша {niche_id} не найдена")
    return {"pattern": rows.iloc[0].to_dict()}


@app.get("/permits/{niche_id}")
def get_permits(niche_id: str):
    """Разрешения и лицензии по нише."""
    df = db.permits[
        db.permits["niche_id"].str.contains(niche_id, na=False) |
        (db.permits["niche_id"] == "ALL")
    ]
    return {"permits": df.to_dict("records")}


@app.get("/macro/{city_id}")
def get_macro(city_id: str):
    """Макроданные по региону города."""
    from engine import get_inflation_region
    inflation = get_inflation_region(db, city_id)
    return {
        "city_id": city_id,
        "inflation_pct": inflation,
        "inflation_label": f"{inflation}% годовых (февраль 2026)"
    }
