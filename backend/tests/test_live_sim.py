"""Live simulation source tests — prices actually vary across ticks."""
from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

from collectors.core.models import Availability, FlightSearchQuery
from collectors.sources.live_sim import SIM_SOURCE_IDS, LiveSimSource

QUERY = FlightSearchQuery(
    origin="DEL", destination="BOM", departure_date=date.today() + timedelta(days=7),
    advance_days=7,
)


@pytest.mark.anyio
async def test_search_returns_canonical_quotes():
    source = LiveSimSource("sim-ota-alpha")
    quotes = await source.search(QUERY)
    assert len(quotes) >= 1
    q = quotes[0]
    assert (q.source_id, q.origin, q.destination) == ("sim-ota-alpha", "DEL", "BOM")
    assert q.currency == "INR"
    for q in quotes:
        if q.availability is Availability.AVAILABLE:
            assert q.total_fare and q.total_fare > 0
            assert q.base_fare and q.taxes is not None
        else:
            assert q.total_fare is None  # sold-out is never a zero price


@pytest.mark.anyio
async def test_off_basket_route_returns_empty():
    source = LiveSimSource("sim-ota-alpha")
    q = FlightSearchQuery(
        origin="BLR", destination="CCU",
        departure_date=date.today() + timedelta(days=7), advance_days=7,
    )
    assert await source.search(q) == []


@pytest.mark.anyio
async def test_prices_move_across_ticks():
    """Two calls in the same 15s tick are identical; forcing a new tick
    changes prices — this is what makes the demo visibly 'live'."""
    source = LiveSimSource("sim-ota-alpha")
    same = await source.search(QUERY)
    again = await source.search(QUERY)
    assert [q.total_fare for q in same] == [q.total_fare for q in again]

    orig = time.time
    try:
        time.time = lambda: orig() + 60  # jump to next tick
        nxt = LiveSimSource("sim-ota-alpha")
        moved = await nxt.search(QUERY)
        fares_a = sorted(q.total_fare or 0 for q in same)
        fares_b = sorted(q.total_fare or 0 for q in moved)
        assert fares_a != fares_b
    finally:
        time.time = orig


@pytest.mark.anyio
async def test_each_sim_source_id_works():
    for sid in SIM_SOURCE_IDS:
        quotes = await LiveSimSource(sid).search(QUERY)
        assert all(q.source_id == sid for q in quotes)


@pytest.mark.anyio
async def test_rejects_unknown_source_id():
    with pytest.raises(ValueError):
        LiveSimSource("sim-nonexistent")


@pytest.mark.anyio
async def test_health_check_ok():
    health = await LiveSimSource("sim-ota-alpha").health_check()
    assert health.ok and health.source_id == "sim-ota-alpha"
