"""
Shared pytest configuration.

The app reads its database URL from the environment at import time, so this must
be set before any test module imports `database`/`config`. A single scratch file
is used for the whole session; individual modules must not override it.
"""
import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / "campuspilot_pytest.db"

if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"

# Keep email sending out of the tests; no test should touch SMTP.
os.environ.setdefault("SMTP_USER", "")
os.environ.setdefault("SMTP_PASSWORD", "")