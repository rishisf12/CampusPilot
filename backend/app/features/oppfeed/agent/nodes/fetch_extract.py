"""Node 5: Fetch and Extract - fetch original page, extract fields with evidence.

What this node does on top of fetch + LLM extraction:
- Fetches pages concurrently in waves (LLM calls stay sequential: the shared DB session
  is not safe for concurrent use).
- Official source: if a page comes from a job/internship aggregator, it follows the
  outbound apply/official link; failing that it searches for the organisation's own page.
  Event platforms (Devfolio, Devpost, Unstop, ...) are accepted for hackathons/events.
- Multi-opportunity pages: the LLM may return several opportunities from one page, and
  listing pages are mined for sibling links (depth-limited) so a company with many roles
  yields all of them.
- Extra fields requested from the LLM: organisation category, short description,
  organisers/coordinators, abroad / fully-sponsored / fee / IIIT-eligibility / open status.
- Filters: expired, closed, fee-charging, abroad-but-not-fully-sponsored, not IIIT-eligible,
  dead apply link, no official source.
- Deadline extensions: duplicates within a run are merged keeping the later deadline and
  flagged ``_deadline_extended``; every opportunity gets a stable ``_dedupe_key`` so the
  persistence stage can update an existing row instead of inserting a new one.

Optional config keys (all have defaults): max_pages_per_run, max_results_per_run,
target_opportunities, fetch_concurrency, max_link_depth, extract_max_chars,
require_official_source, require_iiit_eligible, exclude_fee_based, exclude_stipend_paying,
check_apply_links.
"""
import asyncio
import json
import logging
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import config
from ..llm.router import LLMRouter
from .search import canonicalize_url
from ..schemas.pipeline import PipelineState
from ..tools.fetcher import (
    PageFetcher,
    deadline_extended_hint,
    domain_of,
    is_aggregator,
    is_event_platform,
    is_social,
    looks_closed,
)
from ..tools.searxng import SearXNGClient
from ..utils.text_clean import clean_text, truncate

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))
_EVENT_TYPES = {"hackathon", "event", "competition", "challenge"}

_EXTRA_INSTRUCTIONS = """
Also extract these additional fields (same evidence rule, null if not on the page):
- organization_category: "government" | "psu" | "multinational" | "private_company" | "startup"
  | "ngo" | "academic" | "event_organizer" | "other"
- organization_description: 1-2 factual sentences about the organisation/organiser, only from the page
- organizers: list of {"name": ..., "role": ..., "email": ..., "phone": ...} for organisers,
  coordinators, HR or contact persons named on the page
- event_scale: for hackathons/events: "college" | "state" | "national" | "international"
- is_abroad: true if the opportunity takes place outside India, else false
- fully_sponsored: true only if the page says travel/stay/stipend/fees are covered (fully funded/sponsored);
  false if participants must pay; null if unknown
- fee_required: true if applicants/participants must pay any fee (registration, programme or placement fee);
  false if explicitly free; null if unknown
- iiit_eligible: true if IIIT students can apply (open to all engineering/B.Tech students, or IIITs named);
  false ONLY if the page explicitly restricts to other institutions; null if unclear
- is_open: false if the page says applications/registrations are closed, otherwise true
- deadline_extended: true if the page says the deadline was extended or revised
- official_source_url: the organisation's own page for this opportunity if this page is not it, else this page's URL

If the page lists several distinct opportunities (a careers page, a programme with several tracks), return
{"opportunities": [ {...}, {...} ]} with one object per opportunity, each with its own field_evidence.
Otherwise return a single JSON object. Return JSON only, no markdown fences."""


def _cfg(name: str, default):
    value = getattr(config, name, None)
    return default if value is None else value


# --------------------------------------------------------------------------- helpers
def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _parse_llm_json(raw: str) -> Any:
    """Parse model output even if wrapped in ```json fences or surrounded by prose.

    Returns None if no valid JSON can be extracted (caller decides how to handle).
    Handles: empty responses, truncated JSON, extra data, mixed content.
    """
    text = (raw or "").strip()
    if not text:
        return None

    # Strip markdown code fences
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    if not text:
        return None

    # Strategy 1: Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 2: Find first complete JSON object or array
    # Handles: extra data, wrapped in prose, truncated
    candidates: list[str] = []

    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        # Bracket matching to find complete object/array
        depth = 0
        in_string = False
        escape = False
        for i, ch in enumerate(text[start_idx:], start_idx):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    candidate = text[start_idx : i + 1]
                    candidates.append(candidate)
                    break

    # Try each candidate from outermost to innermost
    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Strategy 3: Try to repair truncated JSON
            repaired = _repair_json(candidate)
            if repaired:
                try:
                    return json.loads(repaired)
                    break
                except json.JSONDecodeError:
                    pass

    return None


