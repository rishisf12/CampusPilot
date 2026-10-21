#!/usr/bin/env python3
"""
IMAP poller for the mail app ingestion.

For every programme group configured in MAIL_MAILBOXES_JSON this connects to
the group's mailbox, reads the unread messages and posts each one to
/mail/ingest with the group's secret. The set of receiving mail ids lives in
the same JSON block, and the backend files a message under the section whose
address it was sent to.

Run as a cron job or systemd timer:
    */5 * * * * /path/to/venv/bin/python /path/to/scripts/ops/imap_mail_poller.py

Environment variables:
    MAIL_INGEST_URL=http://127.0.0.1:8000/mail/ingest
    MAIL_PROCESSED_LABEL=Processed/Mail    # Gmail label to mark processed mail
    MAIL_FROM_DOMAIN=@college.ac.in        # optional sender filter
"""
import email
import email.utils
import imaplib
import os
import re
import sys
from datetime import datetime
from email.header import decode_header
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "backend" / "app"))

import requests  # noqa: E402
from core.config import settings  # noqa: E402

INGEST_URL = os.environ.get("MAIL_INGEST_URL", "http://127.0.0.1:8000/mail/ingest")
PROCESSED_LABEL = os.environ.get("MAIL_PROCESSED_LABEL", "Processed/Mail")
FROM_DOMAIN = os.environ.get("MAIL_FROM_DOMAIN", "").lower()

#: The headers a forwarded or aliased address can arrive in, in order of
#: preference. "To" is last because it may hold every recipient.
RECEIVED_HEADERS = ("Delivered-To", "X-Original-To", "X-Envelope-To", "To")


def receiving_addresses(msg: email.message.Message) -> list[str]:
    """Every address the message was sent to, most specific header first."""
    found: list[str] = []
    for header in RECEIVED_HEADERS:
        value = msg.get(header)
        if not value:
            continue
        for _display, address in email.utils.getaddresses([value]):
            address = address.strip().lower()
            if address and address not in found:
                found.append(address)
    return found


def decode_mime_header(header: str) -> str:
    """Decode a MIME-encoded header."""
    if not header:
        return ""
    decoded = []
    for part, enc in decode_header(header):
        if isinstance(part, bytes):
            decoded.append(part.decode(enc or "utf-8", errors="replace"))
        else:
            decoded.append(part)
    return "".join(decoded)


def extract_body(msg: email.message.Message) -> tuple[str, str]:
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
            if msg.get_content_type() == "text/html":
                html_body = content
            else:
                text_body = content
    return text_body, html_body


def describe_attachments(msg: email.message.Message) -> list[dict]:
    """Attachment metadata; the mail app does not carry the bytes."""
    attachments = []
    for part in msg.walk():
        disp = str(part.get("Content-Disposition", ""))
        if "attachment" not in disp:
            continue
        filename = part.get_filename()
        if not filename:
            continue
        payload = part.get_payload(decode=True)
        attachments.append(
            {
                "filename": decode_mime_header(filename),
                "content_type": part.get_content_type(),
                "size": len(payload) if payload else None,
            }
        )
    return attachments


def section_address(group: str, msg: email.message.Message) -> str | None:
    """The recipient address that names one of the group's sections.

    The message was sent to the group mailbox, but possibly alongside
    others. The address that matches a configured section address goes to
    the backend as ``to``; when none does, the first address stands in and
    the backend's keyword classification decides.
    """
    addresses = receiving_addresses(msg)
    for address in addresses:
        if settings.mail_section_for_address(group, address):
            return address
    return addresses[0] if addresses else None


def get_or_create_label(imap: imaplib.IMAP4, label: str) -> str:
    """Return the Gmail label, creating it when missing."""
    typ, data = imap.list()
    if typ == "OK" and data:
        for line in data:
            if isinstance(line, bytes) and label.encode() in line:
                return label
    typ, _data = imap.create(label)
    if typ == "OK":
        print(f"Created label: {label}")
    return label


def apply_label(imap: imaplib.IMAP4, num: bytes, label: str) -> None:
    """Apply a Gmail label to one message."""
    try:
        imap.store(num, "+X-GM-LABELS", f'("{label}")')
    except imaplib.IMAP4.error:
        # Not Gmail: the seen flag below is what matters.
        pass


