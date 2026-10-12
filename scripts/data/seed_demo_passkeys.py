"""
Enrol a couple of throwaway passkeys so the manage screen has something to show.

Uses a software authenticator, so no real device is involved and the rows can be
removed again afterwards. Run without `--keep` to clean up at the end.

Usage:  python tools/seed_demo_passkeys.py [--keep]
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend" / "tests"))

from test_passkeys import SoftwareAuthenticator  # noqa: E402

BASE = "http://127.0.0.1:8001"
USERNAME = "testuser123"
PASSWORD = "Test@12345"

LABELS = [
    "Windows Hello",
    "Pixel 9",
]


def main() -> int:
    token = requests.post(
        BASE + "/auth/login", data={"username": USERNAME, "password": PASSWORD}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Clear anything already there so the labels below are the only rows.
    existing = requests.get(BASE + "/auth/passkeys", headers=headers).json()
    for item in existing["passkeys"]:
        requests.delete(
            f"{BASE}/auth/passkeys/{item['credential_id']}", headers=headers
        )
    print(f"cleared {existing['count']} existing passkey(s)")

    for label in LABELS:
        authenticator = SoftwareAuthenticator()
        options = requests.post(
            BASE + "/auth/passkeys/register/options", headers=headers, json={}
        ).json()
        response = requests.post(
            BASE + "/auth/passkeys/register",
            headers=headers,
            json={
                "credential": authenticator.create(options["_challenge"]),
                "challenge": options["_challenge"],
                "label": label,
            },
        )
        print(f"  {label}: {response.status_code}")

        # Sign in once with each, so "last used" is not "never".
        signin = requests.post(
            BASE + "/auth/passkeys/login/options", json={"username": USERNAME}
        ).json()
        attempt = requests.post(
            BASE + "/auth/passkeys/login",
            json={
                "credential": authenticator.get(signin["_challenge"]),
                "challenge": signin["_challenge"],
            },
        )
        if attempt.status_code != 200:
            print(f"    sign-in check failed: {attempt.status_code} {attempt.text[:120]}")

    final = requests.get(BASE + "/auth/passkeys", headers=headers).json()
    print(f"\nnow enrolled: {final['count']}")
    for item in final["passkeys"]:
        print(f"  {item['label']:<16} {item['credential_id']}")

    if "--keep" not in sys.argv:
        for item in final["passkeys"]:
            requests.delete(
                f"{BASE}/auth/passkeys/{item['credential_id']}", headers=headers
            )
        print("\ncleaned up - pass through --keep to leave them in place")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
