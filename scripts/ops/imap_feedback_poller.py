#!/usr/bin/env python3
"""
Gmail IMAP poller for feedback ingestion.

Run as a cron job or systemd timer:
    */5 * * * * /path/to/venv/bin/python /path/to/tools/imap_feedback_poller.py

Environment variables required:
    IMAP_HOST=imap.gmail.com
    IMAP_USER=your-email@gmail.com
    IMAP_PASS=your-app-password
    IMAP_FOLDER=INBOX
    INGEST_URL=http://localhost:8001/feedback/ingest
    INGEST_SECRET=optional-shared-secret  # if you add auth to the endpoint
    PROCESSED_LABEL=Processed/Feedback    # Gmail label to mark processed mails
"""
import base64
import email
import imaplib
import os
import re
import sys
import time
from datetime import datetime
from email.header import decode_header
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend" / "backend"))

import requests
from core.config import settings


def get_env(key: str, default: str = "") -> str:
    val = os.environ.get(key, default)
    if not val and key not in ("INGEST_SECRET",):
        print(f"Missing required env: {key}", file=sys.stderr)
        sys.exit(1)
    return val


IMAP_HOST = get_env("IMAP_HOST", "imap.gmail.com")
IMAP_USER = get_env("IMAP_USER")
IMAP_PASS = get_env("IMAP_PASS")
IMAP_FOLDER = get_env("IMAP_FOLDER", "INBOX")
INGEST_URL = get_env("INGEST_URL", "http://localhost:8001/feedback/ingest")
INGEST_SECRET = get_env("INGEST_SECRET", "")
PROCESSED_LABEL = get_env("PROCESSED_LABEL", "Processed/Feedback")

# Only process emails from allowed domain
ALLOWED_DOMAIN = settings.allowed_email_domain.lower()


def decode_mime_header(header: str) -> str:
    """Decode MIME-encoded header."""
    if not header:
        return ""
    parts = decode_header(header)
    decoded = []
    for part, enc in parts:
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def extract_body(msg: email.message.EmailMessage) -> tuple[str, str]:
    """Extract text and html bodies."""
    text_body = ""
    html_body = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition", ""))
            if "attachment" in disp:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                content = payload.decode(charset, errors="replace")
            except Exception:
                content = payload.decode("utf-8", errors="replace")
            if ctype == "text/plain" and not text_body:
                text_body = content
            elif ctype == "text/html" and not html_body:
                html_body = content
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            content = payload.decode(charset, errors="replace")
            ctype = msg.get_content_type()
            if ctype == "text/html":
                html_body = content
            else:
                text_body = content
    return text_body, html_body


def extract_attachments(msg: email.message.EmailMessage) -> list[dict]:
    """Extract attachments as base64-encoded dicts."""
    attachments = []
    for part in msg.walk():
        disp = str(part.get("Content-Disposition", ""))
        if "attachment" not in disp:
            continue
        filename = part.get_filename()
        if not filename:
            continue
        filename = decode_mime_header(filename)
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        ctype = part.get_content_type()
        attachments.append({
            "filename": filename,
            "content": base64.b64encode(payload).decode("ascii"),
            "content_type": ctype,
        })
    return attachments


def get_or_create_label(imap: imaplib.IMAP4_SSL, label: str) -> str:
    """Get or create a Gmail label, return the label name."""
    # List existing labels
    typ, data = imap.list()
    if typ == "OK":
        for line in data:
            if label.encode() in line:
                return label
    # Create label
    typ, data = imap.create(label)
    if typ == "OK":
        print(f"Created label: {label}")
        return label
    # If creation failed (maybe exists), try to use it anyway
    return label


def apply_label(imap: imaplib.IMAP4_SSL, msg_num: bytes, label: str) -> None:
    """Apply label to message."""
    imap.store(msg_num, "+X-GM-LABELS", f'(\"{label}\")')


def mark_seen(imap: imaplib.IMAP4_SSL, msg_num: bytes) -> None:
    """Mark message as read."""
    imap.store(msg_num, "+FLAGS", "\\Seen")


def process_mailbox(imap: imaplib.IMAP4_SSL) -> int:
    """Process unread messages in the selected folder."""
    processed = 0
    label = get_or_create_label(imap, PROCESSED_LABEL)

    # Search for unread messages
    typ, data = imap.search(None, "UNSEEN")
    if typ != "OK" or not data[0]:
        return 0

    msg_nums = data[0].split()
    print(f"Found {len(msg_nums)} unread message(s)")

    for num in msg_nums:
        # Fetch full message
        typ, msg_data = imap.fetch(num, "(RFC822)")
        if typ != "OK":
            print(f"Failed to fetch message {num}")
            continue

        raw = msg_data[0][1]
        msg = email.message_from_bytes(raw)

        # Decode headers
        from_header = decode_mime_header(msg.get("From", ""))
        subject = decode_mime_header(msg.get("Subject", ""))
        date_header = msg.get("Date", "")

        # Extract email address from From header
        from_match = re.search(r"<(.+?)>", from_header)
        from_email = from_match.group(1) if from_match else from_header.strip()
        from_email = from_email.lower()

        # Extract name
        name_match = re.search(r"^(.+?)\s*<", from_header)
        from_name = name_match.group(1).strip().strip('"') if name_match else from_email.split("@")[0]

        # Domain check
        if ALLOWED_DOMAIN and not from_email.endswith(ALLOWED_DOMAIN):
            print(f"Skipping {from_email} (not {ALLOWED_DOMAIN})")
            apply_label(imap, num, label)
            mark_seen(imap, num)
            continue

        # Extract body and attachments
        text_body, html_body = extract_body(msg)
        attachments = extract_attachments(msg)

        if not text_body and not html_body:
            print(f"Skipping {from_email} - empty body")
            apply_label(imap, num, label)
            mark_seen(imap, num)
            continue

        # Send to ingest endpoint
        payload = {
            "from_email": from_email,
            "from_name": from_name,
            "subject": subject,
            "text": text_body,
            "html": html_body,
            "attachments": attachments,
        }
        headers = {"Content-Type": "application/json"}
        if INGEST_SECRET:
            headers["Authorization"] = f"Bearer {INGEST_SECRET}"

        try:
            resp = requests.post(INGEST_URL, json=payload, headers=headers, timeout=30)
            if resp.status_code in (200, 201):
                print(f"✓ Ingested feedback from {from_email}: {subject[:60]}")
                processed += 1
            else:
                print(f"✗ Ingest failed ({resp.status_code}): {resp.text}")
                continue
        except Exception as e:
            print(f"✗ Ingest error: {e}")
            continue

        # Mark as processed
        apply_label(imap, num, label)
        mark_seen(imap, num)

    return processed


def main() -> int:
    print(f"[{datetime.now()}] Starting IMAP poller for {IMAP_USER}")

    try:
        imap = imaplib.IMAP4_SSL(IMAP_HOST)
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select(IMAP_FOLDER)

        count = process_mailbox(imap)

        imap.close()
        imap.logout()

        print(f"[{datetime.now()}] Processed {count} message(s)")
        return 0

    except imaplib.IMAP4.error as e:
        print(f"IMAP error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())