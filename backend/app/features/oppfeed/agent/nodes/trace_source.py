"""Node 4: Source Tracing - follow aggregators to original official source."""

import httpx
from bs4 import BeautifulSoup

from sqlmodel.ext.asyncio.session import AsyncSession

from ..schemas.pipeline import PipelineState
from ..config import config
from ..tools.fetcher import PageFetcher


def _cfg(name: str, default):
    value = getattr(config, name, None)
    return default if value is None else value


OFFICIAL_DOMAIN_PATTERNS = [
    "careers.", "jobs.", "recruitment.", "hiring.",
    "gov.in", "ac.in", "edu.in",
    "linkedin.com/company/",
]


async def trace_source(
    state: PipelineState,
    db: AsyncSession,
) -> PipelineState:
    """For each candidate, find the original official source."""
    fetcher = PageFetcher()
    traced = []

    max_candidates = int(_cfg("max_candidates_per_run", 100))
    for candidate in state.candidates[:max_candidates]:
        url = candidate["url"]

        # Check if already an official source
        is_official = any(pattern in url for pattern in OFFICIAL_DOMAIN_PATTERNS)

        if is_official:
            traced.append({
                **candidate,
                "primary_source": url,
                "secondary_sources": [],
            })
            continue

        # Try to find original source from aggregator page
        try:
            html = await fetcher.fetch(url)
            if html:
                soup = BeautifulSoup(html, "html.parser")
                # Look for apply/visit buttons linking to official source
                apply_links = []
                for a_tag in soup.find_all("a", href=True):
                    href = a_tag["href"]
                    text = a_tag.get_text().lower()
                    if any(kw in text for kw in ["apply", "visit", "register", "official"]):
                        apply_links.append(href)

                if apply_links:
                    traced.append({
                        **candidate,
                        "primary_source": apply_links[0],
                        "secondary_sources": [url],
                    })
                    continue
        except Exception:
            pass

        # Fallback: use original URL as primary
        traced.append({
            **candidate,
            "primary_source": url,
            "secondary_sources": [],
        })

    state.candidates = traced
    state.stages_completed.append("trace_source")
    state.current_stage = "fetch_extract"

    return state
