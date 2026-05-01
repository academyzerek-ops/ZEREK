# Аудит ZEREK — 2026-04-29

**Скоуп:** read-only комплексная проверка состояния репо после месяцев активной разработки.
**HEAD:** `460e06d` (revert(wiki): simplify wiki_only CTA to inactive state) → fast-forward за `b9987d5` (Адиль/Obsidian).
**Метод:** 3 параллельных агента (Backend / PDF / Structure+Security) + прямые пробы Railway, верификация HTML CTA, диффы реестра.

---

## 1. Executive summary

ZEREK в нормальном продакшн-состоянии: backend на Railway отвечает за ~1с, все 33 калибровки загружаются без ошибок, налоговые константы централизованы, city_id-нормализация работает. Wiki и реестр после последних коммитов (5374e82, b902f33, 460e06d) синхронны: 22 wiki_only действительно неактивны, 25/26 production_ready с активным CTA.

Основные проблемы — **архитектурный долг**, не критические баги:
- **MASSAGE показывает стейл «3 000 ₸»** в QC-CTA вместо «5 000 ₸» — единственный production_ready с этой ошибкой (HIGH).
- **Множественные источники правды** для ниш (config/niches.yaml=62, niches_registry.yaml=64, data/niches/*.yaml=54, knowledge/niches/=1) — миграция R12.6 на 1 нише, остальные на legacy (HIGH).
- **Анти-паттерн «новичок+агрессивный маркетинг»** показывается только для A1/MANICURE; остальные ниши не получают предупреждения (MED).
- **PDF-шаблон** не соответствует FAST-палитре Mini App (вместо #7C6CFF — навigator/gold; вместо Geist — Source Sans 3) (MED).
- **Дублирование расчёта ФОТ** в 3+ местах (engine.py + economics_service.py) (MED).

Безопасность чистая: секретов в коде нет, бот-токен только в Railway env. Bot-инфраструктуры в репо нет — это задокументировано в CLAUDE.md как «без кода, через BotFather».

---

## 2. Сводка находок

| #  | Блок | Приоритет | Описание | Предложение | Статус |
|----|------|-----------|----------|-------------|--------|
| 1  | 1.4  | HIGH    | MASSAGE wiki: стейл «3 000 ₸» в QC-CTA вместо «5 000 ₸» | Заменить на 5 000 ₸ (как сделано для Cosmetology в предыдущем коммите) | open |
| 2  | 1.2  | HIGH    | Мульти-источник для ниш: 62 vs 64 vs 54 vs 1 (R12.6 пилот) | Зафиксировать canonical в одном месте, остальные пометить как fallback/устаревшие | open |
| 3  | 2.3  | MED     | Архетип A1 в коде только для MANICURE; BARBER/BROW/LASH/SUGARING на legacy-ветке | Завершить миграцию A1 на оставшиеся 4 ниши | open |
| 4  | 3.2  | MED     | Анти-паттерн «новичок+агрессивный» показывается только для R12.5/A1 | Расширить на остальные ниши или явно задокументировать ограничение | open |
| 5  | 3.4  | MED     | PDF-шаблон не FAST-палитра: navy+gold вместо #7C6CFF, Source Sans 3 вместо Geist | Привести шаблон к FAST или явно зафиксировать «PDF имеет отдельный editorial-стиль» | open |
| 6  | 2.6  | MED     | ФОТ-расчёт дублируется в engine.py:1021,1149 + economics_service.py:57-59,115-117,180-182 | Извлечь helper `_calc_fot_full(fot_net)` в одно место | open |
| 7  | 4.1  | MED     | 7 untracked stale аудит-артефактов в root (~280 КБ): AUDIT_REPORT.md, CLEANUP_PLAN.md и др. | Перенести в `docs/audit_history/` или удалить (после согласия) | open |
| 8  | 4.2  | MED     | .gitignore не покрывает `.env`, `.env.*`, `*.log`, `~$*.xlsx`, `.idea/`, `.vscode/`, `venv/` | Добавить эти строки | open |
| 9  | 4.5  | LOW-MED | config/niches.yaml: декларирует 57 ниш в комменте, фактически 62 | Обновить комментарий или зафиксировать новую цифру | open |
| 10 | 4.4  | LOW     | README.md = stub (7 байт, «# ZEREK»). | Добавить минимальный quick-start или явно указать «см. CLAUDE.md» | open |
| 11 | 6.1  | LOW     | /healthz эндпоинт отсутствует (HTTP 404) | Добавить простой `{"status":"ok"}` для healthcheck Railway | open |
| 12 | 4.3  | LOW     | requirements.txt: 3 unpinned (weasyprint>=, Jinja2>=, pytest>=) | Запинить точные версии для воспроизводимости | open |
| 13 | 3.1  | LOW     | Блок RESERVE на старте — всего 2 строки в шаблоне; коротковато для «наставнического» блока | Расширить пояснением «откуда взялась цифра» | open |
| 14 | 1.1  | LOW     | FORMAT_ID_SYNC между per-niche xlsx и 08_niche_formats.xlsx — упомянут в стейл-репорте от 21.04 | Перепроверить: актуально ли расхождение или закрыто за неделю | open |
| 15 | 2.1  | LOW     | DATA_DIR — hardcoded relative path к api/. Работает на Railway и локально, но хрупко если api/ переедет | Сделать env-driven override (опционально) | open |
| 16 | 2.5  | OK ✓   | FITNESS-баг (пакеты сессий как ежедневная покупка) — в текущем коде НЕ воспроизводится | Тихо не закрывать: записать в changelog «баг отсутствует на 2026-04-29», добавить regression-тест | open |
| 17 | 5.1-2 | OK ✓  | Секретов в коде нет; bot-токен — только Railway env | Подтверждено: статус-кво | — |
| 18 | 5.3  | OK ✓   | Railway: 921a5 канонический и задокументирован; b3ede только в `.claude` worktree | Не трогать | — |

---

## 3. Детальный разбор по блокам

### Блок 1 — Синхронизация контента

**1.1 Матрица «ниша × три статуса»** — уже зафиксирована в `data/kz/niches_registry.yaml` (commit `5374e82`):
- 33 ниш с `status: production_ready` (есть калибровка xlsx)
- 22 ниш `wiki_only` (есть HTML-обзор, нет калибровки): 13 с insight+data, 9 «сирот»
- 9 ниш `research` (только insight)
- Итого 64 уникальных canonical-кода. Один alias: `REPAIR_PHONE.aliases: [REPAIRPHONE]`.

**1.2 niches_registry.yaml** — ✓ существует, валиден, задеплоен на Railway (виден в `/debug` ответе как `niches_registry.yaml` в файлах `data/kz/`).

**1.3 «Совсем пусто» ниш** — нет. Все ниши покрыты хотя бы одним из 4 уровней (calibration/insight/data/wiki).

**1.4 CTA-проверка** (после коммита 460e06d):
- 22/22 wiki_only имеют неактивный «Скоро»-блок (`cursor:not-allowed`, `opacity:.7`, `<span>` вместо `<a>`) ✓
- 25/26 production_ready имеют активный QC-CTA с ценой 5 000 ₸ ✓
- **1/26 проблема: MASSAGE** показывает «3 000 ₸» вместо «5 000 ₸» (`wiki/kz/ZEREK_Massage.html`, первый `cta-block`). Это единственный оставшийся стейл — у COSMETOLOGY такой же был, я его поправил в коммите 460e06d, MASSAGE пропустил.
- Структурное наблюдение: AUTOSERVICE/MANICURE/CLEAN — единый `<section class="cta-block">` с QC и FinModel внутри (как BrowLash). BARBER/DENTAL — 3 блока (QC + промо + FinModel). Не баг, разные дизайн-паттерны.

### Блок 2 — Бэкенд (api/main.py, engine.py, services/, loaders/)

**2.1 xlsx-калибровки.** Загружаются eager на старте через glob (`engine.py:651–698`). Все 33 файла видны в `/debug`, `db_loaded: true`, ошибок при старте нет. Header у per-niche файлов = строка 2 (`engine.py:675`); у legacy/aggregate (01_cities, 07_niches, 08_niche_formats) — строка 4 или 5 (`engine.py:626–642`). DATA_DIR — `os.path.join(api/../data/kz)` (`engine.py:14`), резолвится одинаково локально и на Railway.

**2.2 city_id case.** Закрыто. Нормализация в `loaders/city_loader.py:27–35`, маппинг строится из `config/constants.yaml.cities[].legacy_ids` в `engine.py:562–578`. На входе run_quick_check_v3 (`engine.py:860`) делается `normalize_city_id()`. Хардкоды UPPER/lower city_id в коде, обходящие нормализацию, — не найдены.

**2.3 Архетип A1 (опыт мастера).** Реализован в коде (`engine.py:_apply_r12_5_overrides() lines 220–349`), читает `knowledge/archetypes/A1_BEAUTY_SOLO.md` через `load_archetype_yaml('A1')`. **Активен только для MANICURE** — единственная ниша, имеющая `formats_r12` блок в xlsx. BARBER/BROW/LASH/SUGARING упоминаются как кандидаты, но фактически идут по legacy-ветке.

**2.4 Маркетинговая ось ×0.20 / ×1.0 / ×1.40.** Реализована в `services/marketing_service.py:257–278`. **Влияет только на бюджет**, не на ramp-curve (ramp_curve хранится отдельно в `PHASE_BUDGETS_BY_R12`, lines 183–199, и не модифицируется стратегией). Значения: conservative=0.20, middle=1.00, aggressive=1.40 (из `A1_BEAUTY_SOLO.md:67–100`).

**2.5 FITNESS-баг.** В текущем коде **специальной FITNESS-логики нет**. Все ниши считают выручку униформно: traffic × check (`services/economics_service.py`). Поиск показал упоминание FITNESS только в labels/mappings (`grant_bp.py:105`, `quick_check_renderer.py:484`). Вывод: либо баг закрыт давно и логика унифицирована, либо его никогда не было. Не закрывать тихо — добавить regression-тест перед окончательным признанием закрытым.

**2.6 ФОТ-расчёт.** FOT_MULTIPLIER определён в `engine.py:70` (берётся из `config/constants.yaml.owner.fot_multiplier = 1.175`). **Логика дублируется**: `engine.py:1021, 1149` + `economics_service.py:57-59, 115-117, 180-182` — одинаковый паттерн `if fot_full == 0 and fot_net > 0: fot_full = fot_net * multiplier`. Не критично, но расходится при изменении.

**2.7 Налоги КЗ 2026.** Централизованы в `data/external/kz_tax_constants_2026.yaml`, читается через lru_cache в `loaders/tax_constants_loader.py`. Все актуальные значения:

| Константа | Значение | Источник | Стейл-копии? |
|---|---|---|---|
| МРП | 4 325 ₸ | yaml:48 | Нет; в engine.py есть fallback `4325` на line 57 — допустимо |
| НДС | 16% | yaml:159 | Нет |
| УСН | 3% (большинство), 2% (Шымкент/Туркестан) | yaml:112–121 | Нет |
| ОПВР | 3.5% | yaml:179 | Нет |
| Патент | ABOLISHED 01.01.2026 → Самозанятый | main.py:736, pdf_renderer:1340 (только историческая ссылка) | Нет, только historic-mention |

### Блок 3 — Генерация PDF

**3.1 Пять обязательных «наставнических» блоков** (`api/templates/pdf/quick_check.html`):
- RAMP-UP — стр. 8, lines 1549–1580 («Достаточность капитала» с упоминанием «первые 3 месяца»). ✓
- СЕЗОННОСТЬ — стр. 14, lines 2066–2125 (полная секция с графиком). ✓
- МАРКЕТИНГ — стр. 15, lines 2128–2268 (помечено «Наставничество #3»). ✓
- КАДРЫ — стр. 9, lines 1595–1652 (с tax-callout «11.5% работодатель»). ✓
- РЕЗЕРВ НА СТАРТЕ — стр. 8, lines 1556–1570 (`reserve_breakdown` из `cadq.reserve_total`). ⚠ Текстуально коротковато (2 строки); расчёт корректный, но как «наставнический» блок выглядит куце.

**3.2 Анти-паттерн «новичок+агрессивный».** Есть, на стр. 3 (`quick_check.html:961–972`). Логика триггера в `pdf_renderer_weasyprint.py:1260–1274`: цикл проверяет `experience == "none" AND strategy == "aggressive"`. **Ограничение**: показывается только для R12.5-ниш (только A1/MANICURE сейчас); для legacy-ниш блок пропускается (`r12.is_r12 = False` line 1244).

**3.3 Сценарий 2-3 года.** Есть, стр. 20 «А что дальше?» (`quick_check.html:2635–2675`). Рендерит 3 сценария роста из `growth_scenarios` (источник: `services/growth_service.py:46–60`, читает из niche YAML). Опционально — у не всех ниш есть YAML-блок.

**3.4 FAST-формат (палитра + шрифты).** **Не соответствует** Mini App-спецификации из CLAUDE.md:

| Требование (CLAUDE.md) | PDF-шаблон | Статус |
|---|---|---|
| --bg #FFFFFF | quick_check.html:89 ✓ | OK |
| --accent #7C6CFF | НЕТ; используется navy #1F3864 + gold #C9A961 | MISMATCH |
| --green #10B981 | line 92 ✓ | OK |
| --amber #F59E0B | line 93 ✓ | OK |
| --red #EF4444 | line 94 ✓ | OK |
| Geist (UI) | НЕТ; используется Source Sans 3 | MISMATCH |
| Geist Mono (цифры) | НЕТ; используется JetBrains Mono | MISMATCH |
| Playfair Display (опционально) | line 95 ✓ | OK |

PDF использует «editorial»-палитру (navy+gold), отличную от Mini App. Это могло быть осознанное решение под печатный формат, но не задокументировано.

**3.5 Smoke-тест.** Существующие артефакты в `.claude/worktrees/.../output/r12_5_smoke/` (8 HTML, ~115 КБ каждый, от 2026-04-27): MANICURE HOME/SALON/STUDIO × experience=none/middle/experienced × strategy=conservative/middle/aggressive. **Покрытие узкое — только MANICURE.** Для аудита числа имеет смысл прогнать ≥3 ниши разных архетипов. `tests/integration/test_quick_check.py:44-98` использует реальный xlsx (не моки) для MANICURE_HOME/Астана/none/500K.

### Блок 4 — Структура репо

**4.1 Untracked .md-артефакты в корне** (всё от 21–22 апреля, ~280 КБ суммарно):

| Файл | Размер | Дата | Содержание | Рекомендация |
|---|---|---|---|---|
| AUDIT_REPORT.md | 108 КБ | 2026-04-21 | Inventory Quick Check (57 ниш, 14 sheets шаблонов), ссылается на коммит 784196e | Архив в `docs/audit_history/2026-04-21_audit/` |
| CLEANUP_PLAN.md | 65 КБ | 2026-04-21 | План фазы-1 чистки, ссылка на финальное состояние 7fcc482 | Архив (план выполнен или забыт) |
| DIAGNOSTICS_REPORT.md | 32 КБ | 2026-04-22 | Диагностика 7 багов QC (format_id, ROI, capital_score) | Сверить с текущим кодом, что починено; что нет — в issue tracker |
| DIAG_ROUND2.md | 8 КБ | 2026-04-22 | Раунд 2 той же диагностики | После сверки — архив |
| FORMAT_ID_SYNC_REPORT.md | 26 КБ | 2026-04-21 | Аудит format_id-расхождений: 0% полного sync, 55% partial, 45% mismatch | Перепроверить (см. находку #14) |
| NICHE_INVENTORY.md | 14 КБ | 2026-04-22 | Inventory ниш (5 источников). До регистра. | Заменён на `data/kz/niches_registry.yaml`, можно архивировать |
| YOUTUBE_PIPELINE_AUDIT.md | 29 КБ | 2026-04-22 | Аудит удалённого YouTube→Gemini pipeline (удалён 2026-04-13, e2cd588) | Архив (исторический) |

Все 7 — untracked. Решение надо принимать осознанно: архив или удаление. **Без согласия Адиля не трогаю.**

**4.2 .gitignore**:
```
покрыто:    .claude/, __pycache__/, *.pyc, .DS_Store, tests/fixtures/, tests/local/,
            REFACTOR_PLAN.md, REFACTOR_NOTES.md, docs/refactor_history/,
            .pytest_cache/, audit/output/
не покрыто: .env, .env.*, *.log, ~$*.xlsx, .idea/, .vscode/, venv/, .venv/, *.egg-info/
```

**4.3 requirements.txt**: 13 пакетов. `fastapi==0.115.0`, `pandas==2.2.2`, `pydantic==2.9.2` и др. — pinned. `weasyprint>=68.0`, `Jinja2>=3.1`, `pytest>=8.0` — unpinned (риск drift). Кросс-проверка по импортам: `pyyaml` присутствует в requirements, используется через `import yaml` — соответствует. Лишних/неиспользуемых не найдено.

**4.4 CLAUDE.md и README.md**:
- **CLAUDE.md** (12 КБ, 161 строка) — актуален в основных пунктах:
  - «Бот без кода — настраивается через BotFather» — ✓ верно (нет aiogram/telebot в репо).
  - «Canonical niche list = config/niches.yaml» — ⚠️ устарело: появился `data/kz/niches_registry.yaml` (5374e82), и они расходятся в кол-ве (62 vs 64). См. находку #2.
  - Railway URL `web-production-921a5...` — ✓ правильный (см. блок 5.3).
  - R12.6 раздел («knowledge/ — бизнес-данные») — ✓ верно описан, но фактически только MANICURE мигрирован.
- **README.md** (7 байт, «# ZEREK») — stub. Минимально надо: 1) что это, 2) ссылка на CLAUDE.md, 3) команда `uvicorn api.main:app` для локального запуска.

**4.5 Папки**:
- Логично разделено: `api/` (бэкенд), `data/` (xlsx), `knowledge/` (R12.6 бизнес-контент), `wiki/` (HTML-обзоры), `products/` (Mini App), `config/` (тех-реестры), `templates/` (шаблоны докуметов).
- Подкаталог `api/services/` (16 модулей: economics, marketing, growth, scenario, stress, risk и т.д.) и `api/loaders/` (8 модулей) — структурированно. Не в корне `api/` — правильно.
- **Множественные источники правды для ниш** (главная архитектурная проблема):

| Источник | Кол-во записей | Статус |
|---|---|---|
| `config/niches.yaml` | 62 (комментарий говорит «57») | tech-реестр, упомянут в CLAUDE.md как канон |
| `data/kz/niches_registry.yaml` | 64 (включая wiki_only/research) | свежий (5374e82), деплоится |
| `data/niches/*_data.yaml` | 54 | legacy, fallback |
| `knowledge/niches/*.md` | 1 (только MANICURE) | R12.6 пилот, цель миграции |

CLAUDE.md заявляет канон = `config/niches.yaml` для technical-реестра + `knowledge/niches/{NICHE}.md` для бизнес-данных. Но миграция R12.6 застряла на 1 нише, а `niches_registry.yaml` появился позже и не упомянут в CLAUDE.md.

### Блок 5 — Безопасность

**5.1 Секреты в истории**: `git log --all -p` через grep по `api[_-]?key|token|secret|password|bearer|sk-|ghp_` — реальных секретных строк не обнаружено. Совпадения только в именах переменных, шаблонах и docs.

**5.2 Telegram bot token**: grep по `BOT_TOKEN|TELEGRAM_TOKEN|TG_TOKEN|zerekai_bot.*token` в `.py/.yaml/.json/.toml` — нет совпадений в коде. Должен быть в Railway env, в репо не утёк. ✓

**5.3 Railway-домен**:
- **Канонический: `web-production-921a5.up.railway.app`** — задокументирован в CLAUDE.md:17 и используется в `qc-v3.html`, `app.html`, `audit/runner.py`, `docs/ADDING_NEW_NICHE.md`.
- **`b3ede`** — встречается только в `.claude/worktrees/.../settings.local.json` (Claude-local артефакт, не репо-контент).
- Оба URL живы (HTTP 200). GET `/niches` возвращает bit-identical responses (sha256 совпадает, 3 954 байт). Это один и тот же backend с двумя URL-алиасами Railway.
- **CLAUDE.md обновлять не нужно** — там уже зафиксирован 921a5.

### Блок 6 — Производительность и надёжность

**6.1 /debug**: ✓ работает, возвращает `base_dir`, `data_dir`, список 18 общих xlsx + 33 niche xlsx + `niches_registry.yaml`, `db_loaded: true`, `db_error: null`.

**6.2 /quick-check timing**: 3 прогона на BARBER/STANDARD/almaty/area=50/capital=3M — времена 0.85с, 0.85с, 1.08с. Размер ответа ~21 КБ JSON. Узкое место не выявлено в этом аудите (нужен профилировщик); по заявлениям Agent 1 — eager-загрузка xlsx на старте, рантайм-расчёт без чтения дисков.

**6.3 /healthz**: возвращает HTTP 404 — эндпоинта нет. Railway автодетект работает по факту что `/` отвечает 200. Для явного healthcheck стоит добавить `@app.get("/healthz") def healthz(): return {"status": "ok"}`.

**6.4 Логирование/error handling**: глубоко не проверял (вне scope одного прохода). Stack-trace vs friendly-message — нужна отдельная проба с заведомо невалидным запросом. **Помечаю как UNCLEAR — рекомендую отдельный мини-аудит.**

---

## 4. Что Кот хотел бы поправить, требуется согласие

Перечень — в порядке убывания пользы. Каждый — отдельный коммит.

1. **Поправить MASSAGE «3 000 ₸» → «5 000 ₸»** (находка #1). Однострочная замена в `wiki/kz/ZEREK_Massage.html`. То же что было сделано для COSMETOLOGY в коммите 460e06d. Безопасно, ничего не сломает.
2. **Дополнить .gitignore** (находка #8). Добавить блок:
   ```
   .env
   .env.*
   *.log
   ~$*.xlsx
   .idea/
   .vscode/
   venv/
   .venv/
   *.egg-info/
   ```
   Defensive-hygiene, но требует согласия (вдруг где-то есть `*.log`, который ты хочешь видеть).
3. **Архивировать 7 stale .md-артефактов** (находка #7). Создать `docs/audit_history/2026-04-21/` и переместить туда. Корневое дерево станет чище.
4. **Добавить /healthz** (находка #11). 3 строки в `api/main.py`.
5. **Заменить README.md заглушку** (находка #10) на минимальный quick-start: что такое, как запустить (`uvicorn api.main:app --reload`), ссылка на CLAUDE.md.
6. **Запинить unpinned-зависимости** (находка #12). `weasyprint==68.X`, `Jinja2==3.1.X`, `pytest==8.X.X` под актуальный lock.
7. **Обновить комментарий в `config/niches.yaml`** с «57» на «62» (находка #9).
8. **Извлечь helper `_calc_fot_full(fot_net)`** в один модуль (например, `services/economics_service.py`) и переиспользовать (находка #6).

## 5. Что Кот рекомендует НЕ трогать

1. **PDF-палитра navy+gold** (находка #5). Возможно осознанный editorial-выбор. Прежде чем менять — спросить дизайнера: PDF и Mini App = одна тема или разные намеренно?
2. **Архитектура множественных источников ниш** (находка #2). Большая работа: миграция R12.6 на оставшиеся 30+ ниш. Пока что-нибудь не посыпалось — продолжать пилотный режим.
3. **DATA_DIR hardcoded path** (находка #15). Работает на всех существующих окружениях. Менять — риск регрессии для нулевой пользы.
4. **FORMAT_ID_SYNC** (находка #14). Сначала проверить актуальность отчёта от 21.04 — возможно уже починено за неделю активной разработки. Действовать только после повторного запуска того же аудита.
5. **FITNESS-bug regression-тест** (находка #16). Не закрывать тихо, но и не торопиться добавлять тест без понимания что именно проверять (в прошлом было session-package, но логики такой больше нет — регрессия может вернуться только при добавлении новой ниши с подписочной моделью).
6. **Расширение анти-паттерна «новичок+агрессивный» на legacy-ниши** (находка #4). Связано с миграцией R12.6 — лучше делать одним пакетом, не точечно.
7. **Содержимое `.claude/`** (включая `worktrees/`). Это локальные артефакты Claude Code, в репо они уже в .gitignore. Не лезть.

---

## Приложение A — действия в формате [FIX NOW]/[FIX LATER]/[SKIP]/[DISCUSS]

Заполняется Адилем по каждой находке #1-18:

```
#1  MASSAGE 3 000 → 5 000        [    ]
#2  Мульти-источник ниш          [    ]
#3  Архетип A1 на 4 ниши         [    ]
#4  Анти-паттерн на не-A1        [    ]
#5  PDF FAST-палитра             [    ]
#6  ФОТ duplication              [    ]
#7  Архив 7 stale .md            [    ]
#8  .gitignore gaps              [    ]
#9  niches.yaml 57→62 коммент    [    ]
#10 README.md stub               [    ]
#11 /healthz                     [    ]
#12 Pin weasyprint/Jinja2/pytest [    ]
#13 Расширить RESERVE-блок       [    ]
#14 FORMAT_ID_SYNC re-check      [    ]
#15 DATA_DIR env-driven          [    ]
#16 FITNESS regression test      [    ]
#17 Секреты — статус-кво         [-]   (нет действия)
#18 Railway URL — статус-кво     [-]   (нет действия)
```

После заполнения — Кот делает только `[FIX NOW]`, остальное в бэклог.
