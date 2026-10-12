"""Check that a brand new account can actually be registered.

Signing up is what the reset was for, so this exercises the real endpoint rather
than just counting rows. It signs up, confirms the duplicate is now correctly
rejected, then removes the account again so the database is left as it was found.

Usage:  python tools/check_signup_works.py [username]
"""
import sys
from pathlib import Path

import requests

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

BASE = "http://127.0.0.1:8001"
USERNAME = sys.argv[1] if len(sys.argv) > 1 else "fresh_signup_check"
EMAIL = f"{USERNAME}@iiitdmj.ac.in"
PASSWORD = "Test@12345"

SIGNUP = {
    "first_name": "Fresh",
    "last_name": "Signup",
    "gender": "Other",
    "programme": "BTech",
    "semester": 5,
    "branch": "CSE A",
    "username": USERNAME,
    "roll_number": "23BCS900",
    "email": EMAIL,
    "password": PASSWORD,
}


def main() -> int:
    response = requests.post(f"{BASE}/auth/signup", json=SIGNUP)
    print(f"signup        -> {response.status_code}")
    if response.status_code not in (200, 201):
        print(f"  {response.text[:200]}")
        return 1
    print(f"  {response.json().get('message', 'ok')}")

    # The duplicate check must still work, or the reset just disabled uniqueness.
    again = requests.post(f"{BASE}/auth/signup", json=SIGNUP)
    print(f"duplicate     -> {again.status_code} (want 400)")
    if again.status_code != 400:
        print("  uniqueness is not being enforced - that is a problem")
        return 1

    # An unverified account must be refused at login, not silently accepted.
    login = requests.post(
        f"{BASE}/auth/login", data={"username": USERNAME, "password": PASSWORD}
    )
    print(f"unverified login -> {login.status_code} (want 403)")

    # Leave nothing behind.
    from core.database import get_session  # noqa: E402
    from sqlmodel import delete, select  # noqa: E402

    from models import User, UserProfile  # noqa: E402

    session = next(get_session())
    user = session.exec(select(User).where(User.username == USERNAME)).first()
    if user is not None:
        session.exec(delete(UserProfile).where(UserProfile.user_id == user.id))
        session.exec(delete(User).where(User.id == user.id))
        session.commit()
        print(f"\nremoved {USERNAME} again - database left as found")
    else:
        print(f"\ncould not find {USERNAME} to clean up")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
