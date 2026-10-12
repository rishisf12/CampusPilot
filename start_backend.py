# Start CampusPilot backend server
import sys
import os

sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend")
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app")

import uvicorn
uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)