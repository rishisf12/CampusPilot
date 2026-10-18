"""Web page fetcher using httpx + trafilatura.

Backwards compatible: ``fetch``, ``fetch_and_extract``, ``extract_text`` and
``check_link`` keep their signatures and return types.

Extras used by the smarter pipeline nodes:
- ``fetch_page``: final URL after redirects, status, size cap, retries, PDF text
- ``extract_text``: trafilatura first, BeautifulSoup fallback, and it also falls
  back when trafilatura keeps only a fraction of a listing/careers page
- ``extract_metadata``: title, description, canonical and JSON-LD JobPosting/Event data
- ``extract_links`` / ``find_official_links`` / ``find_opportunity_links``: resolve an
  aggregator listing to the organisation's own page, and discover sibling listings
- ``check_link``: also retries with GET when a server rejects HEAD (403/405/...)
- module helpers: ``is_aggregator``, ``is_official_domain``, ``looks_closed``,
  ``deadline_extended_hint``

Optional config keys (all have defaults): fetch_max_bytes, fetch_retries,
fetch_min_text_len, fetch_concurrency.
"""
import asyncio
import io
import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from urllib.parse import urldefrag, urljoin, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

from ..config import config

logger = logging.getLogger(__name__)

_RETRY_STATUS = {429, 500, 502, 503, 504}


def _cfg(name: str, default):
    value = getattr(config, name, None)
    return default if value is None else value


# --------------------------------------------------------------------------- domains
_TWO_PART_SUFFIXES = {
    "co.in", "ac.in", "gov.in", "nic.in", "edu.in", "org.in", "res.in", "net.in",
    "co.uk", "ac.uk", "gov.uk", "org.uk", "com.au", "edu.au", "gov.au",
}

# Job/internship listing sites: good for discovery, but NOT the main official source.
AGGREGATOR_DOMAINS = {
    "internshala.com", "unstop.com", "linkedin.com", "naukri.com", "indeed.com",
    "glassdoor.com", "letsintern.com", "freshersworld.com", "shine.com", "foundit.in",
    "monsterindia.com", "instahyre.com", "wellfound.com", "angel.co", "cutshort.io",
    "hirist.tech", "apna.co", "ziprecruiter.com", "simplyhired.com", "sarkariresult.com",
    "freejobalert.com", "sarkarinaukri.com", "twenty19.com", "youthincmag.com",
    "campusoption.com", "jobsarkari.com", "rojgarresult.com", "govtjobsalert.com",
    "buddy4study.com", "scholarshipsads.com", "opportunitiescorners.com",
    "opportunitiesforafricans.com", "scholars4dev.com", "afterschoolafrica.com",
}

SOCIAL_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com", "linkedin.com", "youtube.com",
    "youtu.be", "t.me", "telegram.me", "whatsapp.com", "wa.me", "reddit.com", "quora.com",
    "medium.com", "pinterest.com", "discord.com", "discord.gg", "threads.net",
}

# Hackathon / event platforms: acceptable as the official registration page for events.
EVENT_PLATFORMS = {
    "devfolio.co", "devpost.com", "dorahacks.io", "mlh.io", "hackerearth.com",
    "unstop.com", "kaggle.com", "hackclub.com", "lablab.ai",
}

_OFFICIAL_HOST_RE = re.compile(r"(\.(gov|nic|ac|edu|res|mil)(\.[a-z]{2})?$)|(^nic\.in$)")

_STATIC_EXT = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".css", ".js",
    ".woff", ".woff2", ".mp4", ".zip",
)


