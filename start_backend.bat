@echo off
echo ==========================================
echo Starting CampusPilot Backend...
echo ==========================================
set PYTHONPATH=C:\Users\Appex\Documents\Default Project\CampusPilot\backend;C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app
cd /d C:\Users\Appex\Documents\Default Project\CampusPilot\backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
echo.
echo Backend running at http://127.0.0.1:8001
echo.
pause