# Регрессионные тесты ZEREK Quick Check

Гарантируют что движок (`api/`) стабильно выдаёт ожидаемые значения для эталонных сценариев. Меняется бенчмарк, ставка УСН или формула — тесты упадут, и нужно либо вернуть как было, либо обновить эталон **осознанно**.

## Запуск локально

```bash
# Все 13 сценариев + 2 sanity-теста
pytest tests/test_engine_regression.py -v

# Только critical (gate для merge в main)
pytest tests/test_engine_regression.py -v -k critical

# Один конкретный сценарий
pytest tests/test_engine_regression.py -v -k manicure_home_astana_586k
```

Зависимости: `pytest`, `pyyaml` (см. `requirements.txt`). База данных
ZEREK подгружается один раз на сессию через session-scope fixture.

## Структура

```
tests/
├── conftest.py                  # fixture compute() — обёртка над QuickCheckCalculator + build_pdf_context
├── golden_scenarios.yaml        # 13 эталонных сценариев + ожидаемые значения
├── test_engine_regression.py    # pytest, parametrize по scenarios
└── README.md                    # этот файл
```

## Добавление нового сценария

1. Открой `tests/golden_scenarios.yaml`.
2. Скопируй один из существующих блоков как шаблон.
3. Заполни `inputs` (niche/format/city/capital/experience/start_month).
4. **Не заполняй expected руками наугад** — сначала прогони:

   ```bash
   python3 -c "
   import sys; sys.path.insert(0, 'tests')
   from conftest import engine_compute
   r = engine_compute({'inputs': {
       'niche': 'MANICURE', 'format': 'MANICURE_HOME', 'city': 'astana',
       'capital': 700000, 'experience': 'none', 'start_month': 5
   }})
   for k, v in r.items(): print(f'  {k}: {v}')
   "
   ```

5. Подставь полученные значения в `expected` через матчеры:

   - `{ exact: X }` — строгое равенство (используй для категорий: capital_zone, income_grade, label)
   - `{ min: X, max: Y }` — диапазон (для процентов и cashflow-чисел: ratio_pct, avg_y1)
   - `{ approx: X, tolerance_abs: 1000 }` — приближённо ±N ₸
   - `{ approx: X, tolerance_pct: 5 }` — приближённо ±5%

6. Запусти тесты — твой сценарий должен пройти на текущем коде.

7. Закоммить yaml.

## Обновление эталона при намеренной правке

Если ты СОЗНАТЕЛЬНО изменил бенчмарк или формулу — тесты упадут. Это **ожидаемое** поведение: эталон ловит изменение. Обновляй ожидания **отдельным коммитом** с описанием:

```
git commit -m "регрессия: обновлён эталон avg_y1 для Астаны
причина: добавлены ОПВР с 1.07.2026, ставка 3.5%
повлияло: 4 сценария Astana-* выросли на ~8K"
```

Никогда не обновляй yaml тихо вместе с правкой кода. Эталон — это журнал истории движка, его нужно обновлять явно.

## Что покрывается

- **Числа**: CAPEX, avg_y1, mature_monthly, breakeven, safety, marketing-фазы
- **Категории**: capital_zone (RED/AMBER/YELLOW/GREEN/UNKNOWN), income_grade (LOW/MODEST/MIDDLE/DECENT/HIGH/VERY_HIGH)
- **Метки**: capex_education_label («Обучение и курсы» vs «Повышение квалификации»)

13 сценариев покрывают: 4 зоны капитала, 6 градаций дохода, 5 разных регионов, 2 уровня опыта, 3 разных месяца старта, граничные случаи.

## Что НЕ покрывается

- **RAG-блоки** (Gemini): «Взгляд на нишу», «Первый год на практике», «Частые ошибки». Генерируются с T=0.3 и недетерминированы. Для них в R11 будет отдельный аудитор PDF.
- **Визуальный рендер PDF**: цвета, шрифты, расположение блоков. Тоже задача аудитора в R11.
- **Содержание текстовых вердиктов**. Регрессия проверяет что `capital_zone == AMBER`, но не проверяет что текст вердикта написан по правилам. Это аудитор.
- **Граничные баги рендера** (округление 323/324 на разных страницах). На текстовом уровне — R11; визуальный — глазами.

## Текущий baseline

Зафиксирован после **R10 #1+#2** (commit `228a3ad`). Главные значения для канонического сценария **MANICURE × HOME × Астана × 700K × experience=none × start_month=5**:

| Поле | Значение |
|---|---:|
| capex | 480 000 ₸ |
| avg_y1 (среднегодовая прибыль) | 270 351 ₸/мес |
| mature_monthly (на мощности) | 315 000 ₸/мес |
| breakeven_clients | 19 чел/мес |
| safety_mature | ×6.9 |
| safety_ramp | ×2.8 |
| capital_zone | YELLOW |
| income_grade | MODEST (48% от ЗП) |
| marketing_year_total | 715 000 ₸ |

При изменении любого из них — эталон требует осознанного обновления.
