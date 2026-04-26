# Авто-синк knowledge/ через launchd (R12.6.1)

Раз в 30 минут на маке Адиля запускается `scripts/sync_knowledge.sh`:
1. `git pull --rebase --autostash` (подтянуть удалённые правки)
2. `git add knowledge/` (только бизнес-данные)
3. Если есть изменения — commit с user `Адиль (Obsidian)` + push в GitHub.

Когда Адиль сохраняет файл в Obsidian внутри `09_PROD_KNOWLEDGE` (симлинк → `~/Documents/ZEREK/knowledge/`) — через 30 мин эта правка автоматически уходит на main. Railway пересобирает.

## Установка (один раз)

```bash
# 1. Положить plist в LaunchAgents
cp scripts/launchd/com.zerek.knowledge-sync.plist ~/Library/LaunchAgents/

# 2. Загрузить агент
launchctl load ~/Library/LaunchAgents/com.zerek.knowledge-sync.plist

# 3. Проверить что запустился
launchctl list | grep zerek
# должно показать: 17336  0  com.zerek.knowledge-sync
```

## ⚠️ macOS Full Disk Access

После шага 2 launchd запустит скрипт **сразу** (RunAtLoad). Если в логе `/tmp/zerek_knowledge_sync.stderr.log` появится:

```
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
```

Значит macOS блокирует bash доступ в `~/Documents/`. Нужно разово разрешить:

1. **System Settings** (⌘+пробел → "System Settings")
2. **Privacy & Security** → **Full Disk Access**
3. Нажми «**+**» внизу
4. В диалоге Open введи `/bin/bash` (⌘⇧G чтобы вписать путь) → **Open**
5. Включи toggle для **bash**
6. Перезагрузи launchd:
   ```bash
   launchctl unload ~/Library/LaunchAgents/com.zerek.knowledge-sync.plist
   launchctl load ~/Library/LaunchAgents/com.zerek.knowledge-sync.plist
   ```
7. Проверить `tail /tmp/zerek_knowledge_sync.log` — должна быть запись `=== sync start ===` без ошибок.

## Проверить что синк работает

```bash
# 1. Сделать тестовое изменение в knowledge/
echo "# тест $(date)" >> /Users/adil/Documents/ZEREK/knowledge/regions/astana.md

# 2. Дёрнуть launchd job сейчас (вместо ожидания 30 мин)
launchctl kickstart -k gui/$(id -u)/com.zerek.knowledge-sync

# 3. Через 5 секунд проверить лог
tail /tmp/zerek_knowledge_sync.log
# Должно быть:
#   commit ok: <sha> knowledge: автообновление ...
#   push ok

# 4. Откатить тест
git -C /Users/adil/Documents/ZEREK reset --hard HEAD~1
git -C /Users/adil/Documents/ZEREK push --force-with-lease  # или просто оставить тестовый коммит
```

## Удалить (если расхотелось)

```bash
launchctl unload ~/Library/LaunchAgents/com.zerek.knowledge-sync.plist
rm ~/Library/LaunchAgents/com.zerek.knowledge-sync.plist
```

Скрипт `scripts/sync_knowledge.sh` останется — его можно дёргать вручную при необходимости.

## Логи

| Файл | Что в нём |
|---|---|
| `/tmp/zerek_knowledge_sync.log` | Структурированный лог скрипта (timestamp + событие) |
| `/tmp/zerek_knowledge_sync.stdout.log` | stdout процесса (вывод git pull/push) |
| `/tmp/zerek_knowledge_sync.stderr.log` | stderr процесса (ошибки, предупреждения) |

## Что синкает

- ✅ Все изменения внутри `knowledge/` (frontmatter и markdown)
- ❌ Не трогает остальное (`api/`, `data/`, `tests/`, конфиги, output/, .pyc)

## Identity коммитов

В git history правки через Obsidian видны как:
```
Author: Адиль (Obsidian) <small.economy.kaz@gmail.com>
```