def mark_seen(imap: imaplib.IMAP4, num: bytes) -> None:
    """Mark one message as read."""
    imap.store(num, "+FLAGS", "\\Seen")


def ingest(group: str, secret: str, payload: dict) -> bool:
    """Post one message to /mail/ingest. True when the API accepted it."""
    try:
        resp = requests.post(
            INGEST_URL,
            json=payload,
            headers={"Authorization": f"Bearer {secret}"},
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return True
        print(f"  x ingest failed ({resp.status_code}): {resp.text[:200]}")
    except Exception as exc:  # noqa: BLE001 - a network error must not stop the run
        print(f"  x ingest error: {exc}")
    print(f"  (group '{group}', message filed nowhere)")
    return False


def process_group(group: str, cfg: dict) -> int:
    """Read one group's mailbox. Returns how many messages were ingested."""
    name = cfg.get("imap_user") or "<unset>"
    if not settings.mail_group_enabled(group):
        return 0
    secret = settings.mail_group_secret(group)
    if not secret:
        print(f"[{group}] no ingest secret for {name}: skipping")
        return 0

    host = cfg.get("imap_host") or "imap.gmail.com"
    port = int(cfg.get("imap_port") or 993)
    folder = cfg.get("mailbox") or "INBOX"
    processed_label = f"{PROCESSED_LABEL}/{group}"

    print(f"[{group}] polling {name} at {host}:{port} ({folder})")
    try:
        imap = imaplib.IMAP4_SSL(host, port)
        imap.login(name, cfg.get("imap_password") or "")
        imap.select(folder)
    except Exception as exc:  # noqa: BLE001
        print(f"  x could not connect: {exc}")
        return 0

    ingested = 0
    try:
        label = get_or_create_label(imap, processed_label)
        typ, data = imap.search(None, "UNSEEN")
        nums = data[0].split() if typ == "OK" and data and data[0] else []
        print(f"  {len(nums)} unread message(s)")

        for num in nums:
            typ, msg_data = imap.fetch(num, "(RFC822)")
            if typ != "OK" or not msg_data or msg_data[0] is None:
                continue
            msg = email.message_from_bytes(msg_data[0][1])

            from_header = decode_mime_header(msg.get("From", ""))
            match = re.search(r"<(.+?)>", from_header)
            from_email = (match.group(1) if match else from_header).strip().lower()
            name_match = re.search(r"^(.+?)\s*<", from_header)
            from_name = (
                name_match.group(1).strip().strip('"')
                if name_match
                else from_email.split("@")[0]
            )
            subject = decode_mime_header(msg.get("Subject", ""))
            date_hdr = msg.get("Date", "")
            try:
                received = email.utils.parsedate_to_datetime(date_hdr)
            except (TypeError, ValueError):
                received = None

            if FROM_DOMAIN and not from_email.endswith(FROM_DOMAIN):
                print(f"  skip {from_email} (not {FROM_DOMAIN})")
                apply_label(imap, num, label)
                mark_seen(imap, num)
                continue

            text_body, _html_body = extract_body(msg)
            payload = {
                "from_email": from_email,
                "from_name": from_name,
                "to": section_address(group, msg),
                "subject": subject,
                "text": text_body,
                "html": None,
                "date": received.isoformat() if received else None,
                "attachments": describe_attachments(msg),
                "labels": [processed_label],
            }
            if ingest(group, secret, payload):
                print(f"  + {subject[:60]}")
                ingested += 1
                apply_label(imap, num, label)
                mark_seen(imap, num)
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:  # noqa: BLE001
            pass

    return ingested


def main() -> int:
    print(f"[{datetime.now().isoformat()}] mail poller: {INGEST_URL}")
    total = 0
    for group in ("ug", "pg"):
        try:
            total += process_group(group, settings.mail_group_cfg(group))
        except Exception as exc:  # noqa: BLE001 - one group's failure must not stop the other
            print(f"[{group}] error: {exc}")
    print(f"[{datetime.now().isoformat()}] ingested {total} message(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
