"""api/calculators/bizplan.py — BizPlan 15 000 ₸ (заглушка).

Заглушка для будущей реализации BizPlan. Спека продукта в разработке
у продуктового владельца (Адиль через Ноа). Реализация после Этапа 7+.

Текущая логика бизнес-плана:
- api/main.py: `/grant-bp` endpoint (грант 400 МРП Bastau Business)
- api/grant_bp.py: генерация .docx из шаблона
- templates/bizplan/grant_400mrp_template.docx

В Этапе 8 (cleanup) BizPlan переедет в этот класс. Пока — заглушка.
"""


class BizPlanCalculator:
    """BizPlan 15 000 ₸ — генератор бизнес-плана для банка/гранта.

    Заглушка: вызов `run` пока бросает NotImplementedError.
    Текущий рабочий код — api/grant_bp.py + main.grant_bp_endpoint.
    """

    def __init__(self, db):
        self.db = db

    def run(self, input_data):
        raise NotImplementedError(
            "BizPlanCalculator не реализован — используйте main.grant_bp_endpoint "
            "(грант 400 МРП) до миграции в Этапе 8+"
        )
