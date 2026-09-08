"""Tests for the compliance-first scraping engine (rebuild, ethical-v2)."""
from __future__ import annotations

import asyncio
from datetime import date

import httpx
import pytest

from collectors.core.base_source import SourcePolicyError
from collectors.core.models import FlightSearchQuery
from collectors.sources.scrape_engine import (
    LiveSimPortal,
    RateLimiter,
    RobotPolicy,
    ScrapeEngine,
    _anti_bot_signature,
    _looks_like_captcha,
)


def _query() -> FlightSearchQuery:
    return FlightSearchQuery(
        origin="DEL", destination="BOM",
        departure_date=date(2026, 9, 15), advance_days=7,
    )


# ---------------------------------------------------------------- detectors


def test_captcha_detector():
    assert _looks_like_captcha("<html>verify you are human: CAPTCHA</html>")
    assert _looks_like_captcha("<script src='/challenge-platform/x.js'>")
    assert not _looks_like_captcha("<html><div class='fare-row'>…</div></html>")


def _resp(status=403, headers=None, text="ok") -> httpx.Response:
    return httpx.Response(status_code=status, headers=headers or {}, text=text,
                          request=httpx.Request("GET", "https://x.test/f"))


def test_anti_bot_cloudflare():
    assert _anti_bot_signature(_resp(headers={"cf-mitigated": "challenge"})) == "cloudflare_challenge"


def test_anti_bot_akamai():
    body = "Access Denied You don't have permission ... Reference #18.abc123de"
    assert _anti_bot_signature(_resp(403, text=body)) == "akamai_block"


def test_anti_bot_none_on_normal():
    assert _anti_bot_signature(_resp(200, text="<html>fares</html>")) is None


# ---------------------------------------------------------------- robots gate


def _client_for(robots_body: str, status: int = 200) -> httpx.AsyncClient:
    robots_resp = httpx.Response(status_code=status, text=robots_body,
                                 request=httpx.Request("GET", "https://portal.test/robots.txt"))
    page_resp = httpx.Response(200, text="<html>ok</html>",
                               request=httpx.Request("GET", "https://portal.test/flights/search"))
    handler = lambda request: robots_resp if request.url.path == "/robots.txt" else page_resp
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


ROBOTS_ALLOW = "User-agent: *\nAllow: /flights/search\nDisallow: /admin\n"
ROBOTS_DENY_ALL = "User-agent: *\nDisallow: /\n"


def test_robots_allow_search_path():
    async def run():
        async with _client_for(ROBOTS_ALLOW) as client:
            gate = RobotPolicy(client)
            assert await gate.allowed("https://portal.test/flights/search?origin=DEL")
    asyncio.run(run())


def test_robots_block_admin_path():
    async def run():
        async with _client_for(ROBOTS_ALLOW) as client:
            gate = RobotPolicy(client)
            assert not await gate.allowed("https://portal.test/admin")
    asyncio.run(run())


def test_robots_5xx_fail_closed():
    """RFC 9309: robots.txt unreachable with 5xx => assume disallow."""
    async def run():
        async with _client_for("ignored", status=500) as client:
            gate = RobotPolicy(client)
            assert not await gate.allowed("https://portal.test/flights/search")
    asyncio.run(run())


def test_robots_404_fail_open():
    async def run():
        async with _client_for("gone", status=404) as client:
            gate = RobotPolicy(client)
            assert await gate.allowed("https://portal.test/anything")
    asyncio.run(run())


# ---------------------------------------------------------------- rate limiter


def test_rate_limiter_enforces_interval():
    import time as _time

    async def run() -> float:
        limiter = RateLimiter(min_interval_s=0.2)
        t0 = _time.monotonic()
        await limiter.wait()
        await limiter.wait()  # second call must sleep
        return _time.monotonic() - t0

    elapsed = asyncio.run(run())
    assert elapsed >= 0.18  # ~0.2s spacing (small CI tolerance)


# ---------------------------------------------------------------- engine


def test_fetch_blocked_by_robots_raises_policy_error():
    async def run():
        async with _client_for(ROBOTS_DENY_ALL) as client:
            engine = ScrapeEngine(client=client, min_interval_s=0)
            with pytest.raises(SourcePolicyError, match="robots"):
                await engine.fetch_page("https://portal.test/flights/search")
    asyncio.run(run())


def test_fetch_403_raises_policy_error_with_signature():
    async def run():
        handler = lambda req: httpx.Response(
            403, text="Access Denied Reference #1.22.abc",
            request=httpx.Request("GET", "https://portal.test/f"))
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            engine = ScrapeEngine(client=client, min_interval_s=0)
            with pytest.raises(SourcePolicyError, match="akamai_block"):
                await engine.fetch_page("https://portal.test/f")
    asyncio.run(run())


def test_fetch_captcha_body_raises_policy_error():
    async def run():
        robots = httpx.Response(200, text="User-agent: *\nAllow: /\n",
                                request=httpx.Request("GET", "https://portal.test/robots.txt"))
        page = httpx.Response(200, text="<html>please complete CAPTCHA</html>",
                              request=httpx.Request("GET", "https://portal.test/f"))
        handler = lambda req: robots if req.url.path == "/robots.txt" else page
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            engine = ScrapeEngine(client=client, min_interval_s=0)
            with pytest.raises(SourcePolicyError, match="CAPTCHA"):
                await engine.fetch_page("https://portal.test/f")
    asyncio.run(run())


def test_parse_fares_maps_canonical_quotes():
    html = (
        '<div class="fare-row" data-airline="6E" data-price="5100.00" data-soldout="0" '
        'data-time="06:40" data-flight="6E137">6E DEL-BOM 06:40</div>'
        '<div class="fare-row" data-airline="AI" data-price="5304.00" data-soldout="1" '
        'data-time="09:15" data-flight="AI174">AI DEL-BOM 09:15</div>'
    )
    engine = ScrapeEngine(min_interval_s=0)
    quotes = engine.parse_fares(html, _query())
    assert len(quotes) == 2
    assert quotes[0].airline == "6E" and quotes[0].total_fare == 5100.0
    assert quotes[0].availability == "AVAILABLE"
    assert quotes[1].availability == "SOLD_OUT"
    assert all(q.source_id == "scrape-portal-demo" for q in quotes)


def test_parse_fares_empty_html_yields_nothing():
    engine = ScrapeEngine(min_interval_s=0)
    assert engine.parse_fares("<html>no results</html>", _query()) == []
