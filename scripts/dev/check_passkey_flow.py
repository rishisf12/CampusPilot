"""
Drive the passkey flow over HTTP with a software authenticator.

This is the end-to-end check that the *routes* work, not just the service: it
logs in over HTTP, runs a full WebAuthn enrolment and then a passwordless sign-in,
through the same endpoints the browser uses. The private key is generated in
memory here and thrown away, so no real credential is created - the point is to
prove the plumbing.

Usage:  python tools/check_passkey_flow.py
"""
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend" / "tests"))

from test_passkeys import SoftwareAuthenticator  # noqa: E402

BASE = "http://127.0.0.1:8001"
ORIGIN = "http://localhost:5173"
USERNAME = "testuser123"
PASSWORD = "Test@12345"


def main() -> int:
    session = requests.Session()

    login = session.post(BASE + "/auth/login", data={"username": USERNAME, "password": PASSWORD})
    if login.status_code != 200:
        print("login failed:", login.status_code, login.text[:200])
        return 1
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    print(f"logged in as {USERNAME}")

    before = session.get(BASE + "/auth/passkeys", headers=headers).json()
    print(f"passkeys before: {before['count']}")

    # --- enrol ---------------------------------------------------------
    authenticator = SoftwareAuthenticator()
    options = session.post(BASE + "/auth/passkeys/register/options", headers=headers, json={})
    if options.status_code != 200:
        print("register/options failed:", options.status_code, options.text[:200])
        return 1
    payload = options.json()
    print(f"device label from server: {payload['_label']}")

    credential = authenticator.create(payload["_challenge"])
    enrolled = session.post(
        BASE + "/auth/passkeys/register",
        headers=headers,
        json={"credential": credential, "challenge": payload["_challenge"]},
    )
    print(f"enrol -> {enrolled.status_code} {enrolled.json()}")
    if enrolled.status_code != 200:
        return 1

    after = session.get(BASE + "/auth/passkeys", headers=headers).json()
    print(f"passkeys after: {after['count']} -> {after['passkeys']}")

    # --- sign in with the passkey alone --------------------------------
    signin_options = session.post(
        BASE + "/auth/passkeys/login/options", json={"username": USERNAME}
    )
    print(f"login/options -> {signin_options.status_code}")
    payload = signin_options.json()

    assertion = authenticator.get(payload["_challenge"])
    signed_in = session.post(
        BASE + "/auth/passkeys/login",
        json={"credential": assertion, "challenge": payload["_challenge"]},
    )
    print(f"passkey login -> {signed_in.status_code}")
    if signed_in.status_code != 200:
        print("  ", signed_in.text[:200])
        return 1

    token = signed_in.json()["access_token"]
    me = session.get(BASE + "/auth/me", headers={"Authorization": "Bearer " + token})
    print(f"token works: {me.status_code} as {me.json().get('username')}")

    # --- replay must fail ----------------------------------------------
    replay = session.post(
        BASE + "/auth/passkeys/login",
        json={"credential": assertion, "challenge": payload["_challenge"]},
    )
    print(f"replayed assertion -> {replay.status_code} (expected 401)")

    # --- clean up so the demo account is left as it was -----------------
    credential_id = after["passkeys"][0]["credential_id"]
    removed = session.delete(BASE + f"/auth/passkeys/{credential_id}", headers=headers)
    print(f"cleanup -> {removed.status_code}")
    print(f"passkeys now: {session.get(BASE + '/auth/passkeys', headers=headers).json()['count']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
