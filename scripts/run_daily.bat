@echo off
setlocal
chcp 65001 >nul

cd /d "%~dp0.."

if not exist logs mkdir logs

echo [%date% %time%] Starting AI Tech Radar daily pipeline...
python main.py daily >> "logs\daily_console.log" 2>&1
set "EXIT_CODE=%ERRORLEVEL%"

echo [%date% %time%] Daily pipeline finished with exit code %EXIT_CODE%
exit /b %EXIT_CODE%
