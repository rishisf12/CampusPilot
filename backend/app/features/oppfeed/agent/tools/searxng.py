"""SearXNG search tool - self-hosted primary search.

Backwards compatible: ``SearXNGClient().search(query, num_results)`` still works.

Extras:
- retries with exponential backoff on timeouts / 429 / 5xx
- optional fallback SearXNG instances (``config.searxng_fallback_urls``)
- multi-page fetching (``pages=``) so one query can yield far more than 10 hits
- ``time_range`` filter (day / week / month / year) to favour fresh listings,
  automatically widened when it is too strict
- small in-memory TTL cache so repeated queries in one run cost nothing
- ``search_many`` to run many queries concurrently with a concurrency limit

Optional config keys (all have defaults): searxng_fallback_urls, searxng_max_retries,
searxng_cache_ttl, searxng_concurrency, searxng_engines, searxng_language.
"""
import asyncio
import logging
import time
from collections.abc import Sequence
from typing import ClassVar

import httpx

from ..config import config
from ..schemas.search import SearchResponse, SearchResult

logger = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


def _cfg(name: str, default):
    """Read an optional config value without breaking if it is missing."""
    value = getattr(config, name, None)
    return default if value is None else value


class SearXNGClient:
    """Client for self-hosted SearXNG instance."""

    # Shared across instances: {cache_key: (stored_at, results)}
    _cache: ClassVar[dict[tuple, tuple[float, list[SearchResult]]]] = {}

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or config.searxng_url).rstrip("/")
        self.fallback_urls = [u.rstrip("/") for u in _cfg("searxng_fallback_urls", [])]
        self.timeout = config.searxng_timeout
        self.max_retries = int(_cfg("searxng_max_retries", 2))
        self.cache_ttl = int(_cfg("searxng_cache_ttl", 600))
        self.concurrency = int(_cfg("searxng_concurrency", 4))
        self.engines = _cfg("searxng_engines", None)
        self.language = _cfg("searxng_language", "en")

    # ------------------------------------------------------------------ cache
    def _cache_get(self, key: tuple) -> list[SearchResult] | None:
        hit = self._cache.get(key)
        if not hit:
            return None
        stored_at, results = hit
        if time.monotonic() - stored_at > self.cache_ttl:
            self._cache.pop(key, None)
            return None
        return list(results)

    def _cache_put(self, key: tuple, results: list[SearchResult]) -> None:
        if results and self.cache_ttl > 0:
            self._cache[key] = (time.monotonic(), list(results))

    # ---------------------------------------------------------------- request
    async def _get_json(self, client: httpx.AsyncClient, params: dict) -> dict:
        """GET /search with retries, then fail over to backup instances."""
        last_exc: Exception | None = None
        for base in [self.base_url, *self.fallback_urls]:
            for attempt in range(self.max_retries + 1):
                try:
                    response = await client.get(
                        f"{base}/search",
                        params=params,
                        headers={"User-Agent": config.user_agent},
                    )
                    if response.status_code in _RETRY_STATUS:
                        raise httpx.HTTPStatusError(
                            f"retryable status {response.status_code}",
                            request=response.request,
                            response=response,
                        )
                    response.raise_for_status()
                    return response.json()
                except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError, ValueError) as exc:
                    last_exc = exc
                    # Bad JSON or a hard 4xx (e.g. 403 = JSON format disabled) will not
                    # improve by retrying the same instance; try the next one.
                    if isinstance(exc, ValueError):
                        break
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in _RETRY_STATUS:
                        break
                    if attempt < self.max_retries:
                        await asyncio.sleep(0.5 * (2 ** attempt))
        raise last_exc or RuntimeError("SearXNG request failed")

    async def _collect(
        self,
        query: str,
        num_results: int,
        pages: int,
        time_range: str | None,
        categories: str,
        language: str,
        engines: str | None,
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        seen: set = set()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for page in range(1, max(1, pages) + 1):
                params = {
                    "q": query,
                    "format": "json",
                    "language": language,
                    "categories": categories,
                    "pageno": page,
                }
                if time_range:
                    params["time_range"] = time_range
                if engines:
                    params["engines"] = engines
                data = await self._get_json(client, params)
                items = data.get("results", [])
                if not items:
                    break
                for item in items:
                    url = item.get("url", "")
                    if not url.startswith(("http://", "https://")) or url in seen:
                        continue
                    seen.add(url)
                    results.append(
                        SearchResult(
                            url=url,
                            title=item.get("title", ""),
                            snippet=item.get("content", ""),
                            position=len(results) + 1,
                            source="searxng",
                        )
                    )
                    if len(results) >= num_results:
                        return results
        return results

    # ----------------------------------------------------------------- public
    async def search(
        self,
        query: str,
        num_results: int = 10,
        *,
        pages: int = 1,
        time_range: str | None = None,
        categories: str | None = None,
        language: str | None = None,
        engines: str | None = None,
    ) -> SearchResponse:
        """Search using SearXNG. Never raises; failures come back in ``error``."""
        categories = categories or "general"
        language = language or self.language
        engines = engines or self.engines
        key = (query, num_results, pages, time_range, categories, language, engines)

        cached = self._cache_get(key)
        if cached is not None:
            return SearchResponse(results=cached, query=query, total_results=len(cached))

        try:
            results = await self._collect(query, num_results, pages, time_range, categories, language, engines)
            # A time filter that is too strict starves the query: retry without it.
            if time_range and len(results) < max(3, num_results // 3):
                logger.debug("time_range=%s too strict for %r, widening", time_range, query)
                results = await self._collect(query, num_results, pages, None, categories, language, engines)
            self._cache_put(key, results)
            return SearchResponse(results=results, query=query, total_results=len(results))
        except Exception as e:
            logger.warning("SearXNG search failed for %r: %s", query, e)
            return SearchResponse(results=[], query=query, error=str(e))

    async def search_many(
        self,
        queries: Sequence[str],
        num_results: int = 10,
        **kwargs,
    ) -> dict[str, SearchResponse]:
        """Run many queries concurrently (bounded). Returns {query: SearchResponse}."""
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(q: str):
            async with semaphore:
                return q, await self.search(q, num_results, **kwargs)

        pairs = await asyncio.gather(*(run(q) for q in queries))
        return dict(pairs)
