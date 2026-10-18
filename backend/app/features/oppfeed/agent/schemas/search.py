"""Search result schemas."""

from typing import List, Optional

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """Single search result."""

    url: str
    title: str
    snippet: str
    position: int = 0
    source: str = "searxng"  # searxng, duckduckgo


class SearchResponse(BaseModel):
    """Response from search operation."""

    results: List[SearchResult] = Field(default_factory=list)
    query: str = ""
    total_results: int = 0
    error: Optional[str] = None
