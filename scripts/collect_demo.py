"""One realtime demo collection cycle: collect -> ingest -> flag -> recalculate.

    .venv/bin/python scripts/collect_demo.py [--interval N] [--days K]

Runs the simulated live feed (collectors/sources/live_sim.py) over the full
route basket × lead times, ingests the day's jobs, flags outliers and
recalculates the index. Each cycle advances the virtual collection date by
one day (or K with --days), so every cycle appends a new index point whose
value moves up/down — the visible "realtime" dynamism of the demo.

Why a virtual clock: published IndexValues are immutable and job keys are
idempotent on (source, route, lead, collection_date) — both are core
invariants. Intraday re-collection of the same day is correctly deduplicated,
so visible movement comes from new collection days, exactly like a real feed
compressed in time. No scraping, no API keys, no CAPTCHAs: honest simulation.

--interval N loops forever every N seconds (default: single cycle).
"""
from __future__ import annotations

import asyncio
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select

from backend.app.db import session_scope
from backend.app.models import ScrapeJob
from backend.app.services.index_runner import national_series, run_index_calculation
from backend.app.services.pipeline import JobSpec, flag_day_outliers, ingest_quotes
from collectors.core.models import FlightSearchQuery
from collectors.sources.live_sim import ROUTE_BASE, SIM_SOURCE_IDS, LiveSimSource
from scripts.generate_replay_data import LEAD_MULTIPLIER

IST = ZoneInfo("Asia/Kolkata")


def next_collection_day(session) -> date:
    """Virtual clock: day after the latest collection date already in the DB.
    Starting fresh (no jobs), begins today."""
    latest = session.scalar(select(func.max(ScrapeJob.collection_date)))
    return (latest or date.today() - timedelta(days=1)) + timedelta(days=1)


async def one_cycle(days: int = 1) -> None:
    stored_total = 0
    flagged_total = 0
    latest = None
    prev = None
    with session_scope() as session:
        for _ in range(days):
            day = next_collection_day(session)
            now = datetime.combine(day, dtime(8, 0), tzinfo=IST)
            for route_id in ROUTE_BASE:
                origin, dest = route_id.split("-")
                for lead in LEAD_MULTIPLIER:
                    for sid in SIM_SOURCE_IDS:
                        quotes = await LiveSimSource(sid).search(FlightSearchQuery(
                            origin=origin, destination=dest,
                            departure_date=day + timedelta(days=lead),
                            advance_days=lead,
                        ))
                        result = ingest_quotes(session, JobSpec(
                            source_id=sid, route_id=route_id,
                            departure_date=day + timedelta(days=lead), lead_time=lead,
                            collection_date=day, started_at=now,
                        ), quotes)
                        stored_total += result.stored
                flagged_total += flag_day_outliers(session, day)
        run = run_index_calculation(session)
        series = national_series(session, run.methodology_version)
        if len(series) >= 2:
            latest, prev = series[-1], series[-2]
        elif series:
            latest = series[-1]
        if latest and prev:
            delta = latest.value - prev.value
            print(f"index run #{run.id}: latest APIx {latest.value:.2f} ({latest.date}) "
                  f"{'+' if delta >= 0 else ''}{delta:.2f} vs {prev.date}")
        elif latest:
            print(f"index run #{run.id}: latest APIx {latest.value:.2f} ({latest.date})")
        print(f"  quotes stored={stored_total}, outliers flagged={flagged_total}")


def main() -> None:
    interval = None
    if "--interval" in sys.argv:
        interval = int(sys.argv[sys.argv.index("--interval") + 1])
    days = 1
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    if interval is None:
        asyncio.run(one_cycle(days))
        return
    print(f"looping every {interval}s ({days} day(s) per cycle) — Ctrl-C to stop")
    while True:
        asyncio.run(one_cycle(days))
        time.sleep(interval)


if __name__ == "__main__":
    main()
