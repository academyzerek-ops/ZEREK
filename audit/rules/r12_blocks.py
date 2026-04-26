"""Правила: R12.5 блоки в PDF (соло-beauty / архетип A1).

Закрывают S5 чек-лист:
  · если novice + aggressive — стр. 3 должна содержать
    «Предупреждение — антипаттерн» (плашка из A1.antipatterns.novice_aggressive).
  · если experience=none — стр. 3 должна содержать explanation_block
    «Почему ваша первая прибыль ниже чем у знакомых мастеров»
    (A1.explanation_blocks.novice_lower_than_friends).
  · если is_r12=True — стр. «Маркетинг» должна содержать «Ваша стратегия — …»
    с пояснением по выбранной стратегии (A1.strategy_explanations).
  · если r12_level задан (premium/nice) — стр. «Паспорт» должна содержать
    level_label («Премиум-салон», «Приличный кабинет»).

Контракт: правила срабатывают только когда engine_result.is_r12 == True
(для не-A1 ниш проверки пропускаются — нет блоков и нечего проверять).
"""
from __future__ import annotations

from typing import Any, Dict, List

from audit.helpers import text_contains_phrase, find_phrase_context


def check_r12_antipattern_visible(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """novice + aggressive → красная плашка antipattern на стр. 3.

    Источник: archetype.antipatterns.novice_aggressive.block_title =
    «Предупреждение — антипаттерн».
    """
    findings: List[Dict] = []
    if not engine_result.get("is_r12"):
        return findings
    if not engine_result.get("r12_has_antipattern"):
        return findings  # триггер не сработал, нечего проверять
    if len(pdf_text) < 3:
        findings.append({
            "severity": "critical",
            "rule": "r12_antipattern_pdf_too_short",
            "message": f"PDF содержит {len(pdf_text)} страниц — стр. 3 нет",
            "evidence": f"pages={len(pdf_text)}",
        })
        return findings
    page3 = pdf_text[2]
    if not text_contains_phrase(page3, "Предупреждение"):
        findings.append({
            "severity": "critical",
            "rule": "r12_antipattern_missing",
            "message": (
                f"engine.r12_has_antipattern=True (exp={engine_result.get('r12_experience')}, "
                f"strat={engine_result.get('r12_strategy')}), "
                f"но на стр. 3 нет плашки «Предупреждение»"
            ),
            "evidence": page3[:300],
        })
    return findings


def check_r12_explanation_block_for_novice(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """experience=none → стр. 3 должна содержать объяснение
    «Почему ваша первая прибыль ниже чем у знакомых мастеров».
    """
    findings: List[Dict] = []
    if not engine_result.get("is_r12"):
        return findings
    if (engine_result.get("r12_experience") or "").lower() != "none":
        return findings
    if engine_result.get("r12_n_explanation_blocks", 0) <= 0:
        return findings  # бекенд не передал блок — пропускаем
    if len(pdf_text) < 3:
        return findings
    page3 = pdf_text[2]
    if not text_contains_phrase(page3, "Почему ваша первая прибыль"):
        findings.append({
            "severity": "high",
            "rule": "r12_explanation_block_missing",
            "message": (
                "novice (exp=none) — на стр. 3 не найдено объяснение "
                "«Почему ваша первая прибыль ниже чем у знакомых»"
            ),
            "evidence": page3[:300],
        })
    return findings


def check_r12_strategy_block_on_marketing(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """is_r12 → стр. «Маркетинг» (15+) должна содержать «Ваша стратегия — …»
    + текст пояснения. Подсказка: ищем в любой странице после 10-й.
    """
    findings: List[Dict] = []
    if not engine_result.get("is_r12"):
        return findings
    label = engine_result.get("r12_strategy_label") or ""
    if not label:
        return findings
    full_after_p10 = "\n".join(pdf_text[10:]) if len(pdf_text) > 10 else "\n".join(pdf_text)
    if not text_contains_phrase(full_after_p10, f"Ваша стратегия — {label}"):
        # Может быть «Ваша стратегия — Средняя» с длинным тире — проверяем
        # без него тоже на случай артефактов pdftotext.
        if not text_contains_phrase(full_after_p10, f"Ваша стратегия") or \
           not text_contains_phrase(full_after_p10, label):
            findings.append({
                "severity": "high",
                "rule": "r12_strategy_block_missing",
                "message": (
                    f"engine.r12_strategy_label='{label}', "
                    f"но в PDF нет блока «Ваша стратегия — {label}»"
                ),
                "evidence": find_phrase_context(full_after_p10, "Ваша стратегия", 100) or "—",
            })
    return findings


def check_r12_level_label_on_passport(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """r12_level задан (premium/nice/standard/simple) → стр. «Паспорт» (стр. 2)
    должна содержать level_label («Премиум-салон», «Приличный кабинет», …).
    """
    findings: List[Dict] = []
    if not engine_result.get("is_r12"):
        return findings
    level_label = engine_result.get("r12_level_label") or ""
    if not level_label:
        return findings
    # Паспорт — обычно стр. 2 (индекс 1). Но бывают сдвиги (cover на 1 стр.),
    # поэтому ищем по первым 4-м страницам.
    pages_to_check = pdf_text[:4]
    if not any(text_contains_phrase(p, level_label) for p in pages_to_check):
        findings.append({
            "severity": "medium",
            "rule": "r12_level_label_missing_on_passport",
            "message": (
                f"r12_level_label='{level_label}' (level={engine_result.get('r12_level')}), "
                f"но на стр. 1-4 нет упоминания «{level_label}»"
            ),
            "evidence": (pdf_text[1][:200] if len(pdf_text) > 1 else "—"),
        })
    return findings


def check_r12_strategy_label_on_passport(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    """is_r12 → стр. «Паспорт» (1-4) должна содержать «Стратегия маркетинга»
    + значение strategy_label.
    """
    findings: List[Dict] = []
    if not engine_result.get("is_r12"):
        return findings
    strategy_label = engine_result.get("r12_strategy_label") or ""
    if not strategy_label:
        return findings
    pages_to_check = pdf_text[:4]
    has_strategy_row = any(text_contains_phrase(p, "Стратегия маркетинга") for p in pages_to_check)
    has_label = any(text_contains_phrase(p, strategy_label) for p in pages_to_check)
    if not has_strategy_row:
        findings.append({
            "severity": "medium",
            "rule": "r12_strategy_row_missing_on_passport",
            "message": (
                "is_r12=True, но на стр. «Паспорт» (1-4) нет строки "
                "«Стратегия маркетинга»"
            ),
            "evidence": (pdf_text[1][:200] if len(pdf_text) > 1 else "—"),
        })
    elif not has_label:
        findings.append({
            "severity": "medium",
            "rule": "r12_strategy_label_missing_on_passport",
            "message": (
                f"r12_strategy_label='{strategy_label}', но в стр. 1-4 не найдено"
            ),
            "evidence": (pdf_text[1][:200] if len(pdf_text) > 1 else "—"),
        })
    return findings
