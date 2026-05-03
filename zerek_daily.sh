#!/bin/bash
# zerek_daily.sh — мастер-скрипт ежедневного автозапуска
# Запускается launchd ежедневно в 18:00 по времени Астаны/Актобе.
#
# Цепочка действий:
#   1. Активирует .venv
#   2. Читает Google Doc → добавляет новые ссылки в pipeline
#   3. Запускает batch_extract_v3 → обрабатывает pending видео
#      (теперь генерирует 3 артефакта на видео: briefing/insight/audio)
#   4. Зеркалирует в Obsidian Vault через mirror_to_vault.py
#   5. Всё пишется в лог knowledge/logs/daily_YYYY-MM-DD.log
#
# Запуск вручную: ./zerek_daily.sh
# Тест без обработки видео: ./zerek_daily.sh --read-only

set -e

cd "$(dirname "$0")"

LOG_DIR="knowledge/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/daily_$(date '+%Y-%m-%d').log"

# Дублируем вывод в лог И в терминал
exec > >(tee -a "$LOG_FILE") 2>&1

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  ZEREK Daily Pipeline — $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "═══════════════════════════════════════════════════════════"

# Активируем venv
source .venv/bin/activate

# Шаг 1 — читаем Google Doc
echo ""
echo "▶ [1/3] Читаю Google Doc и добавляю новые ссылки в очередь"
python scripts/read_gdoc_links.py

# Если флаг --read-only — выходим
if [ "$1" = "--read-only" ]; then
    echo ""
    echo "[i] Режим --read-only: обработку видео не запускаю."
    exit 0
fi

# Шаг 2 — обрабатываем очередь (3 источника на видео)
echo ""
echo "▶ [2/3] Обрабатываю pending видео (briefing + insight + audio)"
python scripts/batch_extract_v3.py

# Шаг 3 — зеркалирование в Vault
echo ""
echo "▶ [3/3] Зеркалирую в Obsidian Vault (knowledge → vault)"
python scripts/mirror_to_vault.py

echo "═══════════════════════════════════════════════════════════"
echo "  Завершено: $(date '+%Y-%m-%d %H:%M:%S')"
echo "  Лог: $LOG_FILE"
echo "═══════════════════════════════════════════════════════════"
