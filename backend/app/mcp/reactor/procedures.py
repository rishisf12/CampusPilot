"""The action catalogue: what the reactor is allowed to do about a finding.

Every remediation the model may suggest comes from the closed `Action` enum
(`features.monitoring.api.schemas.Action`). Each action maps to exactly one
procedure here, and a procedure is:

- **deterministic** — the same action and target always produce the same
  payload, so re-running it changes nothing;
- **idempotent** — the proposal row is keyed on (scan, action, target), so
  the same suggestion twice is one work item;
- **logged** — every invocation writes an audit row stating what it did.

None of these procedures changes production on its own. The dangerous ones
(rotating credentials, rolling back a release, adding a rate limit, scaling
workers) say so explicitly: they produce the exact steps, the verification
and the undo, and a human runs them. That is the whole point of the
propose-not-execute rule — the model's judgement chooses *what* to look at;
it never gets to *do* it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from features.monitoring.api.schemas import Action


@dataclass(frozen=True)
class Procedure:
    """One action's playbook."""

    action: Action
    #: What the operator should do, in order.
    steps: tuple[str, ...]
    #: How to know it worked.
    verify: tuple[str, ...]
    #: How to undo it. Empty when the action is not reversible.
    rollback: tuple[str, ...] = ()
    #: True when a human must carry it out. The reactor never flips this.
    requires_operator: bool = True
    #: How urgent this action is, for sorting a work list.
    urgency: int = 2
    #: Extra context the operator needs.
    notes: str = ""


def _procedure(
    action: Action,
    steps: tuple[str, ...],
    verify: tuple[str, ...],
    rollback: tuple[str, ...] = (),
    requires_operator: bool = True,
    urgency: int = 2,
    notes: str = "",
) -> Procedure:
    return Procedure(
        action=action,
        steps=steps,
        verify=verify,
        rollback=rollback,
        requires_operator=requires_operator,
        urgency=urgency,
        notes=notes,
    )


