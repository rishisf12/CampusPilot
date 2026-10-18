"""Link checker - verifies URLs are live and valid."""

import httpx
from urllib.parse import urlparse

from ..config import config


class LinkChecker:
    """Checks if URLs are live and accessible."""

    def __init__(self):
        self.timeout = config.fetch_timeout
        self.user_agent = config.user_agent

    async def check(self, url: str) -> dict:
        """
        Check a URL and return status information.
        Returns dict with: is_live, status_code, final_url, content_type, error
        """
        result = {
            "is_live": False,
            "status_code": 0,
            "final_url": url,
            "content_type": None,
            "error": None,
        }

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                headers={"User-Agent": self.user_agent},
            ) as client:
                response = await client.get(url)
                result["is_live"] = 200 <= response.status_code < 400
                result["status_code"] = response.status_code
                result["final_url"] = str(response.url)
                result["content_type"] = response.headers.get("content-type", "")

        except httpx.HTTPStatusError as e:
            result["status_code"] = e.response.status_code
            result["error"] = f"HTTP {e.response.status_code}"
        except Exception as e:
            result["error"] = str(e)

        return result

    async def check_batch(self, urls: list[str]) -> list[dict]:
        """Check multiple URLs concurrently."""
        import asyncio
        tasks = [self.check(url) for url in urls]
        return await asyncio.gather(*tasks)

    @staticmethod
    def is_official_domain(url: str, organization: str) -> bool:
        """Check if URL domain matches the organization."""
        domain = urlparse(url).netloc.lower()
        org_lower = organization.lower().replace(" ", "")
        # Check if org name is in domain or vice versa
        return org_lower in domain or domain.split(".")[0] in org_lower
