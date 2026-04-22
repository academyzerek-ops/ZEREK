"""api/calculators/finmodel.py — FinModel 9 000 ₸ (заглушка).

Заглушка для будущей реализации FinModel. Спека продукта в разработке
у продуктового владельца (Адиль через Ноа). Реализация после Этапа 7+.

Текущая логика финмодели находится в:
- api/main.py: `_compute_finmodel_data`, `_apply_adaptive_answers`,
  `_FM_FIELD_MAP`, `_parse_pct`, `_parse_int`
- api/gen_finmodel.py: генерация xlsx из шаблона
- api/finmodel_report.py: HTML-отчёт

В Этапе 8 (cleanup) FinModel переедет в этот класс.
"""


class FinModelCalculator:
    """FinModel 9 000 ₸ — генератор финансовой модели на 36 месяцев.

    Заглушка: вызов `run` пока бросает NotImplementedError.
    Текущий рабочий код живёт в api/main.py + api/gen_finmodel.py.
    """

    def __init__(self, db):
        self.db = db

    def run(self, input_data):
        raise NotImplementedError(
            "FinModelCalculator не реализован — используйте main.generate_finmodel_endpoint "
            "до миграции в Этапе 8+"
        )
