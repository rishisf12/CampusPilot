"""
Hackathon feed: email ingestion and retention.

Anyone can mail the configured address and the message becomes a feed entry.
That makes every field in this module attacker-controlled, which drives three
decisions that would otherwise look over-cautious:

* **HTML is never stored or rendered.** A public mailbox is a free XSS delivery
  channel. Bodies are flattened to plain text with the stdlib `html.parser` and
  rendered by React as text, so there is no `dangerouslySetInnerHTML` anywhere.
  Links are lifted out separately and only kept when the scheme is http/https,
  which drops `javascript:` and `data:` payloads.
* **Filenames off the wire are never used as paths.** Each attachment gets a
  generated name; the original is kept only as inert text. Extensions are
  allowlisted so the mailbox cannot be used as a file host for executables.
* **UIDs, not the `\\Seen` flag.** If the mailbox owner opens a mail in Gmail it
  gets marked seen and a `UNSEEN` sweep would skip it forever. Cursor-based
  tracking keeps working when that happens.

Ingestion uses stdlib `imaplib` only, so this adds no dependency. It stays inert
until `FEED_IMAP_USER` and `FEED_IMAP_PASSWORD` are both set.
"""
import email
import email.policy
import html
import imaplib
import logging
import re
import uuid
from datetime import datetime, timedelta
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlparse

from sqlmodel import Session, select

from core.config import get_settings
from models import FeedCursor, Hackathon

logger = logging.getLogger(__name__)
settings = get_settings()

#: Extensions worth storing on a hackathon notice. Deliberately excludes
#: executables, scripts, archives and anything else that could be a payload.
ALLOWED_ATTACHMENT_SUFFIXES = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".txt", ".csv", ".md"}
)

#: Block tags whose contents are markup rather than prose. Stripped with their
#: content so `<script>alert(1)</script>` cannot leave text behind.
_DROP_TAGS = frozenset(
    {"script", "style", "head", "title", "iframe", "object", "embed", "svg", "noscript"}
)

_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+", re.IGNORECASE)
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


