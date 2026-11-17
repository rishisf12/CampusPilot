"""Seed GreenMail with demo mailboxes via its REST API.

Usage:
    python scripts/seed_greenmail.py

Requires GREENMAIL_API_URL env (default http://localhost:8080).
Creates: alice@localhost, bob@localhost (password: secret123)
"""
import os
import sys
import httpx

API_URL = os.getenv("GREENMAIL_API_URL", "http://localhost:8080")


def seed() -> None:
    mailboxes = [
        {"address": "alice@localhost", "password": "secret123"},
        {"address": "bob@localhost", "password": "secret123"},
    ]
    for mb in mailboxes:
        try:
            resp = httpx.post(
                f"{API_URL}/api/v2/domains/localhost/accounts",
                json=mb,
                timeout=10,
            )
            if resp.status_code in (200, 201, 409):
                print(f"[seed] {mb['address']} -> {resp.status_code}")
            else:
                print(f"[seed] {mb['address']} -> {resp.status_code} {resp.text}")
        except httpx.ConnectError:
            print(f"[seed] Cannot reach GreenMail at {API_URL}. Is it running?")
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            print(f"[seed] {mb['address']} error: {exc}")


if __name__ == "__main__":
    seed()
