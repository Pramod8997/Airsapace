"""Compliance-first scraping engine (PS 26056 "Expected Solution (a)").

Ethical collection is a gate, not an afterthought: every request is checked
against the target's robots.txt first, rate-limited per source, and any
restriction signal (CAPTCHA, 403/429, robots disallow) raises
SourcePolicyError -> the job is recorded FAILED with the exact error class.
Nothing is ever bypassed: no CAPTCHA solving, no IP rotation, no header
spoofing beyond a declared user agent.

The engine is source-agnostic: ScrapeTarget describes any portal; the
LiveSimPortal below is a controllable target that behaves like a real fare
site (HTML results, CAPTCHA occasionally, robots.txt gating) so the scraping
path itself — fetch, parse, canonical mapping — is exercised end-to-end in
the demo without touching any real portal.

Swapping in a real portal = subclass ScrapeTarget with its URL template and
parser; robots.txt, rate limit, and failure handling stay identical.
"""
from __future__ import annotations

import asyncio
import re
import time
import urllib.robotparser as robotparser
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

from collectors.core.base_source import FlightSource, SourcePolicyError
from collectors.core.models import Availability, FlightQuote, FlightSearchQuery, SourceHealth

IST = ZoneInfo("Asia/Kolkata")
USER_AGENT = "AirStatIndia-SIH26056/1.0 (+research; contact: team@example.com)"

SCRAPE_ENGINE_VERSION = "ethical-v2"  # v1 lost to a reset; v2 adds anti-bot signatures


class RobotPolicy:
    """robots.txt gate, cached per host. Disallow -> SourcePolicyError, never
    fetched anyway. Fetched with our declared UA so the site can identify us.

    robots.txt unreachable with 5xx -> treat as fully disallowed (RFC 9309);
    4xx -> allow-all. Cache is simple and per-process (24h not enforced —
    short-lived demo processes make TTL moot; re-fetch per process run).
    """

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client
        self._cache: dict[str, robotparser.RobotFileParser] = {}

    async def _load(self, robots_url: str) -> robotparser.RobotFileParser:
        rp = robotparser.RobotFileParser()
        if self._client is not None:
            resp = await self._client.get(robots_url)
            if resp.status_code >= 500:
                # RFC 9309: unreachable (5xx) => must assume disallow
                rp.parse(["User-agent: *", "Disallow: /"])
            elif resp.status_code >= 400:
                rp.parse([])  # 4xx => allow all
            else:
                rp.parse(resp.text.splitlines())
        else:
            rp.parse(["User-agent: *", "Disallow: /"])  # no client: fail closed
        self._cache[robots_url] = rp
        return rp

    async def allowed(self, url: str) -> bool:
        base = httpx.URL(url)
        robots_url = str(base.copy_with(path="/robots.txt", query=None))
        rp = self._cache.get(robots_url) or await self._load(robots_url)
        return rp.can_fetch(USER_AGENT, url)


class RateLimiter:
    """Simple per-source token interval. Ceiling: single-process asyncio lock
    # ponytail: per-source locks + jitter if we ever run distributed collectors."""

    def __init__(self, min_interval_s: float = 5.0):
        self._interval = min_interval_s
        self._lock = asyncio.Lock()
        self._last = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._last + self._interval - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._last = time.monotonic()


# TRD §12 resilience: bounded retry budget = 2 retries, exponential backoff.
RETRY_BACKOFF_S = (1.0, 4.0)
RETRY_AFTER_CAP_S = 60.0  # never sleep longer than this on a server's Retry-After


def _retry_after_s(resp: httpx.Response) -> float | None:
    """Retry-After header -> capped seconds. None when absent or in the
    HTTP-date form (fall back to normal backoff rather than parsing dates)."""
    value = resp.headers.get("retry-after")
    if value is None:
        return None
    try:
        return min(float(value), RETRY_AFTER_CAP_S)
    except ValueError:
        return None


FARE_ROW_RE = re.compile(
    '<div class="fare-row" data-airline="(?P<airline>[A-Z0-9]{2})" '
    'data-price="(?P<price>[0-9.]+)" data-soldout="(?P<soldout>[01])" '
    'data-time="(?P<time>[0-9:]+)" data-flight="(?P<flight>[A-Z0-9]+)"[^>]*>'
)


def _looks_like_captcha(body: str) -> bool:
    return bool(re.search(r"(?i)captcha|challenge-platform|cf-chl|px-captcha", body[:5000]))


def _anti_bot_signature(resp: httpx.Response) -> str | None:
    """Documented detection markers, never bypassed:
    - Cloudflare: 'cf-mitigated: challenge' header
    - Akamai: _abck/bm_sz cookies + 403 'Access Denied' with 'Reference #'
    """
    if resp.headers.get("cf-mitigated") == "challenge":
        return "cloudflare_challenge"
    body = resp.text[:3000]
    if resp.status_code == 403 and "Access Denied" in body and re.search(r"Reference\s*#", body):
        return "akamai_block"
    if "_abck" in resp.headers.get("set-cookie", ""):
        return "akamai_bot_manager_cookie"
    return None


def parse_fare_rows(html: str, query: FlightSearchQuery, source_id: str) -> list[FlightQuote]:
    """HTML -> canonical quotes (module-level so the JS engine maps fares with
    the exact same logic). Parse failures -> no quotes (job PARTIAL),
    never fabricated prices."""
    collected = datetime.now(IST)
    quotes: list[FlightQuote] = []
    for m in FARE_ROW_RE.finditer(html):
        price = float(m.group("price"))
        sold = m.group("soldout") == "1"
        quotes.append(FlightQuote(
            source_id=source_id,
            origin=query.origin,
            destination=query.destination,
            departure_date=query.departure_date,
            departure_time=m.group("time"),
            airline=m.group("airline"),
            flight_number=m.group("flight"),
            advance_days=query.advance_days,
            base_fare=price,
            taxes=0.0,
            mandatory_fees=0.0,
            total_fare=price,
            availability=Availability.SOLD_OUT if sold else Availability.AVAILABLE,
            collected_at=collected,
        ))
    return quotes


