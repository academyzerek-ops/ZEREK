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

from engine import ZerekDB, run_quick_check_v3, DEFAULTS_CFG  # noqa: F401
from loaders.niche_loader import (
    get_formats_v2,
    get_niche_config,
    get_niche_survey,
    get_quickcheck_survey,
)
from renderers.quick_check_renderer import render_report_v4


# ───────────────────────────────────────────────────────────────────
# Дефолты финмодели переехали в api/calculators/finmodel.py
# (Этап 8.4). FINMODEL_DEFAULTS_CFG используется только там сейчас.
# ───────────────────────────────────────────────────────────────────


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

# QCReq переехал в api/validators/input_validator.py (Этап 6).
# Re-export для обратной совместимости.
from validators.input_validator import QCReq, QuickCheckRequest  # noqa: F401, E402

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
    # Временный фильтр до обновления фронта: возвращаем только ниши
    # с available=true. Поле `available` сохраняем в ответе, чтобы фронт
    # мог использовать его в будущем.
    all_niches = db.get_available_niches()
    visible = [n for n in all_niches if n.get("available")]
    return {"niches":clean(visible)}

@app.get("/formats/{niche_id}")
def get_formats(niche_id: str):
    if not db: raise HTTPException(503,"БД не загружена")
    if not db.is_niche_available(niche_id):
        raise HTTPException(400, "Ниша пока недоступна для расчёта")
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
    from loaders.tax_constants_loader import get_usn_rate_for_city
    return {"city_id":city_id,"ud_rate_pct":get_usn_rate_for_city(city_id)}

CAPEX_TO_CLS = {"эконом":"Эконом","стандарт":"Стандарт","бизнес":"Бизнес","премиум":"Премиум"}

@app.post("/quick-check")
def quick_check(req: QCReq):
    """Quick Check 5 000 ₸ — двухшаговый calc → render.

    Этап 4: вся логика валидации/нормализации/расчёта переехала в
    api/calculators/quick_check.py.

    Этап 5: рендер (legacy block_1..block_12 + новый block1..block10
    overlay) переехал в api/renderers/quick_check_renderer.render_for_api.
    Calculator возвращает «сырой» calc_result, renderer превращает в API.
    """
    if not db:
        raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        from calculators.quick_check import QuickCheckCalculator
        from renderers.quick_check_renderer import render_for_api
        calc_result = QuickCheckCalculator(db).run(req)
        report = render_for_api(calc_result)
        return {"status": "ok", "result": clean(report)}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        d = traceback.format_exc()
        print("ОШИБКА:", d)
        raise HTTPException(500, str(e) + "\n" + d[-500:])

@app.get("/niche-config/{niche_id}")
def niche_config(niche_id: str):
    """Конфиг адаптивной анкеты Quick Check v2 для указанной ниши."""
    if not db: raise HTTPException(503,"БД не загружена")
    if not db.is_niche_available(niche_id):
        raise HTTPException(400, "Ниша пока недоступна для расчёта")
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
    if not db.is_niche_available(niche_id):
        raise HTTPException(400, "Ниша пока недоступна для расчёта")
    try:
        return clean(get_niche_survey(db, niche_id, tier))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

# ───────────────────────────────────────────────────────────────────────────
# v1.0 spec — Quick Check / FinModel / BizPlan survey endpoints
# ───────────────────────────────────────────────────────────────────────────

@app.get("/configs")
def configs():
    """Возвращает config/*.yaml как JSON (niches / archetypes / locations / questionnaire).
    Используется фронтом для построения адаптивной анкеты."""
    if not db: raise HTTPException(503,"БД не загружена")
    cfg_raw = getattr(db, "configs", {}) or {}
    # Временный фильтр до обновления фронта: оставляем в configs.niches.niches
    # только записи с available=true. Поле `available` остаётся внутри каждой,
    # чтобы фронт мог использовать его в будущем. Верхнеуровневый словарь
    # копируем, не мутируя оригинал в БД.
    niches_section_orig = cfg_raw.get("niches") or {}
    raw_niches = niches_section_orig.get("niches") or {}
    filtered_niches = {
        nid: meta for nid, meta in raw_niches.items()
        if isinstance(meta, dict) and bool(meta.get("available", False))
    }
    niches_section_copy = dict(niches_section_orig)
    niches_section_copy["niches"] = filtered_niches
    cfg_copy = dict(cfg_raw)
    cfg_copy["niches"] = niches_section_copy
    return clean(cfg_copy)

