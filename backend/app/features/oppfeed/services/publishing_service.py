"""OppFeed Publishing service — CampusPilot integration.

Auto-publish rules, scheduled publishing, auto-archive expired.
Uses CampusPilot Session and merged models/settings.
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlmodel import Session, select

from features.oppfeed.models import (
    Opportunity,
    OpportunityStatus,
    AgentSettings,
)
from features.oppfeed.services.opportunity_service import OpportunityService


class PublishingService:
    """Service for publishing logic and auto-publish rules."""

    @staticmethod
    def _get_settings(db: Session) -> AgentSettings:
        """Get agent settings (create default if missing)."""
        settings = db.exec(select(AgentSettings)).first()
        if not settings:
            settings = AgentSettings()
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    @staticmethod
    def should_auto_publish(
        opportunity: Opportunity,
        *,
        enabled: Optional[bool] = None,
        threshold: Optional[float] = None,
    ) -> bool:
        """Check if an opportunity meets auto-publish criteria."""
        settings = enabled if enabled is not None else None
        thresh = threshold if threshold is not None else None

        # Use provided values or fall back to settings
        if enabled is None or threshold is None:
            s = enabled if enabled is not None else None
            if enabled is None or threshold is None:
                from features.oppfeed.models import AgentSettings
                # Note: this is called with db session in practice
                pass
        if enabled is None:
            enabled = True  # default from settings
        if threshold is None:
            threshold = 0.85  # default from settings

        if not enabled:
            return False
        if opportunity.confidence_score is None:
            return False
        if opportunity.confidence_score < threshold:
            return False
        if not opportunity.verification_report:
            return False
        if not isinstance(opportunity.verification_report, dict):
            return False

        checks = opportunity.verification_report.get("checks", {})
        if not isinstance(checks, dict) or not checks:
            return False
        return all(checks.values())

    @staticmethod
    def publish_due_opportunities(db: Session) -> List[Opportunity]:
        """Publish all scheduled opportunities whose time has come."""
        now = datetime.now(timezone.utc)
        stmt = select(Opportunity).where(
            Opportunity.status == OpportunityStatus.SCHEDULED,
            Opportunity.scheduled_publish_at <= now,
        )
        results = list(db.exec(stmt).all())
        published = []

        for opp in results:
            opp.status = OpportunityStatus.PUBLISHED
            opp.published_at = now
            opp.updated_at = now
            published.append(opp)

        if published:
            db.commit()
        return published

    @staticmethod
    def auto_archive_expired(db: Session) -> List[Opportunity]:
        """Archive expired opportunities."""
        now = datetime.now(timezone.utc)
        stmt = select(Opportunity).where(
            Opportunity.status == OpportunityStatus.PUBLISHED,
            Opportunity.registration_deadline < now,
        )
        results = list(db.exec(stmt).all())

        for opp in results:
            opp.status = OpportunityStatus.EXPIRED
            opp.updated_at = now

        if results:
            db.commit()
        return results

    @staticmethod
    def process_auto_publish(db: Session, *, run_id: Optional[str] = None) -> List[Opportunity]:
        """Publish drafts that meet the auto-publish criteria."""
        settings = PublishingService._get_settings(db)
        if not settings.auto_publish_enabled:
            return []

        stmt = select(Opportunity).where(Opportunity.status == OpportunityStatus.DRAFT)
        if run_id is not None:
            stmt = stmt.where(Opportunity.created_by_run_id == run_id)

        published = []
        for opp in db.exec(stmt).all():
            if PublishingService.should_auto_publish(
                opp,
                enabled=settings.auto_publish_enabled,
                threshold=settings.auto_publish_threshold,
            ):
                now = datetime.now(timezone.utc)
                opp.status = OpportunityStatus.PUBLISHED
                opp.published_at = now
                opp.updated_at = now
                published.append(opp)

        if published:
            db.commit()
        return published