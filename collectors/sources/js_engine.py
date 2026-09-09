"""Playwright JS-rendering path behind the same compliance gate (PS 26056).

The problem statement requires handling JavaScript-rendered pages, and names
the Scrapy/Selenium/Playwright toolchain. Real airline/OTA fare search is
JS-rendered AND anti-bot protected; our answer is capability + compliance:
JSScrapeEngine renders with headless Chromium through the exact same gate as
the static engine — robots.txt first, per-source rate limit, declared user
agent, CAPTCHA/anti-bot detection on the rendered result, and
SourcePolicyError (pause, never bypass) on any restriction signal.

Never done here: stealth plugins, headless-detection evasion, UA spoofing,
CAPTCHA solving. Session management is the Playwright browser context — a
real browser session holding cookies across page loads, declared and honest.

Demonstrated on the local sim portal's JS-rendered endpoint
(scripts/serve_sim_portal.py /flights/search-js serves an empty shell; fares
exist only after the browser executes the page's script), so the full path —
gate -> render -> parse -> canonical map — runs in the demo without touching
any real portal.
"""
from __future__ import annotations

import httpx
from datetime import datetime
from zoneinfo import ZoneInfo

from collectors.core.base_source import FlightSource, SourcePolicyError
from collectors.core.models import FlightQuote, FlightSearchQuery, SourceHealth
from collectors.sources.scrape_engine import (
    FARE_ROW_RE,
    RateLimiter,
    RobotPolicy,
    USER_AGENT,
    _looks_like_captcha,
    parse_fare_rows,
)

IST = ZoneInfo("Asia/Kolkata")
JS_ENGINE_VERSION = "ethical-js-v1"
RENDER_TIMEOUT_MS = 15_000


def _playwright_module():
    """Import playwright lazily with a clear install hint — the rest of the
    system never depends on it being installed."""
    try:
        import playwright.async_api as pwa
    except ImportError as exc:
        raise RuntimeError(
            "playwright not installed — the JS-rendering path is optional. "
            "Install with: .venv/bin/pip install playwright && "
            ".venv/bin/playwright install chromium"
        ) from exc
    return pwa


class JSScrapeEngine:
    """Robots-gated, rate-limited, declared-UA Playwright renderer."""

    def __init__(self, client: httpx.AsyncClient | None = None, min_interval_s: float = 5.0):
        _playwright_module()  # fail fast with the install hint
        if not client:
            client = httpx.AsyncClient(
                timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True
            )
        self._client = client  # robots.txt is plain HTTP — no browser needed for the gate
        self._robots = RobotPolicy(self._client)
        self._limiter = RateLimiter(min_interval_s)

    async def render_page(
        self, url: str, marker_selector: str, timeout_ms: int = RENDER_TIMEOUT_MS
    ) -> str:
        """Gate -> render -> return the page HTML once the marker appears.

        The rendered DOM is what a human browser shows; CAPTCHA walls in it
        raise SourcePolicyError — pause, never bypass."""
        if not await self._robots.allowed(url):
            raise SourcePolicyError(f"robots.txt disallows {url} — not fetching")
        await self._limiter.wait()
        pwa = _playwright_module()
        async with pwa.async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=USER_AGENT)  # session: cookies persist in-context
                page = await context.new_page()
                resp = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                if resp is None or resp.status != 200:
                    status = resp.status if resp else "no response"
                    raise SourcePolicyError(f"source refused ({status}) at {url} — pausing")
                if resp.headers.get("cf-mitigated") == "challenge":
                    raise SourcePolicyError(f"cloudflare_challenge at {url} — pausing")
                try:
                    await page.wait_for_selector(marker_selector, timeout=timeout_ms)
                except pwa.TimeoutError as exc:
                    raise RuntimeError(
                        f"marker {marker_selector} never appeared at {url} "
                        "(JS did not render results)"
                    ) from exc
                html = await page.content()
            finally:
                await browser.close()
        if _looks_like_captcha(html):
            raise SourcePolicyError(f"CAPTCHA challenge at {url} — pausing, never bypassing")
        return html


class LiveSimPortalJS(FlightSource):
    """FlightSource over the sim portal's JS-rendered endpoint — proves the
    Playwright path end-to-end: the shell HTML contains no fares, only after a
    browser executes the page's script do .fare-row elements exist."""

    source_id = "scrape-portal-js-demo"
    adapter_version = "1.0"
    DEFAULT_BASE = "http://127.0.0.1:8811"

    def __init__(self, base_url: str = DEFAULT_BASE, engine: JSScrapeEngine | None = None):
        self._base = base_url.rstrip("/")
        self._engine = engine

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        engine = self._engine or JSScrapeEngine()
        url = (
            f"{self._base}/flights/search-js?origin={query.origin}"
            f"&destination={query.destination}&date={query.departure_date.isoformat()}"
        )
        html = await engine.render_page(url, marker_selector=".fare-row")
        return parse_fare_rows(html, query, self.source_id)

    async def health_check(self) -> SourceHealth:
        try:  # plain HTTP probe — health never needs a browser
            resp = await httpx.AsyncClient(timeout=5).get(f"{self._base}/health")
            ok = resp.status_code == 200
            detail = "" if ok else f"HTTP {resp.status_code}"
        except Exception as exc:
            ok, detail = False, str(exc)
        return SourceHealth(
            source_id=self.source_id, ok=ok, detail=detail,
            checked_at=datetime.now(IST),
        )


async def _demo() -> None:
    quotes = await LiveSimPortalJS().search(FlightSearchQuery(
        origin="DEL", destination="BOM", departure_date=datetime.now(IST).date(),
        advance_days=7,
    ))
    for q in quotes:
        print(q.airline, q.departure_time, q.total_fare, q.availability)


if __name__ == "__main__":
    import asyncio

    asyncio.run(_demo())