#: The closed map. A suggestion whose action is not a key here is not
#: something this system knows how to do, and it is refused.
PROCEDURES: dict[Action, Procedure] = {
    Action.NO_ACTION: _procedure(
        Action.NO_ACTION,
        steps=("No action required; record the scan and move on.",),
        verify=("The finding is explained by the measured numbers.",),
        rollback=(),
        requires_operator=False,
        urgency=3,
        notes="Nothing to do - the point of proposing this is to say so.",
    ),
    Action.SCALE_WORKER: _procedure(
        Action.SCALE_WORKER,
        steps=(
            "Check CPU, request latency and queue depth over the last hour.",
            "Add a worker instance and watch p95 latency for 15 minutes.",
            "If latency does not improve, remove the instance again.",
        ),
        verify=("p95 latency and CPU settle back inside the healthy band.",),
        rollback=("Remove the added instance; nothing else is touched.",),
        urgency=2,
        notes="The reactor does not scale anything itself - a human adds the worker.",
    ),
    Action.ROLLBACK_RELEASE: _procedure(
        Action.ROLLBACK_RELEASE,
        steps=(
            "Confirm the regression started with the release named in the finding.",
            "Check whether the previous release is still deployable.",
            "Roll the deployment back to that release.",
        ),
        verify=("The metric that triggered this returns to its previous level.",),
        rollback=("Re-deploy the newer release once the cause is understood.",),
        urgency=1,
        notes="A rollback is a human decision: it trades a bug for an older one.",
    ),
    Action.INVESTIGATE_ENDPOINT: _procedure(
        Action.INVESTIGATE_ENDPOINT,
        steps=(
            "Pull the endpoint's p95, p99 and error count for the window.",
            "Look for a slow query or an N+1 in the request path.",
            "Capture a slow-request sample before changing anything.",
        ),
        verify=("The endpoint's p95 is back inside the healthy band.",),
        rollback=(),
        urgency=2,
        notes="Read-only investigation: no change is implied by this action.",
    ),
    Action.TRIAGE_CRASH_CLUSTER: _procedure(
        Action.TRIAGE_CRASH_CLUSTER,
        steps=(
            "Open the crash fingerprint and the affected app versions.",
            "Reproduce on the oldest affected version first.",
            "File a bug with the fingerprint, the version and the session count.",
        ),
        verify=("Crash count for the fingerprint stops growing.",),
        rollback=(),
        urgency=1,
        notes="The stack trace stays in the crash store; it is not copied around.",
    ),
    Action.ROTATE_CREDENTIALS: _procedure(
        Action.ROTATE_CREDENTIALS,
        steps=(
            "Identify the credential involved and who owns it.",
            "Issue a new secret and update the deployment's environment.",
            "Revoke the old secret and confirm the service still starts.",
        ),
        verify=("The service authenticates with the new secret; the old one fails.",),
        rollback=("Re-issue and redeploy the previous secret if the swap fails.",),
        urgency=1,
        notes="Never automatic: rotating a credential can lock out a human.",
    ),
    Action.ADD_RATE_LIMIT: _procedure(
        Action.ADD_RATE_LIMIT,
        steps=(
            "Confirm the traffic pattern is abusive rather than a real user base.",
            "Set a limit above the observed peak, with a burst allowance.",
            "Watch the error rate for 30 minutes after applying it.",
        ),
        verify=("The abusive pattern is throttled and real traffic is unaffected.",),
        rollback=("Remove the limit; the previous configuration is recorded.",),
        urgency=2,
        notes="A rate limit that is set too low locks out real students.",
    ),
    Action.REVIEW_RECENT_CHANGES: _procedure(
        Action.REVIEW_RECENT_CHANGES,
        steps=(
            "List the commits and deploys in the window.",
            "Compare them with the first bad measurement.",
            "Note which change plausibly explains the movement.",
        ),
        verify=("A candidate change is identified, or ruled out.",),
        rollback=(),
        urgency=2,
        notes="The cheapest action to run and the one that most often explains the rest.",
    ),
    Action.FIX_BLOCKING_BUG: _procedure(
        Action.FIX_BLOCKING_BUG,
        steps=(
            "Reproduce the blocking behaviour with the numbers from the finding.",
            "Fix the smallest cause that explains it.",
            "Ship behind a flag if the fix is not obviously safe.",
        ),
        verify=("The blocking behaviour is gone in the next release.",),
        rollback=("Turn the flag off; the previous behaviour returns.",),
        urgency=1,
        notes="A code change, which is exactly why the model only ever proposes it.",
    ),
    Action.CONTACT_STORE: _procedure(
        Action.CONTACT_STORE,
        steps=(
            "Check whether the store has acknowledged the affected release.",
            "Draft the report with the affected versions and the purchase count.",
            "Send it through the normal store channel.",
        ),
        verify=("The store acknowledges the report.",),
        rollback=(),
        urgency=2,
        notes="Nothing is sent automatically - an account contact is a human act.",
    ),
    Action.INVESTIGATE_DATA_PIPELINE: _procedure(
        Action.INVESTIGATE_DATA_PIPELINE,
        steps=(
            "Check the newest event and crash timestamps for a freshness gap.",
            "Check the collector's error count for the window.",
            "Compare the pipeline's throughput with the previous window.",
        ),
        verify=("Data is fresh again and the gap is explained.",),
        rollback=(),
        urgency=1,
        notes="A stale pipeline makes every other number in the scan a lie.",
    ),
}

#: The action names the model may use, for error messages and for the
#: prompt that tells it what exists.
ALLOWED_ACTIONS = tuple(action.value for action in PROCEDURES)


def procedure_for(action: Any) -> Procedure:
    """The procedure for an action, or None when the action is not on the list.

    The comparison is on the *value*, not the enum member: a model sends the
    string "scale_worker", and a caller may pass the enum member. Anything
    else - including an action that looks similar - is not in the map.
    """
    if isinstance(action, Action):
        return PROCEDURES.get(action)
    if not isinstance(action, str):
        return None
    try:
        member = Action(action.strip().lower())
    except ValueError:
        return None
    return PROCEDURES.get(member)
