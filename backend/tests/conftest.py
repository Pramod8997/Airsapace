"""Test configuration: in-memory SQLite + a compact seeded pipeline run.

Env must be set before any backend import reads settings, so it happens at
conftest import time.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["API_RATE_LIMIT"] = "10000/minute"  # don't fight the limiter in tests
# Tests must never depend on the network or ambient shell env: force every
# live-capable adapter (Yatra) into fixture mode, whatever the shell exported.
os.environ.pop("YATRA_LIVE", None)

from backend.app import config as _config  # noqa: E402
from backend.app.db import create_all, reset_engine_for_tests, session_scope  # noqa: E402

_config.get_settings.cache_clear()
reset_engine_for_tests()

from collectors.core.models import FlightQuote  # noqa: E402
from scripts.seed import (  # noqa: E402
    METHODOLOGY_VERSION,
    seed_registries,
)

IST = ZoneInfo("Asia/Kolkata")
TEST_START = date(2026, 7, 1)
BASE_DAYS = 5  # base period 2026-07-01..07-05
SERIES_DAYS = 30  # index days 07-06..08-04 (forecast needs >= 20)
TEST_ROUTES = ["DEL-BOM", "DEL-BLR"]
TEST_LEADS = [1, 7]


def make_quote(route_id: str, lead: int, day: date, source_id: str, price: float,
               airline: str = "6E", **overrides) -> FlightQuote:
    origin, dest = route_id.split("-")
    base = round(price * 0.82)
    taxes = round(base * 0.18)
    mandatory = 200
    fields = dict(
        source_id=source_id,
        origin=origin,
        destination=dest,
        departure_date=day + timedelta(days=lead),
        departure_time="09:15",
        airline=airline,
        flight_number=f"{airline}123",
        cabin="economy",
        fare_class="Q",
        advance_days=lead,
        base_fare=base,
        taxes=taxes,
        mandatory_fees=mandatory,
        convenience_fee=0,
        other_fee=0,
        total_fare=base + taxes + mandatory,
        currency="INR",
        availability="AVAILABLE",
        stops=0,
        collected_at=datetime(day.year, day.month, day.day, 8, 0, tzinfo=IST),
    )
    fields.update(overrides)
    return FlightQuote(**fields)


def build_test_dataset():
    """~2 quotes per spec per day from 2 sources, gently trending prices."""
    from backend.app.services.pipeline import JobSpec, flag_day_outliers, ingest_quotes

    all_days = [TEST_START + timedelta(days=i) for i in range(BASE_DAYS + SERIES_DAYS)]
    rng_prices = {}
    for route in TEST_ROUTES:
        for lead in TEST_LEADS:
            base_price = 5000 if route == "DEL-BOM" else 6000
            for i, day in enumerate(all_days):
                rng_prices[(route, lead, day)] = base_price * (1 + 0.002 * i) * (1.1 if lead == 1 else 1.0)

    jobs = []
    for day in all_days:
        for route in TEST_ROUTES:
            for lead in TEST_LEADS:
                for source in ("airline-6e-demo", "ota-alpha-demo"):
                    price = rng_prices[(route, lead, day)]
                    quotes = [
                        make_quote(route, lead, day, source, price, airline="6E"),
                        make_quote(route, lead, day, source, price * 1.02, airline="AI",
                                   flight_number="AI456"),
                    ]
                    jobs.append((
                        JobSpec(
                            source_id=source, route_id=route,
                            departure_date=day + timedelta(days=lead), lead_time=lead,
                            collection_date=day,
                            started_at=datetime(day.year, day.month, day.day, 8, 0, tzinfo=IST),
                        ),
                        quotes,
                    ))
    return all_days, jobs


def seed_test_db():
    """Fresh isolated DB: registries + small replay ingest + outlier pass + index run.

    NOTE: drops everything first — pipeline tests rely on this for isolation, so
    don't use the session-scoped `seeded_db` fixture after a test calls this.
    """
    from backend.app.services.index_runner import run_index_calculation
    from backend.app.services.pipeline import flag_day_outliers, ingest_quotes

    from backend.app.db import drop_all

    drop_all()
    create_all()
    base_end = TEST_START + timedelta(days=BASE_DAYS - 1)
    with session_scope() as session:
        seed_registries(session, base_start=TEST_START, base_end=base_end)
    all_days, jobs = build_test_dataset()
    with session_scope() as session:
        for job_spec, quotes in jobs:
            ingest_quotes(session, job_spec, quotes)
    with session_scope() as session:
        for day in all_days:
            flag_day_outliers(session, day)
    with session_scope() as session:
        run_index_calculation(session, METHODOLOGY_VERSION)


import pytest  # noqa: E402


@pytest.fixture(scope="session")
def seeded_db():
    reset_engine_for_tests()
    _config.get_settings.cache_clear()
    seed_test_db()
    yield


@pytest.fixture()
def api_client(seeded_db):
    from fastapi.testclient import TestClient

    from backend.app.main import app

    with TestClient(app) as client:
        yield client
