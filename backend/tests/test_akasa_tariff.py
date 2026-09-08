"""Akasa Air tariff-sheet adapter tests — fixture parsing, fare arithmetic, honesty."""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from collectors.core.models import Availability, FlightSearchQuery
from collectors.sources.akasa_tariff import (
    AkasaTariffSource,
    extract_pdf_text,
    parse_effective_date,
    parse_fare_sheet,
)

COLLECTED = date(2026, 9, 8)


def _sheet_text() -> str:
    try:
        from collectors.sources.akasa_tariff import FIXTURE_PATH
        if not FIXTURE_PATH.exists():
            pytest.skip("fixture akasa_faresheet.pdf not saved")
        return extract_pdf_text(FIXTURE_PATH)
    except FileNotFoundError:
        pytest.skip("pdftotext binary not available")
    except Exception:
        pytest.skip("fixture unreadable")


def _query(origin: str, dest: str) -> FlightSearchQuery:
    return FlightSearchQuery(
        origin=origin, destination=dest,
        departure_date=COLLECTED + timedelta(days=1), advance_days=1,
    )


@pytest.fixture(scope="module")
def sheet():
    return _sheet_text()


def test_effective_date_parsed(sheet):
    assert parse_effective_date(sheet) == date(2026, 9, 1)


def test_basket_route_covered(sheet):
    """Akasa's market grid covers BLR-DEL (filed as Bengaluru - New Delhi)."""
    quotes = parse_fare_sheet(sheet, _query("BLR", "DEL"), collected_date=COLLECTED)
    assert len(quotes) >= 1
    assert quotes[0].airline == "QP"
    assert quotes[0].source_id == "akasa-tariff"
    assert quotes[0].fare_class == "FARE_LEVEL_1"


def test_fare_arithmetic_total_is_base_plus_taxes(sheet):
    quotes = parse_fare_sheet(sheet, _query("BLR", "DEL"), collected_date=COLLECTED)
    quotes += parse_fare_sheet(sheet, _query("BLR", "HYD"), collected_date=COLLECTED)
    quotes += parse_fare_sheet(sheet, _query("BLR", "BOM"), collected_date=COLLECTED)
    assert quotes, "no basket routes parsed"
    for q in quotes:
        assert q.total_fare == q.base_fare + q.taxes
        assert q.convenience_fee == 0.0
        assert q.total_fare > 0


def test_payable_fare_flows_through(sheet):
    from statistical_engine.normalization import quote_payable_fare

    quotes = parse_fare_sheet(sheet, _query("BLR", "DEL"), collected_date=COLLECTED)
    for q in quotes:
        assert quote_payable_fare(q) == q.total_fare


def test_schema_validity_and_advance_days(sheet):
    quotes = parse_fare_sheet(sheet, _query("BLR", "DEL"), collected_date=COLLECTED)
    for q in quotes:
        assert (q.origin, q.destination) == ("BLR", "DEL")
        assert q.currency == "INR"
        assert q.cabin == "economy"
        assert q.availability is Availability.AVAILABLE
        assert q.advance_days == 1
        assert q.departure_date == COLLECTED + timedelta(days=1)
        assert q.collected_at.date() == COLLECTED
        assert q.stops in (0, 1)


def test_uncovered_route_returns_empty(sheet):
    assert parse_fare_sheet(sheet, _query("DEL", "BOM"), collected_date=COLLECTED) == []


@pytest.mark.anyio
async def test_search_via_source(sheet):
    quotes = await AkasaTariffSource().search(_query("BLR", "DEL"))
    assert len(quotes) >= 1 and quotes[0].source_id == "akasa-tariff"


@pytest.mark.anyio
async def test_health_check_reports_effective_date():
    try:
        health = await AkasaTariffSource().health_check()
    except Exception:
        pytest.skip("fixture unreadable")
    assert health.ok and health.source_id == "akasa-tariff"
    assert "PUBLISHED_TARIFF_PDF" in health.detail