@app.get("/formats-v2/{niche_id}")
def formats_v2(niche_id: str):
    """Форматы ниши с расширенными полями v1.0 спецификации:
    format_type, allowed_locations, typical_staff."""
    if not db: raise HTTPException(503,"БД не загружена")
    if not db.is_niche_available(niche_id):
        raise HTTPException(400, "Ниша пока недоступна для расчёта")
    return {"formats": clean(get_formats_v2(db, niche_id))}

@app.get("/quickcheck-survey/{niche_id}")
def quickcheck_survey(niche_id: str, format_id: str = None):
    """Полная конфигурация Quick Check анкеты (8 вопросов) для ниши.
    Если указан format_id — добавляет сгенерированные варианты роли предпринимателя."""
    if not db: raise HTTPException(503,"БД не загружена")
    if not db.is_niche_available(niche_id):
        raise HTTPException(400, "Ниша пока недоступна для расчёта")
    try:
        return clean(get_quickcheck_survey(db, niche_id, format_id))
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
    """Структурированные риски ниши через Gemini (из knowledge/kz/niches/*_insight.md)."""
    from gemini_rag import extract_niche_risks
    diag = {} if debug else None
    risks = extract_niche_risks(niche_id.upper(), diag=diag)
    out = {"niche_id": niche_id.upper(), "risks": risks}
    if debug:
        out["_diag"] = diag
    return out


@app.get("/pdf-rag-debug/{niche_id}")
def pdf_rag_debug(niche_id: str, n: int = 1):
    """Отладка LLM-слота common_mistakes: N прогонов с полными diag.

    Каждый прогон — свежий вызов Gemini (без кеша в текущей реализации),
    что позволяет смотреть вариативность температуры 0.3 на одном insight.
    """
    n = max(1, min(int(n or 1), 5))
    from services.pdf_rag_service import generate_common_mistakes
    runs = []
    for i in range(n):
        diag: dict = {}
        text = generate_common_mistakes(niche_id, diag=diag)
        runs.append({
            "run": i + 1,
            "text": text,
            "accepted": text is not None,
            "diag": diag,
        })
    return {"niche_id": (niche_id or "").upper(), "runs": runs}


@app.get("/pdf-health")
def pdf_health():
    """Диагностика: какой PDF-движок активен сейчас + может ли рендерить.

    Приоритет: WeasyPrint (премиум HTML-шаблон) → ReportLab fallback.
    Показывает что активен и тестирует PDF-генерацию.
    """
    from renderers.pdf_renderer import which_engine
    active = which_engine()
    info = {"active_engine": active}

    # WeasyPrint info.
    try:
        import weasyprint
        info["weasyprint_version"] = weasyprint.__version__
        info["weasyprint_available"] = True
    except Exception as e:
        info["weasyprint_available"] = False
        info["weasyprint_error"] = str(e)[:200]

    # ReportLab info.
    try:
        import reportlab
        info["reportlab_version"] = reportlab.Version
        info["reportlab_available"] = True
    except Exception as e:
        info["reportlab_available"] = False
        info["reportlab_error"] = str(e)[:200]

    # Проверяем что активный движок реально работает.
    try:
        if active == "weasyprint":
            pdf_bytes = weasyprint.HTML(string="<h1>Health</h1>").write_pdf()
        else:
            from renderers.pdf_renderer_reportlab import _register_fonts_once
            _register_fonts_once()
            pdf_bytes = b"%PDF-reportlab-fonts-registered"
        info["pdf_test_bytes"] = len(pdf_bytes)
        info["status"] = "ok"
        return info
    except Exception as e:
        import traceback
        info["status"] = "fail"
        info["error"] = str(e)[:200]
        info["trace"] = traceback.format_exc()[-1000:]
        return info


