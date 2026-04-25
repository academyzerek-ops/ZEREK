# ZEREK PDF Auditor (R11)

Автоматическая проверка PDF Quick Check. Дополняет R10 (`tests/`):
R10 проверяет что движок выдаёт правильные числа, **R11 проверяет что
PDF правильно эти числа описывает текстом** (без противоречий, без
запрещённых формулировок, без рассинхронов между страницами).

## Запуск локально

Через прод-API (рекомендуется на macOS — нет libgobject для WeasyPrint):

```bash
python3 -m audit.auditor --use-prod              # все сценарии
python3 -m audit.auditor --limit 3 --use-prod    # первые 3 (отладка)
```

Через локальный рендер (Linux/CI с установленным WeasyPrint):

```bash
python3 -m audit.auditor                          # все сценарии
```

CI gate — exit 1 при наличии critical:

```bash
python3 -m audit.auditor --critical-only-exit
```

## Где смотреть результаты

```
audit/output/findings_YYYY-MM-DD.csv  — таблица всех findings
audit/output/pdfs/                    — сгенерированные PDF для верификации
```

CSV открывается в Excel/Numbers. Колонки: `scenario_id, severity, rule,
message, evidence`. Сортируй по severity → разбирай critical → high → medium.

## Severity-уровни

| Уровень | Смысл | CI gate? |
|---|---|:---:|
| **critical** | Продукт нельзя продавать в этом сценарии (вердикт противоречит зоне; HOME-формат с советом «наймите команду»; grade=DECENT с заголовком «Низкий доход») | ❌ exit 1 |
| **high** | Серьёзная ошибка тона/вердикта (запрещённая фраза «дефицит капитала»; лейбл зоны отсутствует) | ⚠ warning |
| **medium** | Стилистическая или числовая мелочь (RAG отсутствует; рассинхрон 1-50K) | ⚠ warning |
| **low** | Диагностика (orphan numbers — числа в PDF без пары в engine) | info |

## Структура

```
audit/
├── auditor.py           — главный скрипт
├── runner.py            — обёртка над QuickCheckCalculator + рендер PDF
├── helpers.py           — extract_block, find_phrase_context,
│                          extract_numbers_after, parse_number,
│                          collect_all_engine_numbers
├── rules/
│   ├── verdict_consistency.py   — лейбл зоны и противоречия GREEN/AMBER
│   ├── tone_violations.py       — blacklist «дефицит/урежьте/откладывайте»
│   ├── grade_consistency.py     — grade ↔ заголовок ↔ ratio
│   ├── numerical_consistency.py — sync mature_profit, avg_y1, orphan numbers
│   └── rag_quality.py           — RAG-блоки: наличие, длина, отсутствие валюты
├── scenarios.yaml       — список сценариев для прогона
├── output/              — CSV и PDF (gitignored)
└── README.md
```

## Контракт правила

```python
def check_X(pdf_text: List[str], engine_result: Dict[str, Any]) -> List[Dict]:
    # ...
    return [{
        'severity': 'critical|high|medium|low',
        'rule':     'snake_case_id',
        'message':  'человекочитаемый текст',
        'evidence': 'кусок PDF подтверждающий находку',
    }, ...]
```

Правила должны быть **детерминированными** и **устойчивыми к шуму**.
На R10 baseline (5 сценариев) они должны давать 0 critical/high.

## Добавление нового правила

1. Создай функцию `check_*` в одном из модулей `rules/`.
2. Прогони `python3 -m audit.auditor --limit 5 --use-prod` на baseline.
3. Если правило выдаёт high/critical на baseline R10 — оно **слишком жёсткое**, ослабь.

## Добавление нового сценария

`audit/scenarios.yaml` — формат тот же что в R10 `tests/golden_scenarios.yaml`,
но без секции `expected` (правила сами генерируют ожидания).

```yaml
- id: имя_сценария
  inputs:
    niche: MANICURE
    format: HOME
    city: astana
    capital: 700000
    experience: none
    start_month: 5
```

## Расширение на новую нишу

1. Добавь сценарии в `audit/scenarios.yaml` для новой ниши.
2. Прогон `--use-prod`. Изучи findings в CSV.
3. Если правил недостаточно (есть проблема, но правило не словило) —
   добавь новое в `rules/`.
4. Когда findings чистые (0 critical, 0 high) — нишу можно публиковать.

## Что НЕ покрывается

- **LLM-судья** (Claude/Gemini читает PDF и оценивает «как живой текст
  для предпринимателя») — R12, опционально.
- **Визуальный рендер** (расположение блоков, шрифты, цвета) — пока
  глазами; в будущем — скриншот-сравнение.
- **Точность фактов в RAG** (Gemini не выдумал ли цифры рынка) —
  частично через `check_rag_no_currency_in_common_mistakes`, полно — ручной аудит.

## Известные диагностические findings

На R10 baseline (commit `228a3ad+`):
- `rag_common_mistakes_missing` (medium, для ~50% сценариев) — RAG
  Gemini нестабильно генерирует блок common_mistakes. Не блокер,
  отчёт валиден без него. Нужно мониторить долю.
- `orphan_numbers` (low, ~5 на сценарий) — числа из RAG-фраз
  типа «50-100К мобилограф». Это диагностика, не баг.
