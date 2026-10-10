"""Add subject column to feedback table (run once after deploy)."""
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"


def main() -> int:
    if not DB.is_file():
        print(f"no database at {DB}")
        return 1

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # Check if column exists
    cur.execute("PRAGMA table_info(feedback)")
    cols = [row[1] for row in cur.fetchall()]

    if "subject" in cols:
        print("subject column already exists")
        return 0

    print("Adding subject column to feedback table...")
    cur.execute("ALTER TABLE feedback ADD COLUMN subject TEXT")
    conn.commit()
    conn.close()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())