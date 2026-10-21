"""DuckDuckGo search tool - the fallback search provider.

The ``duckduckgo_search`` library talks to **Bing** by default, which is a
different search engine wearing DuckDuckGo's name, and it is refused by
some networks (and by some DNS resolvers). DuckDuckGo's own HTML endpoint
answers with plain HTML and is what the library itself falls back to, so
it is used first here; the library is kept as the fallback for the
networks where the endpoint is not reachable.
"""

from typing import Optional
from urllib.parse import parse_qs, unquote, urlparse

from ..schemas.search import SearchResult, SearchResponse

#: DuckDuckGo's HTML endpoint. It answers with a plain results page.
ENDPOINT = "https://html.duckduckgo.com/html/"

#: A browser-like agent, because the endpoint serves a different page to
#: anything it recognises as a script.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def _unwrap(url: str) -> str:
    """
    The real destination of a DuckDuckGo result link.

    The HTML endpoint wraps every result in a redirect whose target is in
    the ``uddg`` parameter; a link that is not wrapped is already the
    destination.
    """
    if not url:
        return ""
    if url.startswith("//"):
        url = "https:" + url
    parsed = urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            return unquote(target)
    return url


class DuckDuckGoClient:
    """Client for DuckDuckGo search (fallback)."""

    def __init__(self):
        self._ddgs = None

    async def search(self, query: str, num_results: int = 10) -> SearchResponse:
        """Search using DuckDuckGo."""
        results = await self._search_html(query, num_results)
        if not results:
            results = await self._search_library(query, num_results)
        return SearchResponse(
            results=results,
            query=query,
            total_results=len(results),
        )

    async def _search_html(self, query: str, num_results: int) -> list:
        """The HTML endpoint: DuckDuckGo's own, no third party in between."""
        try:
            import httpx
            from bs4 import BeautifulSoup

            async with httpx.AsyncClient(
                timeout=25, follow_redirects=True, headers=HEADERS
            ) as client:
                response = await client.get(ENDPOINT, params={"q": query})
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")

            results = []
            for node in soup.select("div.result"):
                if len(results) >= num_results:
                    break
                link = node.select_one("a.result__a")
                if link is None:
                    continue
                url = _unwrap((link.get("href") or "").strip())
                if not url:
                    continue
                title = (link.get_text() or "").strip()
                snippet_node = node.select_one("a.result__snippet")
                snippet = (
                    (snippet_node.get_text() or "").strip() if snippet_node else ""
                )
                results.append(
                    SearchResult(
                        url=url,
                        title=title,
                        snippet=snippet,
                        position=len(results) + 1,
                        source="duckduckgo",
                    )
                )
            return results
        except Exception as exc:  # noqa: BLE001 - the fallback takes over
            import logging

            logging.getLogger(__name__).debug(
                "DuckDuckGo HTML endpoint failed for %r: %s", query, exc
            )
            return []

    async def _search_library(self, query: str, num_results: int) -> list:
        """The library, for the networks where the endpoint is not reachable."""
        try:
            from duckduckgo_search import DDGS

            if self._ddgs is None:
                self._ddgs = DDGS()

            results = []
            for i, item in enumerate(self._ddgs.text(query, max_results=num_results)):
                results.append(
                    SearchResult(
                        url=item.get("href", ""),
                        title=item.get("title", ""),
                        snippet=item.get("body", ""),
                        position=i + 1,
                        source="duckduckgo",
                    )
                )
            return results
        except Exception as e:
            return []
