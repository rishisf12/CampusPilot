"""
End-to-end smoke test of the exam flow against the real downloaded PDFs.

Runs the ASGI app in-process against a throwaway SQLite file so it never touches
the development database.
"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

# Point the app at a scratch database *before* importing config.
_DB = Path(tempfile.gettempdir()) / "campuspilot_smoke.db"
if _DB.exists():
    _DB.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_DB}"

from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, select  # noqa: E402

import jwt  # noqa: E402
from config import get_settings  # noqa: E402
from database import create_db_and_tables, engine  # noqa: E402
from main import app  # noqa: E402
from models import User, UserProfile  # noqa: E402
from services.exam_parser import BRANCH_OPTIONS  # noqa: E402

settings = get_settings()
DOWNLOADS = Path.home() / "Downloads"
SEATING_PDF = DOWNLOADS / "MID SEM Indexing 2026-27 (Odd Sem)-print.PDF"
TIMETABLE_PDF = DOWNLOADS / "Mid Sem Examination Time Table _23rd Sept, 2025 - Table 1.pdf"

failures = []


def safe(text) -> str:
    """Force printable ASCII so cp1252 consoles do not blow up on PDF bytes."""
    return str(text).encode("ascii", "replace").decode("ascii")


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    if not condition:
        failures.append(label)
    print(f"  [{status}] {label}" + (f" -- {safe(detail)}" if detail else ""))


def make_user(username, roll, branch="CSE A", semester=5, programme="BTech"):
    """Create a verified user directly, bypassing the SMTP email step."""
    create_db_and_tables()
    with Session(engine) as session:
        user = User(
            email=f"{username}@iiitdmj.ac.in",
            password_hash="x",
            full_name="Test Student",
            username=username,
            roll_number=roll,
            is_email_verified=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        session.add(
            UserProfile(
                user_id=user.id,
                first_name="Test",
                last_name="Student",
                programme=programme,
                semester=semester,
                branch=branch,
            )
        )
        session.commit()
        user_id = user.id

    token = jwt.encode(
        {"sub": str(user_id), "username": username,
         "exp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
         + __import__("datetime").timedelta(days=7)},
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


def main():
    client = TestClient(app)
    headers = make_user("smokeuser", "23BCS125")

    print("\n1. Unauthenticated access is rejected")
    check("GET /exam/timetable without token -> 401",
          client.get("/exam/timetable").status_code == 401)
    check("GET /profile/ without token -> 401",
          client.get("/profile/").status_code == 401)

    print("\n2. Seating index upload")
    if not SEATING_PDF.exists():
        check("seating PDF present", False, str(SEATING_PDF))
    else:
        with SEATING_PDF.open("rb") as fh:
            res = client.post("/exam/seating/upload", headers=headers,
                              files={"file": (SEATING_PDF.name, fh, "application/pdf")})
        check("POST /exam/seating/upload -> 200", res.status_code == 200, res.text[:160])
        if res.status_code == 200:
            print(f"        {res.json()['message']}")

    print("\n3. Mid-sem timetable upload")
    if not TIMETABLE_PDF.exists():
        check("timetable PDF present", False, str(TIMETABLE_PDF))
    else:
        with TIMETABLE_PDF.open("rb") as fh:
            res = client.post("/exam/timetable/upload", headers=headers,
                              files={"file": (TIMETABLE_PDF.name, fh, "application/pdf")})
        check("POST /exam/timetable/upload -> 200", res.status_code == 200, res.text[:160])
        if res.status_code == 200:
            print(f"        {res.json()['message']}")

    print("\n4. Exam status")
    res = client.get("/exam/status", headers=headers)
    check("GET /exam/status -> 200", res.status_code == 200)
    if res.status_code == 200:
        body = res.json()
        check("seating rows present", body["seating_rows"] > 0, f"{body['seating_rows']} rows")
        check("timetable rows present", body["timetable_rows"] > 0, f"{body['timetable_rows']} rows")

    print("\n5. Day-grouped timetable")
    res = client.get("/exam/timetable", headers=headers)
    check("GET /exam/timetable -> 200", res.status_code == 200)
    if res.status_code == 200:
        body = res.json()
        check("groups by day", len(body["days"]) > 0, f"{len(body['days'])} day group(s)")
        check("filters by profile", body["total"] > 0, f"{body['total']} exams for CSE A sem 5")
        if body["days"]:
            first = body["days"][0]
            print(f"        {first['date']} ({first['day']}): {len(first['exams'])} exam(s)")
            print(f"        e.g. {first['exams'][0]}")

    print("\n6. Day-grouped seating")
    res = client.get("/exam/seating", headers=headers)
    check("GET /exam/seating -> 200", res.status_code == 200)
    if res.status_code == 200:
        check("seating grouped", len(res.json()["days"]) > 0)

    print("\n7. Roll lookup (3 rules)")
    res = client.get("/exam/lookup", headers=headers, params={"roll": "23BCS125"})
    check("GET /exam/lookup -> 200", res.status_code == 200, res.text[:160])
    if res.status_code == 200:
        body = res.json()
        check("finds exams for own roll", len(body["exams"]) > 0, f"{len(body['exams'])} exams")
        check("rules reported", bool(body["rules_used"]), str(body["rules_used"]))
        if body["exams"]:
            for exam in body["exams"][:4]:
                print(f"        {exam['date']} {exam['start_time']}-{exam['end_time']} "
                      f"{exam['course_code']} @ {exam['room']} (rule {exam['rule']})")
            check("every exam has a room", all(e["room"] for e in body["exams"]))

    print("\n8. Quick lookup (date/room/course only)")
    res = client.get("/exam/quick-lookup", headers=headers, params={"roll": "23BCS125"})
    check("GET /exam/quick-lookup -> 200", res.status_code == 200)
    if res.status_code == 200:
        exams = res.json()["exams"]
        check("returns only 3 fields",
              exams and set(exams[0]) == {"date", "day", "room", "course_code"},
              str(sorted(exams[0])) if exams else "no rows")

    print("\n9. Exam PDF")
    res = client.get("/exam/pdf", headers=headers, params={"roll": "23BCS125"})
    check("GET /exam/pdf -> 200", res.status_code == 200, res.text[:120])
    check("is a PDF", res.content[:4] == b"%PDF", f"{len(res.content)} bytes")

    print("\n10. Profile + branch change")
    res = client.get("/profile/", headers=headers)
    check("GET /profile/ -> 200", res.status_code == 200)
    res = client.get("/profile/options", headers=headers)
    check("GET /profile/options -> 200", res.status_code == 200)
    if res.status_code == 200:
        check("branch options exact", res.json()["branches"] == BRANCH_OPTIONS,
              str(res.json()["branches"]))

    res = client.post("/profile/branch-change", headers=headers,
                      json={"to_branch": "ECE", "reason": "interest in VLSI"})
    check("POST /profile/branch-change -> 200", res.status_code == 200, res.text[:160])
    if res.status_code == 200:
        body = res.json()
        check("records original_branch", body["original_branch"] == "CSE A", str(body))
        check("records requested_branch", body["requested_branch"] == "ECE")

    res = client.get("/profile/", headers=headers)
    check("request persisted", res.json()["branch_change_requested"] is True)
    check("requested branch persisted", res.json()["requested_branch"] == "ECE")

    res = client.delete("/profile/branch-change", headers=headers)
    check("DELETE /profile/branch-change -> 200", res.status_code == 200)
    if res.status_code == 200:
        check("clears requested_branch", res.json()["requested_branch"] is None)
        check("keeps original_branch", res.json()["original_branch"] == "CSE A")

    res = client.post("/profile/branch-change", headers=headers, json={"to_branch": "NOPE"})
    check("rejects unknown branch -> 400", res.status_code == 400)

    res = client.post("/profile/branch-change", headers=headers,
                      json={"from_branch": "CSE A", "to_branch": "CSE A"})
    check("rejects same source/target -> 400", res.status_code == 400)

    print("\n11. Attendance")
    res = client.get("/attendance/subjects", headers=headers)
    check("GET /attendance/subjects -> 200", res.status_code == 200, res.text[:160])
    if res.status_code == 200:
        print(f"        {res.json()['count']} subject(s) for CSE A sem 5")
    res = client.get("/attendance/summary", headers=headers)
    check("GET /attendance/summary -> 200", res.status_code == 200)
    check("summary reports a percentage", "overall_percentage" in res.json())

    print("\n12. Rooms + timetable options")
    res = client.get("/rooms/vacant", headers=headers, params={"mode": "live"})
    check("GET /rooms/vacant -> 200 (no timetable loaded)", res.status_code == 200, res.text[:160])
    if res.status_code == 200:
        check("reports has_timetable flag", "has_timetable" in res.json())
    res = client.get("/rooms/vacant", headers=headers,
                     params={"mode": "manual", "day": "Mon", "hour": "10:30"})
    check("GET /rooms/vacant manual -> 200", res.status_code == 200, res.text[:160])
    res = client.get("/rooms/all", headers=headers)
    check("GET /rooms/all -> 200", res.status_code == 200)

    res = client.get("/timetable/options", headers=headers)
    check("GET /timetable/options -> 200", res.status_code == 200, res.text[:160])

    print("\n13. Invalid roll rejected")
    check("GET /exam/lookup?roll=nonsense -> 400",
          client.get("/exam/lookup", headers=headers, params={"roll": "nonsense"}).status_code == 400)

    print("\n" + "=" * 60)
    if failures:
        print(f"FAILED ({len(failures)}):")
        for item in failures:
            print("  -", item)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())