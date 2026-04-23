"""api/calculators/quick_check.py — Quick Check (5 000 ₸) фасад.

Тонкий оркестратор: валидирует вход, нормализует HOME/SOLO патчи,
вызывает run_quick_check_v3 (engine) для базовых расчётов, инъектит
pnl_aggregates, накладывает блоки 1–10.

Цель Этапа 4 — убрать дублирование логики из main.py (R-1: pnl_aggregates
инъекция, R-6: HOME/SOLO хот-патчи).

Цель Этапа 5 — отделить calc от render. Calculator больше НЕ вызывает
render_report_v4 — это делает renderer (renderers/quick_check_renderer.
render_for_api) после calculator.

Зависит от: engine (run_quick_check_v3 + compute_block*), services
(compute_pnl_aggregates, compute_first_year_chart).

Контракт:
- Принимает QCReq (Pydantic-модель) либо совместимый объект.
- Возвращает calc_result dict с raw данными от engine + block1..block10
  overlay + user_inputs. БЕЗ legacy block_1..block_12 (это renderer).
- main.py вызывает renderer для финального форматирования.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from fastapi import HTTPException  # noqa: E402

from engine import run_quick_check_v3  # noqa: E402
from models import CalcResult  # noqa: E402
from renderers.quick_check_renderer import compute_block2_passport  # noqa: E402
from services.action_plan_service import compute_block10_next_steps  # noqa: E402
from services.economics_service import (  # noqa: E402
    compute_block4_unit_economics,
    compute_block5_pnl,
    compute_block6_capital,
    compute_pnl_aggregates,
)
from services.growth_service import compute_growth_block  # noqa: E402
from services.market_service import compute_block3_market  # noqa: E402
from services.risk_service import compute_block9_risks  # noqa: E402
from services.seasonality_service import compute_block_season, compute_first_year_chart  # noqa: E402
from services.stress_service import compute_block8_stress_test  # noqa: E402
from services.verdict_service import compute_block1_verdict  # noqa: E402
from validators.input_validator import QuickCheckRequest  # noqa: E402

_log = logging.getLogger("zerek.quick_check_calculator")

# capex_level (с фронта анкеты) → cls (Pydantic поле). Маппинг был в main.py.
CAPEX_TO_CLS = {"эконом": "Эконом", "стандарт": "Стандарт",
                "бизнес": "Бизнес", "премиум": "Премиум"}


class QuickCheckCalculator:
    """Quick Check 5 000 ₸ — фасад над движком + блоки.

    Стандартный пайплайн:
        calc = QuickCheckCalculator(db)
        report = calc.run(req)  # req: QCReq

    `report` — готовый dict для clean() + return клиенту.
    """

    def __init__(self, db):
        self.db = db

    # ════════════════════════════════════════════════════════════════════
    # Публичный API
    # ════════════════════════════════════════════════════════════════════

    def run(self, req: QuickCheckRequest) -> CalcResult:
        """Главный метод — оркестрирует все шаги от валидации до calc_result.

        Возвращает «сырой» calc_result (без legacy block_1..block_12).
        Renderer (renderers/quick_check_renderer.render_for_api) превращает
        его в финальный API-отчёт.
        """
        # 1. Валидация + резолв cls
        cls = self._validate_and_resolve_cls(req)
        # 2. Нормализация HOME/SOLO (R-6)
        founder_works_eff = self._normalize_params(req)
        # 3. Базовый расчёт через engine
        result = self._compute_base(req, cls, founder_works_eff)
        # 4. Инъекция pnl_aggregates (R-1)
        result["pnl_aggregates"] = compute_pnl_aggregates(result)
        # 5. Overlay новых блоков (block1..block10 + block_season + first_year_chart)
        self._overlay_blocks(result, req)
        # 6. user_inputs (адаптивные поля v2)
        self._add_user_inputs(result, req)
        return result

    # ════════════════════════════════════════════════════════════════════
    # Внутренние шаги
    # ════════════════════════════════════════════════════════════════════

    def _validate_and_resolve_cls(self, req):
        """Шаг 1: валидация ниши + start_month + HOME/SOLO калибровки.

        Возвращает резолвенный cls (с capex_level фронта или дефолт из req).
        Бросает HTTPException 400 на ошибках.
        """
        if not self.db.is_niche_available(req.niche_id):
            raise HTTPException(400, "Эта ниша пока недоступна для расчёта")
        if req.start_month is None:
            raise HTTPException(
                400,
                "Укажите месяц планируемого старта (start_month ∈ 1..12). Это влияет на прогноз первого года.",
            )
        if not isinstance(req.start_month, int) or req.start_month < 1 or req.start_month > 12:
            raise HTTPException(400, f"start_month должен быть 1..12, получен: {req.start_month}")

        cls = CAPEX_TO_CLS.get((req.capex_level or "").strip().lower(), req.cls)

        # HOME/SOLO: marketing_med + other_opex_med обязательны (см. спека Р-2, 7.1)
        _fmt_up = (req.format_id or "").upper()
        if _fmt_up.endswith("_HOME") or _fmt_up.endswith("_SOLO"):
            _fin_row = self.db.get_format_row(req.niche_id, "FINANCIALS", req.format_id, cls) or {}
            _mk = _fin_row.get("marketing_med") or _fin_row.get("marketing")
            _ox = _fin_row.get("other_opex_med")
            if not _mk or not _ox:
                raise HTTPException(
                    400,
                    f"Ниша {req.niche_id} / формат {req.format_id} не откалибрована: "
                    f"в FINANCIALS должны быть заданы marketing_med и other_opex_med. "
                    f"Сейчас: marketing_med={_fin_row.get('marketing_med')}, "
                    f"other_opex_med={_fin_row.get('other_opex_med')}.",
                )

        return cls

    def _normalize_params(self, req):
        """Шаг 2: HOME/SOLO патчи (R-6).

        Для HOME/SOLO форматов:
        - founder_works_eff = True (мастер = предприниматель)
        - default entrepreneur_role = 'owner_plus_master' (мутирует req.specific_answers)

        Для остальных форматов:
        - founder_works_eff = req.founder_works OR ent_role.startswith('owner_plus_')

        Возвращает founder_works_eff. Мутирует req.specific_answers если
        нужно (поведение совместимо с прежним main.py).
        """
        ent_role = (req.specific_answers or {}).get("entrepreneur_role", "") or ""
        fmt_id_upper = (req.format_id or "").upper()
        is_solo_format = fmt_id_upper.endswith("_HOME") or fmt_id_upper.endswith("_SOLO")
        if is_solo_format:
            if not ent_role or ent_role == "owner_only":
                sa = dict(req.specific_answers or {})
                sa["entrepreneur_role"] = "owner_plus_master"
                req.specific_answers = sa
            founder_works_eff = True
        else:
            founder_works_eff = req.founder_works or ent_role.startswith("owner_plus_")
        return founder_works_eff

    def _compute_base(self, req, cls, founder_works_eff):
        """Шаг 3: базовый расчёт через engine.run_quick_check_v3."""
        return run_quick_check_v3(
            db=self.db,
            city_id=req.city_id,
            niche_id=req.niche_id,
            format_id=req.format_id,
            cls=cls,
            area_m2=req.area_m2,
            loc_type=req.loc_type,
            capital=req.capital or 0,
            qty=req.qty,
            founder_works=founder_works_eff,
            rent_override=req.rent_override,
            start_month=req.start_month,
        )

    def _overlay_blocks(self, result, req):
        """Шаг 5: накладывает block1..block10 (новый формат) внутрь result.

        Каждый блок в try/except — падение одного блока не должно ломать
        весь расчёт. Renderer потом скопирует эти ключи в финальный отчёт.
        """
        block1_inputs = dict(req.specific_answers or {})
        block1_inputs.update({
            "has_license": req.has_license,
            "staff_mode": req.staff_mode,
            "staff_count": req.staff_count,
        })

        # Block 1 — Вердикт
        try:
            result["block1"] = compute_block1_verdict(result, block1_inputs)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 2 — Паспорт бизнеса
        block2_obj = None
        try:
            block2_inputs = dict(req.specific_answers or {})
            block2_inputs["loc_type"] = req.loc_type
            block2_obj = compute_block2_passport(self.db, result, block2_inputs)
            result["block2"] = block2_obj
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 3 — Рынок
        try:
            result["block3"] = compute_block3_market(result)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 4 — Юнит-экономика
        try:
            result["block4"] = compute_block4_unit_economics(self.db, result, block1_inputs, block2=block2_obj)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 5 — P&L + first_year_chart
        try:
            result["block5"] = compute_block5_pnl(self.db, result, block1_inputs)
            result["block5"]["first_year_chart"] = compute_first_year_chart(result)
        except Exception:
            import traceback
            traceback.print_exc()

        # Growth scenarios — «А что дальше?» (берётся из YAML ниши).
        # Рендерится на фронте между entrepreneur_income и first_year_chart.
        try:
            inp = result.get("input", {}) or {}
            mature_profit = (
                (result.get("pnl_aggregates") or {}).get("mature", {}).get("profit_monthly")
                or 0
            )
            growth = compute_growth_block(
                niche_id=inp.get("niche_id", "") or "",
                format_id=inp.get("format_id", "") or "",
                base_profit_monthly=int(mature_profit),
            )
            if growth:
                result["growth_scenarios"] = growth
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 6 — Стартовый капитал
        try:
            result["block6"] = compute_block6_capital(self.db, result, block1_inputs, block2=block2_obj)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block Season — нужен raw_fin (полная FINANCIALS-row с s01..s12)
        try:
            inp = result.get("input", {}) or {}
            raw_fin = self.db.get_format_row(
                inp.get("niche_id", ""), "FINANCIALS",
                inp.get("format_id", ""), inp.get("class", "") or inp.get("cls", "")
            ) if inp.get("niche_id") else {}
            result["block_season"] = compute_block_season(raw_fin)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 8 — Стресс-тест
        try:
            result["block8"] = compute_block8_stress_test(result)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 9 — Риски ниши
        try:
            result["block9"] = compute_block9_risks(self.db, result, block1_inputs)
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 10 — Следующие шаги
        try:
            block1_obj = result.get("block1")
            result["block10"] = compute_block10_next_steps(
                self.db, result, block1_inputs,
                block1=block1_obj, block2=block2_obj,
            )
        except Exception:
            import traceback
            traceback.print_exc()

    def _add_user_inputs(self, result, req):
        """Шаг 6: вставляет user_inputs (адаптивные поля v2)."""
        adaptive = {
            "has_license": req.has_license,
            "staff_mode": req.staff_mode,
            "staff_count": req.staff_count,
            "specific_answers": req.specific_answers,
        }
        if any(v is not None for v in adaptive.values()):
            result.setdefault("user_inputs", {}).update(
                {k: v for k, v in adaptive.items() if v is not None}
            )
        # Прокидываем experience из specific_answers в result.input —
        # чтобы renderer'ы (PDF, UI) могли читать его напрямую, без погружения
        # в user_inputs.specific_answers.experience. Защита от рассинхрона.
        sa = req.specific_answers or {}
        exp = sa.get("experience")
        if exp is not None:
            result.setdefault("input", {})["experience"] = exp
