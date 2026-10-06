"""
Prove, against the running backend, whether two students share attendance.

Multi-user safety is not a code-reading exercise: the only convincing answer is
two signed-in students hitting the real API. This creates a second account on the
same branch and semester - so both share every course - then checks three things:

  1. can one student see the other's marks?
  2. can one student's mark overwrite the other's?
  3. can one student delete the other's record?

Writes real rows, and removes them again at the end.

Usage:  python tools/audit_two_students.py
"""
import sqlite3
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
DB = REPO / "database" / "classpilot.db"
BASE = "http://127.0.0.1:8001"

PASSWORD = "Test@12345"

#: Two accounts created by this script, so it does not depend on knowing the
#: password of whatever account happens to be in the database.
STUDENTS = [
    {"alias": "audit_student1", "roll": "23BCS776"},
    {"alias": "audit_student2", "roll": "23BCS777"},
]


def signup_payload(alias: str, roll: str) -> dict:
    return {
        "first_name": "Audit",
        "last_name": "Student",
        "gender": "Other",
        "programme": "BTech",
        "semester": 5,
        # The same branch on purpose: both students then share every course,
        # which is the condition under which a shared-record bug shows up.
        "branch": "CSE A",
        "username": alias,
        "roll_number": roll,
        "email": f"{alias}@iiitdmj.ac.in",
        "password": PASSWORD,
    }


def read_code(email: str) -> str:
    """Recover the signup code from the local dev database.

    Only possible because this is a database the developer owns; in a real
    deployment the code is in the student's inbox.
    """
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT code_hash FROM pending_signup WHERE email = ?", (email.lower(),)
    ).fetchone()
    conn.close()
    if not row:
        raise SystemExit("no pending signup - did step 1 run?")
    for number in range(1000000):
        candidate = f"{number:06d}"
        import hashlib

        if hashlib.sha256(f"{email.lower()}:{candidate}".encode()).hexdigest() == row[0]:
            return candidate
    raise SystemExit("code not found")


def signup(alias: str, roll: str) -> str:
    """Run the real three-step signup, returning a bearer token."""
    email = f"{alias}@iiitdmj.ac.in"
    requests.post(BASE + "/auth/signup/start", json={"email": email})
    code = read_code(email)
    verified = requests.post(BASE + "/auth/signup/verify", json={"email": email, "code": code})
    if verified.status_code != 200:
        raise SystemExit(f"{alias}: verify failed: {verified.status_code} {verified.text[:200]}")
    created = requests.post(BASE + "/auth/signup", json=signup_payload(alias, roll))
    if created.status_code != 200:
        raise SystemExit(f"{alias}: signup failed: {created.status_code} {created.text[:200]}")
    return requests.post(
        BASE + "/auth/login", data={"username": alias, "password": PASSWORD}
    ).json()["access_token"]


def main() -> int:
    aliases = [item["alias"] for item in STUDENTS]
    tokens = [signup(item["alias"], item["roll"]) for item in STUDENTS]
    headers = [{"Authorization": f"Bearer {t}"} for t in tokens]
    print(f"student A: {aliases[0]}")
    print(f"student B: {aliases[1]}  (same branch and semester, so shared courses)")

    subjects = requests.get(BASE + "/attendance/subjects", headers=headers[1]).json()
    subject = subjects["subjects"][0]
    shared = subject["course_code"]
    course_id = subject["course_id"]
    print(f"a course both students sit: {shared} (id={course_id})")

    date = "2026-10-05"

    # --- 1. Can B see A's marks? -----------------------------------------
    requests.post(
        BASE + "/attendance/",
        headers=headers[0],
        json={"course_id": course_id, "date": date, "status": "Present"},
    )
    a_records = requests.get(
        BASE + f"/attendance/records?course_id={course_id}", headers=headers[0]
    ).json()
    b_records = requests.get(
        BASE + f"/attendance/records?course_id={course_id}", headers=headers[1]
    ).json()
    leak = b_records == a_records and len(a_records) > 0
    print(f"\n1. A's records : {a_records}")
    print(f"   B's records : {b_records}")
    print(f"   -> B sees A's marks: {'YES - LEAK' if leak else 'no'}")

    # --- 2. Can B overwrite A? --------------------------------------------
    requests.post(
        BASE + "/attendance/",
        headers=headers[1],
        json={"course_id": course_id, "date": date, "status": "Absent"},
    )
    after = requests.get(
        BASE + f"/attendance/records?course_id={course_id}", headers=headers[0]
    ).json()
    a_status = after[0]["status"] if after else "(none)"
    collision = len(after) == 1 and a_status == "Absent"
    print(f"\n2. A marked Present, B marked Absent, same course and date")
    print(f"   A now sees: {a_status}")
    print(f"   -> B overwrote A: {'YES - BUG' if collision else 'no'}")

    # --- 3. Can B delete A's record? --------------------------------------
    record_id = after[0]["id"] if after else None
    if record_id:
        deleted = requests.delete(
            BASE + f"/attendance/{record_id}", headers=headers[1]
        )
        gone = requests.get(
            BASE + f"/attendance/records?course_id={course_id}", headers=headers[0]
        ).json()
        print(f"\n3. B deleted A's record id={record_id} -> HTTP {deleted.status_code}")
        print(f"   A's records now: {gone}")
        print(f"   -> B can delete A's data: {'YES - BUG' if not gone else 'no'}")

    # --- clean up ---------------------------------------------------------
    conn = sqlite3.connect(DB)
    conn.execute("DELETE FROM attendance_record")
    conn.execute("DELETE FROM pending_signup")
    for alias in aliases:
        row = conn.execute("SELECT id FROM user WHERE username = ?", (alias,)).fetchone()
        if row:
            conn.execute("DELETE FROM user_profile WHERE user_id = ?", (row[0],))
            conn.execute("DELETE FROM user WHERE id = ?", (row[0],))
    conn.commit()
    conn.close()
    print(f"\ncleaned up: removed {', '.join(aliases)} and every attendance row")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
