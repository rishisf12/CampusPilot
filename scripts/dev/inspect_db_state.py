"""Inspect the app database: users, timetable rows, and which file the app is using."""
import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "database" / "classpilot.db"

conn = sqlite3.connect(DB)
print("database file:", DB)
print("size          :", DB.stat().st_size, "bytes")

print("\nusers")
for row in conn.execute(
    "SELECT id, username, email, roll_number, is_email_verified FROM user"
):
    print("  ", row)

print("\nrow counts")
for table in ("timetable_slot", "course", "exam_seating", "mid_sem_schedule", "timetable_upload", "exam_upload"):
    try:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except sqlite3.Error as exc:
        count = f"({exc})"
    print(f"  {table:<20} {count}")

print("\ntables present")
names = sorted(r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'"))
print("  " + ", ".join(names))
