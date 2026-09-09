"""Scheduler tests — real-clock day selection, idempotency, time parsing."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from scripts.collect_demo import collection_day, next_collection_day
from scripts.schedule_collect import parse_at

IST = ZoneInfo("Asia/Kolkata")


# ---------------------------------------------------------------- day selection


def test_real_clock_pins_today():
    """The scheduler's mode: collection day is today (IST), not the virtual clock."""
    assert collection_day(None, real_clock=True) == datetime.now(IST).date()


def test_virtual_clock_advances_past_the_latest_day(seeded_db):
    from backend.app.db import session_scope
    from backend.app.models import ScrapeJob
    from sqlalchemy import func, select

    with session_scope() as session:
        latest = session.scalar(select(func.max(ScrapeJob.collection_date)))
        expected = latest + timedelta(days=1) if latest else date.today()
        assert collection_day(session, real_clock=False) == next_collection_day(session)
        assert collection_day(session, real_clock=False) == expected


# ---------------------------------------------------------------- idempotency


def test_same_day_rerun_is_skipped(seeded_db):
    """The safety behind scheduled runs firing twice: the job key dedups."""
    from backend.app.db import session_scope
    from backend.app.services.pipeline import IngestResult, JobSpec, ingest_quotes
    from collectors.core.models import Availability, FlightQuote

    day = date.today()
    now = datetime(day.year, day.month, day.day, 8, 0, tzinfo=IST)

    def one_job() -> IngestResult:
        with session_scope() as session:
            quote = FlightQuote(
                source_id="airline-6e-demo", origin="DEL", destination="BOM",
                departure_date=day + timedelta(days=1), departure_time="09:15",
                airline="6E", flight_number="6E123", advance_days=1,
                base_fare=4000, taxes=720, mandatory_fees=200, total_fare=4920,
                availability=Availability.AVAILABLE, collected_at=now,
            )
            return ingest_quotes(session, JobSpec(
                source_id="airline-6e-demo", route_id="DEL-BOM",
                departure_date=day + timedelta(days=1), lead_time=1,
                collection_date=day, started_at=now,
            ), [quote])

    first = one_job()
    assert first.status == "SUCCESS" and first.stored == 1
    second = one_job()
    assert second.status == "SKIPPED" and second.stored == 0


# ---------------------------------------------------------------- time parsing


def test_parse_at_valid():
    assert parse_at("08:00") == (8, 0)
    assert parse_at("23:59") == (23, 59)
    assert parse_at("00:00") == (0, 0)


@pytest.mark.parametrize("bad", ["8am", "25:00", "08:75", "", "08:0:0"])
def test_parse_at_rejects_garbage(bad):
    with pytest.raises(SystemExit):
        parse_at(bad)


def test_schedule_collect_imports_cleanly():
    """apscheduler present + module importable (guards the requirements line)."""
    import scripts.schedule_collect as sc

    assert sc.DEFAULT_AT == "08:00"
    assert hasattr(sc, "amain") and hasattr(sc, "run_cycle")
