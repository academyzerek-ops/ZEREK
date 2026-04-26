#!/bin/bash
# scripts/sync_knowledge.sh — R12.6.1 авто-синк knowledge/ в GitHub.
#
# Запускается launchd-агентом (~/Library/LaunchAgents/com.zerek.knowledge-sync.plist)
# раз в 30 минут. Делает:
#   1. cd в репо
#   2. git pull --rebase --autostash (подтянуть удалённые изменения если есть)
#   3. git add knowledge/  (только бизнес-данные, не code)
#   4. если есть изменения → commit + push
#   5. лог в /tmp/zerek_knowledge_sync.log
#
# Не падает при ошибках сети — пропускает итерацию, ждёт следующего запуска.
# Все ошибки логируются.
#
# Ручной запуск (для теста):
#   bash scripts/sync_knowledge.sh

set -uo pipefail

REPO="/Users/adil/Documents/ZEREK"
LOG="/tmp/zerek_knowledge_sync.log"

# PATH для launchd (по умолчанию минимальный — нужен gh для git credential)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

log "=== sync start ==="

cd "$REPO" || { log "ERROR: cd $REPO failed"; exit 1; }

# Шаг 1: pull (подтянуть удалённые правки если они есть, до push)
if ! git pull --rebase --autostash 2>>"$LOG"; then
  log "WARN: git pull failed (нет интернета? конфликт?) — пропускаю итерацию"
  exit 0
fi

# Шаг 2: add только knowledge/ (черновики, output/ и .pyc не трогаем)
git add knowledge/ 2>>"$LOG" || { log "ERROR: git add failed"; exit 1; }

# Шаг 3: если staged-изменений нет — выходим тихо
if git diff --cached --quiet -- knowledge/; then
  log "no knowledge/ changes — skip"
  exit 0
fi

# Шаг 4: коммит со списком изменённых файлов в теле сообщения
CHANGED_FILES=$(git diff --cached --name-only -- knowledge/ | head -10)
COMMIT_MSG="knowledge: автообновление $(date '+%Y-%m-%d %H:%M')

Файлы:
$CHANGED_FILES

(автокоммит через scripts/sync_knowledge.sh)"

if ! git -c user.email="small.economy.kaz@gmail.com" \
        -c user.name="Адиль (Obsidian)" \
        commit -m "$COMMIT_MSG" 2>>"$LOG"; then
  log "ERROR: git commit failed"
  exit 1
fi
log "commit ok: $(git log -1 --pretty=oneline)"

# Шаг 5: push (если нет интернета — оставит коммит локально, следующий запуск дотолкнёт)
if ! git push 2>>"$LOG"; then
  log "WARN: git push failed (нет интернета?) — коммит остался локально"
  exit 0
fi
log "push ok"
log "=== sync end ==="
