#!/usr/bin/env python3
"""Record one end-to-end scan, and show the trail it left.

The point is not the verdict - it is the evidence. After the scan this
prints the `tool_call_audit` rows: which tool ran, what it answered, how
much was masked, how many bytes went out, and to which provider.

With a provider key in the environment the model call is real. Without
one the call is stubbed and the transcript says so - everything up to and
including the wire payload is still real, because that is where the
guarantees live.

    python scripts/demo_scan.py --subsection A_W_HEALTH
    python scripts/demo_scan.py --provider openrouter --write docs/observability/DEMO-SCAN.md
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_ROOT = REPO_ROOT / "backend" / "app"


def _app_on_path() -> None:
    if str(APP_ROOT) not in sys.path:
        sys.path.insert(0, str(APP_ROOT))


def _provider_ready(provider: str) -> bool:
    """Is there a credential for this provider?"""
    if provider == "nvidia_nim":
        return bool(os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVIDIA_NIM_API_KEY"))
    if provider == "openrouter":
        return bool(os.environ.get("OPENROUTER_API_KEY"))
    return False


async def _real_chat(messages):
    """The real thing: the egress-gated gateway, telemetry job kind."""
    from mcp.core.llm import chat as gateway_chat

    response = await gateway_chat(
        _SESSION,
        job_kind="telemetry",
        provider=_PROVIDER,
        messages=messages,
        scan_id=_SCAN_ID,
    )
    return getattr(response, "text", response)


class _StubClient:
    """A provider client that answers without a network.

    The demo still goes through the real gateway - the job gate, the
    redaction, the byte counting and the outbound audit row are all real.
    Only the HTTP request is replaced, so the demo can run without a
    provider key.
    """

    name = "stub"

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.sent: list = []

    async def chat(self, messages, temperature=0.1, max_tokens=4096, response_format=None):
        self.sent.append(messages)
        return type("R", (), {"text": self.reply, "provider": _PROVIDER, "model": "demo"})()


def _stub_chat():
    """A stand-in model: it cites the numbers it was actually given.

    Used when no provider key is configured, so the demo still shows the
    real tool output, the real redaction and the real audit trail.
    """

    async def chat(messages):
        payload = json.loads(messages[1]["content"])
        outputs = payload.get("tool_output") or []
        evidence = []
        for output in outputs[:2]:
            value = _first_number(output.get("data"))
            if value is None:
                continue
            evidence.append(
                {
                    "metric": output.get("metric_key"),
                    "value": value,
                    "unit": "count",
                    "window": "7d",
                    "source": output.get("tool"),
                }
            )
        if not evidence:
            evidence = [
                {
                    "metric": "telemetry_health_7d_web",
                    "value": 0.0,
                    "unit": "count",
                    "window": "7d",
                    "source": "telemetry_health",
                }
            ]
        return {
            "status": "healthy",
            "summary": (
                "Demo scan: the measured signals in this window are inside their "
                "thresholds, and every number below came from a tool call."
            ),
            "findings": [
                {
                    "title": "Measured signal within budget",
                    "severity": "info",
                    "evidence": evidence,
                }
            ],
            "root_causes": [],
            "recommended_actions": [],
            "confidence": {"level": "high"},
        }

    return chat


def _first_number(data):
    if isinstance(data, dict):
        for value in data.values():
            found = _first_number(value)
            if found is not None:
                return found
    elif isinstance(data, list):
        for item in data:
            found = _first_number(item)
            if found is not None:
                return found
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        return float(data)
    return None


def _stubbed_gateway_chat():
    """The real gateway, with the provider's HTTP call replaced.

    Everything the demo is meant to show - the job gate, the redaction of
    the prompt, the byte count, the outbound audit row - happens for real.
    """

    async def chat(messages):
        from mcp.core.llm import chat as gateway_chat

        reply = _stub_reply(messages)
        response = await gateway_chat(
            _SESSION,
            job_kind="telemetry",
            provider=_PROVIDER,
            messages=messages,
            scan_id=_SCAN_ID,
            client=_StubClient(reply),
        )
        return getattr(response, "text", response)

    return chat


def _stub_reply(messages) -> str:
    """The body a stand-in model would return, citing the numbers it was given."""
    payload = json.loads(messages[1]["content"])
    outputs = payload.get("tool_output") or []
    evidence = []
    for output in outputs[:2]:
        value = _first_number(output.get("data"))
        if value is None:
            continue
        evidence.append(
            {
                "metric": output.get("metric_key"),
                "value": value,
                "unit": "count",
                "window": "7d",
                "source": output.get("tool"),
            }
        )
    if not evidence:
        evidence = [
            {
                "metric": "telemetry_health_7d_web",
                "value": 0.0,
                "unit": "count",
                "window": "7d",
                "source": "telemetry_health",
            }
        ]
    return json.dumps(
        {
            "status": "healthy",
            "summary": (
                "Demo scan: the measured signals in this window are inside their "
                "thresholds, and every number below came from a tool call."
            ),
            "findings": [
                {
                    "title": "Measured signal within budget",
                    "severity": "info",
                    "evidence": evidence,
                }
            ],
            "root_causes": [],
            "recommended_actions": [],
            "confidence": {"level": "high"},
        }
    )


_SESSION = None
_PROVIDER = "nvidia_nim"
_SCAN_ID = "demo-scan"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subsection", default="A_W_HEALTH")
    parser.add_argument("--provider", default="nvidia_nim")
    parser.add_argument("--write", help="write the transcript to this file")
    args = parser.parse_args(argv)

    global _SESSION, _PROVIDER, _SCAN_ID
    _app_on_path()
    _PROVIDER = args.provider
    _SCAN_ID = f"demo-{args.subsection.lower()}-{int(datetime.now(timezone.utc).timestamp())}"

    from sqlmodel import Session

    from core.database import engine
    from features.monitoring.domain.models import ToolCallAudit
    from mcp.agent import run_scan

    real = _provider_ready(args.provider)
    if real:
        chat = _real_chat
    else:
        # The gateway is still the one that sends: only the HTTP call is
        # replaced, so the outbound audit row (provider, bytes, mask count)
        # is the real one.
        chat = _stubbed_gateway_chat()

    with Session(engine) as session:
        _SESSION = session
        result = asyncio.run(
            run_scan(
                session,
                subsection=args.subsection,
                scan_id=_SCAN_ID,
                provider=args.provider,
                chat=chat,
                store=True,
            )
        )
        rows = session.exec(
            select_tool_audit(session, _SCAN_ID)
        ).all()

    lines = []
    lines.append(f"# Demo scan - {args.subsection}")
    lines.append("")
    lines.append(f"- scan id: `{_SCAN_ID}`")
    lines.append(f"- recorded: {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    lines.append(f"- provider: `{args.provider}`")
    lines.append(
        "- model call: "
        + ("**real** (a provider key was configured)" if real else "**stubbed** (no provider key in this environment; the tool output, the redaction and the audit trail below are real)")
    )
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- status: **{result.status.value}**")
    lines.append(f"- summary: {result.summary}")
    for finding in result.findings:
        lines.append(f"- finding: {finding.title} ({finding.severity})")
        for evidence in finding.evidence:
            lines.append(
                f"  - `{evidence.metric}` = {evidence.value} {evidence.unit} "
                f"(source: {evidence.source})"
            )
    lines.append("")
    lines.append("## The trail it left (`telemetry.tool_call_audit`)")
    lines.append("")
    lines.append("| tool | metric_key | ok | bytes_out | redactions | sent_to |")
    lines.append("|---|---|---|---|---|---|")
    for row in rows:
        lines.append(
            f"| `{row.tool}` | `{row.metric_key or ''}` | {row.ok} | "
            f"{row.bytes_out} | {row.redactions_applied} | {row.sent_to or '-'} |"
        )
    lines.append("")
    lines.append(
        "Every tool call is redacted before it is returned, the run has one salt "
        "so pseudonyms line up across rows, and an outbound request names the "
        "provider it went to and the size of the payload that left."
    )
    transcript = "\n".join(lines) + "\n"

    print(transcript)
    if args.write:
        path = pathlib.Path(args.write)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(transcript, encoding="utf-8")
        print(f"written to {path}")
    return 0


def select_tool_audit(session, scan_id: str):
    from sqlmodel import select

    from features.monitoring.domain.models import ToolCallAudit

    return select(ToolCallAudit).where(ToolCallAudit.scan_id == scan_id)


if __name__ == "__main__":
    sys.exit(main())
