"""OppFeed Feedback service — CampusPilot integration.

Aggregation, guideline rebuild, few-shot integration.
Uses CampusPilot Session and merged models.
"""
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlmodel import Session, select

from features.oppfeed.models import (
    Opportunity,
    OpportunityStatus,
    Feedback,
)
from features.oppfeed.schemas import FeedbackCreateRequest, FeedbackResponse


class FeedbackService:
    """Service for feedback business logic."""

    def get_feedback_for_opportunity(
        self, db: Session, opportunity_id: int
    ) -> List[Feedback]:
        """Get all feedback for an opportunity."""
        return list(
            db.exec(
                select(Feedback)
                .where(Feedback.opportunity_id == opportunity_id)
                .order_by(Feedback.created_at.desc())
            ).all()
        )

    def create_feedback(
        self,
        db: Session,
        opportunity_id: int,
        payload: FeedbackCreateRequest,
    ) -> Feedback:
        """Create feedback for an opportunity."""
        opp = db.get(Opportunity, opportunity_id)
        if not opp:
            raise ValueError("Opportunity not found")

        feedback = Feedback(
            opportunity_id=opportunity_id,
            thumbs_up=payload.thumbs_up,
            rating=payload.rating,
            tags=payload.tags or [],
            comment=payload.comment,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        return feedback

    def aggregate_tags(self, db: Session) -> Dict[str, int]:
        """Aggregate all feedback tags into counts."""
        results = list(db.exec(select(Feedback)).all())
        tag_counts: Dict[str, int] = {}
        for fb in results:
            for tag in fb.tags or []:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        return tag_counts

    def rebuild_guidelines(self, db: Session) -> str:
        """Rebuild agent guidelines from all feedback."""
        tag_counts = self.aggregate_tags(db)
        if not tag_counts:
            return ""
        lines = ["## Agent Guidelines (Auto-generated from Reviewer Feedback)", ""]
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            lines.append(f"- **{tag}** ({count} reports)")
        return "\n".join(lines)

    def get_fewshot_examples(
        self, db: Session, opportunity_type: Optional[str] = None, limit: int = 3
    ) -> List[dict]:
        """Get approved examples for few-shot prompting."""
        stmt = select(Opportunity).where(Opportunity.status == OpportunityStatus.APPROVED)
        if opportunity_type:
            try:
                from features.oppfeed.models import OpportunityType
                stmt = stmt.where(Opportunity.opportunity_type == OpportunityType(opportunity_type))
            except ValueError:
                pass
        stmt = stmt.order_by(Opportunity.confidence_score.desc().nullslast()).limit(limit)
        results = list(db.exec(stmt).all())

        return [
            {
                "title": o.title,
                "organization_name": o.organization_name,
                "opportunity_type": o.opportunity_type.value,
                "location": o.location,
                "work_mode": o.work_mode.value if o.work_mode else None,
                "stipend_min": o.stipend_min,
                "stipend_max": o.stipend_max,
                "stipend_currency": o.stipend_currency,
                "stipend_period": o.stipend_period,
                "short_summary": o.short_summary,
                "skills_required": o.skills_required,
                "how_to_apply": o.how_to_apply,
                "apply_url": o.apply_url,
            }
            for o in results
        ]