"""Playwright fetcher for JS-heavy pages - fallback only."""

from typing import Optional


class PlaywrightFetcher:
    """Fetches pages using Playwright for JavaScript-heavy sites."""

    def __init__(self):
        self._browser = None

    async def fetch(self, url: str) -> Optional[str]:
        """Fetch page using Playwright."""
        try:
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page(
                    user_agent="Mozilla/5.0 (compatible; OppFeedAgent/1.0)"
                )
                await page.goto(url, wait_until="networkidle", timeout=30000)
                content = await page.content()
                await browser.close()
                return content

        except Exception:
            return None

    async def fetch_and_extract(self, url: str) -> Optional[str]:
        """Fetch and extract text from JS-heavy page."""
        html = await self.fetch(url)
        if not html:
            return None

        # Use trafilatura for text extraction
        import trafilatura
        text = trafilatura.extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
        )
        return text

    async def close(self):
        """Close browser if open."""
        if self._browser:
            await self._browser.close()
