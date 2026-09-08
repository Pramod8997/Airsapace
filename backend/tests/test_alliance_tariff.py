"""Tests for the Alliance Air tariff adapter (rebuild, fixture-backed)."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not Path("data/fixtures/alliance_air_tariff_15MAR23.pdf").exists(),
    reason="tariff PDF fixture not present",
)

from collectors.sources.alliance_tariff import (  # noqa: E402
    AllianceTariffSource,
    build_quotes,
    parse_tariff,
)


@pytest.fixture(scope="module")
def parsed():
    return parse_tariff()


def test_pdf_parses_sectors_and_stations(parsed):
    sector_fares, station_fees = parsed
    assert len(sector_fares) >= 10
    assert len(station_fees) >= 60


def test_del_kolkata_sector_present(parsed):
    sector_fares, _ = parsed
    assert ("DEL", "CCU") in sector_fares
    levels = sector_fares[("DEL", "CCU")]
    assert levels[0] == 2500.0  # documented row 36, Fare Level 1


def test_station_fees_known_values(parsed):
    _, station_fees = parsed
    # Delhi: AUDF 66, DVF 0, CUTE 105, UDF 152, PSF 91, ASF 236, GST 5%
    assert station_fees["Delhi"] == (66.0, 0.0, 105.0, 152.0, 91.0, 236.0, 5.0)
    # Kolkata: CUTE 105, UDF 760, ASF 236, GST 5%
    assert station_fees["Kolkata"][:1] == (0.0,)
    assert station_fees["Kolkata"][2] == 105.0
    assert station_fees["Kolkata"][3] == 760.0


def test_quote_fare_math_documented_row(parsed):
    """DEL-CCU Level 1: base 2500 + GST 5% (125) + station fees + convenience 350."""
    sector_fares, station_fees = parsed
    quotes, _ = build_quotes(sector_fares, station_fees,
                             collection_day=date(2026, 9, 8))
    del_ccu = [q for q in quotes if (q.origin, q.destination) == ("DEL", "CCU")]
    assert del_ccu, "DEL-CCU quotes missing"
    q = del_ccu[0]
    assert q.base_fare == 2500.0
    assert q.taxes == 125.0
    # mandatory = sum of all six fee columns for Delhi + Kolkata
    del_fees = station_fees["Delhi"]
    ccu_fees = station_fees["Kolkata"]
    expected_mandatory = round(sum(del_fees[:6]) + sum(ccu_fees[:6]), 2)
    assert q.mandatory_fees == expected_mandatory
    assert q.total_fare == round(
        q.base_fare + q.taxes + q.mandatory_fees + q.convenience_fee, 2
    )
    assert q.convenience_fee == 350.0


def test_quotes_are_valid_canonical(parsed):
    sector_fares, station_fees = parsed
    quotes, skipped = build_quotes(sector_fares, station_fees,
                                   collection_day=date(2026, 9, 8))
    assert len(quotes) > 30
    for q in quotes:
        assert q.source_id == "alliance-tariff"
        assert q.currency == "INR"
        assert q.availability == "AVAILABLE"
        assert q.total_fare is not None and q.total_fare > 0
        assert q.collected_at.tzinfo is not None


def test_adapter_search_filters_route(parsed):
    from collectors.core.models import FlightSearchQuery

    quotes = asyncio.run(AllianceTariffSource().search(FlightSearchQuery(
        origin="DEL", destination="CCU",
        departure_date=date(2026, 9, 9), advance_days=1,
    )))
    assert quotes and all(q.origin == "DEL" and q.destination == "CCU" for q in quotes)


def test_adapter_health():
    health = asyncio.run(AllianceTariffSource().health_check())
    assert health.ok, health.detail
    assert health.source_id == "alliance-tariff"