def domain_of(url: str) -> str:
    """Host without port and leading www (empty string if unparsable)."""
    try:
        host = (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


def registered_domain(url_or_host: str) -> str:
    """Approximate registrable domain, e.g. careers.foo.co.in -> foo.co.in."""
    host = domain_of(url_or_host) if "/" in url_or_host or ":" in url_or_host else url_or_host.lower()
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in _TWO_PART_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def is_aggregator(url: str) -> bool:
    return registered_domain(url) in AGGREGATOR_DOMAINS


def is_social(url: str) -> bool:
    return registered_domain(url) in SOCIAL_DOMAINS


def is_event_platform(url: str) -> bool:
    return registered_domain(url) in EVENT_PLATFORMS


def is_official_domain(url: str) -> bool:
    """Government / academic domains (gov.in, nic.in, ac.in, .edu, ...)."""
    return bool(_OFFICIAL_HOST_RE.search(domain_of(url)))


# --------------------------------------------------------------------- text signals
_CLOSED_RE = re.compile(
    r"(applications?|registrations?|submissions?|nominations?)\s+(?:are\s+|is\s+|have\s+been\s+|has\s+been\s+)?(?:now\s+)?closed"
    r"|no\s+longer\s+accepting"
    r"|deadline\s+(?:has\s+)?(?:passed|expired)"
    r"|position\s+(?:has\s+been\s+)?filled"
    r"|(?:job|internship|opportunity|listing|posting)\s+(?:is\s+)?(?:no\s+longer\s+available|has\s+expired|expired)"
    r"|applications?\s+(?:have\s+)?ended",
    re.I,
)

_EXTENDED_RE = re.compile(
    r"(?:deadline|last\s+date|registrations?|applications?)[^.\n]{0,60}\bextended\b"
    r"|\bextended\s+(?:till|until|to|up\s+to)\b"
    r"|(?:revised|new)\s+(?:deadline|last\s+date)"
    r"|(?:deadline|last\s+date)\s+(?:has\s+been\s+)?(?:revised|extended)",
    re.I,
)


def looks_closed(text: str) -> bool:
    """Heuristic: page text says applications/registrations are closed."""
    return bool(text and _CLOSED_RE.search(text))


def deadline_extended_hint(text: str) -> bool:
    """Heuristic: page text says the deadline was extended or revised."""
    return bool(text and _EXTENDED_RE.search(text))


# ------------------------------------------------------------------- link scoring
_OFFICIAL_TEXT_HINTS = (
    "apply", "official", "visit website", "company website", "register",
    "careers", "know more", "brochure", "notification",
)
_OFFICIAL_URL_HINTS = (
    "apply", "career", "jobs", "register", "recruit",
    "internship", "hackathon", "vacanc", "notification",
)

_OPPORTUNITY_HINTS = (
    "internship", "intern", "apply", "career", "job", "vacanc", "recruit", "hackathon",
    "fellowship", "opening", "position", "scheme", "challenge", "summit", "competition",
    "registration", "notification", "advertisement", "trainee", "apprentice", "programme", "program",
)
_LINK_NOISE = (
    "login", "signin", "sign-in", "signup", "sign-up", "register-account", "privacy", "terms",
    "cookie", "contact", "about", "faq", "press", "blog", "mailto:", "tel:", "javascript:",
    "facebook", "twitter", "instagram", "linkedin", "youtube", "sitemap", "disclaimer",
)


@dataclass
class FetchedPage:
    url: str                 # final URL after redirects
    status: int
    content_type: str
    text: str                # raw HTML, or extracted text when is_pdf
    is_pdf: bool = False


class _RetryableError(Exception):
    pass


class PageFetcher:
    """Fetches and extracts clean text from web pages."""

    def __init__(self):
        self.timeout = config.fetch_timeout
        self.user_agent = config.user_agent
        self.max_bytes = int(_cfg("fetch_max_bytes", 3_000_000))
        self.retries = int(_cfg("fetch_retries", 1))
        self.min_text_len = int(_cfg("fetch_min_text_len", 100))
        self.concurrency = int(_cfg("fetch_concurrency", 5))

    # ----------------------------------------------------------------- plumbing
    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-IN,en;q=0.9",
            },
        )

    async def _read_limited(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            chunks.append(chunk)
            size += len(chunk)
            if size >= self.max_bytes:
                break
        return b"".join(chunks)

    @staticmethod
    def _pdf_text(body: bytes) -> str:
        try:
            from pypdf import PdfReader  # optional dependency
        except ImportError:
            logger.debug("pypdf not installed; skipping PDF text extraction")
            return ""
        try:
            reader = PdfReader(io.BytesIO(body))
            pages = [(page.extract_text() or "") for page in reader.pages[:15]]
            return "\n".join(p for p in pages if p).strip()
        except Exception as e:
            logger.debug("PDF extraction failed: %s", e)
            return ""

    # -------------------------------------------------------------------- fetch
    async def fetch_page(self, url: str) -> FetchedPage | None:
        """Fetch a URL. Returns None on failure (never raises)."""
        for attempt in range(self.retries + 1):
            try:
                async with self._client() as client, client.stream("GET", url) as response:
                    if response.status_code in _RETRY_STATUS:
                        raise _RetryableError(str(response.status_code))
                    response.raise_for_status()
                    body = await self._read_limited(response)
                    ctype = response.headers.get("content-type", "").lower()
                    final_url = str(response.url)
                    status = response.status_code
                    encoding = response.encoding or "utf-8"

                is_pdf = (
                    "application/pdf" in ctype
                    or final_url.lower().split("?")[0].endswith(".pdf")
                    or body[:5] == b"%PDF-"
                )
                if is_pdf:
                    return FetchedPage(final_url, status, ctype, self._pdf_text(body), True)
                try:
                    text = body.decode(encoding, errors="replace")
                except LookupError:
                    text = body.decode("utf-8", errors="replace")
                return FetchedPage(final_url, status, ctype, text, False)
            except (_RetryableError, httpx.TimeoutException, httpx.TransportError):
                if attempt < self.retries:
                    await asyncio.sleep(0.7 * (attempt + 1))
                    continue
                return None
            except Exception:
                return None
        return None

    async def fetch(self, url: str) -> str | None:
        """Fetch raw HTML from a URL."""
        page = await self.fetch_page(url)
        return page.text if page and page.text else None

    async def fetch_many(self, urls: Sequence[str]) -> dict[str, FetchedPage | None]:
        """Fetch several URLs concurrently (bounded)."""
        semaphore = asyncio.Semaphore(self.concurrency)

        async def run(u: str):
            async with semaphore:
                return u, await self.fetch_page(u)

        return dict(await asyncio.gather(*(run(u) for u in urls)))

    async def fetch_and_extract(self, url: str) -> str | None:
        """Fetch page and extract clean text content."""
        page = await self.fetch_page(url)
        if not page or not page.text:
            return None
        if page.is_pdf:
            return page.text
        return self.extract_text(page.text, page.url)

    # ------------------------------------------------------------------ extract
    @staticmethod
    def _soup_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "aside", "form"]):
            tag.decompose()
        return soup.get_text(separator="\n", strip=True)

    def extract_text(self, html: str, url: str = "") -> str | None:
        """Extract clean text from HTML using trafilatura (BeautifulSoup fallback)."""
        try:
            text = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_tables=True,
                include_links=False,
                deduplicate=True,
            )
            if text and len(text) > self.min_text_len:
                # trafilatura targets article bodies and can drop most of a listing /
                # careers page. If it kept only a sliver, prefer the fuller text.
                fuller = self._soup_text(html)
                if len(fuller) > 1500 and len(text) < 0.25 * len(fuller):
                    return fuller
                return text
            fallback = self._soup_text(html)
            return fallback or None
        except Exception:
            return None

    def extract_metadata(self, html: str, url: str = "") -> dict:
        """Title / description / canonical plus JSON-LD JobPosting and Event data."""
        meta: dict = {"title": "", "description": "", "canonical": "", "site_name": "", "structured": []}
        try:
            soup = BeautifulSoup(html, "html.parser")

            def meta_content(*names: str) -> str:
                for name in names:
                    tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
                    if tag and tag.get("content"):
                        return tag["content"].strip()
                return ""

            og_title = meta_content("og:title", "twitter:title")
            meta["title"] = og_title or (soup.title.get_text(strip=True) if soup.title else "")
            meta["description"] = meta_content("og:description", "description", "twitter:description")
            meta["site_name"] = meta_content("og:site_name")
            canonical = soup.find("link", rel="canonical")
            if canonical and canonical.get("href"):
                meta["canonical"] = urljoin(url, canonical["href"])

            for script in soup.find_all("script", type="application/ld+json"):
                raw = script.string or script.get_text()
                try:
                    data = json.loads(raw)
                except (ValueError, TypeError):
                    continue
                meta["structured"].extend(self._parse_jsonld(data))
        except Exception as e:
            logger.debug("metadata extraction failed for %s: %s", url, e)
        return meta

    @staticmethod
    def _ld_text(value) -> str:
        if isinstance(value, list):
            value = value[0] if value else ""
        if isinstance(value, dict):
            address = value.get("address")
            if isinstance(address, dict):
                parts = [address.get(k) for k in ("addressLocality", "addressRegion", "addressCountry")]
                return ", ".join(str(p) for p in parts if p)
            return str(value.get("name") or value.get("@id") or "")
        return str(value or "")

    def _parse_jsonld(self, data) -> list[dict]:
        found: list[dict] = []
        if isinstance(data, list):
            for item in data:
                found.extend(self._parse_jsonld(item))
            return found
        if not isinstance(data, dict):
            return found
        if "@graph" in data:
            found.extend(self._parse_jsonld(data["@graph"]))
        types = data.get("@type")
        types = types if isinstance(types, list) else [types]
        if "JobPosting" in types:
            found.append({
                "type": "JobPosting",
                "title": self._ld_text(data.get("title")),
                "organization": self._ld_text(data.get("hiringOrganization")),
                "date_posted": self._ld_text(data.get("datePosted")),
                "valid_through": self._ld_text(data.get("validThrough")),
                "employment_type": self._ld_text(data.get("employmentType")),
                "location": self._ld_text(data.get("jobLocation")),
                "url": self._ld_text(data.get("url")),
            })
        elif any(isinstance(t, str) and t.endswith("Event") for t in types):
            found.append({
                "type": "Event",
                "title": self._ld_text(data.get("name")),
                "organization": self._ld_text(data.get("organizer")),
                "start_date": self._ld_text(data.get("startDate")),
                "end_date": self._ld_text(data.get("endDate")),
                "location": self._ld_text(data.get("location")),
                "url": self._ld_text(data.get("url")),
            })
        return found

    # -------------------------------------------------------------------- links
    @staticmethod
    def extract_links(html: str, base_url: str) -> list[dict[str, str]]:
        """All absolute http(s) links on the page as [{'url', 'text'}], de-duplicated."""
        links: list[dict[str, str]] = []
        seen = set()
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
                    continue
                absolute, _ = urldefrag(urljoin(base_url, href))
                if not absolute.startswith(("http://", "https://")) or absolute in seen:
                    continue
                if absolute.lower().split("?")[0].endswith(_STATIC_EXT):
                    continue
                seen.add(absolute)
                links.append({"url": absolute, "text": a.get_text(" ", strip=True)})
        except Exception as e:
            logger.debug("link extraction failed for %s: %s", base_url, e)
        return links

    def find_official_links(self, html: str, base_url: str, limit: int = 5) -> list[str]:
        """Outbound links on an aggregator page that most likely lead to the organiser's own page."""
        base_reg = registered_domain(base_url)
        scored = []
        for link in self.extract_links(html, base_url):
            url = link["url"]
            if registered_domain(url) == base_reg or is_aggregator(url) or is_social(url):
                continue
            text = link["text"].lower()
            href = url.lower()
            score = sum(4 for h in _OFFICIAL_TEXT_HINTS if h in text)
            score += sum(2 for h in _OFFICIAL_URL_HINTS if h in href)
            if is_official_domain(url):
                score += 5
            if score > 0:
                scored.append((score, url))
        scored.sort(key=lambda s: -s[0])
        return [url for _, url in scored[:limit]]

    def find_opportunity_links(self, html: str, base_url: str, limit: int = 12) -> list[str]:
        """Same-site links that look like individual opportunities (roles, events, notifications)."""
        base_reg = registered_domain(base_url)
        scored = []
        for link in self.extract_links(html, base_url):
            url = link["url"]
            if registered_domain(url) != base_reg or url.rstrip("/") == base_url.rstrip("/"):
                continue
            haystack = f"{url.lower()} {link['text'].lower()}"
            if any(n in haystack for n in _LINK_NOISE):
                continue
            score = sum(1 for h in _OPPORTUNITY_HINTS if h in haystack)
            if url.lower().split("?")[0].endswith(".pdf") and score:
                score += 1  # official notifications are often PDFs
            if score > 0:
                scored.append((score, url))
        scored.sort(key=lambda s: -s[0])
        return [url for _, url in scored[:limit]]

    # --------------------------------------------------------------- link check
    async def check_link(self, url: str) -> tuple[bool, int]:
        """Check if a link is live. Returns (is_live, status_code)."""
        try:
            async with self._client() as client:
                response = await client.head(url)
                # Many servers reject HEAD; don't treat that as a dead link.
                if response.status_code not in (400, 403, 405, 501):
                    return (200 <= response.status_code < 400), response.status_code
        except Exception:
            pass
        try:
            async with self._client() as client, client.stream("GET", url) as response:
                return (200 <= response.status_code < 400), response.status_code
        except Exception:
            return False, 0
