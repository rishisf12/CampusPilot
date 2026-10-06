"""Upload the real class timetable PDF through the API and report what stuck.

This is the end-to-end check: it goes through the same route the browser uses,
so it proves the parser, the storage and the profile filter all agree.
"""
import sys
from collections import Counter
from pathlib import Path

import requests

BASE = "http://127.0.0.1:8001"
PDF = Path(sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\Appex\Downloads\DOC-20260817-WA0002-print.PDF")


def login():
    response = requests.post(
        BASE + "/auth/login", data={"username": "testuser123", "password": "Test@12345"}
    )
    if response.status_code != 200:
        print("login failed:", response.status_code, response.text[:200])
        print("(set a known password, or pass one as the second argument)")
        raise SystemExit(1)
    return response.json()["access_token"]


def main() -> int:
    token = login()
    headers = {"Authorization": f"Bearer {token}"}

    with PDF.open("rb") as handle:
        upload = requests.post(
            BASE + "/timetable/upload",
            headers=headers,
            files={"file": (PDF.name, handle, "application/pdf")},
        )

    print("upload ->", upload.status_code)
    if upload.status_code != 200:
        print("  ", upload.text[:400])
        return 1
    body = upload.json()
    print("  slots_inserted:", body["slots_inserted"])
    print("  warnings      :", body.get("warnings", [])[:3])

    slots = requests.get(BASE + "/timetable/slots", headers=headers).json()
    print("\nstored slots:", len(slots))

    print("\nby day")
    for day, count in Counter(s["day"] for s in slots).items():
        print(f"  {day}: {count}")

    print("\nby semester")
    for sem, count in sorted(Counter(s["semester"] for s in slots).items()):
        print(f"  sem {sem}: {count}")

    with_instructor = sum(1 for s in slots if s.get("instructor"))
    with_room = sum(1 for s in slots if s["room"] not in ("TBA", "", None))
    print(f"\ninstructor parsed: {with_instructor}/{len(slots)}")
    print(f"room parsed      : {with_room}/{len(slots)}")

    # The demo profile is CSE A sem 5; show exactly what that student sees.
    profile = requests.get(BASE + "/profile/", headers=headers).json()
    print(f"\nprofile: {profile['branch']} sem {profile['semester']}")
    subjects = requests.get(BASE + "/attendance/subjects", headers=headers).json()
    codes = sorted(s["course_code"] for s in subjects.get("subjects", []))
    print(f"attendance subjects ({len(codes)}): {codes}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
