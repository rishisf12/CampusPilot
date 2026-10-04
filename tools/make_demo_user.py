"""Create a verified demo account so the UI can be exercised end to end."""
import datetime
import sqlite3
import sys
from pathlib import Path

from passlib.hash import sha256_crypt

REPO = Path(__file__).resolve().parents[1]
db_path = REPO / "database" / "classpilot.db"

USERNAME = "testuser123"
PASSWORD = "Test@12345"
EMAIL = "demo@iiitdmj.ac.in"
ROLL = "23BCS125"

conn = sqlite3.connect(db_path)
now = datetime.datetime.utcnow().isoformat(sep=" ")
conn.execute(
    "UPDATE user SET is_email_verified=1, password_hash=?, email=?, roll_number=?, updated_at=? "
    "WHERE username=?",
    (sha256_crypt.hash(PASSWORD), EMAIL, ROLL, now, USERNAME),
)
conn.execute(
    "UPDATE user_profile SET programme='BTech', semester=5, branch='CSE A', elective_codes=? "
    "WHERE user_id=(SELECT id FROM user WHERE username=?)",
    ('["OE3E33"]', USERNAME),
)
conn.commit()

row = conn.execute(
    "SELECT id, email, username, roll_number, is_email_verified FROM user WHERE username=?",
    (USERNAME,),
).fetchone()
conn.close()

if not row:
    print("No user named 'demo'. Available:", file=sys.stderr)
    sys.exit(1)

print("user:", row)
print(f"login -> {USERNAME} / {PASSWORD}")