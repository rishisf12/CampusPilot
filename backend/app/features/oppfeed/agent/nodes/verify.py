"""Node 6: Verify - check URL live, deadline, India eligibility, duplicates, scams.

Self-contained: defines its own Opportunity/OpportunityStatus models, no backend imports needed.
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional

from sqlmodel import Field, select

from ..base import AgentBase
from ..utils.dates import is_future_deadline


class OpportunityStatus(str, Enum):
    """Opportunity lifecycle status."""

    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    REJECTED = "rejected"
    EXPIRED = "expired"
    ARCHIVED = "archived"


class Opportunity(AgentBase, table=True):
    """Minimal opportunity model for duplicate verification.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_opportunity_verify"

    id: Optional[int] = Field(default=None, primary_key=True)
    organization_name: str = Field(max_length=200)
    title: str = Field(max_length=500)
    apply_url: str = Field(max_length=1000)
    status: OpportunityStatus = Field(default=OpportunityStatus.DRAFT)


async def verify(
    state,
    db,
    llm: "LLMRouter",
) -> "PipelineState":
    """Verify all checks: URL live, deadline, India eligibility, duplicates, scams."""
    from ..tools.link_checker import LinkChecker

    link_checker = LinkChecker()
    verified = []
    rejected_checks: Dict[str, int] = {}

    # Fetch existing opportunities for duplicate check
    existing_stmt = select(Opportunity).where(
        Opportunity.status != OpportunityStatus.REJECTED
    )
    existing = (await db.exec(existing_stmt)).all()
    existing_items = [
        {"company": o.organization_name, "title": o.title, "url": o.apply_url}
        for o in existing
    ]

    for item in state.extracted_fields or []:
        url = str(item.get("_source_url", ""))
        title = str(item.get("title", ""))
        company = str(item.get("organization_name", ""))

        if not url or not title:
            continue

        # Check 1: URL is live
        link_result = await link_checker.check(url)
        is_live = link_result["is_live"]

        # Check 2: Deadline valid
        deadline = item.get("registration_deadline")
        deadline_valid = True
        if deadline:
            try:
                deadline_dt = datetime.fromisoformat(deadline)
                deadline_valid = is_future_deadline(deadline_dt)
            except (ValueError, TypeError):
                deadline_valid = False
        else:
            deadline_valid = True  # Rolling/unspecified

        # Check 3: Open to India
        countries = item.get("open_to_countries", [])
        open_to_india = (not countries) or ("India" in countries) or ("india" in countries)

        # Check 4: Not duplicate - against what is already stored plus what this
        # run has verified so far (the same opportunity surfaces under many queries)
        from ..utils.dedupe import is_duplicate

        seen_items = existing_items + [
            {"title": seen.get("title", ""), "url": seen.get("_source_url", "")}
            for seen in verified
        ]
        is_dup = any(
            is_duplicate(title, entry["title"], url, entry["url"]) for entry in seen_items
        )

        # Check 5: Not scam
        text = json.dumps(item).lower()
        scam_keywords = ["registration fee", "refundable deposit", "pay to apply"]
        is_scam = any(kw in text for kw in scam_keywords)

        # Compute confidence score
        checks = {
            "url_live": is_live,
            "deadline_future": deadline_valid,
            "india_eligible": open_to_india,
            "not_duplicate": not is_dup,
            "not_scam": not is_scam,
        }
        passed = sum(checks.values())
        confidence = passed / len(checks)

        verification = {
            "is_live": is_live,
            "deadline_valid": deadline_valid,
            "open_to_india": open_to_india,
            "is_duplicate": is_dup,
            "is_scam": is_scam,
            "confidence_score": confidence,
            "checks": checks,
        }

        # Only keep if all checks pass
        if all(checks.values()):
            item["_verification"] = verification
            item["_confidence_score"] = confidence
            verified.append(item)
        else:
            # Record why it was dropped so the run step can explain an empty result
            for check_name, passed_check in checks.items():
                if not passed_check:
                    rejected_checks[check_name] = rejected_checks.get(check_name, 0) + 1

    # Checked/passed plus per-check rejection counts, surfaced on the run step
    summary = {"checked": len(state.extracted_fields or []), "passed": len(verified)}
    summary.update({f"rejected_{name}": count for name, count in rejected_checks.items()})
    state.verification_summary = summary

    state.verification_result = verified
    state.confidence_score = (
        sum(v["_confidence_score"] for v in verified) / len(verified) if verified else 0
    )
    state.stages_completed.append("verify")
    state.current_stage = "generate_template"

    return state