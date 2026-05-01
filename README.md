# ZEREK

AI-аналитика для предпринимателей Казахстана. Защита от потерь, не «успешный успех».

5 продуктов в воронке + Академия + канал «Чужие грабли».

## Документация

Главный навигатор для разработчика и AI-агента — [`CLAUDE.md`](./CLAUDE.md). Глубина по темам — в [`docs/context/`](./docs/context/).

## Quick start (локально)

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить API
uvicorn api.main:app --reload --port 8000
```

Эндпоинты:
- `GET /` — статус
- `GET /healthz` — health check
- `GET /debug` — список загруженных файлов
- `POST /quick-check` — главный расчёт ($10)
- `POST /finmodel` — финансовая модель ($20)

## Стек

Python 3.12 / FastAPI / WeasyPrint / Gemini Flash RAG. Frontend — чистый HTML/CSS/JS, GitHub Pages. API — Railway.

## Source of Truth

| Тема | Файл |
|---|---|
| Налоги КЗ 2026 | `data/external/kz_tax_constants_2026.yaml` |
| Ниши и форматы | `data/kz/niches_registry.yaml` |
| Цены продуктов | `data/products.yaml` |
| Архитектура движка | `ARCHITECTURE.md` |
| Архетипы | `knowledge/archetypes/*.md` |

Протокол изменений и запреты на дублирование — в [`docs/context/10_OPERATIONS.md`](./docs/context/10_OPERATIONS.md).

## Лицензия

Closed-source, all rights reserved © Adil / ZEREK.
