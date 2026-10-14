@echo off
cd /d C:\Users\Appex\Documents\Default Project\CampusPilot
set PYTHONPATH=C:\Users\Appex\Documents\Default Project\CampusPilot\backend;C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app
set DATABASE_URL=sqlite:///C:/Users/Appex/Documents/Default Project/CampusPilot/database/classpilot.db
"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\venv\Scripts\python.exe" run_local.py
pause