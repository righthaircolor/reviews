#!/bin/bash
# Запуск сбора с компьютера (macOS / Linux): двойной щелчок по файлу или ./run_local.command
cd "$(dirname "$0")" || exit 1
set -e
command -v python3 >/dev/null || { echo "Нужен Python 3: https://www.python.org/downloads/"; read -r; exit 1; }
git pull --rebase --autostash
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m collector
git add docs/data
if git diff --cached --quiet; then echo "Новых отзывов нет"; else git commit -q -m "Обновление базы отзывов (с компьютера)"; git push; echo "Готово: данные отправлены, сайт обновится через пару минут"; fi
echo; read -r -p "Нажмите Enter, чтобы закрыть"
