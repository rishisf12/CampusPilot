"""Node 7: Generate Template - structured template + short summary."""

import json
from sqlmodel.ext.asyncio.session import AsyncSession

from ..llm.router import LLMRouter
from ..schemas.pipeline import PipelineState
from ..utils.text_clean import clean_text


async def generate_template(
    state: PipelineState,
    db: AsyncSession,
    llm: LLMRouter,
) -> PipelineState:
    """Generate structured template + short student-friendly summary for each verified item."""
    templates = []

    # The cap is the app's setting, carried in the state. It bounds what one
    # run may write, and the run reports what it left out - dropping
    # verified opportunities silently is how a run ends up reporting ten
    # drafts when it verified fifty-three.
    cap = max(0, int(getattr(state, "max_drafts", 100) or 0))
    for item in (state.verification_result or [])[:cap]:
        verification = item.get("_verification", {})
        confidence = verification.get("confidence_score", 0)

        # Build template
        template = {
            "title": item.get("title", ""),
            "organization_name": item.get("organization_name", ""),
            "opportunity_type": item.get("opportunity_type", "Internship"),
            "location": item.get("location"),
            "work_mode": item.get("work_mode"),
            "duration": item.get("duration"),
            "start_date": item.get("start_date"),
            "stipend_min": item.get("stipend_min"),
            "stipend_max": item.get("stipend_max"),
            "stipend_currency": item.get("stipend_currency", "INR"),
            "stipend_period": item.get("stipend_period"),
            "registration_deadline": item.get("registration_deadline"),
            "deadline_type": item.get("deadline_type", "fixed"),
            "education_levels": item.get("education_levels", []),
            "allowed_branches": item.get("allowed_branches", []),
            "graduation_years": item.get("graduation_years", []),
            "min_cgpa_or_percentage": item.get("min_cgpa_or_percentage"),
            "other_criteria": item.get("other_criteria"),
            "skills_required": item.get("skills_required", []),
            "perks_benefits": item.get("perks_benefits", []),
            "selection_process": item.get("selection_process"),
            "documents_required": item.get("documents_required", []),
            "how_to_apply": item.get("how_to_apply"),
            "apply_url": item.get("_source_url", ""),
            "secondary_sources": item.get("_secondary_sources", []),
            "contact_email": item.get("contact_email"),
            "field_evidence": item.get("field_evidence", {}),
            "confidence_score": confidence,
            "verification_report": verification,
            "source_domain": item.get("_source_url", "").split("/")[2] if item.get("_source_url") else None,
            "tags": [],
        }

        # Generate short summary
        summary_prompt = f"""Write a short summary (max 80 words) for this opportunity.
Role: {template['title']}
Organization: {template['organization_name']}
Location: {template['location']}
Stipend: {template['stipend_min']}-{template['stipend_max']} {template['stipend_currency']}/{template['stipend_period']}
Duration: {template['duration']}

Be factual, concise, no hype. Return JSON: {{"short_summary": "..."}}"""

        try:
            response = await llm.chat(
                messages=[{"role": "user", "content": summary_prompt}],
                prompt_version="summarizer_v1",
                db=db,
                temperature=0.3,
            )
            summary_data = json.loads(response.text)
            template["short_summary"] = clean_text(summary_data.get("short_summary", ""))
            state.llm_calls += 1
            state.llm_tokens += response.input_tokens + response.output_tokens
        except (json.JSONDecodeError, Exception):
            template["short_summary"] = f"{template['title']} at {template['organization_name']}. {template['location'] or 'Location TBD'}."

        templates.append(template)

    state.template_data = templates
    state.stages_completed.append("generate_template")
    state.current_stage = "save_draft"

    return state