def _repair_json(text: str) -> str | None:
    """Attempt to repair common JSON issues from truncated/malformed LLM output.

    Handles: unterminated strings, missing closing brackets, extra data.
    """
    text = text.strip()
    if not text:
        return None

    # Remove trailing content after the last complete value (handles extra data)
    # Try to find the last } or ] that balances
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue
        depth = 0
        in_string = False
        escape = False
        last_complete = -1
        for i, ch in enumerate(text[start_idx:], start_idx):
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == start_char:
                depth += 1
            elif ch == end_char:
                depth -= 1
                if depth == 0:
                    last_complete = i
                    break
        if last_complete > start_idx:
            candidate = text[start_idx : last_complete + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

    return None


def _as_opportunities(data: Any) -> list[dict]:
    """Accept a single object, {"opportunities": [...]}, or a bare list."""
    if isinstance(data, dict) and isinstance(data.get("opportunities"), list):
        items = data["opportunities"]
    elif isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = [data]
    else:
        raise ValueError("extractor returned neither an object nor a list")
    return [item for item in items if isinstance(item, dict)]


def _parse_deadline(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    v = value.strip().replace("Z", "+00:00")
    date_only = len(v) == 10
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        try:
            dt = datetime.strptime(v[:10], "%Y-%m-%d")
            date_only = True
        except ValueError:
            return None
    if date_only:
        dt = dt.replace(hour=23, minute=59, second=59)  # a bare date is valid through that day
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    return dt


def _filled(opp: dict) -> int:
    return sum(1 for k, v in opp.items() if not k.startswith("_") and v not in (None, "", [], {}))


def _evidence_ratio(opp: dict, page_text: str) -> float | None:
    """Share of evidence quotes that really appear in the page text (hallucination signal)."""
    evidence = opp.get("field_evidence")
    if not isinstance(evidence, dict) or not evidence:
        return None
    haystack = _norm(page_text)
    quotes = [_norm(q) for q in evidence.values() if isinstance(q, str) and q.strip()]
    if not quotes:
        return None
    return round(sum(1 for q in quotes if q and q in haystack) / len(quotes), 2)


def _dedupe_key(opp: dict) -> str:
    org = _norm(opp.get("organization_name"))
    title = _norm(opp.get("title"))
    if org:
        return f"{org}|{title}"
    return f"{domain_of(opp.get('_official_source_url') or opp.get('_source_url') or '')}|{title}"


def _build_prompt(url: str, text: str, now: datetime, hint: str) -> str:
    return (
        "Extract all opportunity fields from this page text.\n"
        f"Today's date: {now:%Y-%m-%d} (IST). Parse deadlines to ISO 8601 with timezone.\n"
        f"Page URL: {url}\n"
        f"{hint}"
        "Page text:\n"
        f"{text}\n\n"
        "For each field, provide the exact quote from the page as evidence.\n"
        "If a field is not found, set it to null. NEVER invent values.\n"
        "Return JSON with all fields and field_evidence."
        f"{_EXTRA_INSTRUCTIONS}"
    )


def _structured_hint(meta: dict) -> str:
    items = meta.get("structured") or []
    if not items:
        return ""
    return (
        "Structured data found on the page (use only to confirm what the text says):\n"
        + json.dumps(items[:5], ensure_ascii=False)
        + "\n"
    )


def _reject_reason(opp: dict, page_closed: bool, now: datetime) -> str | None:
    """Return why this opportunity must not be shown, or None to keep it."""
    if not opp.get("title"):
        return "no title"
    if opp.get("is_open") is False:
        return "marked closed"
    deadline = opp.get("_deadline_dt")
    if deadline is not None and deadline < now:
        return "deadline passed"
    if page_closed and deadline is None and opp.get("deadline_type") != "rolling":
        return "page says closed"
    if _cfg("exclude_fee_based", True) and opp.get("fee_required") is True:
        return "applicants must pay a fee"
    if _cfg("exclude_stipend_paying", False) and (opp.get("stipend_min") or 0) > 0:
        return "stipend-paying (excluded by config)"
    if opp.get("is_abroad") is True and opp.get("fully_sponsored") is not True:
        return "abroad but not confirmed fully sponsored"
    if _cfg("require_iiit_eligible", True) and opp.get("iiit_eligible") is False:
        return "not open to IIIT students"
    return None


async def _find_official_by_search(
    searx: SearXNGClient, fetcher: PageFetcher, org: str, title: str
) -> str | None:
    """Last resort: search for the organisation's own page and verify it mentions the org."""
    if not org:
        return None
    response = await searx.search(f"{org} {title} official apply", num_results=8)
    org_tokens = [t for t in _norm(org).split() if len(t) > 2]
    tried = 0
    for result in response.results or []:
        if is_aggregator(result.url) or is_social(result.url):
            continue
        tried += 1
        if tried > 3:
            break
        page = await fetcher.fetch_page(result.url)
        text = _norm(page.text if page else "")
        if page and org_tokens and all(t in text for t in org_tokens[:2]):
            return page.url
    return None


# --------------------------------------------------------------------------- node
async def fetch_extract(
    state: PipelineState,
    db: AsyncSession,
    llm: LLMRouter,
) -> PipelineState:
    """Fetch original page, extract all template fields with evidence quotes."""
    now = datetime.now(IST)
    fetcher = PageFetcher()
    searx = SearXNGClient()

    max_pages = int(_cfg("max_pages_per_run", 40))
    max_results = int(_cfg("max_results_per_run", 40))
    target = int(_cfg("target_opportunities", 20))
    wave_size = int(_cfg("fetch_concurrency", 5))
    max_depth = int(_cfg("max_link_depth", 1))
    max_chars = int(_cfg("extract_max_chars", 10000))
    require_official = bool(_cfg("require_official_source", True))

    queue: deque[dict] = deque()
    queued: set = set()

    def enqueue(url: str, title: str = "", snippet: str = "", depth: int = 0) -> None:
        if not url:
            return
        key = canonicalize_url(url)
        if key in queued:
            return
        queued.add(key)
        queue.append({"url": url, "title": title, "snippet": snippet, "depth": depth})

    for candidate in state.candidates:
        enqueue(
            candidate.get("primary_source") or candidate.get("url", ""),
            candidate.get("title", ""),
            candidate.get("snippet", ""),
        )

    results: dict[str, dict] = {}   # dedupe_key -> opportunity
    attempts = 0
    max_attempts = max_pages * 2

    async def load(item: dict) -> dict | None:
        """Fetch one page; for aggregators resolve to the official page when possible."""
        page = await fetcher.fetch_page(item["url"])
        if not page or not page.text:
            return None
        html = None if page.is_pdf else page.text
        text = page.text if page.is_pdf else fetcher.extract_text(page.text, page.url)
        if not text:
            return None
        loaded = {
            "url": page.url, "html": html, "text": text,
            "meta": fetcher.extract_metadata(html, page.url) if html else {},
            "discovered_via": None, "official_url": None if is_aggregator(page.url) else page.url,
        }
        if html and is_aggregator(page.url):
            for official in fetcher.find_official_links(html, page.url, limit=3):
                official_page = await fetcher.fetch_page(official)
                if not official_page or not official_page.text:
                    continue
                official_text = (
                    official_page.text if official_page.is_pdf
                    else fetcher.extract_text(official_page.text, official_page.url)
                )
                loaded["official_url"] = official_page.url
                official_meta = (
                    {}
                    if official_page.is_pdf
                    else fetcher.extract_metadata(official_page.text, official_page.url)
                )
                if official_text and len(official_text) > 400:
                    # Extract from the organiser's own page; it is the authoritative source.
                    loaded.update(
                        url=official_page.url,
                        html=None if official_page.is_pdf else official_page.text,
                        text=official_text,
                        discovered_via=page.url,
                        meta=official_meta,
                    )
                break  # keep aggregator text if the official page is thin (JS-only site)
        return loaded

    while queue and attempts < max_attempts and state.pages_fetched < max_pages and len(results) < max_results and len(results) < target:
        wave: list[dict] = []
        while queue and len(wave) < wave_size and attempts + len(wave) < max_attempts:
            wave.append(queue.popleft())
        attempts += len(wave)
        loaded_pages = await asyncio.gather(*(load(item) for item in wave), return_exceptions=True)

        for item, loaded in zip(wave, loaded_pages, strict=False):
            if isinstance(loaded, Exception) or not loaded:
                continue
            if state.pages_fetched >= max_pages:
                break
            state.pages_fetched += 1
            url = loaded["url"]
            page_text = loaded["text"]
            page_closed = looks_closed(page_text)
            extension_hint = deadline_extended_hint(page_text)

            # Clean and truncate
            text = truncate(clean_text(page_text), max_chars)  # Context discipline
            prompt = _build_prompt(url, text, now, _structured_hint(loaded["meta"]))

            try:
                opportunities: list[dict] = []
                last_error: Exception | None = None
                for _ in range(2):  # one retry for malformed JSON
                    response = await llm.chat(
                        messages=[{"role": "user", "content": prompt}],
                        prompt_version="extractor_v1",
                        db=db,
                        temperature=0.1,
                    )
                    state.llm_calls += 1
                    state.llm_tokens += response.input_tokens + response.output_tokens
                    parsed = _parse_llm_json(response.text)
                    if parsed is not None:
                        try:
                            opportunities = _as_opportunities(parsed)
                            last_error = None
                            break
                        except ValueError as exc:
                            last_error = exc
                    else:
                        last_error = ValueError("Empty or non-JSON LLM response")
                if last_error:
                    raise last_error
            except Exception as e:
                state.errors.append({"stage": "fetch_extract", "url": url, "error": str(e)})
                continue

            for opp in opportunities:
                opp["_source_url"] = url
                opp["_source_title"] = item.get("title", "")
                opp["_source_snippet"] = item.get("snippet", "")
                opp["_discovered_via"] = loaded["discovered_via"] or (item["url"] if item["url"] != url else None)
                # Verified = we actually fetched that page; an LLM-supplied URL is kept but flagged.
                opp["_official_source_url"] = loaded["official_url"] or opp.get("official_source_url") or None
                opp["_official_verified"] = bool(loaded["official_url"])
                opp["_evidence_ratio"] = _evidence_ratio(opp, page_text)

                deadline = _parse_deadline(opp.get("registration_deadline"))
                opp["_deadline_dt"] = deadline
                if deadline is not None:
                    opp["registration_deadline"] = deadline.isoformat()
                opp["_deadline_extended"] = bool(opp.get("deadline_extended")) or extension_hint

                reason = _reject_reason(opp, page_closed, now)
                if reason:
                    logger.info("skip %r (%s): %s", opp.get("title"), url, reason)
                    continue

                # Always resolve the main official source.
                is_event = _norm(opp.get("opportunity_type")) in _EVENT_TYPES
                if not opp["_official_source_url"] or is_aggregator(opp["_official_source_url"]):
                    if is_event and is_event_platform(url):
                        opp["_official_source_url"] = url  # hackathon platform is the registration page
                    else:
                        found = await _find_official_by_search(
                            searx, fetcher, opp.get("organization_name") or "", opp.get("title") or ""
                        )
                        opp["_official_source_url"] = found
                        opp["_official_verified"] = bool(found)
                opp["_official_found"] = bool(opp["_official_source_url"])
                if require_official and not opp["_official_found"]:
                    logger.info("skip %r: no official source found", opp.get("title"))
                    continue

                opp["_dedupe_key"] = _dedupe_key(opp)
                existing = results.get(opp["_dedupe_key"])
                if existing is None:
                    results[opp["_dedupe_key"]] = opp
                else:
                    # Same opportunity seen twice: keep the richer record. If the two
                    # deadlines differ this is an extension/revision - keep the later one.
                    old_dl, new_dl = existing.get("_deadline_dt"), opp.get("_deadline_dt")
                    keep = opp if _filled(opp) > _filled(existing) else existing
                    extended = bool(existing.get("_deadline_extended") or opp.get("_deadline_extended"))
                    if old_dl and new_dl and old_dl != new_dl:
                        extended = True
                    later = max((d for d in (old_dl, new_dl) if d), default=None)
                    if later:
                        keep["_deadline_dt"] = later
                        keep["registration_deadline"] = later.isoformat()
                    keep["_deadline_extended"] = extended
                    results[opp["_dedupe_key"]] = keep

            # Listing / careers pages: mine sibling opportunities (depth-limited).
            if loaded["html"] and item["depth"] < max_depth and len(opportunities) != 1:
                for link in fetcher.find_opportunity_links(loaded["html"], url, limit=8):
                    enqueue(link, depth=item["depth"] + 1)

    # Drop opportunities whose apply link is definitely dead (404/410); unknown stays.
    final: list[dict] = list(results.values())
    if _cfg("check_apply_links", True):
        checks = await asyncio.gather(
            *(
                fetcher.check_link(o["apply_url"]) if o.get("apply_url") else asyncio.sleep(0, result=None)
                for o in final
            ),
            return_exceptions=True,
        )
        kept = []
        for opp, check in zip(final, checks, strict=False):
            if isinstance(check, tuple):
                live, status = check
                opp["_apply_link_live"] = True if live else (False if status in (404, 410) else None)
                if status in (404, 410):
                    logger.info("skip %r: apply link %s returned %s", opp.get("title"), opp.get("apply_url"), status)
                    continue
            kept.append(opp)
        final = kept

    for opp in final:  # datetimes are internal; keep the JSON-friendly ISO string only
        opp.pop("_deadline_dt", None)

    if len(final) < target:
        logger.warning(
            "fetch_extract: only %d opportunities (target %d); %d pages fetched",
            len(final), target, state.pages_fetched,
        )

    state.extracted_fields = final
    state.stages_completed.append("fetch_extract")
    state.current_stage = "verify"
    return state
