#!/usr/bin/env python
"""Run CampusPilot locally with SQLite database - simplified."""
import os
import sys

# Set the database URL for SQLite BEFORE any imports
os.environ["DATABASE_URL"] = "sqlite:///C:/Users/Appex/Documents/Default Project/CampusPilot/database/classpilot.db"

# Add backend to path
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend")
sys.path.insert(0, r"C:\Users\Appex\Documents\Default Project\CampusPilot\backend\app")

# Now import and run - this will use the existing database.py but with SQLite URL
# We need to patch the engine creation to work with SQLite
import core.config as config_module
# Force reload settings with our SQLite URL
config_module.settings = config_module.Settings(_env_file=None)

# Patch the database module
import core.database as database_module

# Override engine_kwargs to work with SQLite
original_engine_kwargs = database_module.engine_kwargs

def patched_engine_kwargs():
    from urllib.parse import urlparse
    from sqlalchemy.pool import StaticPool
    
    url = config_module.settings.database_url
    parsed = urlparse(url)
    
    if parsed.scheme in ("sqlite", "sqlite+pysqlite"):
        return {
            "poolclass": StaticPool,
            "connect_args": {
                "check_same_thread": False,
                "timeout": 30,
            },
        }
    else:
        return original_engine_kwargs()

database_module.engine_kwargs = patched_engine_kwargs

# Also patch create_engine_with_retry to not retry so aggressively for SQLite
original_create_engine_with_retry = database_module.create_engine_with_retry

def patched_create_engine_with_retry(url, max_retries=3, base_delay=0.5):
    if parsed.scheme in ("sqlite", "sqlite+pysqlite"):
        max_retries = 3
        base_delay = 0.5
    return original_create_engine_with_retry(url, max_retries, base_delay)

database_module.create_engine_with_retry = patched_create_engine_with_retry

# Re-create the engine with our patched function
from sqlmodel import Session, create_engine
from sqlalchemy import text, event

database_module.engine = database_module.create_engine_with_retry(config_module.settings.database_url)

# Enable foreign keys for SQLite
from urllib.parse import urlparse
parsed = urlparse(config_module.settings.database_url)
if parsed.scheme in ("sqlite", "sqlite+pysqlite"):
    @event.listens_for(database_module.engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# Override upgrade_schema and create_db_and_tables for SQLite
original_upgrade_schema = database_module.upgrade_schema
original_create_db_and_tables = database_module.create_db_and_tables

def patched_upgrade_schema():
    if parsed.scheme in ("sqlite", "sqlite+pysqlite"):
        print("SQLite detected: creating tables from models")
        from sqlmodel import SQLModel
        SQLModel.metadata.create_all(database_module.engine)
    else:
        original_upgrade_schema()

def patched_create_db_and_tables():
    patched_upgrade_schema()

database_module.upgrade_schema = patched_upgrade_schema
database_module.create_db_and_tables = patched_create_db_and_tables

# Now import and run
import uvicorn
from app.main import app

if __name__ == "__main__":
    print("Starting CampusPilot backend on http://127.0.0.1:8001")
    print("Using SQLite database:", config_module.settings.database_url)
    uvicorn.run(app, host="127.0.0.1", port=8001, reload=True)