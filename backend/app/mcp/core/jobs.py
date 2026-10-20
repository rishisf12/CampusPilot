"""Job kinds and the gate that decides what may talk to a model.

Two kinds of work use a language model in this codebase, and they are not
allowed to look alike:

``telemetry``
    Monitoring work over the product's own data. Its context can contain
    student rows, feedback text and identifiers, so it must pass the egress
    gate (`mcp.core.redact`) before anything leaves the building. A telemetry
    job that cannot prove the gate is wired **refuses to start** — it does
    not start "carefully" and it sends nothing.

``public_data``
    Work over public information (the OppFeed discovery agent). Nothing
    private is in scope, so it may use any allowlisted provider freely. It
    still never gets a write tool and still never gets a shell.

The gate is deliberately boring and server-side: a job announces its kind and
provider, `validate_job` answers yes or no, and the answer is the same for
every caller. `egress_selfcheck` is the proof of the proof — it runs the
egress path on a canary and refuses if the canary survives.
"""
from __future__ import annotations

from dataclasses import dataclass

from llms import ALLOWED_PROVIDERS, JOB_KINDS

#: The canary the egress self-check runs through the real path. If this
#: string ever comes back unmasked, the gate is not wired and telemetry work
#: must not run.
_CANARY = "canary.check@example.invalid"


class JobRefused(RuntimeError):
    """The job may not run as configured. Nothing was sent."""


@dataclass(frozen=True)
class JobContext:
    """A job that passed the gate."""

    job_kind: str
    provider: str
    scan_id: str
    #: The per-run salt: shared by every call of this run, so pseudonyms are
    #: stable inside it and unlinkable outside it.
    salt: str


def egress_selfcheck(session, scan_id: str = "egress-selfcheck") -> bool:
    """True when the egress gate demonstrably redacts.

    The strong form of the check: it runs the *actual* egress path —
    `run_tool` and its redaction wiring — over a canary string, so a
    refactor that quietly unplugs redaction is caught at job start instead
    of at the incident review. The check leaves an audit row of its own, so
    the log shows when the gate was last proven.

    `registry.redaction_wired()` is the cheap sessionless pre-flight (source
    tripwire plus a masking probe); this one is the end-to-end proof.
    """
    from mcp.core import redact
    from mcp.core.registry import ToolRegistry, ToolResult, ToolSpec, run_tool

    def _canary_tool(session, **kwargs):  # noqa: ARG001 - the canary reads nothing
        return ToolResult(data={"note": _CANARY}, row_count=1, metric_key="canary")

    registry = ToolRegistry()
    registry.register(ToolSpec(name="__egress_canary"), _canary_tool)
    result = run_tool(
        session,
        registry,
        scan_id=scan_id,
        subsection="A_W_HEALTH",
        name="__egress_canary",
    )
    text = str(result.data)
    return _CANARY not in text and redact.EMAIL_MASK in text


def validate_job(
    *,
    job_kind: str,
    provider: str,
    scan_id: str,
    salt: str,
    session,
) -> JobContext:
    """Approve or refuse a job. Raises `JobRefused` — never sends anything.

    The order matters: the provider is checked first (a paid provider is
    refused whatever the job kind), then the egress gate for telemetry work.
    """
    if job_kind not in JOB_KINDS:
        raise JobRefused(
            f"job kind {job_kind!r} is not one of {sorted(JOB_KINDS)}"
        )
    if provider not in ALLOWED_PROVIDERS:
        raise JobRefused(
            f"provider {provider!r} is not on the free allowlist "
            f"({sorted(ALLOWED_PROVIDERS)}) - refusing to start the job"
        )
    if job_kind == "telemetry":
        from mcp.core.registry import redaction_wired

        if not redaction_wired():
            raise JobRefused(
                "telemetry job refused: the egress gate is not wired "
                "(redaction self-check failed) - no request was sent"
            )
        if not egress_selfcheck(session, scan_id=scan_id):
            raise JobRefused(
                "telemetry job refused: the egress gate did not mask a canary "
                "end to end - no request was sent"
            )
    return JobContext(
        job_kind=job_kind, provider=provider, scan_id=scan_id, salt=salt
    )
