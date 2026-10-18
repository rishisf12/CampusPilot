"""Robots.txt checker - respect website crawling policies."""

import httpx
from urllib.parse import urlparse
from robotstxt import RobotsFile

from ..config import config


class RobotsChecker:
    """Checks robots.txt compliance."""

    def __init__(self):
        self.user_agent = config.user_agent
        self._cache: dict[str, RobotsFile] = {}

    async def can_fetch(self, url: str) -> bool:
        """Check if we can fetch a URL according to robots.txt."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        if base_url not in self._cache:
            robots_url = f"{base_url}/robots.txt"
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(robots_url)
                    if response.status_code == 200:
                        self._cache[base_url] = RobotsFile(response.text)
                    else:
                        self._cache[base_url] = None
            except Exception:
                self._cache[base_url] = None

        robots = self._cache[base_url]
        if robots is None:
            return True  # No robots.txt = allow all

        return robots.can_fetch(self.user_agent, url)

    async def get_crawl_delay(self, url: str) -> float:
        """Get crawl delay from robots.txt."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        robots = self._cache.get(base_url)
        if robots:
            delay = robots.get_crawl_delay(self.user_agent)
            return float(delay) if delay else 0.0
        return 0.0