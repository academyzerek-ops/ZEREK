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
from services.capital_service import compute_capital_adequacy  # noqa: E402
from services.danger_zone_service import compute_danger_zone  # noqa: E402
from services.economics_service import (  # noqa: E402
    compute_block4_unit_economics,
    compute_block5_pnl,
    compute_block6_capital,
    compute_pnl_aggregates,
)
from services.growth_service import compute_growth_block  # noqa: E402
from services.marketing_service import compute_marketing_plan  # noqa: E402
from services.staff_paradox_service import compute_staff_paradox  # noqa: E402
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
        # R12.5: experience + strategy + level прокидываются из
        # specific_answers до engine. experience override fin/capex/staff
        # через formats_r12 (если ниша в R12.5). strategy управляет
        # маркетинг-фазами и ramp curve. level (если задан) выбирает
        # SALON_RENT premium / STUDIO nice вместо дефолтов; если не задан,
        # _resolve_r12_level выбирает автоматически (SALON_RENT × experienced
        # → premium).
        sa = req.specific_answers or {}
        experience = sa.get('experience') or 'none'
        strategy = sa.get('strategy') or 'middle'
        level = sa.get('level')  # None допустим — авто-выбор в engine
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
            experience=experience,
            strategy=strategy,
            level=level,
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

        # Marketing plan (ДО block5) — архетипная воронка + помесячный бюджет.
        # Патчит pnl_aggregates.mature.marketing_monthly на avg_monthly_budget
        # → P&L-таблица в block5 показывает ту же цифру что блок «Маркетинг».
        # first_year_chart вычисляется отдельно (не зависит от block5).
        try:
            inp = result.get("input", {}) or {}
            fin = result.get("financials") or {}
            sa = (req.specific_answers or {})
            exp = (sa.get("experience") or inp.get("experience") or "none") or "none"
            content_self = bool(sa.get("content_self_produced", True))
            fyc_early = compute_first_year_chart(result)
            months_early = (fyc_early or {}).get("months") or []
            check_med = int(fin.get("check_med") or 0)
            clients_per_month = []
            if check_med > 0 and months_early:
                for m in months_early:
                    rev_m = int(m.get("revenue") or 0)
                    clients_per_month.append(int(round(rev_m / max(check_med, 1))))
            if clients_per_month:
                # R12.5 Сессия 2 калибровка: level — уровень формата
                # (premium/standard для SALON_RENT). Используется
                # marketing_service для выбора marketing_phases_premium
                # vs marketing_phases_standard (премиум-салон требует
                # меньше своего маркетинга — есть трафик от салона).
                resolved_level = (
                    (fin.get('r12_level') if isinstance(fin, dict) else None)
                    or sa.get('level')
                )
                mp = compute_marketing_plan(
                    niche_id=(inp.get("niche_id") or "").upper(),
                    city_id=(inp.get("city_id") or "").lower(),
                    total_clients_per_month=clients_per_month,
                    experience=exp,
                    content_self_produced=content_self,
                    legal_form="ip",
                    format_id=(inp.get("format_id") or "").upper(),  # R12 S2
                    strategy=sa.get("strategy") or "middle",  # R12.5 S2 хвост
                    level=resolved_level,  # R12.5 калибровка
                )
                if mp and not mp.get("error"):
                    result["marketing_plan"] = mp
                    avg_mkt = int((mp.get("summary") or {}).get("avg_monthly_budget") or 0)
                    if avg_mkt > 0:
                        result.setdefault("pnl_aggregates", {}).setdefault("mature", {})["marketing_monthly"] = avg_mkt
            result["_first_year_chart_cache"] = fyc_early
        except Exception:
            import traceback
            traceback.print_exc()

        # Block 5 — P&L + first_year_chart (marketing_monthly уже запатчен выше).
        try:
            result["block5"] = compute_block5_pnl(self.db, result, block1_inputs)
            fyc = result.pop("_first_year_chart_cache", None) or compute_first_year_chart(result)
            result["block5"]["first_year_chart"] = fyc
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

        # Danger zone — cashflow-анализ первого года (разгон + сезонность).
        # Строим enriched cashflow из first_year_chart + mature P&L, вызываем
        # сервис ДО capital_adequacy — его worst_month.profit пойдёт
        # в seasonal_buffer капитала.
        danger_zone = None
        try:
            inp = result.get("input", {}) or {}
            fin = result.get("financials") or {}
            nb6 = result.get("block6") or {}
            agg = (result.get("pnl_aggregates") or {}).get("mature") or {}
            fyc = (result.get("block5") or {}).get("first_year_chart") or {}
            months = fyc.get("months") or []

            capex_total = int(
                nb6.get("capex_needed")
                or (result.get("capex") or {}).get("total")
                or 0
            )
            fot_m = int(agg.get("fot_monthly") or 0)
            rent_m = int(agg.get("rent_monthly") or fin.get("rent_month") or 0)
            marketing_m = int(agg.get("marketing_monthly") or fin.get("marketing_med") or 0)
            other_m = int(agg.get("other_opex_monthly") or fin.get("other_opex_med") or 0)
            cogs_pct = float(agg.get("cogs_pct") or fin.get("cogs_pct") or 0.30)
            tax_rate = float(agg.get("tax_rate") or 0.03)
            rampup = int(fin.get("rampup_months") or 3)
            fixed_m = fot_m + rent_m + marketing_m + other_m

            cashflow_year1 = []
            for m in months:
                rev = int(m.get("revenue") or 0)
                costs_m = int(rev * (cogs_pct + tax_rate)) + fixed_m
                profit_m = rev - costs_m
                cashflow_year1.append({
                    "month_index": int(m.get("n") or 0),
                    "calendar_label": m.get("calendar_label", ""),
                    "revenue": rev,
                    "total_costs": costs_m,
                    "profit": profit_m,
                    "is_rampup": (m.get("color") == "ramp") or int(m.get("n") or 0) <= rampup,
                })

            if cashflow_year1:
                danger_zone = compute_danger_zone(cashflow_year1, capex_total)
                if danger_zone:
                    result["danger_zone"] = danger_zone
        except Exception:
            import traceback
            traceback.print_exc()

        # Staff paradox — блок «потолок и стратегии» для beauty-ниш (A1).
        # Формат HOME → короткий, SOLO → средний, STANDARD/PREMIUM → полный.
        # Для других архетипов возвращает None (не рендерится).
        try:
            inp = result.get("input", {}) or {}
            fin = result.get("financials") or {}
            agg = (result.get("pnl_aggregates") or {}).get("mature") or {}
            sp = compute_staff_paradox(
                niche_id=(inp.get("niche_id") or "").upper(),
                format_id=(inp.get("format_id") or "").upper(),
                avg_check=int(fin.get("check_med") or 0),
                rent_monthly=int(agg.get("rent_monthly") or fin.get("rent_month") or 0),
                city_id=(inp.get("city_id") or "").lower(),
            )
            if sp:
                result["staff_paradox"] = sp
        except Exception:
            import traceback
            traceback.print_exc()

        # Capital adequacy — 3 уровня (minimum / comfortable / safe) + вердикт.
        # seasonal_buffer теперь строится из реального worst_month.profit
        # (danger_zone), не из константы 0.
        try:
            inp = result.get("input", {}) or {}
            fin = result.get("financials") or {}
            nb6 = result.get("block6") or {}
            agg = (result.get("pnl_aggregates") or {}).get("mature") or {}

            capex_total = int(
                nb6.get("capex_needed")
                or (result.get("capex") or {}).get("total")
                or 0
            )
            marketing_m = int(agg.get("marketing_monthly") or fin.get("marketing_med") or 0)
            other_opex_m = int(agg.get("other_opex_monthly") or fin.get("other_opex_med") or 0)
            rent_m = int(agg.get("rent_monthly") or fin.get("rent_month") or 0)
            rampup = int(fin.get("rampup_months") or 3)
            user_cap = inp.get("capital")
            user_cap_int = int(user_cap) if user_cap else None

            # R6 C.1: «комфортно» должно покрывать РАЗГОННЫЙ маркетинг
            # (М1-М3 из marketing_plan, а не среднегодовой × 3). Для
            # MANICURE_HOME ramp_total ≈ 460K, а avg×3 = 180K — занижало
            # резерв в 2.5 раза.
            ramp_marketing_total = 0
            mp = result.get("marketing_plan") or {}
            monthly_plan = mp.get("monthly_plan") or []
            if monthly_plan:
                for m in monthly_plan[:rampup]:
                    if isinstance(m, dict):
                        ramp_marketing_total += int(m.get("total_marketing", 0) or 0)

            # worst_season_drawdown = худший single-month loss (абсолют).
            worst_drawdown = 0
            if danger_zone:
                wp = int(danger_zone.get("worst_month", {}).get("profit") or 0)
                worst_drawdown = abs(wp) if wp < 0 else 0

            result["capital_adequacy"] = compute_capital_adequacy(
                capex_total=capex_total,
                marketing_monthly=marketing_m,
                other_opex_monthly=other_opex_m,
                rent_monthly=rent_m,
                rampup_months=rampup,
                worst_season_drawdown=worst_drawdown,
                user_capital=user_cap_int,
                legal_form="ip",  # TODO: брать из YAML niche когда появится поле
                ramp_marketing_total=ramp_marketing_total,
            )
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
