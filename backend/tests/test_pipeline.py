"""Integration tests: ingest -> clean -> index (TRD §15)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from backend.app.db import session_scope
from backend.app.models import CalculationRun, FareQuote, IndexValue, RawObservation, ScrapeJob
from backend.app.services.index_runner import run_index_calculation
from backend.app.services.pipeline import JobSpec, flag_day_outliers, ingest_quotes
from backend.tests.conftest import IST, TEST_START, make_quote, seed_test_db
from collectors.core.models import Availability
from scripts.seed import METHODOLOGY_VERSION

IST_TZ = IST


def _job(day: date, route: str = "DEL-BOM", lead: int = 1, source: str = "ota-beta-demo") -> JobSpec:
    return JobSpec(
        source_id=source, route_id=route, departure_date=day + timedelta(days=lead),
        lead_time=lead, collection_date=day,
        started_at=datetime(day.year, day.month, day.day, 10, 0, tzinfo=IST_TZ),
    )


def test_ingest_classifies_dedups_and_preserves_raw():
    seed_test_db()  # isolated per-test DB (session fixture not used on purpose)
    day = date(2026, 8, 20)
    quotes = [
        make_quote("DEL-BOM", 1, day, "ota-beta-demo", 5000, flight_number="6E100"),
        make_quote("DEL-BOM", 1, day, "ota-beta-demo", 5000, flight_number="6E100"),  # exact duplicate
        make_quote("DEL-BOM", 1, day, "ota-beta-demo", 6000, airline="AI", flight_number="AI200",
                   availability=Availability.SOLD_OUT),
        make_quote("DEL-BOM", 1, day, "ota-beta-demo", 7000, airline="QP", flight_number="QP300",
                   total_fare=99999),  # arithmetic error
    ]
    with session_scope() as session:
        result = ingest_quotes(session, _job(day), quotes)
        assert result.status == "PARTIAL"
        assert result.stored == 3  # duplicate dropped
        assert result.duplicates == 1
        assert result.sold_out == 1
        assert result.invalid == 1

        rows = session.scalars(select(FareQuote).where(FareQuote.collection_date == day)).all()
        by_avail = {r.availability for r in rows}
        assert "AVAILABLE" in by_avail and "SOLD_OUT" in by_avail and "INVALID" in by_avail

        # raw is immutable and kept for every canonical quote (2 kept + dup + sold + invalid)
        raws = session.scalars(
            select(RawObservation).join(ScrapeJob).where(ScrapeJob.collection_date == day)
        ).all()
        assert len(raws) == 4  # duplicates keep their raw record too


def test_ingest_rejected_payload_is_raw_only():
    seed_test_db()
    day = date(2026, 8, 21)
    with session_scope() as session:
        result = ingest_quotes(session, _job(day), [make_quote("DEL-BOM", 1, day, "ota-beta-demo", 5000)],
                               rejected_payloads=[{"garbage": True}])
        assert result.raw_only == 1
        assert result.stored == 1


def test_ingest_is_idempotent_on_job_key():
    seed_test_db()
    day = date(2026, 8, 22)
    quotes = [make_quote("DEL-BOM", 1, day, "ota-beta-demo", 5000)]
    with session_scope() as session:
        first = ingest_quotes(session, _job(day), quotes)
    with session_scope() as session:
        second = ingest_quotes(session, _job(day), quotes)
    assert first.status == "SUCCESS"
    assert second.status == "SKIPPED"


def test_failed_job_records_error_class():
    seed_test_db()
    day = date(2026, 8, 23)
    with session_scope() as session:
        result = ingest_quotes(session, _job(day), [], error_class="SOURCE_DOWN")
        assert result.status == "FAILED"
        job = session.scalar(select(ScrapeJob).where(ScrapeJob.collection_date == day))
        assert job.error_class == "SOURCE_DOWN"


def test_flag_day_outliers_flags_fat_finger():
    seed_test_db()
    day = date(2026, 8, 24)
    quotes = [make_quote("DEL-BOM", 1, day, "ota-beta-demo", 5000 + i * 50, flight_number=f"6E{100 + i}")
              for i in range(4)]
    quotes.append(make_quote("DEL-BOM", 1, day, "ota-beta-demo", 60000, flight_number="6E900"))  # fat finger
    with session_scope() as session:
        ingest_quotes(session, _job(day), quotes)
    with session_scope() as session:
        flagged = flag_day_outliers(session, day)
        assert flagged == 1
        row = session.scalar(
            select(FareQuote).where(FareQuote.collection_date == day, FareQuote.outlier_flag)
        )
        assert row.outlier_reason == "fat_finger"
        assert row.consumer_payable_fare > 50000  # flagged, not deleted


def test_index_run_deterministic_and_idempotent():
    seed_test_db()
    with session_scope() as session:
        run1 = run_index_calculation(session, METHODOLOGY_VERSION)
    with session_scope() as session:
        run2 = run_index_calculation(session, METHODOLOGY_VERSION)
        total = len(session.scalars(select(IndexValue)).all())
        assert run1.input_hash == run2.input_hash  # deterministic
        assert run2.id != run1.id

    with session_scope() as session:
        runs = session.scalars(select(CalculationRun).where(CalculationRun.run_type == "INDEX")).all()
        assert len(runs) >= 2
        # idempotent: same (date, route, lead, methodology, basket) never duplicated
        values = session.scalars(
            select(IndexValue).where(
                IndexValue.route_id.is_(None), IndexValue.lead_time.is_(None)
            ).order_by(IndexValue.index_date)
        ).all()
        keys = [(v.index_date, v.route_id, v.lead_time) for v in values]
        assert len(keys) == len(set(keys))
        # base-period day must index ~100
        assert abs(values[0].value - 100.0) < 1.0
        # series rises with the fixture's gentle inflation
        assert values[-1].value > values[0].value
