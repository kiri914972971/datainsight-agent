@echo off
setlocal

cd /d "%~dp0"

set "HTTP_PROXY=http://127.0.0.1:7897"
set "HTTPS_PROXY=http://127.0.0.1:7897"
set "NO_PROXY=127.0.0.1,localhost"

if not exist ".venv312\Scripts\python.exe" (
    echo DataInsight Agent environment was not found: .venv312
    echo Please configure the Python environment before starting the app.
    pause
    exit /b 1
)

echo Starting DataInsight Agent...
echo Local website: http://localhost:8501
echo Codex browser website: http://198.18.0.1:8501
echo AI proxy: http://127.0.0.1:7897
echo Keep Clash Verge running while using AI features.
echo.

".venv312\Scripts\python.exe" -m streamlit run app.py --server.headless=true --server.address=0.0.0.0 --server.port=8501 --browser.gatherUsageStats=false

echo.
echo DataInsight Agent has stopped. If this window closed because port 8501 is already in use,
echo close the existing Streamlit window/process first, then run start_app.cmd again.
pause

endlocal