class ScrapeEngine:
    """Fetch + parse + canonical-map, with robots gate and rate limit. Raises
    SourcePolicyError on ANY restriction; callers record FAILED jobs.

    Resilience (TRD §12): transient failures (network errors, 5xx) are retried
    up to 2 times with exponential backoff; a 429/503 Retry-After is honored
    once, capped at 60s. Policy stops (robots disallow, 401/403, 429 without
    Retry-After, CAPTCHA) raise immediately and are never retried."""

    def __init__(self, client: httpx.AsyncClient | None = None, min_interval_s: float = 5.0):
        if not client:
            client = httpx.AsyncClient(
                timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            )
        self._client = client
        self._robots = RobotPolicy(self._client)
        self._limiter = RateLimiter(min_interval_s)

    async def fetch_page(self, url: str) -> str:
        if not await self._robots.allowed(url):
            raise SourcePolicyError(f"robots.txt disallows {url} — not fetching")
        await self._limiter.wait()
        body = (await self._get_with_retry(url)).text
        if _looks_like_captcha(body):
            raise SourcePolicyError(f"CAPTCHA challenge at {url} — pausing, never bypassing")
        return body

    async def fetch_bytes(self, url: str) -> bytes:
        """Binary variant (published tariff PDFs): identical compliance path."""
        if not await self._robots.allowed(url):
            raise SourcePolicyError(f"robots.txt disallows {url} — not fetching")
        await self._limiter.wait()
        return (await self._get_with_retry(url)).content

    async def _get_with_retry(self, url: str) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(1 + len(RETRY_BACKOFF_S)):
            try:
                resp = await self._client.get(url)
            except (httpx.HTTPError, OSError) as exc:  # timeout / connect / DNS
                last_exc = exc
                if attempt < len(RETRY_BACKOFF_S):
                    await asyncio.sleep(RETRY_BACKOFF_S[attempt])
                continue
            if resp.status_code == 200:
                return resp
            if resp.status_code in (401, 403):
                reason = _anti_bot_signature(resp) or f"source refused ({resp.status_code})"
                raise SourcePolicyError(f"{reason} at {url} — pausing")
            if resp.status_code == 429:
                wait_s = _retry_after_s(resp)
                if wait_s is None or attempt == len(RETRY_BACKOFF_S):
                    raise SourcePolicyError(f"throttled (429) at {url} — pausing")
                await asyncio.sleep(wait_s)
                continue
            if resp.status_code >= 500:
                last_exc = RuntimeError(f"HTTP {resp.status_code} from {url}")
                if attempt < len(RETRY_BACKOFF_S):
                    wait_s = _retry_after_s(resp) or RETRY_BACKOFF_S[attempt]
                    await asyncio.sleep(wait_s)
                continue
            raise RuntimeError(f"HTTP {resp.status_code} from {url}")
        assert last_exc is not None
        raise last_exc

    def parse_fares(self, html: str, query: FlightSearchQuery) -> list[FlightQuote]:
        """HTML -> canonical quotes. Parse failures -> no quotes (job PARTIAL),
        never fabricated prices."""
        return parse_fare_rows(html, query, "scrape-portal-demo")


class LiveSimPortal(FlightSource):
    """FlightSource adapter that scrapes the local simulation portal
    (scripts/serve_sim_portal.py). Exercises the full scraping path —
    robots.txt check, HTML fetch, regex parse, canonical mapping — against a
    target we are permitted to collect from."""

    source_id = "scrape-portal-demo"
    adapter_version = "1.0"
    DEFAULT_BASE = "http://127.0.0.1:8811"

    def __init__(self, base_url: str = DEFAULT_BASE, engine: ScrapeEngine | None = None):
        self._base = base_url.rstrip("/")
        if not engine:
            engine = ScrapeEngine()
        self._engine = engine

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        url = (
            f"{self._base}/flights/search?origin={query.origin}"
            f"&destination={query.destination}&date={query.departure_date.isoformat()}"
        )
        html = await self._engine.fetch_page(url)
        quotes = self._engine.parse_fares(html, query)
        for q in quotes:
            q.source_id = self.source_id
        return quotes

    async def health_check(self) -> SourceHealth:
        try:
            resp = await self._engine._client.get(f"{self._base}/health")
            ok = resp.status_code == 200
            detail = "" if ok else f"HTTP {resp.status_code}"
        except Exception as exc:  # engine never raises raw errors to health
            ok, detail = False, str(exc)
        return SourceHealth(
            source_id=self.source_id, ok=ok, detail=detail,
            checked_at=datetime.now(IST),
        )


async def _demo() -> None:
    portal = LiveSimPortal()
    health = await portal.health_check()
    print(f"portal health: {health.ok} {health.detail}")
    from collectors.core.models import Availability

    quotes = await portal.search(FlightSearchQuery(
        origin="DEL", destination="BOM", departure_date=date_today(), advance_days=7,
    ))
    for q in quotes:
        print(q.airline, q.departure_time, q.total_fare, q.availability)


def date_today():
    from datetime import date

    return date.today()


if __name__ == "__main__":
    asyncio.run(_demo())
