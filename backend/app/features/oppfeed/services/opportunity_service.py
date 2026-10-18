"""OppFeed Opportunity service — CampusPilot integration.

CRUD, versioning, state transitions, bulk operations.
Uses CampusPilot Session (SQLModel) and merged models.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from sqlmodel import Session, select

from features.oppfeed.models import (
    Opportunity,
    OpportunityStatus,
)
from features.oppfeed.schemas import (
    OpportunityUpdateRequest,
    StateTransitionRequest,
    BulkActionRequest,
)


# Valid state transitions (mirrors OppFeed logic)
VALID_TRANSITIONS = {
    OpportunityStatus.DRAFT: [OpportunityStatus.IN_REVIEW, OpportunityStatus.REJECTED],
    OpportunityStatus.IN_REVIEW: [
        OpportunityStatus.APPROVED,
        OpportunityStatus.REJECTED,
        OpportunityStatus.DRAFT,
    ],
    OpportunityStatus.APPROVED: [
        OpportunityStatus.PUBLISHED,
        OpportunityStatus.SCHEDULED,
        OpportunityStatus.REJECTED,
    ],
    OpportunityStatus.SCHEDULED: [
        OpportunityStatus.PUBLISHED,
        OpportunityStatus.REJECTED,
    ],
    OpportunityStatus.PUBLISHED: [
        OpportunityStatus.ARCHIVED,
        OpportunityStatus.EXPIRED,
    ],
    OpportunityStatus.REJECTED: [],
    OpportunityStatus.EXPIRED: [OpportunityStatus.ARCHIVED],
    OpportunityStatus.ARCHIVED: [],
}


class OpportunityService:
    """Service for opportunity business logic."""

    @staticmethod
    def list_opportunities(
        db: Session,
        status: Optional[OpportunityStatus] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> List[Opportunity]:
        """List opportunities with optional status filter."""
        stmt = select(Opportunity)
        if status:
            stmt = stmt.where(Opportunity.status == status)
        stmt = stmt.order_by(Opportunity.created_at.desc().nullslast())
        offset = (page - 1) * page_size
        return list(db.exec(stmt.offset(offset).limit(page_size)).all())

    @staticmethod
    def get_by_id(db: Session, opportunity_id: int) -> Optional[Opportunity]:
        """Get opportunity by ID."""
        return db.get(Opportunity, opportunity_id)

    @staticmethod
    def get_by_slug(db: Session, slug: str) -> Optional[Opportunity]:
        """Get opportunity by slug."""
        return db.exec(select(Opportunity).where(Opportunity.slug == slug)).first()

    @staticmethod
    def update_opportunity(
        db: Session,
        opportunity_id: int,
        update_data: OpportunityUpdateRequest,
    ) -> Opportunity:
        """Update an opportunity, bumping version."""
        opp = db.get(Opportunity, opportunity_id)
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")

        if opp.status not in (
            OpportunityStatus.DRAFT,
            OpportunityStatus.IN_REVIEW,
            OpportunityStatus.APPROVED,
        ):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot edit opportunity in {opp.status.value} status",
            )

        data = update_data.model_dump(exclude_unset=True)
        for field, value in data.items():
            if hasattr(opp, field):
                setattr(opp, field, value)

        opp.version += 1
        opp.updated_at = datetime.now(timezone.utc)
        db.add(opp)
        db.commit()
        db.refresh(opp)
        return opp

    @staticmethod
    def transition_status(
        db: Session,
        opportunity_id: int,
        new_status: OpportunityStatus,
        scheduled_publish_at: Optional[datetime] = None,
    ) -> Opportunity:
        """Transition opportunity to a new status with validation."""
        from features.oppfeed.models import Opportunity  # local import to avoid circular

        opp = db.get(Opportunity, opportunity_id)
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")

        valid_next = VALID_TRANSITIONS.get(opp.status, [])
        if new_status not in valid_next:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid transition: {opp.status.value} -> {new_status.value}. "
                       f"Valid transitions: {[s.value for s in valid_next]}",
            )

        opp.status = new_status
        if new_status == OpportunityStatus.PUBLISHED:
            opp.published_at = datetime.now(timezone.utc)
        if new_status == OpportunityStatus.SCHEDULED and scheduled_publish_at:
            opp.scheduled_publish_at = scheduled_publish_at

        opp.updated_at = datetime.now(timezone.utc)
        db.add(opp)
        db.commit()
        db.refresh(opp)
        return opp

    @staticmethod
    def get_versions(db: Session, opportunity_id: int) -> List[Dict[str, Any]]:
        """Get version history for an opportunity (simplified — single row versioning)."""
        opp = db.get(Opportunity, opportunity_id)
        if not opp:
            raise HTTPException(status_code=404, detail="Opportunity not found")

        return [
            {
                "version": opp.version,
                "title": opp.title,
                "status": opp.status.value,
                "changed_at": opp.updated_at.isoformat() if opp.updated_at else None,
                "changed_by": "admin",
            }
        ]

    @staticmethod
    def bulk_transition(
        db: Session,
        ids: List[int],
        new_status: OpportunityStatus,
        scheduled_publish_at: Optional[datetime] = None,
    ) -> List[int]:
        """Bulk transition multiple opportunities."""
        from features.oppfeed.models import Opportunity  # local import

        updated = []
        for opp_id in ids:
            opp = db.get(Opportunity, opp_id)
            if not opp:
                continue

            valid_next = VALID_TRANSITIONS.get(opp.status, [])
            if new_status not in valid_next:
                continue

            opp.status = new_status
            if new_status == OpportunityStatus.PUBLISHED:
                opp.published_at = datetime.now(timezone.utc)
            if new_status == OpportunityStatus.SCHEDULED and scheduled_publish_at:
                opp.scheduled_publish_at = scheduled_publish_at

            opp.updated_at = datetime.now(timezone.utc)
            db.add(opp)
            updated.append(opp_id)

        db.commit()
        return updated