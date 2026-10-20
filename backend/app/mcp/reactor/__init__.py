"""The reactor: proposals in, work items out - never actions.

`procedures` is the closed catalogue (an action the model may not invent
maps to exactly one deterministic playbook), and `executor` is the only path
from a suggestion to a recorded work item. A suggestion the catalogue does
not know is rejected and audited as a rejection.
"""
from mcp.reactor.executor import (
    STATE_EXECUTED,
    STATE_PROPOSED,
    STATE_REJECTED,
    ProposalOutcome,
    ProposalRejected,
    propose,
    propose_from_result,
)
from mcp.reactor.procedures import ALLOWED_ACTIONS, PROCEDURES, Procedure, procedure_for

__all__ = [
    "ALLOWED_ACTIONS",
    "PROCEDURES",
    "Procedure",
    "ProposalOutcome",
    "ProposalRejected",
    "STATE_EXECUTED",
    "STATE_PROPOSED",
    "STATE_REJECTED",
    "procedure_for",
    "propose",
    "propose_from_result",
]
