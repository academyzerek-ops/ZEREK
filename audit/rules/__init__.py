"""Каталог правил аудитора. Каждый модуль содержит функции `check_*`.

Контракт правила:
    def check_X(pdf_text: List[str], engine_result: dict) -> List[dict]:
        # ...
        return [{
            'severity': 'critical' | 'high' | 'medium' | 'low',
            'rule':     'snake_case_id',
            'message':  'человекочитаемый текст',
            'evidence': 'кусок PDF подтверждающий находку',
        }, ...]

Правила должны быть детерминированными и устойчивыми к шуму. На «правильных»
PDF (R10 baseline) они должны давать 0 critical/high.
"""

# Список модулей правил для динамической загрузки в auditor.py
RULE_MODULES = (
    "audit.rules.verdict_consistency",
    "audit.rules.tone_violations",
    "audit.rules.grade_consistency",
    "audit.rules.numerical_consistency",
    "audit.rules.rag_quality",
)
