"""MIME parser: parse RFC822 email bytes into structured fields."""
from email import policy
from email.parser import BytesParser
from email.message import EmailMessage
from email.header import decode_header, make_header
from email.utils import parsedate_to_datetime, getaddresses
import html
import re


def _decode_header_value(value) -> str:
    if value is None:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return str(value)


def _parse_addresses(header_value) -> list:
    """Return list of {name, address} from a header."""
    if not header_value:
        return []
    try:
        pairs = getaddresses([str(header_value)])
    except Exception:
        return []
    result = []
    for name, addr in pairs:
        result.append({"name": _decode_header_value(name) if name else "", "address": addr})
    return result


def _get_best_text(msg: EmailMessage) -> tuple:
    """Return (plain_text, html_text) from a multipart or simple message."""
    plain = ""
    html_ = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = part.get_content_disposition()
            if disposition == "attachment":
                continue
            try:
                payload = part.get_content()
            except Exception:
                continue
            if ctype == "text/plain" and not plain:
                plain = payload or ""
            elif ctype == "text/html" and not html_:
                html_ = payload or ""
    else:
        ctype = msg.get_content_type()
        try:
            payload = msg.get_content()
        except Exception:
            payload = ""
        if ctype == "text/html":
            html_ = payload or ""
        else:
            plain = payload or ""
    return plain, html_


def _generate_snippet(plain: str, html_: str, max_len: int = 200) -> str:
    text = plain or re.sub(r"<[^>]+>", " ", html_ or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_len]


def parse_message(raw_bytes: bytes) -> dict:
    """Parse raw RFC822 message bytes into a structured dict."""
    msg = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    # Envelope
    subject = _decode_header_value(msg.get("Subject"))
    message_id = msg.get("Message-ID")
    in_reply_to = msg.get("In-Reply-To")
    references = msg.get("References")

    from_list = _parse_addresses(msg.get("From"))
    to_list = _parse_addresses(msg.get("To"))
    cc_list = _parse_addresses(msg.get("Cc"))
    bcc_list = _parse_addresses(msg.get("Bcc"))

    # Date
    date_str = msg.get("Date")
    internal_date = None
    if date_str:
        try:
            internal_date = parsedate_to_datetime(date_str)
        except Exception:
            internal_date = None

    # Body
    body_text, body_html = _get_best_text(msg)
    snippet = _generate_snippet(body_text, body_html)

    # Attachments info
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                filename = part.get_filename()
                if filename:
                    attachments.append({
                        "filename": _decode_header_value(filename),
                        "mime_type": part.get_content_type(),
                        "size": len(part.get_payload(decode=True) or b""),
                    })

    return {
        "subject": subject,
        "message_id": message_id,
        "in_reply_to": in_reply_to,
        "references": references,
        "from": from_list[0] if from_list else None,
        "from_list": from_list,
        "to": to_list,
        "cc": cc_list,
        "bcc": bcc_list,
        "internal_date": internal_date.isoformat() if internal_date else None,
        "body_text": body_text,
        "body_html": body_html,
        "snippet": snippet,
        "has_attachments": len(attachments) > 0,
        "attachments": attachments,
        "size": len(raw_bytes),
    }
