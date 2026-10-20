"""The reactor: the only way a suggestion becomes a work item.

The model proposes; the reactor decides. `propose()` takes an action, a
target and a rationale, and:

1. **Checks the action against the closed enum.** An action that is not on
   the list is rejected, logged and dropped. The model never gets to invent
   a procedure.
2. **Records the proposal idempotently.** The work item is keyed on
   (scan, action, target), so the same suggestion twice is one row, and the
   second call returns the first one's result instead of duplicating it.
3. **Runs the whitelisted procedure.** Deterministic, logged, and - for
   everything that touches production - advisory: the payload says what a
   human should do, how to check it and how to undo it. The reactor does not
   change production, and it never pretends to have.
4. **Writes the audit rows.** Every invocation writes a row in
   `telemetry.tool_call_audit` with `proposal_state` = proposed | executed |
   rejected, so the trail shows what happened to every suggestion.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Optional

from sqlmodel import Session, select

from features.monitoring.domain.models import ReactorProposal
from mcp.core.redact import redact_value, salt_for
from mcp.core.registry import write_audit
from mcp.reactor.procedures import ALLOWED_ACTIONS, Procedure, procedure_for

logger = logging.getLogger(__name__)

#: The states a proposal can be in. They are the same words the audit rows
#: carry, so the trail and the work item always agree.
STATE_PROPOSED = "proposed"
STATE_EXECUTED = "executed"
STATE_REJECTED = "rejected"

#: A target is a short pointer ("/api/feedback", "fp-1a2b"). Long targets are
#: truncated: the work item is a pointer, not a payload.
MAX_TARGET_LENGTH = 200
MAX_DETAIL_LENGTH = 800


class ProposalRejected(RuntimeError):
    """The suggestion is not something the reactor will act on."""


@dataclass(frozen=True)
class ProposalOutcome:
    """What happened to a suggestion."""

    state: str
    action: str
    target: str
    detail: str
    proposal_id: Optional[int]
    procedure: dict[str, Any]
    #: True when the proposal was already recorded (the idempotent path).
    duplicate: bool = False

    @property
    def rejected(self) -> bool:
        return self.state == STATE_REJECTED


def _target_key(scan_id: str, action: str, target: str) -> str:
    """The idempotency key: same scan, same action, same target."""
    digest = hashlib.sha256(f"{action}:{target}".encode()).hexdigest()[:32]
    return digest


def _audit(
    session: Session,
    *,
    scan_id: str,
    action: str,
    target: str,
    state: str,
    detail: str,
    proposal_id: Optional[int],
    salt: str,
) -> None:
    write_audit(
        session,
        scan_id=scan_id,
        tool="reactor.propose",
        args={
            "action": action,
            "target": target,
            "state": state,
            "detail": detail[:MAX_DETAIL_LENGTH],
        },
        metric_key=None,
        metric_value=None,
        row_count=1,
        duration_ms=0,
        ok=(state != STATE_REJECTED),
        error=detail if state == STATE_REJECTED else None,
        sent_to=None,
        redactions_applied=0,
        bytes_out=0,
        redaction_salt=salt,
        proposal_state=state,
        proposal_id=proposal_id,
    )


def propose(
    session: Session,
    *,
    scan_id: str,
    action: Any,
    target: str,
    detail: str = "",
    subsection: str | None = None,
) -> ProposalOutcome:
    """Record one proposal. Raises `ProposalRejected` for a refused action.

    The rejection is also audited before the exception is raised: a refused
    suggestion is exactly the thing an operator needs to see.
    """
    salt = salt_for(scan_id)
    raw_action = action.value if hasattr(action, "value") else str(action or "")
    redacted_target, _ = redact_value(str(target or ""), salt)
    redacted_detail, _ = redact_value(str(detail or ""), salt)
    clean_target = str(redacted_target)[:MAX_TARGET_LENGTH]
    clean_detail = str(redacted_detail)[:MAX_DETAIL_LENGTH]

    procedure: Optional[Procedure] = procedure_for(action)
    if procedure is None:
        reason = (
            f"action {raw_action!r} is not one of the allowed actions "
            f"({', '.join(ALLOWED_ACTIONS)}) - rejected"
        )
        _audit(
            session,
            scan_id=scan_id,
            action=raw_action[:64],
            target=clean_target,
            state=STATE_REJECTED,
            detail=reason,
            proposal_id=None,
            salt=salt,
        )
        raise ProposalRejected(reason)

    if not clean_target.strip():
        reason = "proposal has no target - rejected"
        _audit(
            session,
            scan_id=scan_id,
            action=procedure.action.value,
            target="",
            state=STATE_REJECTED,
            detail=reason,
            proposal_id=None,
            salt=salt,
        )
        raise ProposalRejected(reason)

    key = _target_key(scan_id, procedure.action.value, clean_target)
    existing = session.exec(
        select(ReactorProposal).where(
            ReactorProposal.scan_id == scan_id,
            ReactorProposal.action == procedure.action.value,
            ReactorProposal.target_key == key,
        )
    ).first()
    if existing is not None:
        # Idempotent: the same suggestion is the same work item. The
        # procedure is deterministic, so there is nothing to redo.
        _audit(
            session,
            scan_id=scan_id,
            action=existing.action,
            target=existing.target,
            state=existing.state,
            detail="already recorded - no duplicate created",
            proposal_id=existing.id,
            salt=salt,
        )
        return ProposalOutcome(
            state=existing.state,
            action=existing.action,
            target=existing.target,
            detail=existing.detail,
            proposal_id=existing.id,
            procedure=existing.procedure or {},
            duplicate=True,
        )

    payload = {
        "steps": list(procedure.steps),
        "verify": list(procedure.verify),
        "rollback": list(procedure.rollback),
        "requires_operator": procedure.requires_operator,
        "urgency": procedure.urgency,
        "notes": procedure.notes,
        "action": procedure.action.value,
    }
    state = STATE_PROPOSED if procedure.requires_operator else STATE_EXECUTED

    proposal = ReactorProposal(
        scan_id=scan_id,
        action=procedure.action.value,
        target_key=key,
        target=clean_target,
        state=state,
        detail=clean_detail,
        procedure=payload,
    )
    session.add(proposal)
    session.commit()
    session.refresh(proposal)

    _audit(
        session,
        scan_id=scan_id,
        action=proposal.action,
        target=proposal.target,
        state=state,
        detail=clean_detail or procedure.notes,
        proposal_id=proposal.id,
        salt=salt,
    )
    logger.info(
        "proposal %s recorded for scan %s (%s)",
        proposal.id,
        scan_id,
        proposal.action,
    )
    return ProposalOutcome(
        state=state,
        action=proposal.action,
        target=proposal.target,
        detail=proposal.detail,
        proposal_id=proposal.id,
        procedure=payload,
    )


def propose_from_result(
    session: Session,
    result: Any,
    *,
    scan_id: str | None = None,
) -> list[ProposalOutcome]:
    """Record every recommended action of a scan verdict.

    A refused action does not stop the others: each one is proposed on its
    own merits, and the refusals are audited as refusals.
    """
    resolved_scan_id = scan_id or getattr(result, "scan_id", "")
    outcomes: list[ProposalOutcome] = []
    for recommendation in getattr(result, "recommended_actions", []) or []:
        action = getattr(recommendation, "action", None)
        target = _target_from(recommendation)
        detail = getattr(recommendation, "detail", "") or ""
        try:
            outcomes.append(
                propose(
                    session,
                    scan_id=resolved_scan_id,
                    action=action,
                    target=target,
                    detail=detail,
                )
            )
        except ProposalRejected:
            # Already audited inside propose(); the refusal stands on its own.
            continue
    return outcomes


def _target_from(recommendation: Any) -> str:
    """The work item's target: the first evidence reference, or the action."""
    refs = getattr(recommendation, "evidence_refs", []) or []
    if refs:
        return str(refs[0])
    return str(getattr(recommendation, "action", "") or "")
