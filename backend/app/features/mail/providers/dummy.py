"""Dummy mail provider - a simulated mail server used for development.

Generates realistic sample mail for every section and alias: registered and
unregistered senders, spoofed mail, attachments, threads, Cc/Bcc, HTML and
plain text. Sent mail can be looped back as inbound to test replies and
threads. Controllable health status.

This is the default provider; no real mail server is required.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import os

from features.mail.providers.base import (
    InboundProvider,
    OutboundProvider,
    RawMessage,
    SendResult,
    register_provider,
    register_providers,
)
import os

#: When true, the dummy provider simulates failed-auth mail so the quarantine
#: path can be exercised without a real mail server.
DUMMY_FAIL_AUTH = os.environ.get("MAIL_DUMMY_FAIL_AUTH", "0") in ("1", "true", "yes", "on")

#: The six aliases that all feed one common intake.
ALIASES = (
    "ug-placement@iiitdmj.ac.in",
    "registrar@iiitdmj.ac.in",
    "ug-cultural@iiitdmj.ac.in",
    "ug-technical@iiitdmj.ac.in",
    "ug-sports@iiitdmj.ac.in",
    "ug-other@iiitdmj.ac.in",
)

#: Registered senders per section.
CLUSTERS = {
    "placement": ["tnp@iiitdmj.ac.in", "placement@iiitdmj.ac.in", "@placementcell.iiitdmj.ac.in"],
    "academics": ["registrar@iiitdmj.ac.in", "dean.acad@iiitdmj.ac.in", "examcell@iiitdmj.ac.in"],
    "cultural": ["cultural-club@iiitdmj.ac.in", "cultural@iiitdmj.ac.in"],
    "technical": ["tech-fest@iiitdmj.ac.in", "technical@iiitdmj.ac.in", "hackathon@iiitdmj.ac.in"],
    "sports": ["sports-office@iiitdmj.ac.in", "sports@iiitdmj.ac.in"],
    "other": ["principal@iiitdmj.ac.in"],
}

#: Sender -> subject templates per section.
SECTION_MAIL = {
    "placement": [
        ("Internship drive: Samsung shortlist", "The shortlist for the Samsung internship drive is out. Check your selection status on the portal."),
        ("TCS campus placement drive", "Register for the TCS campus placement drive before Wednesday. Eligibility: 60 percent and above."),
        ("Placement cell: off-campus opportunities", "Several off-campus hiring drives are scheduled for next month."),
    ],
    "academics": [
        ("Mid semester timetable published", "The mid semester examination timetable is now available on the portal. Exams begin from 5 November, 2026."),
        ("Fee payment window", "The fee payment window for the even semester opens on the 1st and closes on the 10th."),
        ("Attendance policy update", "The attendance policy has changed. Minimum 75 percent attendance is now mandatory."),
    ],
    "cultural": [
        ("Auditions for the annual cultural night", "Auditions for music, dance and drama will be held this Friday in the auditorium."),
        ("Cultural fest registrations open", "Registrations for the annual cultural fest are now open. Team entries only."),
        ("Fine arts workshop schedule", "The fine arts workshop schedule is posted on the notice board."),
    ],
    "technical": [
        ("Hackathon registration is live", "Team registration for the 36-hour hackathon is now open. Last date to register is Sunday."),
        ("Tech fest workshops", "Technical workshops for the upcoming tech fest are listed on the website."),
        ("Project expo submissions", "Submit your project expo entries by Friday to be considered for the showcase."),
    ],
    "sports": [
        ("Inter-university basketball invite", "You are invited to the inter-university basketball tournament next month."),
        ("Inter hostel football tournament", "The inter hostel football tournament begins next week. Register your hostel team."),
        ("Sports fest schedule", "The sports fest schedule is now available. Events start Monday morning."),
    ],
    "other": [
        ("Fee payment window for even semester", "The fee payment window opens on the 1st and closes on the 10th. Late payments attract a fine."),
        ("Library book bank distribution", "Book bank distribution for the even semester starts next week."),
        ("Hostel mess menu change", "The hostel mess menu changes from next Monday. Feedback is welcome."),
    ],
}

#: Unregistered senders (for the worklist).
UNREGISTERED_SENDERS = [
    ("unknown@gmail.com", "A stranger"),
    ("dr.random@external-university.edu", "Dr. Random"),
    ("spoofed@evil-domain.com", "Spoofed Sender"),
]

#: Spoofed/suspicious senders (failed auth).
SPOOFED_SENDERS = [
    ("spoofed-hr@acme.com", "HR Team"),
]


class DummyProvider(InboundProvider, OutboundProvider):
    """A simulated mail server with realistic seed data.

    The provider keeps an in-memory queue of messages. ``fetch_new`` returns
    messages that haven't been fetched yet; ``mark_fetched`` removes them.
    ``send`` stores a copy and optionally loops it back as inbound.
    """

    def __init__(self) -> None:
        self._inbox: list[RawMessage] = []
        self._fetched: set[str] = set()
        self._sent: list[SendResult] = []
        self._health_status = "green"
        self._seed()

    # ------------------------------------------------------------------
    # Seeding
    # ------------------------------------------------------------------
    def _seed(self) -> None:
        """Fill the inbox with realistic mail for every section and alias."""
        now = datetime.now(timezone.utc)
        counter = 0
        for section, senders in CLUSTERS.items():
            for subject, body in SECTION_MAIL[section]:
                for sender in senders[:2]:  # two senders per section
                    counter += 1
                    alias = ALIASES[counter % len(ALIASES)]
                    received = now - timedelta(hours=counter * 3)
                    self._inbox.append(
                        RawMessage(
                            message_id=f"<dummy-{counter}@{section}.iiitdmj.ac.in>",
                            from_email=sender,
                            from_name=sender.split("@")[0].replace("-", " ").title(),
                            to=[alias],
                            delivered_to=alias,
                            subject=subject,
                            body_text=body,
                            received_at=received,
                            headers={"X-Dummy-Section": section},
                        )
                    )
        # Unregistered senders -> unassigned
        counter += 1
        for sender, name in UNREGISTERED_SENDERS:
            counter += 1
            alias = ALIASES[counter % len(ALIASES)]
            self._inbox.append(
                RawMessage(
                    message_id=f"<dummy-unreg-{counter}@iiitdmj.ac.in>",
                    from_email=sender,
                    from_name=name,
                    to=[alias],
                    delivered_to=alias,
                    subject="A notice from an unregistered office",
                    body_text="This sender is not registered in any cluster.",
                    received_at=now - timedelta(hours=counter * 2),
                    headers={},
                )
            )
        # Spoofed mail -> quarantine
        if DUMMY_FAIL_AUTH:
            counter += 1
            sender, name = SPOOFED_SENDERS[0]
            alias = ALIASES[counter % len(ALIASES)]
            self._inbox.append(
                RawMessage(
                    message_id=f"<dummy-spoof-{counter}@iiitdmj.ac.in>",
                    from_email=sender,
                    from_name=name,
                    to=[alias],
                    delivered_to=alias,
                    subject="Urgent: verify your account",
                    body_text="Please click the link to verify your account immediately.",
                    received_at=now - timedelta(hours=counter),
                    auth_spf="fail",
                    auth_dkim="fail",
                    auth_dmarc="fail",
                    headers={"X-Dummy-Spoofed": "true"},
                )
            )

    # ------------------------------------------------------------------
    # Inbound
    # ------------------------------------------------------------------
    async def fetch_new(self, since: Optional[datetime] = None) -> list[RawMessage]:
        if self._health_status != "green":
            return []
        now = datetime.now(timezone.utc)
        new_messages: list[RawMessage] = []
        for msg in self._inbox:
            msg_id = msg.message_id or ""
            if msg_id in self._fetched:
                continue
            if since is not None and msg.received_at is not None and msg.received_at < since:
                continue
            self._fetched.add(msg_id)
            new_messages.append(msg)
        return new_messages

    async def mark_fetched(self, message_ids: list[str]) -> None:
        self._fetched.update(message_ids)

    async def health(self) -> dict[str, Any]:
        return {
            "provider": "dummy",
            "status": self._health_status,
            "inbox_size": len(self._inbox),
            "fetched_count": len(self._fetched),
            "simulated_fail_auth": DUMMY_FAIL_AUTH,
        }

    # ------------------------------------------------------------------
    # Outbound
    # ------------------------------------------------------------------
    async def send(self, message: OutgoingMessage) -> SendResult:
        """Store a sent message and optionally loop it back as inbound."""
        result = SendResult(
            provider_message_id=f"<dummy-sent-{len(self._sent) + 1}@iiitdmj.ac.in>",
            status="sent",
        )
        self._sent.append(result)

        # Loop back as inbound so replies/threads can be tested without a
        # real mail server.
        loopback = RawMessage(
            message_id=result.provider_message_id,
            from_email=message.to[0] if message.to else "loopback@iiitdmj.ac.in",
            from_name="Loopback",
            to=[message.from_email],
            subject=f"Re: {message.subject}" if message.subject else "(no subject)",
            body_text=f"Re: {message.body_text or ''}",
            received_at=datetime.now(timezone.utc),
            headers={"X-Dummy-Loopback": "true"},
        )
        self._inbox.append(loopback)
        return result

    # ------------------------------------------------------------------
    # Test helpers (not part of the provider interface)
    # ------------------------------------------------------------------
    def inject(self, message: RawMessage) -> None:
        """Inject a message directly into the inbox (for tests/dev tools)."""
        self._inbox.append(message)

    def set_health(self, status: str) -> None:
        self._health_status = status

    def clear(self) -> None:
        self._inbox.clear()
        self._fetched.clear()
        self._sent.clear()
        self._seed()


register_provider("dummy", DummyProvider)


# ------------------------------------------------------------------
# Backwards-compatible module-level functions (used by tests/scripts)
# ------------------------------------------------------------------
_provider: Optional[DummyProvider] = None


def get_dummy_provider() -> DummyProvider:
    """Return the module-level dummy provider instance."""
    global _provider
    if _provider is None:
        _provider = DummyProvider()
    return _provider


def dummy_fetch_new() -> list[RawMessage]:
    import asyncio

    provider = get_dummy_provider()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        return asyncio.ensure_future(provider.fetch_new())  # type: ignore[return-value]
    return asyncio.run(provider.fetch_new())


def dummy_send(message: OutgoingMessage) -> SendResult:
    import asyncio

    provider = get_dummy_provider()
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        return asyncio.ensure_future(provider.send(message))  # type: ignore[return-value]
    return asyncio.run(provider.send(message))


# Register providers when this module is imported.
register_providers()
