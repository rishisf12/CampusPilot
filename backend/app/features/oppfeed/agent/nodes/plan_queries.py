"""Node 1: Query Planner - generates diverse search queries.

Self-contained: defines its own SearchQuery model, no backend imports needed.
"""

from typing import Optional
from sqlmodel import Field, select

from ..base import AgentBase


class SearchQuery(AgentBase, table=True):
    """Search query model for agent pipeline.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_search_query"

    id: Optional[int] = Field(default=None, primary_key=True)
    query: str = Field(max_length=500)
    category: str = Field(default=None, max_length=50)
    enabled: bool = Field(default=True)
    is_seed: bool = Field(default=False)
    priority: int = Field(default=5)  # 1-10, higher = more important


async def plan_queries(
    state: "PipelineState",
    db,
    llm: "LLMRouter",
) -> "PipelineState":
    """Generate 15-30 diverse queries targeting Indian students.

    Self-contained: defines its own SearchQuery model, no backend imports needed.
    """
    # Fetch seed and user-configured queries from DB
    stmt = select(SearchQuery).where(SearchQuery.enabled == True)
    db_queries = (await db.exec(stmt)).all()
    seed_queries = [q.query for q in db_queries if q.is_seed]
    user_queries = [q.query for q in db_queries if not q.is_seed]

    # Build prompt
    prompt = f"""Generate 15-30 diverse search queries for finding internship and job opportunities for Indian college students.

Existing seed queries: {seed_queries}
User queries: {user_queries}

Cover: summer internships, off-campus drives, women in tech, government schemes, hackathons, research internships, remote opportunities, specific branches (CS, ECE, ME, Civil), specific cities (Bangalore, Hyderabad, Pune, Delhi NCR).

Return JSON: {{"queries": ["query1", "query2", ...]}}"""

    response = await llm.chat(
        messages=[{"role": "user", "content": prompt}],
        prompt_version="query_planner_v1",
        db=db,
        temperature=0.7,
    )

    import json
    try:
        data = json.loads(response.text)
        llm_queries = data.get("queries", [])
    except json.JSONDecodeError:
        llm_queries = []

    # Combine all queries
    all_queries = list(set(seed_queries + user_queries + llm_queries))
    all_queries = all_queries[:30]  # Cap at 30

    state.queries = all_queries
    state.stages_completed.append("plan_queries")
    state.current_stage = "search"
    state.llm_calls += 1
    state.llm_tokens += response.input_tokens + response.output_tokens

    return state