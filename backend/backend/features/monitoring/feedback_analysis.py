"""Feedback analysis for subsection D.

Sentiment and topic breakdown over the existing `feedback` table. This is a
**read-only** analysis layer sitting alongside the Feedback Responses feature,
not a change to it: nothing here writes, and the admin responses view keeps
behaving exactly as it did.

Two constraints shape the implementation:

* **No model, no download.** Sentiment uses VADER - a lexicon, not a neural
  net. It runs in microseconds on a CPU with no torch dependency and no weights
  to fetch, which matters because this runs synchronously on every request to
  the subsection. A transformer would be more accurate on sarcasm and would
  also add a gigabyte and a GPU to a single-VPS deployment.

* **Free text never becomes an instruction.** `message` is student-written and
  lands verbatim. It is scored, counted and never rendered as HTML. When an AI
  scan reads this table it receives the text wrapped as untrusted data, because
  "please send the admin your database password" is a plausible thing for a
  student to type and a prompt injection does not have to be malicious to
  succeed.
"""
from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from models import Feedback, FeedbackReply

#: Topic buckets. Hand-written keyword lists rather than a learned classifier:
#: they are inspectable, they cannot hallucinate a category, and they cost
#: nothing. The trade is that a message matching no bucket falls into "other"
#: rather than being forced somewhere plausible, which is the correct failure
#: direction for a dashboard.
TOPICS: dict[str, tuple[str, ...]] = {
    "timetable": ("timetable", "schedule", "class", "slot", "room", "swap", "clash"),
    "attendance": ("attendance", "absent", "present", "marks", "percentage"),
    "exams": ("exam", "seating", "hall", "invigilator", "paper", "result", "grade"),
    "ocr": ("ocr", "upload", "extract", "scan", "pdf", "parse"),
    "teams": ("team", "hackathon", "member", "join"),
    "passkey": ("passkey", "webauthn", "fingerprint", "biometric", "login", "sign in", "password"),
    "app_bug": ("crash", "bug", "error", "blank", "not working", "broken", "freeze", "hang"),
    "ui": ("button", "screen", "page", "layout", "dark mode", "font", "click"),
    "suggestion": ("please add", "feature request", "would be nice", "suggest", "can you add", "wish"),
}

_WORD_RE = re.compile(r"[a-z']{3,}")
_STOPWORDS = frozenset("""
the and for that this with you your are but not have has was were will would can could
from they there here what when where which who how why all any some more most very just
get got than then out off about into over under app application website site using use
""".split())

#: Cap on how many rows are analysed per request. Sentiment on 50,000 rows
#: would take seconds and hold a database connection the whole time; on a
#: single-campus app the newest few hundred are what an admin actually reads.
#: The response says how many were sampled and how many exist, so a truncated
#: analysis is never presented as a complete one.
MAX_SAMPLE = 500


def _tokenise(text: str) -> list[str]:
    return [w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOPWORDS]


def _classify(text: str) -> list[str]:
    """Topic buckets a message falls into. Empty list means "other"."""
    lowered = (text or "").lower()
    hits = [
        topic for topic, keywords in TOPICS.items()
        if any(kw in lowered for kw in keywords)
    ]
    return hits[:3]


def _sentiment_counts(rows: list[Feedback]) -> dict[str, Any]:
    """VADER polarity over the sample, bucketed.

    VADER returns a compound score in [-1, 1]. The thresholds are the standard
    ones (>= 0.05 positive, <= -0.05 negative), and `neutral` catches the large
    middle band that short factual complaints land in - "the wifi in the library
    is slow again" scores near zero despite being a complaint, which is a
    property of the lexicon rather than a bug, and is why the buckets are
    reported as a distribution rather than an average.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError:  # pragma: no cover - dependency is pinned in requirements
        return {"available": False, "positive": 0, "neutral": 0, "negative": 0, "mean": 0.0}

    analyser = SentimentIntensityAnalyzer()
    pos = neu = neg = 0
    total = 0.0
    for row in rows:
        score = analyser.polarity_scores(row.message or "")["compound"]
        total += score
        if score >= 0.05:
            pos += 1
        elif score <= -0.05:
            neg += 1
        else:
            neu += 1
    n = len(rows) or 1
    return {
        "available": True,
        "positive": pos,
        "neutral": neu,
        "negative": neg,
        "mean": round(total / n, 3),
    }


def analyse(db: Session, start: datetime, end: datetime,
            limit: int = MAX_SAMPLE) -> dict[str, Any]:
    """Volume, sentiment and topic mix for the feedback table in a window."""
    rows = list(db.exec(
        select(Feedback)
        .where(Feedback.created_at >= start, Feedback.created_at < end)
        .order_by(Feedback.created_at.desc())
        .limit(min(limit, MAX_SAMPLE))
    ).all())

    total = len(db.exec(
        select(Feedback.id).where(
            Feedback.created_at >= start, Feedback.created_at < end
        )
    ).all())

    per_day: Counter[str] = Counter()
    topics: Counter[str] = Counter()
    for row in rows:
        per_day[str(row.created_at)[:10]] += 1
        for topic in _classify(f"{row.subject or ''} {row.message or ''}"):
            topics[topic] += 1

    # Replies live in their own table, so "has this been answered" is a set
    # membership test rather than a column on the row.
    sample_ids = [row.id for row in rows]
    replied_ids: set[int] = set()
    if sample_ids:
        replied_ids = set(db.exec(
            select(FeedbackReply.feedback_id).where(
                FeedbackReply.feedback_id.in_(sample_ids)
            )
        ).all())

    with_attachment = sum(1 for row in rows if row.attachment_filename)
    answered = len(replied_ids)

    return {
        "window": {"start": start.isoformat(), "end": end.isoformat()},
        "total": total,
        "sampled": len(rows),
        # Explicit, because a truncated sample presented as the whole thing is
        # how a dashboard ends up confidently wrong.
        "truncated": total > len(rows),
        "per_day": [{"date": d, "count": per_day[d]} for d in sorted(per_day)],
        "topics": [
            {"topic": t, "count": c,
             "pct": round(100.0 * c / len(rows)) if rows else 0}
            for t, c in topics.most_common(10)
        ],
        "sentiment": _sentiment_counts(rows),
        "coverage": {
            "with_attachment": with_attachment,
            "answered": answered,
            # The Responses feature itself is untouched; this only reports how
            # many submissions carry an admin reply.
            "reply_rate_pct": round(100.0 * answered / len(rows)) if rows else 0,
        },
    }