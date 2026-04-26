"""runner.py · Прогон одного сценария: engine → PDF → текст по страницам.

Адаптирует фактический pipeline (`QuickCheckCalculator + build_pdf_context
+ generate_quick_check_pdf`) под формат ожидаемый правилами аудитора:

    {
        'pdf_text_by_page': List[str],   # текст каждой страницы
        'pdf_full_text':   str,          # весь PDF одной строкой
        'pdf_bytes':       bytes,        # сам файл (для сохранения)
        'engine_result': dict,           # плоский dict с числами и категориями
    }

Извлечение текста — через системный `pdftotext -layout` (есть в Ubuntu CI
по умолчанию через poppler-utils, локально — `brew install poppler`).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List

_REPO_ROOT = Path(__file__).resolve().parent.parent
_API_DIR = _REPO_ROOT / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))


_db_singleton = None


def _get_db():
    global _db_singleton
    if _db_singleton is None:
        from main import db, db_error  # noqa: WPS433
        if not db:
            raise RuntimeError(f"DB не загрузилась: {db_error}")
        _db_singleton = db
    return _db_singleton


_GRADE_MAP = {
    "Низкий доход":       "LOW",
    "Невысокий доход":    "MODEST",
    "Средний доход":      "MIDDLE",
    "Достойный доход":    "DECENT",
    "Высокий доход":      "HIGH",
    "Очень высокий":      "VERY_HIGH",
    "Сомнительная":       "BAD",
}


def _grade_from_title(title: str) -> str:
    for prefix, code in _GRADE_MAP.items():
        if (title or "").startswith(prefix):
            return code
    return "?"


def _phase_avg(monthly_plan, lo, hi):
    items = (monthly_plan or [])[lo:hi]
    if not items:
        return 0
    return int(round(sum(int(m.get("total_marketing", 0) or 0) for m in items) / len(items)))


def _flatten_engine(result: dict, ctx: dict) -> Dict[str, Any]:
    """Собрать плоский dict для использования правилами.

    Ключи такие же что в `tests/conftest.py:engine_compute` — единая
    точка истины для R10 + R11.
    """
    cap = ctx.get("cap") or {}
    fin = ctx.get("fin") or {}
    vrd = ctx.get("vrd") or {}
    cadq = ctx.get("cadq") or {}
    inp = ctx.get("inp") or {}
    mp = result.get("marketing_plan") or {}
    monthly_plan = mp.get("monthly_plan") or []
    summary = mp.get("summary") or {}
    ei = (result.get("block5") or {}).get("entrepreneur_income") or {}

    # R12.5 S5: r12-контекст уже собран в build_pdf_context. Берём готовое.
    r12_ctx = ctx.get("r12") or {}
    return {
        # категории
        "capital_zone":           cadq.get("capital_zone") or "UNKNOWN",
        "income_grade":           _grade_from_title(vrd.get("direction_title") or ""),
        # числа: основные
        "capex":                  int(cap.get("total") or 0),
        "avg_y1":                 int(ei.get("total_monthly") or 0),
        "mature_monthly":         int(ei.get("mature_monthly") or 0),
        "mature_profit":          int(fin.get("mature_profit") or 0),
        "income_ratio_pct":       int(vrd.get("income_ratio_pct") or 0),
        "breakeven_clients":      int(fin.get("break_even_clients") or 0),
        "safety_mature":          float(fin.get("safety_multiplier") or 0),
        "safety_ramp":            float(fin.get("safety_multiplier_ramp") or 0),
        # маркетинг
        "marketing_year_total":   int(summary.get("total_year_budget") or 0),
        "marketing_phase_ramp":   _phase_avg(monthly_plan, 0, 3),
        "marketing_phase_tuning": _phase_avg(monthly_plan, 3, 6),
        "marketing_phase_mature": _phase_avg(monthly_plan, 6, 12),
        # вход (для условных правил)
        "format":                 (inp.get("format_id") or "").upper(),
        "niche":                  (inp.get("niche_id") or "").upper(),
        "city":                   (inp.get("city_id") or "").lower(),
        "experience":             (inp.get("experience") or "none").lower(),
        # R12.5 контекст (для check_r12_*)
        "is_r12":                 bool(r12_ctx.get("is_r12")),
        "r12_format_key":         r12_ctx.get("format_key") or "",
        "r12_experience":         r12_ctx.get("experience") or "",
        "r12_strategy":           r12_ctx.get("strategy") or "",
        "r12_level":              r12_ctx.get("level") or "",
        "r12_level_label":        r12_ctx.get("level_label") or "",
        "r12_strategy_label":     r12_ctx.get("strategy_label") or "",
        "r12_has_antipattern":    bool(r12_ctx.get("antipattern")),
        "r12_n_explanation_blocks": len(r12_ctx.get("explanation_blocks") or []),
    }


def _pdftotext_pages(pdf_path: Path) -> List[str]:
    """Извлечь текст постранично через системный pdftotext -layout.

    Разделитель страниц — \\f (form feed). Возвращает list текстов.
    Если pdftotext не установлен — fallback на pypdf (медленнее).
    """
    try:
        out = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            capture_output=True, text=True, timeout=30, check=True,
        ).stdout
        # Разделитель страниц — \f. Хвостовой \f даёт пустую страницу
        # — отбрасываем её.
        pages = out.split("\f")
        if pages and not pages[-1].strip():
            pages = pages[:-1]
        return pages
    except (FileNotFoundError, subprocess.CalledProcessError):
        # Fallback — pypdf (требует pip install pypdf)
        from pypdf import PdfReader
        return [(p.extract_text() or "") for p in PdfReader(str(pdf_path)).pages]


_PROD_API = "https://web-production-921a5.up.railway.app"


def _normalize_format(niche: str, fmt: str) -> str:
    fmt = fmt.upper()
    if not fmt.startswith(niche.upper() + "_"):
        return f"{niche.upper()}_{fmt}"
    return fmt


def _build_qc_payload(inp: Dict[str, Any]) -> Dict[str, Any]:
    # R12.5 S5: для соло-beauty (A1) сценариев — проброс strategy / level
    # из YAML-сценария. Если поле отсутствует — engine использует дефолты
    # (strategy="middle", level=None — авто-выбор через _resolve_r12_level).
    sa = {"experience": str(inp.get("experience") or "none")}
    if inp.get("strategy"):
        sa["strategy"] = str(inp["strategy"])
    if inp.get("level"):
        sa["level"] = str(inp["level"])
    return {
        "city_id":       str(inp["city"]).lower(),
        "niche_id":      str(inp["niche"]).upper(),
        "format_id":     _normalize_format(str(inp["niche"]), str(inp["format"])),
        "loc_type":      "дома",
        "area_m2":       0,
        "capital":       int(inp.get("capital") or 0),
        "start_month":   int(inp.get("start_month") or 5),
        "capex_level":   "стандарт",
        "specific_answers": sa,
    }


def compute_and_render(scenario: Dict[str, Any], use_prod: bool = False) -> Dict[str, Any]:
    """Прогнать сценарий через ZEREK pipeline + извлечь PDF в текст.

    Сценарий: {id, inputs: {niche/format/city/capital/experience/start_month}}.

    use_prod=True: вместо локального рендера PDF — fetch с прод-API.
                   Полезно когда локально WeasyPrint не работает (macOS
                   без libgobject) — тогда локально аудитор бьёт по
                   реальному прод-PDF.
    """
    from main import QCReq  # noqa: WPS433
    from calculators.quick_check import QuickCheckCalculator
    from renderers.pdf_renderer_weasyprint import build_pdf_context

    inp = scenario["inputs"]
    db = _get_db()
    payload = _build_qc_payload(inp)

    req = QCReq(**payload)
    result = QuickCheckCalculator(db).run(req)
    ctx = build_pdf_context(result)

    if use_prod:
        # Тянем PDF с прода через POST /quick-check/pdf → GET /download.
        import json
        import urllib.request
        body = json.dumps(payload).encode("utf-8")
        req_pdf = urllib.request.Request(
            f"{_PROD_API}/quick-check/pdf",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req_pdf, timeout=60) as resp:
            j = json.loads(resp.read().decode("utf-8"))
        token = j.get("token")
        if not token:
            raise RuntimeError(f"Prod API не вернул token: {j}")
        with urllib.request.urlopen(
            f"{_PROD_API}/download/{token}", timeout=60,
        ) as resp:
            pdf_bytes = resp.read()
    else:
        from renderers.pdf_renderer import generate_quick_check_pdf
        pdf_bytes, _rid, _fname = generate_quick_check_pdf(
            result, str(inp["niche"]).upper(),
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(pdf_bytes)
        tmp_path = Path(tmp.name)
    try:
        pages = _pdftotext_pages(tmp_path)
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return {
        "pdf_text_by_page": pages,
        "pdf_full_text":    "\n".join(pages),
        "pdf_bytes":        pdf_bytes,
        "engine_result":    _flatten_engine(result, ctx),
    }
