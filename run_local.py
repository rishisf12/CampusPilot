#!/usr/bin/env python
"""Run CampusPilot locally with SQLite database."""
import os
import sys

# Add backend to path
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend")
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app")

# Use local database module
os.environ["DATABASE_URL"] = "sqlite:///C:/Users/Appex/Documents/Default Project/CampusPilot/database/classpilot.db"

# Patch the database module before importing main
import core.database_local as database_local
import core.database as database_orig
import sys

# Replace the original database module with our local version
sys.modules['core.database'] = database_local
sys.modules['app.core.database'] = database_local

# Now import and run
import uvicorn
from app.main import app

if __name__ == "__main__":
    print("Starting CampusPilot backend on http://127.0.0.1:8001")
    print("Using SQLite database: C:/Users/Appex/Documents/Default Project/CampusPilot/database/classpilot.db")
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)