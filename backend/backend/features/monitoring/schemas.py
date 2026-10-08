"""Request bodies for the telemetry collector.

Deliberately permissive about shape and strict about content. The collector
accepts a loose envelope because two very different clients post to it (a browser
beacon and an Android SDK) and neither can be forced to upgrade in step with the
server. It is strict about every individual event in `collector.validate_event`.

Note what is *absent*: there is no field anywhere in this schema that a client
can use to name a user. `user_hash` is derived server-side from the bearer token
or left NULL. A client that could set its own identity field would be able to
forge activity for anyone, and every user-count metric would become attacker
controlled.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class CollectBatch(BaseModel):
    """A batch of events from one client."""

    #: Client-declared platform for the whole batch. Only used to label
    #: accept/reject metrics; each event's own `platform` field is what counts.
    platform: Optional[str] = Field(default=None, max_length=16)
    events: list[dict[str, Any]] = Field(default_factory=list)


class CrashIn(BaseModel):
    """A crash or ANR report from the Android client (and the web client).

    Separate endpoint rather than an event type because crashes arrive when the
    process is already unstable: a dedicated route can be given a much longer
    timeout, is easier to rate-limit independently, and lets the stack trace go
    into a column that dashboards never scan.
    """

    platform: str = Field(default="android", max_length=16)
    #: "crash" or "anr".
    kind: str = Field(default="crash", max_length=16)
    session_id: str = Field(min_length=8, max_length=64)
    #: Client-computed grouping key. Treated as an opaque label, never parsed.
    fingerprint: str = Field(min_length=1, max_length=128)
    exception_type: Optional[str] = Field(default=None, max_length=256)
    message: Optional[str] = Field(default=None, max_length=1000)
    #: Hard cap on stack length. Untrusted text from a client, and a 40 MB
    #: traceback is both a storage problem and a prompt-injection vector once it
    #: reaches a scan.
    stack_trace: Optional[str] = Field(default=None, max_length=20000)
    fatal: bool = True
    app_version: Optional[str] = Field(default=None, max_length=32)
    os_version: Optional[str] = Field(default=None, max_length=32)
    device_model: Optional[str] = Field(default=None, max_length=64)
    foreground: bool = True


class SecuritySignal(BaseModel):
    """A client-observed security signal (root, emulator, tampering).

    Recorded as an observation with a boolean `blocked`. It is never used to
    refuse a request: these checks are defeated in minutes on a rooted device,
    so gating on them mostly generates support tickets about the security feature
    working as designed.
    """

    platform: str = Field(default="android", max_length=16)
    #: root_detected, emulator_detected, tamper_detected.
    kind: str = Field(min_length=1, max_length=48)
    session_id: Optional[str] = Field(default=None, max_length=64)
    app_version: Optional[str] = Field(default=None, max_length=32)
    blocked: bool = False
    detail: dict[str, Any] = Field(default_factory=dict)