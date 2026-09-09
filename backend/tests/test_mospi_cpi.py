"""Tests for the MoSPI CPI Airfare reference loader (collectors/sources/mospi_cpi.py).

Covers: fixture round-trip, month bucketing, a full backtest run on a small
seeded series, and (opt-in via CPI_LIVE=1) a live API fetch.
"""
from __future__ import annotations

import json
import os
from datetime import date

import pytest

from statistical_engine.backtest import SeriesPoint

from collectors.sources.mospi_cpi import (
    CPI_REFERENCE_NAME,
    cpi_fixture_path,
    load_cpi_from_fixture,
    national_monthly_series,
    save_cpi_fixture,
)


def test_fixture_round_trip(tmp_path, monkeypatch):
    points = [
        SeriesPoint(date(2026, 5, 1), 127.62),
        SeriesPoint(date(2026, 6, 1), 126.09),
        SeriesPoint(date(2026, 7, 1), 125.46),
    ]
    monkeypatch.setattr("collectors.sources.mospi_cpi.cpi_fixture_path",
                        lambda: tmp_path / "cpi_airfare.json")
    path = save_cpi_fixture(points)
    loaded = load_cpi_from_fixture()
    assert [p.date for p in loaded] == [date(2026, 5, 1), date(2026, 6, 1), date(2026, 7, 1)]
    assert [p.value for p in loaded] == [127.62, 126.09, 125.46]
    payload = json.loads(path.read_text())
    assert payload["_meta"]["name"] == CPI_REFERENCE_NAME
    # sorts on save
    save_cpi_fixture(list(reversed(points)))
    assert [p.date for p in load_cpi_from_fixture()] == [p.date for p in points]


def test_repo_fixture_loads():
    """The committed offline fixture must be present and parseable."""
    assert cpi_fixture_path().exists(), "data/fixtures/cpi_airfare.json missing"
    points = load_cpi_from_fixture()
    assert points, "fixture is empty"
    for p in points:
        assert p.date.day == 1
        assert p.value > 0
    dates = [p.date for p in points]
    assert dates == sorted(dates)


def test_month_bucketing():
    """Daily APIx series -> monthly means (June: 2 days, July: 3 days)."""
    daily = [
        SeriesPoint(date(2026, 6, 28), 110.0),
        SeriesPoint(date(2026, 6, 29), 112.0),
        SeriesPoint(date(2026, 7, 1), 114.0),
        SeriesPoint(date(2026, 7, 15), 118.0),
        SeriesPoint(date(2026, 7, 30), 122.0),
    ]
    expected = [
        SeriesPoint(date(2026, 6, 1), 111.0),
        SeriesPoint(date(2026, 7, 1), round((114.0 + 118.0 + 122.0) / 3, 4)),
    ]
    # national_monthly_series needs a session; test the same bucketing logic
    # through it with a stubbed national_series.
    import collectors.sources.mospi_cpi as m

    class _StubSession:
        pass

    monkeypatch_target = "backend.app.services.index_runner.national_series"

    def fake_national_series(session, methodology_version):
        return daily

    import backend.app.services.index_runner as ir
    original = ir.national_series
    ir.national_series = fake_national_series
    try:
        result = m.national_monthly_series(_StubSession(), "APIX-v1.0")
    finally:
        ir.national_series = original
    assert result == expected


@pytest.fixture()
def seeded_monthly_db(seeded_db):
    """The standard conftest reseed: registries + small replay + index run."""
    yield


def test_backtest_run(seeded_monthly_db):
    from backend.app.db import session_scope
    from backend.app.services.index_runner import run_backtest
    from scripts.seed import METHODOLOGY_VERSION
    cpi = load_cpi_from_fixture()
    assert cpi, "CPI fixture required for backtest test"
    with session_scope() as session:
        actual = national_monthly_series(session, METHODOLOGY_VERSION)
        assert actual, "no APIx series in test DB"
        period_start = max(min(p.date for p in actual), min(p.date for p in cpi))
        period_end = min(max(p.date for p in actual), max(p.date for p in cpi))
        bt = run_backtest(
            session, cpi, CPI_REFERENCE_NAME,
            period_start, period_end, METHODOLOGY_VERSION,
            actual_series=actual,
        )
        assert bt.reference_series == CPI_REFERENCE_NAME
        assert bt.metrics["n_points"] >= 1
        assert bt.metrics["mae"] is not None
        assert bt.period_start == period_start
        assert bt.period_end == period_end


@pytest.mark.skipif(os.environ.get("CPI_LIVE") != "1",
                    reason="live fetch requires network + opt-in (CPI_LIVE=1)")
def test_live_fetch():
    import asyncio
    from collectors.sources.mospi_cpi import fetch_cpi_airfare

    points = asyncio.run(fetch_cpi_airfare([2026]))
    assert points, "no Combined rows returned for 2026"
    for p in points:
        assert p.date.year == 2026 and p.date.day == 1
        assert p.value > 0
    dates = [p.date for p in points]
    assert dates == sorted(dates)
    # verified research anchor
    june = [p for p in points if p.date == date(2026, 6, 1)]
    if june:
        assert june[0].value == pytest.approx(126.09, abs=0.01)


def test_every_cpi_month_lies_inside_the_replay_window():
    """PS 26056 demands a real backtest depth: the replay window must cover
    every month of the official CPI Airfare series, so the monthly-mean
    alignment never silently shrinks (it was 2 points before 2026-09-10)."""
    from datetime import timedelta

    from scripts.generate_replay_data import DAYS, START

    points = load_cpi_from_fixture()
    assert points, "CPI fixture missing"
    last_day = START + timedelta(days=DAYS - 1)
    for p in points:
        assert START <= p.date <= last_day, (
            f"CPI month {p.date} falls outside replay window "
            f"{START}..{last_day} — backtest would lose an aligned point"
        )
