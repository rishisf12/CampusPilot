"""Egress gate: the redaction layer every tool output passes through.

A monitor model never sees a raw row (architecture rule 2). Every value that
crosses `run_tool` comes through this module first:

- `redact(text)` masks emails, JWT-shaped tokens, Luhn-valid card runs, IP
  addresses and phone numbers with bracket placeholders.
- `pseudonymize_id(value, salt)` folds an identifier onto `USER_xxxxxxxx`
  (SHA-256 truncated) - stable within one scan run so the model can count
  recurrences, useless for re-identifying anyone across runs because the salt
  is per-run random.
- `redact_value(obj, salt)` walks dicts/lists and additionally blanks the
  values of password/secret/hash-named fields and pseudonymizes user-ish id
  fields.

Strictness beats cleverness: a date-like digit run getting masked as a phone
number costs the model nothing re-identifiable; a mask that doesn't fire could
cost a student their phone number.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

#: Bracket placeholders used in free text. Fixed strings: the model reading a
#: scan must be able to rely on them, and tests assert on their exact form.
EMAIL_MASK = "[email]"
JWT_MASK = "[jwt]"
CARD_MASK = "[card]"
IP_MASK = "[ip]"
PHONE_MASK = "[phone]"
SECRET_MASK = "[masked]"
ID_PREFIX = "USER_"

# --- text patterns, applied in order ----------------------------------------
# JWT first (its base64url blob would otherwise be nibbled by the other
# patterns), then email (its local digits would look phone-ish), then cards,
# then IPs, then the coarse phone catch-all.

_EMAIL_RE = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"
)

_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")

#: A card-shaped run: 13-19 digits, optionally separated by single spaces or
#: dashes. Whether it is masked is decided by the Luhn check in `_mask_card`.
_CARD_RE = re.compile(r"(?<![\w.])(?:\d[ -]?){12,18}\d(?![\w.])")

_IPV4_RE = re.compile(r"(?<![\w])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")

#: Catch-all for anything else digit-flavoured (10+ characters' worth). This
#: also mops up card runs that failed Luhn and date-like strings - accepted
#: strictness, see the module docstring.
_PHONE_RE = re.compile(r"(?<!\w)\+?\d[\d()\-.\s]{7,}\d(?!\w)")


def _luhn_ok(digits: str) -> bool:
    """Standard Luhn checksum, for deciding whether a digit run is card-shaped."""
    total, doubled = 0, False
    for ch in reversed(digits):
        d = ord(ch) - 48
        if doubled:
            d *= 2
            if d > 9:
                d -= 9
        total += d
        doubled = not doubled
    return total % 10 == 0


def _mask_card(match: re.Match[str]) -> str:
    return CARD_MASK if _luhn_ok(match.group(0).replace(" ", "").replace("-", "")) else match.group(0)


def _mask_ip(match: re.Match[str]) -> str:
    octets = match.group(0).split(".")
    valid = len(octets) == 4 and all(o.isdigit() and int(o) <= 255 for o in octets)
    return IP_MASK if valid else match.group(0)


#: (pattern, replacement) in application order. `re.subn` with callables keeps
#: the conditional masks (Luhn, octet bounds) honest.
_TEXT_PATTERNS: tuple[tuple[re.Pattern[str], Any], ...] = (
    (_JWT_RE, JWT_MASK),
    (_EMAIL_RE, EMAIL_MASK),
    (_CARD_RE, _mask_card),
    (_IPV4_RE, _mask_ip),
    (_PHONE_RE, PHONE_MASK),
)


def redact(text: str) -> str:
    """Mask every recognisable PII shape in `text`. See module docstring."""
    if not text:
        return text
    for pattern, repl in _TEXT_PATTERNS:
        text = pattern.sub(repl, text)
    return text


#: Dict keys whose value is a credential and gets blanked entirely, rather than
#: pattern-masked: field names beat content analysis every time.
SECRET_KEYS = frozenset(
    {"password", "passwd", "password_hash", "secret", "secret_key", "api_key", "authorization"}
)

#: Dict keys whose value is a person identifier: pseudonymized, never raw, so
#: the model can still tell "3 different complainants" from "one, three times".
ID_KEYS = frozenset(
    {
        "user_id",
        "student_id",
        "faculty_id",
        "admin_id",
        "author_id",
        "owner_id",
        "by_user_id",
        "submitted_by",
    }
)


def pseudonymize_id(value: Any, salt: str) -> str:
    """`USER_` + first 8 hex chars of SHA-256(salt:value).

    Stable for one salt (= one scan run), unlinkable across runs, and - because
    the salt never leaves the backend except as an opaque hex blob in the audit
    row - useless for anyone without DB access to invert.
    """
    digest = hashlib.sha256(f"{salt}:{str(value)}".encode()).hexdigest()[:8]
    return f"{ID_PREFIX}{digest}"


def _is_secret_key(key: str) -> bool:
    lowered = key.strip().lower()
    return lowered in SECRET_KEYS or lowered.endswith("_hash")


def _is_id_key(key: str) -> bool:
    return key.strip().lower() in ID_KEYS


def redact_value(obj: Any, salt: str) -> tuple[Any, int]:
    """Deep-walk `obj`, masking/pseudonymizing. Returns (new object, count).

    Structurally unchanged otherwise: numbers, booleans and None pass through;
    every string is passed through `redact()`. Only containers (dict/list/
    tuple) are rebuilt.
    """
    count = 0

    def walk(node: Any) -> Any:
        nonlocal count
        if isinstance(node, str):
            masked = redact(node)
            if masked != node:
                count += 1
            return masked
        if isinstance(node, dict):
            out: dict[Any, Any] = {}
            for k, v in node.items():
                k_str = str(k)
                if _is_secret_key(k_str) and v is not None:
                    out[k] = SECRET_MASK
                    count += 1
                elif _is_id_key(k_str) and v is not None:
                    if isinstance(v, (list, tuple)):
                        out[k] = [pseudonymize_id(item, salt) for item in v]
                        count += len(v)
                    else:
                        out[k] = pseudonymize_id(v, salt)
                        count += 1
                else:
                    out[k] = walk(v)
            return out
        if isinstance(node, (list, tuple)):
            items = [walk(item) for item in node]
            return list(items) if isinstance(node, list) else type(node)(items)
        return node

    return walk(obj), count
