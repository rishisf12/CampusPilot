"""Upload the real exam PDFs to a running CampusPilot server."""
import datetime
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

import jwt

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "backend"))
from core.config import get_settings  # noqa: E402

BASE = os.environ.get("CAMPUSPILOT_API", "http://localhost:8002")
USERNAME = "testuser123"
REPO = Path(__file__).resolve().parents[1]
DOWNLOADS = Path.home() / "Downloads"

UPLOADS = [
    ("/exam/seating/upload", DOWNLOADS / "MID SEM Indexing 2026-27 (Odd Sem)-print.PDF"),
    ("/exam/timetable/upload", DOWNLOADS / "Mid Sem Examination Time Table _23rd Sept, 2025 - Table 1.pdf"),
]


def get_token() -> str:
    settings = get_settings()
    conn = sqlite3.connect(REPO / "database" / "classpilot.db")
    row = conn.execute("SELECT id, username FROM user WHERE username=?", (USERNAME,)).fetchone()
    conn.close()
    if not row:
        raise SystemExit(f"no user named {USERNAME}; run tools/make_demo_user.py first")
    return jwt.encode(
        {
            "sub": str(row[0]),
            "username": row[1],
            "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )


def upload(endpoint: str, path: Path, token: str) -> None:
    boundary = "----campuspilotboundary"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()
    body = header + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()

    request = urllib.request.Request(
        BASE + endpoint,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(request) as response:
            print(f"{endpoint} -> {response.status} {response.read().decode()}")
    except urllib.error.HTTPError as error:
        print(f"{endpoint} -> {error.code} {error.read().decode()[:400]}")


def main() -> int:
    token = get_token()
    for endpoint, path in UPLOADS:
        if not path.exists():
            print(f"missing {path}")
            return 1
        upload(endpoint, path, token)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())