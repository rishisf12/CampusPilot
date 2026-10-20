"""Tests for the reactor (Phase 6).

The contract under test:

1. **The model cannot invent a procedure.** An action outside the closed
   enum is rejected, audited as a rejection, and leaves no work item.
2. **Every proposal invocation is audited** with its state: proposed,
   executed or rejected.
3. **Proposals are idempotent.** The same suggestion in the same scan is one
   work item, not two.
4. **The reactor does not act.** The procedures are advisory - the payload
   says what a human should do - and nothing here changes production.
"""
import pytest
from sqlmodel import Session, delete, select

from core.database import engine
from features.monitoring.domain.models import ReactorProposal, ToolCallAudit
from mcp.reactor import (
    ALLOWED_ACTIONS,
    STATE_EXECUTED,
    STATE_PROPOSED,
    STATE_REJECTED,
    ProposalRejected,
    propose,
    propose_from_result,
)


@pytest.fixture
def db_session():
    with Session(engine) as session:
        for model in (ReactorProposal, ToolCallAudit):
            session.exec(delete(model))
        session.commit()
        yield session
        for model in (ReactorProposal, ToolCallAudit):
            session.exec(delete(model))
        session.commit()


def _audit_rows(session):
    return session.exec(select(ToolCallAudit)).all()


# --- the closed catalogue ----------------------------------------------------


def test_every_allowed_action_has_a_procedure():
    from mcp.reactor.procedures import PROCEDURES

    assert len(ALLOWED_ACTIONS) == 11
    assert set(ALLOWED_ACTIONS) == {a.value for a in PROCEDURES}
    for procedure in PROCEDURES.values():
        assert procedure.steps, procedure.action
        assert procedure.verify, procedure.action


def test_an_action_outside_the_enum_is_rejected(db_session):
    with pytest.raises(ProposalRejected, match="not one of the allowed actions"):
        propose(
            db_session,
            scan_id="scan-reactor-1",
            action="drop_all_students",
            target="core.user",
        )
    # No work item, and the refusal is on the record.
    assert db_session.exec(select(ReactorProposal)).all() == []
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].proposal_state == STATE_REJECTED
    assert rows[0].ok is False
    assert "drop_all_students" in (rows[0].error or "")


def test_a_proposal_without_a_target_is_rejected(db_session):
    with pytest.raises(ProposalRejected, match="no target"):
        propose(db_session, scan_id="scan-reactor-2", action="scale_worker", target="  ")
    assert db_session.exec(select(ReactorProposal)).all() == []
    assert _audit_rows(db_session)[0].proposal_state == STATE_REJECTED


# --- the work item -----------------------------------------------------------


def test_a_proposal_is_recorded_and_audited(db_session):
    outcome = propose(
        db_session,
        scan_id="scan-reactor-3",
        action="investigate_endpoint",
        target="/api/feedback",
        detail="p95 is 900 ms on the feedback endpoint",
    )
    assert outcome.state == STATE_PROPOSED
    assert outcome.proposal_id is not None
    assert outcome.action == "investigate_endpoint"
    # The procedure is advisory: steps, verification, no automatic action.
    assert outcome.procedure["steps"]
    assert outcome.procedure["verify"]
    assert outcome.procedure["requires_operator"] is True

    stored = db_session.exec(select(ReactorProposal)).all()
    assert len(stored) == 1
    assert stored[0].state == STATE_PROPOSED
    assert stored[0].target == "/api/feedback"

    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].tool == "reactor.propose"
    assert rows[0].proposal_state == STATE_PROPOSED
    assert rows[0].proposal_id == stored[0].id


def test_no_action_needs_no_operator(db_session):
    outcome = propose(
        db_session,
        scan_id="scan-reactor-4",
        action="no_action",
        target="all-good",
    )
    assert outcome.state == STATE_EXECUTED
    assert outcome.procedure["requires_operator"] is False


def test_proposals_are_idempotent(db_session):
    first = propose(
        db_session,
        scan_id="scan-reactor-5",
        action="investigate_endpoint",
        target="/api/feedback",
    )
    second = propose(
        db_session,
        scan_id="scan-reactor-5",
        action="investigate_endpoint",
        target="/api/feedback",
    )
    assert second.duplicate is True
    assert second.proposal_id == first.proposal_id
    # One work item, two audit rows (the second says it was already there).
    assert len(db_session.exec(select(ReactorProposal)).all()) == 1
    assert len(_audit_rows(db_session)) == 2
    assert all(r.proposal_state == STATE_PROPOSED for r in _audit_rows(db_session))


def test_the_same_target_in_another_scan_is_a_separate_item(db_session):
    propose(
        db_session,
        scan_id="scan-reactor-6a",
        action="investigate_endpoint",
        target="/api/feedback",
    )
    propose(
        db_session,
        scan_id="scan-reactor-6b",
        action="investigate_endpoint",
        target="/api/feedback",
    )
    assert len(db_session.exec(select(ReactorProposal)).all()) == 2


def test_the_target_and_detail_are_redacted(db_session):
    outcome = propose(
        db_session,
        scan_id="scan-reactor-7",
        action="investigate_endpoint",
        target="/api/feedback?email=student@campus.edu",
        detail="the caller was +91 98765 43210",
    )
    assert "student@campus.edu" not in outcome.target
    assert "98765 43210" not in outcome.detail
    assert "[email]" in outcome.target


# --- from a verdict ----------------------------------------------------------


def test_the_schema_itself_refuses_an_action_outside_the_enum():
    """The first line of defence: the verdict schema will not hold one."""
    from pydantic import ValidationError

    from features.monitoring.api.schemas import Recommendation

    with pytest.raises(ValidationError):
        Recommendation(
            action="delete_everything",  # type: ignore[arg-type]
            priority=1,
            detail="not a real action",
        )


def test_proposals_from_a_verdict_record_every_allowed_action(db_session):
    from types import SimpleNamespace

    from features.monitoring.api.schemas import Recommendation, ScanResult as Schema
    from features.monitoring.api.schemas import Action as SchemaAction
    from features.monitoring.api.schemas import Status

    verdict = Schema(
        scan_id="scan-reactor-8",
        subsection="A_W_HEALTH",
        status=Status.WARNING,
        summary="A verdict with one recommendation worth recording.",
        findings=[],
        recommended_actions=[
            Recommendation(
                action=SchemaAction.INVESTIGATE_ENDPOINT,
                priority=1,
                detail="p95 is 900 ms",
                evidence_refs=["/api/feedback"],
            ),
        ],
        confidence={"level": "medium"},
    )
    outcomes = propose_from_result(db_session, verdict)
    assert len(outcomes) == 1
    assert outcomes[0].action == "investigate_endpoint"
    assert _audit_rows(db_session)[0].proposal_state == STATE_PROPOSED


def test_a_verdict_built_outside_the_schema_is_still_filtered(db_session):
    """The reactor's own check: the path around the schema is guarded too."""
    from types import SimpleNamespace

    verdict = SimpleNamespace(
        scan_id="scan-reactor-9",
        recommended_actions=[
            SimpleNamespace(
                action="delete_everything",
                detail="not a real action",
                evidence_refs=["core.user"],
            )
        ],
    )
    outcomes = propose_from_result(db_session, verdict)
    assert outcomes == []
    rows = _audit_rows(db_session)
    assert len(rows) == 1
    assert rows[0].proposal_state == STATE_REJECTED
    assert db_session.exec(select(ReactorProposal)).all() == []