@app.post("/quick-check/pdf")
def generate_pdf(req: QCReq):
    """Генерирует премиум PDF через WeasyPrint + Jinja2 (api/templates/pdf/quick_check.html).

    Возвращает {token, filename, pdf_url, report_id} — клиент открывает
    pdf_url напрямую через `<a href download>` или Telegram.WebApp.openLink.
    """
    if not db:
        raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        # Используем тот же путь что /quick-check — QuickCheckCalculator
        # собирает result со всеми новыми блоками (block1/block4/block5/block6
        # /capital_adequacy/marketing_plan/staff_paradox/...) которые нужны
        # build_pdf_context в pdf_renderer.
        from calculators.quick_check import QuickCheckCalculator
        from renderers.pdf_renderer import generate_quick_check_pdf
        calc_result = QuickCheckCalculator(db).run(req)
        pdf_bytes, report_id, filename = generate_quick_check_pdf(
            calc_result, (req.niche_id or "").upper()
        )
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


# ── Финансовая модель ──
# Логика finmodel переехала в api/calculators/finmodel.py (Этап 8.4).
# Endpoint /finmodel ниже использует FinModelCalculator.



@app.post("/finmodel")
def generate_finmodel_endpoint(req: FMReq):
    """Генерирует xlsx финмодель + HTML отчёт.

    Логика расчёта (compute_finmodel_data, build_params, apply_adaptive_answers)
    переехала в api/calculators/finmodel.py (Этап 8.4). Endpoint оркестрирует:
    Quick Check (для базовых данных) → FinModelCalculator (params + data)
    → gen_finmodel (xlsx) → finmodel_report (HTML).
    """
    if not db:
        raise HTTPException(503, f"БД не загружена: {db_error}")
    try:
        from calculators.finmodel import FinModelCalculator
        calc = FinModelCalculator(db)
        # 0. Адаптивные ответы → req
        calc.apply_adaptive_answers(req)
        # 1. Quick Check для базовых данных (financials, tax, capex)
        qc_result = run_quick_check_v3(
            db=db, city_id=req.city_id, niche_id=req.niche_id,
            format_id=req.format_id, cls=req.cls, area_m2=req.area_m2,
            loc_type=req.loc_type, capital=req.capital or 0, qty=req.qty,
            founder_works=req.founder_works, rent_override=req.rent_override,
            start_month=req.start_month,
        )
        # 2. Собираем params + считаем 36 мес P&L/CF
        params = calc.build_params_from_request(req, qc_result)

        # 3. Генерируем xlsx
        from gen_finmodel import generate_finmodel
        template = os.path.join(os.path.dirname(BASE_DIR), "templates", "finmodel", "finmodel_template.xlsx")
        if not os.path.exists(template):
            template = os.path.join(DATA_DIR, "templates", "finmodel_template.xlsx")
        if not os.path.exists(template):
            raise HTTPException(404, f"Шаблон не найден: {template}")

        output = os.path.join("/tmp", f"ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx")
        generate_finmodel(template, params, output_path=output)

        with open(output, "rb") as fh:
            xlsx_bytes = fh.read()
        fname = f"ZEREK_FinModel_{req.niche_id}_{req.city_id}.xlsx"
        token = _store_file(xlsx_bytes, fname, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # 4. HTML-отчёт (через calculator.compute → renderer)
        report_token = None
        try:
            from finmodel_report import render_finmodel_report
            report_data = calc.compute(params)
            report_html = render_finmodel_report(report_data)
            report_fname = f"ZEREK_FinReport_{req.niche_id}_{req.city_id}.html"
            report_token = _store_file(report_html.encode("utf-8"), report_fname, "text/html; charset=utf-8")
        except Exception as e:
            print(f"WARN: finmodel report failed: {e}")

        return {"status": "ok", "token": token, "filename": fname, "report_token": report_token}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        d = traceback.format_exc()
        print("ОШИБКА finmodel:", d)
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

2. **Обзоры рынка** — 50 ниш малого бизнеса × 14 городов РК. Бесплатно.

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
