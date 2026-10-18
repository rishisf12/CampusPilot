"""Node 3: Candidate Filter - drop spam, expired, non-India, denied domains.

Self-contained: defines its own SourceRule model, no backend imports needed.
"""

from typing import Optional
from urllib.parse import urlparse

from sqlmodel import Field, select

from ..base import AgentBase
from ..config import config


class SourceRule(AgentBase, table=True):
    """Source domain rule model for agent pipeline.

    Self-contained model - no backend imports needed.
    """

    __tablename__ = "oppfeed_source_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field(index=True, unique=True, max_length=200)
    rule_type: str = Field(max_length=10)  # "allow" or "deny"
    enabled: bool = Field(default=True)


AGGREGATOR_DOMAINS = {
    "indeed.com", "naukri.com", "monster.com", "shine.com",
    "freshersworld.com", "internshala.com", "247fresher.com",
    "fresherslive.com", "indgovtjobs.in", " Sarkariresult.com",
    "sarkarinaukri.com", "govtjobs.com", "freejobalert.com",
}

NON_INDIA_KEYWORDS = {
    "usa", "us only", "united states", "uk only", "canada",
    "australia", "germany", "work from usa", "us citizens",
    "green card", "h1b", "opt required", "cpt required",
}


def _cfg(name: str, default):
    value = getattr(config, name, None)
    return default if value is None else value


async def filter_candidates(
    state: "PipelineState",
    db,
) -> "PipelineState":
    """Filter out aggregator spam, expired, non-India listings, denied domains.

    Self-contained: defines its own SourceRule model, no backend imports needed.
    """
    # Fetch denied domains from DB
    stmt = select(SourceRule).where(SourceRule.enabled == True)
    rules = (await db.exec(stmt)).all()
    denied_domains = {r.domain.lower() for r in rules if r.rule_type == "deny"}

    candidates = []
    for result in state.search_results:
        url = result.get("url", "")
        title = result.get("title", "")
        snippet = result.get("snippet", "")
        domain = urlparse(url).netloc.lower()

        # Skip denied domains
        if any(d in domain for d in denied_domains):
            continue

        # Skip aggregators
        if any(agg in domain for agg in AGGREGATOR_DOMAINS):
            # Store as secondary source
            state.secondary_sources.append(url)
            continue

        # Skip non-India listings
        combined = f"{title} {snippet}".lower()
        if any(kw in combined for kw in NON_INDIA_KEYWORDS):
            continue

        # Skip obviously expired (title/snippet indicates past date)
        if any(kw in combined for kw in ["2024", "2023", "2022", "expired", "closed"]):
            continue

        candidates.append(result)

    max_candidates = int(_cfg("max_candidates_per_run", 100))
    state.candidates = candidates[:max_candidates]
    state.stages_completed.append("filter_candidates")
    state.current_stage = "trace_source"

    return state