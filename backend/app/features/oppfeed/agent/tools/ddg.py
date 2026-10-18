"""DuckDuckGo search tool - fallback search provider."""

from typing import Optional

from ..schemas.search import SearchResult, SearchResponse


class DuckDuckGoClient:
    """Client for DuckDuckGo search (fallback)."""

    def __init__(self):
        self._ddgs = None

    async def search(self, query: str, num_results: int = 10) -> SearchResponse:
        """Search using DuckDuckGo."""
        try:
            from duckduckgo_search import DDGS

            if self._ddgs is None:
                self._ddgs = DDGS()

            results = []
            for i, item in enumerate(self._ddgs.text(query, max_results=num_results)):
                results.append(SearchResult(
                    url=item.get("href", ""),
                    title=item.get("title", ""),
                    snippet=item.get("body", ""),
                    position=i + 1,
                    source="duckduckgo",
                ))

            return SearchResponse(
                results=results,
                query=query,
                total_results=len(results),
            )

        except Exception as e:
            return SearchResponse(
                results=[],
                query=query,
                error=str(e),
            )
