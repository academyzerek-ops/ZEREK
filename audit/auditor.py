"""auditor.py · главный скрипт R11 PDF Audit.

Принцип:
    1. Прогоняем все сценарии из audit/scenarios.yaml.
    2. Для каждого: engine.compute → render PDF → pdftotext → правила.
    3. Все нарушения собираем в один CSV (audit/output/findings_*.csv).
    4. PDF файлы складываем в audit/output/pdfs/ для ручной проверки.

Запуск:
    python3 -m audit.auditor                       # все сценарии
    python3 -m audit.auditor --limit 3             # первые 3 (отладка)
    python3 -m audit.auditor --scenarios path.yaml # другой YAML
    python3 -m audit.auditor --critical-only-exit  # exit 1 если есть critical

Exit codes:
    0  — нет critical findings (или вообще нет findings)
    1  — есть critical findings (для CI gate)
"""
from __future__ import annotations

import argparse
import csv
import importlib
import sys
from datetime import date
from pathlib import Path
from typing import Any, Dict, Iterable, List

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from audit.rules import RULE_MODULES  # noqa: E402
from audit.runner import compute_and_render  # noqa: E402


def _load_scenarios(path: Path) -> List[Dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or []
    return data


def _collect_check_functions() -> List:
    funcs = []
    for mod_name in RULE_MODULES:
        mod = importlib.import_module(mod_name)
        for attr in dir(mod):
            if attr.startswith("check_"):
                funcs.append(getattr(mod, attr))
    return funcs


def _run_rules(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for func in _collect_check_functions():
        try:
            findings = func(pdf_text, engine_result) or []
        except Exception as e:  # noqa: BLE001 — правила не должны валить аудит
            findings = [{
                "severity": "high",
                "rule": f"{func.__name__}_crashed",
                "message": f"Правило {func.__name__} упало: {e}",
                "evidence": str(e)[:200],
            }]
        out.extend(findings)
    return out


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="audit.auditor")
    parser.add_argument("--scenarios", default="audit/scenarios.yaml",
                        help="Путь к YAML со сценариями")
    parser.add_argument("--limit", type=int, default=None,
                        help="Прогнать только первые N (для отладки)")
    parser.add_argument("--output-dir", default="audit/output",
                        help="Куда писать CSV и PDF (по умолчанию audit/output)")
    parser.add_argument("--critical-only-exit", action="store_true",
                        help="Exit 1 если есть critical findings (для CI)")
    parser.add_argument("--keep-pdfs", action="store_true", default=True,
                        help="Сохранять PDF в output-dir/pdfs/ (по умолчанию ДА)")
    parser.add_argument("--use-prod", action="store_true",
                        help="Качать PDF с прод-API (для локальной отладки "
                             "когда WeasyPrint не установлен)")
    args = parser.parse_args(argv)

    scenarios_path = Path(args.scenarios)
    if not scenarios_path.exists():
        print(f"❌ Не найден файл сценариев: {scenarios_path}")
        return 2

    scenarios = _load_scenarios(scenarios_path)
    if args.limit:
        scenarios = scenarios[: args.limit]

    output_dir = Path(args.output_dir)
    pdfs_dir = output_dir / "pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.keep_pdfs:
        pdfs_dir.mkdir(parents=True, exist_ok=True)

    findings_csv = output_dir / f"findings_{date.today().isoformat()}.csv"

    total_findings = 0
    severity_counts: Dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    print(f"=== PDF Audit · {len(scenarios)} сценариев → {findings_csv} ===\n")

    with open(findings_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=("scenario_id", "severity", "rule", "message", "evidence"),
        )
        writer.writeheader()

        for scenario in scenarios:
            sid = scenario.get("id", "unnamed")
            print(f"  · {sid:60}", end=" ", flush=True)

            try:
                bundle = compute_and_render(scenario, use_prod=args.use_prod)
            except Exception as e:  # noqa: BLE001
                writer.writerow({
                    "scenario_id": sid, "severity": "critical",
                    "rule": "pipeline_error",
                    "message": f"compute/render failed: {e}",
                    "evidence": str(e)[:200],
                })
                severity_counts["critical"] += 1
                total_findings += 1
                print("❌ pipeline_error")
                continue

            if args.keep_pdfs:
                (pdfs_dir / f"{sid}.pdf").write_bytes(bundle["pdf_bytes"])

            findings = _run_rules(
                bundle["pdf_text_by_page"], bundle["engine_result"],
            )
            for fnd in findings:
                writer.writerow({"scenario_id": sid, **fnd})
                severity_counts[fnd.get("severity", "low")] = (
                    severity_counts.get(fnd.get("severity", "low"), 0) + 1
                )
            total_findings += len(findings)

            sev_summary = " ".join(
                f"{lvl[:1].upper()}={cnt}"
                for lvl, cnt in [
                    ("critical", sum(1 for x in findings if x["severity"] == "critical")),
                    ("high", sum(1 for x in findings if x["severity"] == "high")),
                    ("medium", sum(1 for x in findings if x["severity"] == "medium")),
                    ("low", sum(1 for x in findings if x["severity"] == "low")),
                ]
                if cnt
            ) or "✓"
            print(sev_summary)

    print()
    print(f"=== ИТОГО: {total_findings} findings ===")
    print(f"  critical: {severity_counts['critical']}")
    print(f"  high:     {severity_counts['high']}")
    print(f"  medium:   {severity_counts['medium']}")
    print(f"  low:      {severity_counts['low']}")
    print(f"\nCSV: {findings_csv}")

    if args.critical_only_exit and severity_counts["critical"] > 0:
        print(f"\n❌ {severity_counts['critical']} critical findings → exit 1")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