class _TextExtractor(HTMLParser):
    """
    Flatten HTML to plain text.

    `convert_charrefs` handles entities, and a depth counter drops the content
    of the tags in `_DROP_TAGS`. Unclosed tags are tolerated - real mail is
    full of them and raising here would just lose the entry.

    Anchor *text* is dropped as well as collecting its href. The link is already
    rendered separately from `links`, so keeping the visible label too would
    merge unrelated words into the prose - a "bad"/"Apply" pair ended up as the
    single run-on word `badApply`.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._drop_depth = 0
        self._anchor_depth = 0
        self.links: List[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in _DROP_TAGS:
            self._drop_depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
            self._anchor_depth += 1

    def handle_endtag(self, tag):
        if tag in _DROP_TAGS and self._drop_depth > 0:
            self._drop_depth -= 1
        if tag == "a" and self._anchor_depth > 0:
            self._anchor_depth -= 1
        if tag in {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if self._drop_depth or self._anchor_depth:
            return
        if data.strip():
            self.parts.append(data)

    def error(self, message):  # pragma: no cover - py<3.10 compat hook
        pass


def html_to_text(raw: str) -> Tuple[str, List[str]]:
    """Return `(plain_text, hrefs)` for an HTML fragment. Never raises."""
    if not raw:
        return "", []
    parser = _TextExtractor()
    try:
        parser.feed(raw)
        parser.close()
    except Exception as exc:  # noqa: BLE001 - malformed mail must not kill the sweep
        logger.warning("could not parse html body: %s", exc)

    text = "".join(parser.parts)
    text = _WS_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = _NL_RE.sub("\n\n", text).strip()

    links = [href for href in parser.links if is_safe_url(href)]
    links.extend(url for url in _URL_RE.findall(text) if is_safe_url(url))
    return text, dedupe(links)


def is_safe_url(url: str) -> bool:
    """
    Only http(s) survives.

    This is the guard that stops `javascript:alert(1)` and `data:text/html,...`
    from ever reaching an href in the feed.
    """
    try:
        parsed = urlparse((url or "").strip())
    except ValueError:
        return False
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


def dedupe(values: Iterable[str]) -> List[str]:
    seen = set()
    out = []
    for value in values:
        key = value.strip()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _strip_reply_quotes(body: str) -> str:
    """Cut the reply chain so the entry is the notice, not the whole thread."""
    lines = body.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        # Gmail/Outlook quote markers. Matching on the leading '>' alone would
        # eat any line that happens to start with a comparison operator.
        if stripped.startswith("-----Original Message-----"):
            break
        if stripped.startswith("On ") and stripped.endswith("wrote:"):
            break
        if re.match(r"^>+", stripped) and len(stripped) > 1:
            break
        if stripped.lower().startswith("from:") and "@" in stripped:
            break
        kept.append(line)
    return "\n".join(kept).strip()


def sanitize_body(message: email.message.Message) -> Tuple[str, List[str]]:
    """Plain text plus vetted links, preferring the text/plain alternative."""
    plain_part = None
    html_part = None

    # `walk()` yields the message itself when it is not multipart, so this loop
    # must run unconditionally. Guarding it with `is_multipart()` looks
    # reasonable and is not: a plain single-part mail - the common case - would
    # skip the loop entirely and produce an empty body, so the feed would show
    # a title and nothing behind the disclosure.
    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        if "attachment" in disposition:
            continue
        subtype = part.get_content_subtype()
        if subtype == "plain" and plain_part is None:
            plain_part = part
        elif subtype == "html" and html_part is None:
            html_part = part

    source = plain_part or html_part
    if source is None:
        return "", []

    try:
        raw = source.get_content()
    except Exception as exc:  # noqa: BLE001 - undecodable charset
        logger.warning("could not decode body: %s", exc)
        payload = source.get_payload(decode=True) or b""
        raw = payload.decode("utf-8", errors="replace")

    if not isinstance(raw, str):
        raw = str(raw)

    text, links = html_to_text(raw)
    text = _strip_reply_quotes(text)
    text = text[: settings.feed_max_body_chars]

    # A body that is nothing but a link is not a description. Keep the first
    # link as `link` instead and leave the text empty.
    return text, dedupe(links)


def subject_to_title(subject: Optional[str]) -> str:
    """Strip the usual `Re:` / `Fwd:` prefixes; fall back to something usable."""
    title = (subject or "").strip()
    title = re.sub(r"^(?:(?:re|fw|fwd|aw)\s*:\s*)+", "", title, flags=re.IGNORECASE).strip()
    return title[:200] or "(no subject)"


def sender_of(message: email.message.Message) -> Optional[str]:
    """Best-effort sender address, preferring the Reply-To people will use."""
    for header in ("Reply-To", "From"):
        raw = message.get(header)
        if not raw:
            continue
        try:
            addresses = getaddresses([raw])
        except Exception:  # noqa: BLE001
            continue
        for name, address in addresses:
            if address and "@" in address:
                return f"{name} <{address}>" if name else address
    return None


def received_at_of(message: email.message.Message) -> datetime:
    """
    Use the `Date:` header so retention is measured from when the notice was
    sent. Falling back to import time would make a two-month-old newsletter
    look brand new and keep it a full month.
    """
    try:
        parsed = parsedate_to_datetime(message.get("Date"))
        if parsed is not None:
            # Emails carry tz-aware datetimes, the column is naive.
            return parsed.replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    return datetime.utcnow()


def _looks_executable(data: bytes) -> bool:
    """
    True when the payload's magic bytes say "this is a program".

    Checked regardless of the claimed extension. The allowlist already refuses
    a `.exe` name, but nothing stopped `innocent.pdf` carrying an MZ header, and
    a mailbox that will store and serve arbitrary payloads is a malware host
    however carefully the filename is sanitised. Only confident signatures
    count: a mislabelled PDF is a curiosity, an MZ header is not.
    """
    head = data[:8]
    if head.startswith(b"MZ"):            # DOS / Windows PE
        return True
    if head.startswith(b"\x7fELF"):      # Linux ELF
        return True
    if head[:4] in {b"\xfe\xed\xfa\xce", b"\xfe\xed\xfa\xcf", b"\xce\xfa\xed\xfe", b"\xcf\xfa\xed\xfe"}:
        return True                       # Mach-O
    if head[:2] == b"MZ" or head[:2] == b"#!":
        return True                       # DOS stub / shebang
    return False


def safe_filename(original: Optional[str], data: bytes) -> Tuple[str, Optional[str]]:
    """
    Return `(stored_name, display_name)`.

    The stored name is generated. Nothing from the wire reaches the filesystem,
    so `../../etc/passwd` and `a/b\\x00c` are both inert. The extension is taken
    from the original name but re-checked against the allowlist, and falls back
    to sniffing the payload so a mislabelled `.exe` is still refused.
    """
    display = Path((original or "attachment").strip()).name[:120] or "attachment"

    # An executable is refused whatever it is called.
    if _looks_executable(data):
        return "", None

    suffix = Path(display).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_SUFFIXES:
        guessed = _sniff_suffix(data)
        if guessed is None:
            return "", None
        suffix = guessed

    return f"{uuid.uuid4().hex}{suffix}", display


def _sniff_suffix(data: bytes) -> Optional[str]:
    """Identify a few formats from their magic bytes."""
    head = data[:16]
    if head.startswith(b"%PDF"):
        return ".pdf"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if head.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return ".gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


def save_attachments(message: email.message.Message) -> Tuple[List[str], List[str]]:
    """Write allowed attachments to disk. Returns `(stored_names, display_names)`."""
    target_dir = Path(settings.feed_media_dir)
    stored: List[str] = []
    displays: List[str] = []

    for part in message.walk():
        if part.get_content_maintype() == "multipart":
            continue
        if len(stored) >= settings.feed_max_attachments:
            logger.info("attachment limit reached, skipping the rest")
            break

        filename = part.get_filename()
        if not filename:
            continue

        try:
            data = part.get_payload(decode=True) or b""
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not decode attachment %s: %s", filename, exc)
            continue

        if not data or len(data) > settings.feed_max_attachment_bytes:
            logger.info("skipping %s: %s bytes", filename, len(data))
            continue

        stored_name, display = safe_filename(filename, data)
        if not stored_name:
            logger.info("refused attachment %s: type not allowed", filename)
            continue

        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / stored_name).write_bytes(data)
        except OSError as exc:
            logger.warning("could not store %s: %s", display, exc)
            continue

        stored.append(stored_name)
        displays.append(display)

    return stored, displays


def delete_media(stored_names: Iterable[str]) -> int:
    """Remove attachment files. Returns how many went. Never raises."""
    target_dir = Path(settings.feed_media_dir)
    removed = 0
    for name in stored_names or []:
        # Stored names are ours, but resolve anyway so a corrupted row cannot
        # turn a sweep into an arbitrary delete.
        try:
            path = (target_dir / str(name)).resolve()
            if path.parent != target_dir.resolve() or not path.is_file():
                continue
            path.unlink()
            removed += 1
        except OSError as exc:
            logger.warning("could not delete media %s: %s", name, exc)
    return removed


def orphan_media(session: Session) -> List[str]:
    """
    Stored files that no surviving row points at.

    Rows and files are written in two steps, so a crash between them - or an
    ingest that stored files then failed to commit - leaves files behind. Since
    the whole reason for the retention window is disk, a sweep that only walked
    rows would leak indefinitely. Returns the unreferenced names.
    """
    target_dir = Path(settings.feed_media_dir)
    if not target_dir.is_dir():
        return []

    referenced = set()
    for row in session.exec(select(Hackathon)).all():
        referenced.update(str(name) for name in (row.attachments or []))

    try:
        on_disk = {path.name for path in target_dir.iterdir() if path.is_file()}
    except OSError as exc:
        logger.warning("could not list media dir: %s", exc)
        return []

    return sorted(on_disk - referenced)


def sweep_orphans(session: Session) -> int:
    """Delete unreferenced attachment files. Returns how many went."""
    names = orphan_media(session)
    if not names:
        return 0
    removed = delete_media(names)
    logger.info("feed retention: removed %d orphaned files", removed)
    return removed


# ------------------------------------------------------------------ retention


def cutoff(days: Optional[int] = None) -> datetime:
    span = settings.feed_retention_days if days is None else days
    return datetime.utcnow() - timedelta(days=span)


def purge_expired(session: Session, days: Optional[int] = None) -> Dict[str, int]:
    """
    Delete rows older than the retention window, and their files with them.

    Deleting the row alone would leak attachment files forever, which defeats
    the point of the window. Teams keep working: `Team.hackathon_id` is nullable
    and a dangling id is only ever used to look up an event that is gone.
    """
    rows = session.exec(select(Hackathon).where(Hackathon.created_at < cutoff(days))).all()
    entries = len(rows)
    files = 0
    for row in rows:
        files += delete_media(row.attachments)
        session.delete(row)
    if rows:
        session.commit()
        logger.info("feed retention: removed %d entries, %d files", entries, files)

    # After the rows go, anything left on disk is unreferenced. Sweeping here as
    # well means the window bounds disk use even if a previous run died between
    # storing a file and committing its row.
    orphans = sweep_orphans(session)
    return {"entries": entries, "files": files + orphans}


# ------------------------------------------------------------------- ingestion


def _decode_payload(raw: bytes) -> email.message.Message:
    return email.message_from_bytes(raw, policy=email.policy.default)


def _entry_from(message: email.message.Message, uid: int) -> Optional[Hackathon]:
    body_text, links = sanitize_body(message)
    title = subject_to_title(message.get("Subject"))
    sender = sender_of(message)
    stored, _ = save_attachments(message)

    # A mail with neither a subject nor a body is noise, not a notice.
    if title == "(no subject)" and not body_text and not stored:
        return None

    return Hackathon(
        title=title,
        # `description` is the short form other views already render; the feed
        # itself uses `body_text` for the full text behind the disclosure.
        description=body_text[:280],
        link=links[0] if links else None,
        body_text=body_text,
        links=links,
        attachments=stored,
        sender=sender,
        # From the Date: header, not import time - see received_at_of.
        created_at=received_at_of(message),
        source="email",
        feed_uid=uid,
        is_active=True,
        tech_stack=[],
    )


def _cursor(session: Session, mailbox: str) -> FeedCursor:
    row = session.exec(select(FeedCursor).where(FeedCursor.mailbox == mailbox)).first()
    if row is None:
        row = FeedCursor(mailbox=mailbox, last_uid=0)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def ingest_once(session: Session) -> Dict[str, Any]:
    """
    Pull everything newer than the cursor into the feed.

    Returns a summary dict. Any failure is logged and reported in the result
    rather than raised, because this is driven by a button and a schedule, and
    a transient network error should not look like a crash.
    """
    if not settings.feed_enabled:
        return {"ok": False, "reason": "feed is not configured", "added": 0}

    mailbox = settings.feed_mailbox or "INBOX"
    client: Optional[imaplib.IMAP4_SSL] = None
    added = 0

    try:
        client = imaplib.IMAP4_SSL(settings.feed_imap_host, settings.feed_imap_port)
        client.login(settings.feed_imap_user, settings.feed_imap_password)
        client.select(mailbox)

        cursor = _cursor(session, mailbox)

        # A different UIDVALIDITY means the mailbox was rebuilt and our UIDs
        # refer to nothing, so start again rather than skipping everything.
        status, info = client.response("UIDVALIDITY")
        server_validity = int(info[0]) if status == "OK" and info and info[0] else None
        if server_validity and cursor.uidvalidity and server_validity != cursor.uidvalidity:
            logger.info("mailbox rebuilt (uidvalidity %s -> %s), resetting cursor", cursor.uidvalidity, server_validity)
            cursor.last_uid = 0
        cursor.uidvalidity = server_validity

        status, data = client.uid("SEARCH", None, "ALL")
        if status != "OK":
            return {"ok": False, "reason": "UID SEARCH failed", "added": 0}

        uids = [int(u) for u in (data[0] or b"").split() if u.strip().isdigit()]
        pending = sorted(u for u in uids if u > cursor.last_uid)
        logger.info("feed sweep: %d messages, %d new", len(uids), len(pending))

        for uid in pending:
            status, payload = client.uid("FETCH", str(uid), "(RFC822)")
            if status != "OK" or not payload or not isinstance(payload[0], tuple):
                logger.warning("could not fetch uid %s", uid)
                continue

            try:
                message = _decode_payload(payload[0][1])
                entry = _entry_from(message, uid)
            except Exception as exc:  # noqa: BLE001 - one bad mail must not stop the rest
                logger.warning("could not parse uid %s: %s", uid, exc)
                cursor.last_uid = uid
                continue

            if entry is not None:
                session.add(entry)
                added += 1
            cursor.last_uid = uid

        session.commit()
        # Marking seen keeps the mailbox tidy without being load-bearing - the
        # cursor is what actually prevents duplicates.
        client.uid("STORE", str(cursor.last_uid), "+FLAGS", "\\Seen")
        return {"ok": True, "added": added, "last_uid": cursor.last_uid}

    except imaplib.IMAP4.error as exc:
        logger.error("imap error: %s", exc)
        return {"ok": False, "reason": f"imap error: {exc}", "added": added}
    except Exception as exc:  # noqa: BLE001
        logger.error("feed ingest failed: %s", exc)
        return {"ok": False, "reason": str(exc), "added": added}
    finally:
        if client is not None:
            try:
                client.logout()
            except Exception:  # noqa: BLE001
                pass


def ingest_and_purge(session: Session) -> Dict[str, Any]:
    """What the feed endpoint and the sweep button both call."""
    purge_expired(session)
    return ingest_once(session)
