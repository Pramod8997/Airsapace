"""Yatra OTA adapter tests — fixture parsing, schema validity, honesty fields."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from collectors.core.models import Availability, FlightSearchQuery
from collectors.sources.yatra import YatraSource, parse_yatra_page

FIXTURES = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"
ROUTES = [
    ("yatra_del_bom", "DEL", "BOM", {6500, 6529, 6447, 6109}),
    ("yatra_del_ccu", "DEL", "CCU", {7376, 7507}),
    ("yatra_bom_blr", "BOM", "BLR", {5050, 5848}),
]


def _query(origin: str, dest: str) -> FlightSearchQuery:
    return FlightSearchQuery(
        origin=origin, destination=dest,
        departure_date=date(2026, 9, 15), advance_days=7,
    )


def _fixture(name: str) -> str:
    path = FIXTURES / f"{name}.txt"
    if not path.exists():
        pytest.skip(f"fixture {path} not saved")
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("name,origin,dest,fares", ROUTES)
def test_fixture_parses_seven_days_with_expected_fares(name, origin, dest, fares):
    quotes = parse_yatra_page(_fixture(name), _query(origin, dest))
    assert len(quotes) == 7
    assert fares <= {q.total_fare for q in quotes}


@pytest.mark.parametrize("name,origin,dest,fares", ROUTES)
def test_quotes_are_schema_valid_and_in_sept_2026(name, origin, dest, fares):
    quotes = parse_yatra_page(_fixture(name), _query(origin, dest))
    for q in quotes:
        assert (q.origin, q.destination) == (origin, dest)
        assert q.source_id == "yatra-ota"
        assert q.currency == "INR"
        assert q.cabin == "economy"
        assert q.availability is Availability.AVAILABLE
        assert q.airline == "MULTI"
        assert q.flight_number is None  # no per-flight prices fabricated
        assert q.departure_date.year == 2026
        assert q.departure_date.month == 9
        assert q.total_fare > 0
        assert q.collected_at.tzinfo is not None


@pytest.mark.parametrize("name,origin,dest,fares", ROUTES)
def test_advance_days_consistent_with_dates(name, origin, dest, fares):
    quotes = parse_yatra_page(_fixture(name), _query(origin, dest))
    collected = quotes[0].collected_at.date()
    assert collected == date(2026, 9, 8)  # "Fares verified on 8 September 2026"
    for q in quotes:
        assert q.advance_days == (q.departure_date - collected).days
    assert [q.departure_date for q in quotes] == sorted(q.departure_date for q in quotes)


def test_components_make_fare_payable():
    """All-in strip fare must flow through quote_payable_fare (base+tax+fees)."""
    from statistical_engine.normalization import quote_payable_fare

    quotes = parse_yatra_page(_fixture("yatra_del_bom"), _query("DEL", "BOM"))
    for q in quotes:
        assert quote_payable_fare(q) == q.total_fare


def test_day_strip_regex_ignores_flight_block_dates():
    """Flight blocks use 'Tue, Sep 15, 2026' — must never match the strip pattern."""
    text = "flight block: Tue, Sep 15, 2026 dep\n1.   Mon, 14 Sep₹6,500 \n"
    quotes = parse_yatra_page(text, _query("DEL", "BOM"))
    assert len(quotes) == 1
    assert quotes[0].total_fare == 6500.0


@pytest.mark.anyio
async def test_search_uses_fixture_mode_by_default():
    quotes = await YatraSource().search(_query("DEL", "BOM"))
    assert len(quotes) == 7 and quotes[0].source_id == "yatra-ota"


@pytest.mark.anyio
async def test_search_returns_empty_for_uncovered_route():
    quotes = await YatraSource().search(_query("MAA", "DEL"))
    assert quotes == []


@pytest.mark.anyio
async def test_health_check_fixture_mode():
    health = await YatraSource().health_check()
    assert health.ok and health.source_id == "yatra-ota"
    assert "ROBOTS_ALLOWED_SEO" in health.detail


@pytest.mark.anyio
async def test_live_mode_routes_through_the_compliance_engine(monkeypatch):
    """YATRA_LIVE=1 must fetch via ScrapeEngine — robots gate, rate limit,
    anti-bot detection — never a raw httpx call (closes the old TODO)."""
    monkeypatch.setenv("YATRA_LIVE", "1")
    fetched: list[str] = []

    class FakeEngine:
        async def fetch_page(self, url: str) -> str:
            fetched.append(url)
            return _fixture("yatra_del_bom")

    quotes = await YatraSource(engine=FakeEngine()).search(_query("DEL", "BOM"))
    assert len(quotes) == 7
    assert fetched == [
        "https://www.yatra.com/cheap-flights/search/delhi-to-mumbai-flights"
    ]
