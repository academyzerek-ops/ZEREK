"""api/services/scenario_service.py — 3 сценария (пессимист/база/оптимист).

Согласно спеке (Часть 2.9, Шаг 9):
- Меняется ТОЛЬКО traffic_k и check_k (коэффициенты из defaults.yaml).
- ФОТ, аренда, маркетинг — одинаковые во всех 3 сценариях.
- Используется в Block 5 P&L таблице.

Извлечено из run_quick_check_v3 в Этапе 3 рефакторинга.
"""
import logging
import os
import sys

_API_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _API_DIR not in sys.path:
    sys.path.insert(0, _API_DIR)

from engine import (  # noqa: E402
    SCENARIO_BASE,
    SCENARIO_OPT,
    SCENARIO_PESS,
    _safe_int,
)
from services.economics_service import calc_cashflow, calc_payback  # noqa: E402

_log = logging.getLogger("zerek.scenario_service")


def compute_3_scenarios(fin, staff, capex_total, tax_rate, start_month=1, qty=1):
    """3 сценария (pess/base/opt) через calc_cashflow.

    Меняется только traffic_med и check_med (по коэффициентам из SCENARIO_*).
    ФОТ, аренда, маркетинг фиксированы (инвариант аксиомы 2.9).

    Возвращает dict {pess: {...}, base: {...}, opt: {...}} где каждый сценарий
    содержит: трафик_день, чек, выручка_год, прибыль_год, прибыль_среднемес,
    окупаемость (dict от calc_payback).
    """
    coefs = [
        ("pess", SCENARIO_PESS["traffic_k"], SCENARIO_PESS["check_k"]),
        ("base", SCENARIO_BASE["traffic_k"], SCENARIO_BASE["check_k"]),
        ("opt",  SCENARIO_OPT["traffic_k"],  SCENARIO_OPT["check_k"]),
    ]
    scenarios = {}
    for label, traffic_k, check_k in coefs:
        fin_sc = dict(fin)
        fin_sc["traffic_med"] = int(_safe_int(fin.get("traffic_med"), 50) * traffic_k)
        fin_sc["check_med"] = int(_safe_int(fin.get("check_med"), 1000) * check_k)
        sc_cf = calc_cashflow(fin_sc, staff, capex_total, tax_rate, start_month, 12, qty)
        sc_payback = calc_payback(capex_total, sc_cf)
        sc_rev = sum(cf["выручка"] for cf in sc_cf)
        sc_profit = sum(cf["прибыль"] for cf in sc_cf)
        scenarios[label] = {
            "трафик_день": fin_sc["traffic_med"],
            "чек": fin_sc["check_med"],
            "выручка_год": sc_rev,
            "прибыль_год": sc_profit,
            "прибыль_среднемес": int(sc_profit / 12),
            "окупаемость": sc_payback,
            # 12-месячный cashflow [{month, выручка, прибыль, ...}] для
            # кумулятивного payback и danger_zone. Хранится только для base,
            # чтобы не раздувать JSON.
            "cashflow": sc_cf if label == "base" else None,
        }
    return scenarios
