@echo off
rem Запуск сбора с компьютера (Windows): двойной щелчок по файлу
chcp 65001 >nul
cd /d "%~dp0"
git pull --rebase --autostash || goto :err
if not exist .venv ( py -3 -m venv .venv || goto :err )
.venv\Scripts\pip install -q -r requirements.txt || goto :err
.venv\Scripts\python -m collector || goto :err
git add docs/data
git diff --cached --quiet && ( echo Новых отзывов нет & goto :end )
git commit -q -m "Обновление базы отзывов (с компьютера)" || goto :err
git push || goto :err
echo Готово: данные отправлены, сайт обновится через пару минут
goto :end
:err
echo Что-то пошло не так - пришлите текст выше в чат
:end
pause
