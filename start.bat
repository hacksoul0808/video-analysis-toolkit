@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   Video Script Analyzer
echo ========================================
echo.

echo Starting API server (port 8840)...
start "API Server" python server/server.py

timeout /t 2 /nobreak >nul

echo Opening browser...
start http://localhost:8840

echo.
echo Server running. Close this window to stop.
echo ========================================
pause
