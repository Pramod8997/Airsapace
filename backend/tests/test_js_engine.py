"""JS-rendering path tests — parse mapping, portal endpoints, browser path.

The browser end-to-end test needs playwright + chromium AND the local sim
portal running; everything else runs browserless.
"""
from __future__ import annotations

import asyncio
import time
from datetime import date

import httpx
import pytest

from collectors.core.models import FlightSearchQuery
from collectors.sources.scrape_engine import parse_fare_rows

SHELL_HTML = "<html><body><h1>results</h1><div id='results'></div></body></html>"
RENDERED_HTML = (
    '<html><body><h1>results</h1><div id="results">'
    '<div class="fare-row" data-airline="6E" data-price="5100.00" data-soldout="0" '
    'data-time="06:40" data-flight="6E137"> 6E DEL-BOM 06:40</div>'
    '<div class="fare-row" data-airline="AI" data-price="5304.00" data-soldout="1" '
    'data-time="09:15" data-flight="AI174"> AI DEL-BOM 09:15</div>'
    "</div></body></html>"
)


def _query() -> FlightSearchQuery:
    return FlightSearchQuery(
        origin="DEL", destination="BOM",
        departure_date=date(2026, 9, 15), advance_days=7,
    )


# ---------------------------------------------------------------- parse mapping


def test_static_fetch_of_a_js_page_sees_no_fares():
    """The whole point of the JS path: regex over the shell finds nothing."""
    assert parse_fare_rows(SHELL_HTML, _query(), "scrape-portal-js-demo") == []


def test_rendered_dom_maps_to_canonical_quotes():
    quotes = parse_fare_rows(RENDERED_HTML, _query(), "scrape-portal-js-demo")
    assert len(quotes) == 2
    assert all(q.source_id == "scrape-portal-js-demo" for q in quotes)
    assert quotes[0].airline == "6E" and quotes[0].total_fare == 5100.0
    assert quotes[0].availability == "AVAILABLE"
    assert quotes[1].availability == "SOLD_OUT"


def test_js_engine_version_is_declared():
    from collectors.sources.js_engine import JS_ENGINE_VERSION

    assert JS_ENGINE_VERSION == "ethical-js-v1"


# ---------------------------------------------------------------- portal endpoints


def _portal_client():
    from fastapi.testclient import TestClient
    from scripts.serve_sim_portal import app

    return TestClient(app)


def test_portal_js_shell_serves_no_fares_server_side():
    with _portal_client() as client:
        body = client.get("/flights/search-js", params={
            "origin": "DEL", "destination": "BOM", "date": "2026-09-15",
        }).text
    assert "search-data" in body  # the script fetches the JSON endpoint
    assert parse_fare_rows(body, _query(), "scrape-portal-js-demo") == []


def test_portal_search_data_returns_json_rows():
    """The portal rolls CAPTCHA (3%) / 403 (2%) per second-seed; retry until a
    clean row payload arrives (expected immediately, bounded for CI)."""
    with _portal_client() as client:
        for _ in range(20):
            resp = client.get("/flights/search-data", params={
                "origin": "DEL", "destination": "BOM", "date": "2026-09-15",
            })
            if resp.status_code == 200 and "rows" in resp.json():
                rows = resp.json()["rows"]
                break
            time.sleep(1.05)  # next seed second
        else:
            pytest.fail("search-data never returned rows (captcha/blocked streak)")
    assert rows, "DEL-BOM must yield fare rows"
    for r in rows:
        assert set(r) >= {"airline", "price", "soldout", "time", "flight"}
        float(r["price"]) > 0


def test_portal_robots_permits_all_search_paths():
    with _portal_client() as client:
        body = client.get("/robots.txt").text
    assert "Allow: /flights/search" in body
    assert "Allow: /flights/search-js" in body
    assert "Allow: /flights/search-data" in body
    assert "Disallow: /admin" in body


# ---------------------------------------------------------------- browser path


def test_browser_render_path_end_to_end():
    pytest.importorskip("playwright")
    try:
        httpx.get("http://127.0.0.1:8811/health", timeout=1.0)
    except httpx.HTTPError:
        pytest.skip("sim portal not running (.venv/bin/python scripts/serve_sim_portal.py)")

    from collectors.sources.js_engine import LiveSimPortalJS

    # occasional portal captcha/403 rolls: retry a few times
    for _ in range(3):
        try:
            quotes = asyncio.run(LiveSimPortalJS().search(_query()))
            break
        except RuntimeError:
            continue
    else:
        pytest.fail("JS render never produced quotes")
    assert quotes
    assert all(q.source_id == "scrape-portal-js-demo" for q in quotes)
    assert all(q.total_fare > 0 for q in quotes)
