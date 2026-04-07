# ZEREK — Контекст проекта для Claude Code

## Что такое ZEREK
AI-платформа финансовой аналитики для предпринимателей Казахстана. Telegram Mini App (@zerekai_bot).

## Основатель
Адиль — финансист из Актобе. Не разработчик. Техническую часть ведёт Claude.

## Продуктовая линейка (Блок 1 — через Telegram Mini App)
1. Wiki-обзоры — бесплатно (лид-магнит)
2. Quick Check — 3 000 ₸ (экспресс-оценка бизнес-идеи, MVP запущен)
3. Финансовая модель — 9 000 ₸ (Excel 36 мес)
4. Бизнес-план — 15 000 ₸
5. Pitch Deck — цена TBD

## Стек
- Backend: Python 3.12, FastAPI, Railway (https://web-production-b3ede.up.railway.app)
- Frontend: чистый HTML/CSS/JS, GitHub Pages
- Данные: 19 xlsx файлов в /data/ (БНС РК, рыночные данные КЗ 2026)
- Бот: @zerekai_bot, Mini App URL: https://academyzerek-ops.github.io/ZEREK/products/quick-check.html

## Структура репозитория
```
ZEREK/
index.html              — главная сайта (GitHub Pages root)
about.html, privacy.html, wiki.html — страницы сайта
products/
  quick-check.html      — Mini App Quick Check (главный продукт)
  index.html            — лендинг продуктов
wiki/                   — обзоры ниш
api/                    — бэкенд (копия для Railway)
  main.py, engine.py, report.py
data/                   — 19 xlsx файлов базы данных
engine/                 — расчётный движок
  engine.py, report.py, init.py
Procfile, railway.json, requirements.txt
```

## API эндпоинты
- GET /cities — 15 городов КЗ
- GET /niches — 33 ниши
- GET /formats/{niche_id} — форматы по нише
- POST /quick-check — главный расчёт (city_id, niche_id, format_id, area_m2, loc_type, capital, start_month, capex_level)
- POST /quick-check/report — текстовый отчёт

## 33 ниши (niche_id → русское название)
AUTOSERVICE=Автосервис, BAKERY=Пекарня, BARBER=Барбершоп, BROW=Брови, CANTEEN=Столовая, CARWASH=Автомойка, CLEAN=Клининг, COFFEE=Кофейня, CONFECTION=Кондитерская, CYBERCLUB=Компьютерный клуб, DENTAL=Стоматология, DONER=Донерная, DRYCLEAN=Химчистка, FASTFOOD=Фастфуд, FITNESS=Фитнес, FLOWERS=Цветы, FRUITSVEGS=Овощи и фрукты, FURNITURE=Мебель, GROCERY=Продукты, KINDERGARTEN=Детский сад, LASH=Ресницы, MASSAGE=Массаж, NAIL=Маникюр, PHARMA=Аптека, PIZZA=Пиццерия, PVZ=ПВЗ, REPAIR_PHONE=Ремонт телефонов, SEMIFOOD=Полуфабрикаты, SUGARING=Шугаринг, SUSHI=Суши, TAILOR=Ателье, TIRE=Шиномонтаж, WATER=Вода

## Налоги КЗ 2026
- МРП = 4 325 ₸
- Патент ОТМЕНЁН с 01.01.2026 → заменён на «Самозанятый»
- УСН порог = 600 000 МРП ≈ 2,595 млрд ₸
- НДС = 16%, ОПВР = 3.5%
- Ставки УСН: Астана 3%, Алматы 3%, Шымкент 2%, Актобе 3%, Караганда 2%, Атырау 2%, Павлодар 3%, Костанай 3%, УК 2%, Уральск 3%

## Правила работы
- Все тексты пользователю — на русском языке
- Все ID в коде — на английском (COFFEE, BAKERY и тд)
- Названия в интерфейсе — всегда на русском через маппинг
- Quick Check стоит 3 000 ₸ (НЕ бесплатно)
- GitHub Pages настроен на / (root), НЕ на /docs
- При любых изменениях — git add, commit, push
- Тон ZEREK: практичный консультант, не мотиватор. Акцент на рисках.

## Дизайн
- Тёмная тема: #06060B, акцент #7C6CFF / #6C63FF, зелёный #00D4AA
- Шрифты: Outfit (UI), JetBrains Mono (цифры), Playfair Display + Source Sans 3 (отчёты)
- Mobile-first, max-width 440px
