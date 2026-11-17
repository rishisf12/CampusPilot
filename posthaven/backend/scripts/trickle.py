"""Live mail trickle: periodically sends demo mails between alice@localhost and bob@localhost via GreenMail SMTP.

Usage:
    GREENMAIL_API_URL=http://localhost:8080 python scripts/trickle.py

Sends one mail every ~15 seconds to demonstrate real-time delivery.
"""
import os
import time
import smtplib
from email.message import EmailMessage

API_URL = os.getenv("GREENMAIL_API_URL", "http://localhost:8080")
SMTP_HOST = os.getenv("GREENMAIL_SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("GREENMAIL_SMTP_PORT", "3025"))
INTERVAL = int(os.getenv("TRICKLE_INTERVAL", "15"))

from_addr = "alice@localhost"
to_addr = "bob@localhost"

subjects = [
    "Project update",
    "Design review",
    "Meeting notes",
    "Invoice #1001",
    "Welcome to PostHaven",
    "Quick question",
]

bodies = [
    "Here are the latest designs for your review.",
    "Don't forget about tomorrow's meeting at 10am.",
    "Please review the attached invoice when you get a chance.",
    "Thanks for joining PostHaven! Your account is ready.",
    "Do you have a quick moment to chat?",
]


def send_one(index: int) -> None:
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subjects[index % len(subjects)]
    msg.set_content(bodies[index % len(bodies)])
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
        smtp.send_message(msg)
    print(f"[trickle] sent: {msg['Subject']}")


def main() -> None:
    print(f"[trickle] sending to {to_addr} every {INTERVAL}s via {SMTP_HOST}:{SMTP_PORT}")
    index = 0
    while True:
        try:
            send_one(index)
        except Exception as exc:  # noqa: BLE001
            print(f"[trickle] error: {exc}")
        index += 1
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
