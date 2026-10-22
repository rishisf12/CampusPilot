"""The scan subsections the admin console offers.

Four web subsections, in the order the console shows them. The Android
halves went with the Android client: a subsection with no writer would
report "awaiting first data" forever, which is a fact nobody can act on.

The list lives here rather than inside either router because two routers
need it - the MCP panel surface serves it to the UI, and the monitoring
export endpoint validates against it - and the two must agree. If they
drifted, the console would offer a subsection the export then refuses.
"""
from __future__ import annotations

SUBSECTIONS: tuple[dict[str, str], ...] = (
    {"id": "A_W_HEALTH", "platform": "web", "group": "Web App Monitoring", "title": "Health & Performance"},
    {"id": "B_W_ACTIVITY", "platform": "web", "group": "Web App Monitoring", "title": "User Activity"},
    {"id": "C_W_SECURITY", "platform": "web", "group": "Web App Monitoring", "title": "Security Monitoring"},
    {"id": "D_W_FEEDBACK", "platform": "web", "group": "Web App Monitoring", "title": "Feedback Analysis"},
)

#: The ids, for the membership checks the endpoints do.
SUBSECTION_IDS: frozenset[str] = frozenset(s["id"] for s in SUBSECTIONS)

__all__ = ["SUBSECTIONS", "SUBSECTION_IDS"]
