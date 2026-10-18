"""Node 2: Search - SearXNG primary, DuckDuckGo fallback.

What this node does on top of plain search:
1. Plans queries: the pipeline's own queries plus built-in seed queries that cover every
   category the product needs (government, startup, multinational, entrepreneurship events,
   mass-level hackathons, fully funded internships abroad, IIIT-eligible), stamped with the
   current month/year so results are current.
2. Runs queries concurrently (SearXNG, multi-page, year time filter) and falls back to
   DuckDuckGo when a query yields too little.
3. De-duplicates by a better canonical URL (keeps meaningful ?id= params, strips tracking).
4. Ranks results: official domains and career pages up, aggregators and stale/listicle
   pages down, repeat hits across queries up.
5. Company expansion: for organisations that show up with a careers/internship page, runs
   extra ``site:`` queries so a company offering several roles yields all of them.

Optional config keys (all have defaults): search_seed_queries, search_max_queries,
search_pages, search_results_per_query, search_time_range, search_concurrency,
search_min_hits, search_expand_domains, max_search_results.
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlparse

from sqlmodel.ext.asyncio.session import AsyncSession

from ..config import config
from ..schemas.pipeline import PipelineState
from ..tools.ddg import DuckDuckGoClient
from ..tools.fetcher import (
    is_aggregator,
    is_event_platform,
    is_official_domain,
    is_social,
    registered_domain,
)
from ..tools.searxng import SearXNGClient

logger = logging.getLogger(__name__)

IST = timezone(timedelta(hours=5, minutes=30))

_TRACKING_PARAMS = {"fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ref", "ref_src", "trk", "trkid", "spm"}


def _cfg(name: str, default):
    value = getattr(config, name, None)
    return default if value is None else value


def canonicalize_url(url: str) -> str:
    """Canonicalize URL for deduplication.

    Host (no www) + lowercase path without trailing slash + sorted non-tracking query
    params. Query params are kept on purpose: ``/jobs?id=1`` and ``/jobs?id=2`` are
    different opportunities. Scheme and fragment are ignored.
    """
    parsed = urlparse(url)
    netloc = parsed.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = parsed.path.rstrip("/").lower()
    kept = sorted(
        (k.lower(), v)
        for k, v in parse_qsl(parsed.query)
        if k.lower() not in _TRACKING_PARAMS and not k.lower().startswith("utm_")
    )
    key = f"{netloc}{path}"
    return f"{key}?{urlencode(kept)}" if kept else key


# ------------------------------------------------------------------------- queries
def _seed_queries(now: datetime) -> list[tuple[str, str]]:
    """Category-covering queries stamped with the current date. [(query, category_hint)]"""
    y = now.year
    month = now.strftime("%B %Y")
    return [
        # Government
        (f"government internship {y} engineering students apply online last date", "government"),
        (f"PSU internship {y} B.Tech students apply official notification", "government"),
        (f"government recruitment {y} engineering graduates apply online notification", "government"),
        (f"ministry internship scheme {y} students apply", "government"),
        (f"ISRO DRDO BARC CSIR NIC internship {y} apply", "government"),
        # Private companies
        (f"startup internship {y} B.Tech students apply hiring interns", "startup"),
        (f"startup hiring fresher engineers {y} careers apply", "startup"),
        (f"multinational company internship {y} India engineering students careers apply", "multinational"),
        (f"summer winter internship {y} global tech company India students apply", "multinational"),
        # Entrepreneurship events
        (f"entrepreneurship event college students {y} registration open", "entrepreneurship"),
        (f"startup pitch competition {y} college students registration deadline", "entrepreneurship"),
        (f"E-Summit {y} startup competition students register", "entrepreneurship"),
        # Hackathons (mass level)
        (f"national level hackathon {month} registration open", "hackathon"),
        (f"hackathon {y} college students registration open prize pool", "hackathon"),
        (f"online hackathon {y} India students register last date", "hackathon"),
        (f"Smart India Hackathon {y}", "hackathon"),
        # Fully funded abroad
        (f"fully funded internship abroad {y} Indian students", "abroad"),
        (f"fully sponsored international research internship {y} undergraduate India", "abroad"),
        (f"DAAD WISE {y} internship Germany Indian students", "abroad"),
        (f"Mitacs Globalink Research Internship {y} India", "abroad"),
        # IIIT eligibility
        (f"internship {y} eligible IIIT students apply", "iiit"),
        (f"internship {y} open to IIIT IIT NIT students", "iiit"),
    ]


def _round_robin(seeds: list[tuple[str, str]], limit: int) -> list[tuple[str, str]]:
    """Take seeds category by category so a small budget still covers every category."""
    groups: dict[str, list[tuple[str, str]]] = {}
    for item in seeds:
        groups.setdefault(item[1], []).append(item)
    picked: list[tuple[str, str]] = []
    while len(picked) < limit and any(groups.values()):
        for items in groups.values():
            if items and len(picked) < limit:
                picked.append(items.pop(0))
    return picked


def _plan_queries(
    state_queries: list[str] | None, now: datetime, max_queries: int, use_seeds: bool
) -> list[tuple[str, str | None]]:
    """Pipeline queries first, but always leave room for the seed categories."""
    seeds = _round_robin(_seed_queries(now), max_queries // 2) if use_seeds else []
    pipeline_cap = max_queries - len(seeds)
    planned: list[tuple[str, str | None]] = []
    seen = set()

    def add(query: str, category: str | None) -> None:
        key = " ".join(query.lower().split())
        if query and query.strip() and key not in seen:
            seen.add(key)
            planned.append((query, category))

    for q in state_queries or []:  # de-duplicate first, then cap
        if len(planned) >= pipeline_cap:
            break
        add(q, None)
    for q, category in seeds:
        add(q, category)
    return planned[:max_queries]


# ------------------------------------------------------------------------- ranking
_KEYWORDS = (
    "internship", "intern ", "hackathon", "fellowship", "apply", "registration",
    "last date", "deadline", "recruitment", "notification", "opening", "hiring",
)
_CAREER_HINTS = ("career", "jobs", "internship", "recruit", "vacanc", "opening", "hackathon", "apply")
_LISTICLE_RE = re.compile(
    r"\b(top|best)\s+\d+|\blist of\b|\bhow to\b|\bresume\b|\bsalary\b|\binterview questions\b",
    re.I,
)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_SKIP_EXPAND = {"wikipedia.org", "github.com", "google.com", "gov.in"}


def _score(entry: dict, now: datetime) -> float:
    url = entry["url"]
    text = f"{entry['title']} {entry['snippet']}".lower()
    path = urlparse(url).path.lower()
    score = 0.0

    if is_official_domain(url):
        score += 30
    if is_aggregator(url):
        score -= 10  # still useful for discovery; the official source gets resolved later
    if any(h in path for h in _CAREER_HINTS):
        score += 8
    score += min(5, sum(1 for k in _KEYWORDS if k in text)) * 3

    years = {int(y) for y in _YEAR_RE.findall(f"{text} {url}")}
    if now.year in years:
        score += 10
    elif now.year + 1 in years:
        score += 6
    elif years and max(years) < now.year:
        score -= 15  # only mentions past years: probably stale

    if _LISTICLE_RE.search(text):
        score -= 8
    score += max(0, 10 - int(entry.get("position") or 10))
    score += min(6, 2 * (entry.get("hits", 1) - 1))  # same URL surfaced by several queries
    return score


# --------------------------------------------------------------------- query runner
async def _search_one(
    searxng: SearXNGClient,
    ddg: DuckDuckGoClient,
    query: str,
    per_query: int,
    pages: int,
    time_range: str | None,
    min_hits: int,
) -> list:
    results: list = []
    response = await searxng.search(query, per_query, pages=pages, time_range=time_range)
    results.extend(response.results or [])
    if len(results) < min_hits:
        try:
            ddg_response = await ddg.search(query)
            results.extend(getattr(ddg_response, "results", None) or [])
        except Exception as e:
            logger.warning("DuckDuckGo fallback failed for %r: %s", query, e)
    return results


def _merge(by_key: dict[str, dict], results: list, query: str, category: str | None) -> None:
    for result in results:
        if not result.url:
            continue
        key = canonicalize_url(result.url)
        existing = by_key.get(key)
        if existing:
            existing["hits"] += 1
            continue
        by_key[key] = {
            "url": result.url,
            "title": result.title,
            "snippet": result.snippet,
            "source": result.source,
            "position": result.position,
            "query": query,
            "category_hint": category,
            "hits": 1,
        }


def _pick_expansion_domains(entries: list[dict], limit: int, already: set) -> list[str]:
    """Organisations with a careers/internship page: worth a dedicated site: query."""
    stats: dict[str, dict] = {}
    for entry in entries:
        url = entry["url"]
        if is_aggregator(url) or is_social(url) or is_event_platform(url):
            continue
        domain = registered_domain(url)
        if domain in _SKIP_EXPAND or domain in already:
            continue
        haystack = f"{url.lower()} {entry['title'].lower()}"
        if not any(h in haystack for h in _CAREER_HINTS):
            continue
        s = stats.setdefault(domain, {"count": 0, "official": is_official_domain(url)})
        s["count"] += entry.get("hits", 1)
    ranked = sorted(stats.items(), key=lambda kv: (-kv[1]["count"], not kv[1]["official"]))
    return [domain for domain, _ in ranked[:limit]]


async def search(
    state: PipelineState,
    db: AsyncSession,
) -> PipelineState:
    """Search using SearXNG, fallback to DuckDuckGo. Deduplicate by canonical URL."""
    now = datetime.now(IST)
    searxng = SearXNGClient()
    ddg = DuckDuckGoClient()

    max_queries = int(_cfg("search_max_queries", 40))
    per_query = int(_cfg("search_results_per_query", 15))
    pages = int(_cfg("search_pages", 2))
    time_range = _cfg("search_time_range", "year") or None
    min_hits = int(_cfg("search_min_hits", 3))
    expand_n = int(_cfg("search_expand_domains", 6))
    cap = int(_cfg("max_search_results", 100))
    semaphore = asyncio.Semaphore(int(_cfg("search_concurrency", 4)))

    async def run(query: str, category: str | None):
        async with semaphore:
            results = await _search_one(searxng, ddg, query, per_query, pages, time_range, min_hits)
        return query, category, results

    by_key: dict[str, dict] = {}

    # Pass 1: pipeline queries + category seeds
    plan = _plan_queries(state.queries, now, max_queries, bool(_cfg("search_seed_queries", True)))
    for query, category, results in await asyncio.gather(*(run(q, c) for q, c in plan)):
        _merge(by_key, results, query, category)
    first_pass = len(by_key)

    # Pass 2: companies/organisers that showed up with a careers page -> all their roles
    if expand_n > 0:
        domains = _pick_expansion_domains(list(by_key.values()), expand_n, set())
        expansion = [
            (f"site:{d} internship OR hiring OR apply OR hackathon OR fellowship {now.year}", "company_expansion")
            for d in domains
        ]
        for query, category, results in await asyncio.gather(*(run(q, c) for q, c in expansion)):
            _merge(by_key, results, query, category)

    ranked = list(by_key.values())
    for entry in ranked:
        entry["score"] = round(_score(entry, now), 2)
        entry["is_official_domain"] = is_official_domain(entry["url"])
        entry["is_aggregator"] = is_aggregator(entry["url"])
    ranked.sort(key=lambda e: -e["score"])

    logger.info(
        "search: %d queries, %d unique urls (%d after expansion), keeping %d",
        len(plan), first_pass, len(ranked), min(len(ranked), cap),
    )

    state.search_results = ranked[:cap]  # Cap results per run
    state.stages_completed.append("search")
    state.current_stage = "filter_candidates"
    return state
