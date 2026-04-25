"""ZEREK Quick Check · регрессионные тесты движка.

Принцип: каждый сценарий из tests/golden_scenarios.yaml прогоняется
через `compute()` (см. conftest.py) и сверяется с эталонными
ожиданиями. Если значение отклоняется — тест падает с конкретным
сообщением «поле X: получили Y, ожидали Z».

Эталоны зафиксированы на коде после R10 #1+#2 (commit 228a3ad).
Если меняется бенчмарк / формула / ставка налога — эталоны нужно
обновлять ОТДЕЛЬНЫМ коммитом с описанием причины (см. README).

Запуск:
    pytest tests/test_engine_regression.py -v
    pytest tests/test_engine_regression.py -v -k critical   # только critical
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml


SCENARIOS_FILE = Path(__file__).parent / "golden_scenarios.yaml"


def _load_scenarios():
    with open(SCENARIOS_FILE, encoding="utf-8") as f:
        return yaml.safe_load(f) or []


def _match(actual: Any, spec: Dict[str, Any], field_name: str) -> None:
    """Сравнить actual со спекой матчера. На несоответствии — assert fail
    с понятным сообщением."""
    if "exact" in spec:
        expected = spec["exact"]
        # Числа сравниваем через approx чтобы float-юниты типа 6.9 не
        # ломались на repr-сериализации.
        if isinstance(expected, float) and isinstance(actual, (int, float)):
            assert abs(float(actual) - expected) < 0.05, (
                f"{field_name}: ожидалось {expected}, получили {actual}"
            )
        else:
            assert actual == expected, (
                f"{field_name}: ожидалось {expected!r}, получили {actual!r}"
            )
    elif "min" in spec and "max" in spec:
        lo, hi = spec["min"], spec["max"]
        assert lo <= actual <= hi, (
            f"{field_name}: {actual} вне диапазона [{lo}, {hi}]"
        )
    elif "approx" in spec:
        approx = spec["approx"]
        if "tolerance_pct" in spec:
            tol = abs(approx) * spec["tolerance_pct"] / 100
        elif "tolerance_abs" in spec:
            tol = spec["tolerance_abs"]
        else:
            raise ValueError(f"approx без tolerance_pct/tolerance_abs: {spec}")
        assert abs(actual - approx) <= tol, (
            f"{field_name}: {actual} отклонение от {approx} больше чем {tol}"
        )
    else:
        raise ValueError(f"неизвестный матчер для {field_name}: {spec}")


_SCENARIOS = _load_scenarios()


@pytest.mark.parametrize(
    "scenario",
    _SCENARIOS,
    ids=[s["id"] for s in _SCENARIOS],
)
def test_scenario(scenario, compute):
    """Прогон одного сценария: входы → engine → проверка expected.

    Все провалившие проверки собираются в одно сообщение, а не падаем
    на первой — чтобы видеть полную картину расхождений за один прогон.
    """
    result = compute(scenario)
    failures = []
    for field_name, spec in (scenario.get("expected") or {}).items():
        if field_name not in result:
            failures.append(f"{field_name}: нет в выходе compute() (проверь conftest)")
            continue
        try:
            _match(result[field_name], spec, field_name)
        except AssertionError as e:
            failures.append(str(e))
    if failures:
        sev = scenario.get("severity", "?")
        msg = (
            f"\nСценарий {scenario['id']} ({sev}) — провал {len(failures)}/{len(scenario['expected'])} проверок:\n"
            + "\n".join(f"  · {line}" for line in failures)
        )
        pytest.fail(msg)


def test_critical_scenarios_present():
    """Должно быть >= 5 critical-сценариев (gate для PR)."""
    critical = [s for s in _SCENARIOS if s.get("severity") == "critical"]
    assert len(critical) >= 5, f"ожидаем минимум 5 critical-сценариев, нашли {len(critical)}"


def test_yaml_well_formed():
    """Каждый сценарий должен иметь id/inputs/expected/severity."""
    for s in _SCENARIOS:
        assert "id" in s, f"сценарий без id: {s}"
        assert "inputs" in s, f"сценарий {s.get('id')} без inputs"
        assert "expected" in s, f"сценарий {s.get('id')} без expected"
        assert s.get("severity") in ("critical", "standard"), (
            f"сценарий {s.get('id')}: severity должен быть critical/standard, есть {s.get('severity')}"
        )
