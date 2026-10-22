"""The scan agent's prompts.

Two things the agent needs before it can ask a model anything: the system
prompt (the contract from `docs/observability/SCAN-AGENT.md`) and the
per-subsection focus line that narrows it.

They live here rather than with the monitoring feature because they belong
to the agent: the prompts describe the tool contract the agent runs under,
and the agent is what runs them. The legacy Stage 2 client that used to
carry them is gone - `mcp.core.llm` is the one outbound path now, and it
redacts, audits and fails over.
"""
from __future__ import annotations

import pathlib
import re

#: Where the authoritative prompt lives. Read at call time rather than at
#: import time so an edited prompt does not need a restart to take effect.
PROMPT_PATH = (
    pathlib.Path(__file__).parent.parent.parent.parent
    / "docs"
    / "observability"
    / "SCAN-AGENT.md"
)

#: The section of SCAN-AGENT.md that holds the system prompt.
_SYSTEM_PROMPT_RE = re.compile(r"## 1\. System prompt\s*\n```text\n(.*?)\n```", re.DOTALL)

#: Used when the prompt file cannot be read - a missing file must not stop
#: a scan, and the fallback still carries the one rule that matters.
_FALLBACK_PROMPT = """You are a monitoring analyst for CampusPilot. Produce a structured status report per invocation.
You are given a subsection id and time window. Use the tools to gather data, compare current vs previous vs baseline, and return JSON matching the ScanResult schema.
NEVER invent numbers. Every finding must have evidence from a tool you actually called.
Output only valid JSON matching the schema."""


def load_system_prompt() -> str:
    """The agent's system prompt, from SCAN-AGENT.md."""
    try:
        content = PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_PROMPT
    match = _SYSTEM_PROMPT_RE.search(content)
    return match.group(1).strip() if match else _FALLBACK_PROMPT


#: Subsection-specific prompt suffixes.
SUBSECTION_PROMPTS = {
    "A_W_HEALTH": "Focus on: uptime, response time p95, 4xx/5xx rates, CPU/RAM/disk, SSL expiry, DB performance, slow endpoints.",
    "B_W_ACTIVITY": "Focus on: DAU/WAU/MAU, new vs returning, sessions, retention, top pages, funnels, geography, devices, traffic sources, revenue, ARPU, ad metrics.",
    "C_W_SECURITY": "Focus on: failed logins, brute force, suspicious IPs, WAF blocking, dependency CVEs, security headers, audit logs.",
    "D_W_FEEDBACK": "Focus on: sentiment, topic clustering, rating trends, volume, top complaints, correlation with crashes/releases.",
    "A_A_HEALTH": "Focus on: crash-free rate, crashes/ANRs with stack traces, startup time, slow frames, API failure rate, battery/memory, breakdown by app version/OS/device.",
    "B_A_ACTIVITY": "Focus on: DAU/WAU/MAU, new vs returning, sessions, retention, top screens, funnels, geography, devices, IAP revenue, ad events.",
    "C_A_SECURITY": "Focus on: root/emulator/tamper signals, API abuse, token misuse, APK tampering, dependency CVEs.",
    "D_A_FEEDBACK": "Focus on: in-app feedback sentiment, topics, ratings, correlation with crashes and releases.",
}

__all__ = ["PROMPT_PATH", "SUBSECTION_PROMPTS", "load_system_prompt"]
