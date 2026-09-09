"""One realtime demo collection cycle: collect -> ingest -> flag -> recalculate.

    .venv/bin/python scripts/collect_demo.py [--interval N] [--days K] [--real-clock]

Runs the simulated live feed (collectors/sources/live_sim.py) over the full
route basket × lead times, ingests the day's jobs, flags outliers and
recalculates the index. Each cycle advances the virtual collection date by
one day (or K with --days), so every cycle appends a new index point whose
value moves up/down — the visible "realtime" dynamism of the demo.

--real-clock collects for TODAY (IST) instead of advancing the virtual clock
— the mode scripts/schedule_collect.py uses for real scheduled daily runs.
Job keys are idempotent on (source, route, lead, collection_date), so a
same-day re-run is correctly deduplicated either way.

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

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete, func, select

from backend.app.db import session_scope
from backend.app.models import (
    FareQuote,
    MethodologyVersion,
    QualityAssessment,
    RawObservation,
    ScrapeJob,
)
from backend.app.services.index_runner import national_series, run_index_calculation
from backend.app.services.pipeline import JobSpec, flag_day_outliers, ingest_quotes
from collectors.core.models import FlightSearchQuery
from collectors.sources.live_sim import ROUTE_BASE, SIM_SOURCE_IDS, LiveSimSource

from collectors.core.base_source import SourcePolicyError
from collectors.sources.scrape_engine import LiveSimPortal
from collectors.sources.yatra import YatraSource

# Routes with saved Yatra fixtures (real SEO fare strips; live mode via YATRA_LIVE=1).
YATRA_ROUTES = {"DEL-BOM", "DEL-CCU", "BOM-BLR"}
from scripts.generate_replay_data import LEAD_MULTIPLIER

IST = ZoneInfo("Asia/Kolkata")


def next_collection_day(session) -> date:
    """Virtual clock: day after the latest collection date already in the DB.
    Starting fresh (no jobs), begins today."""
    latest = session.scalar(select(func.max(ScrapeJob.collection_date)))
    return (latest or date.today() - timedelta(days=1)) + timedelta(days=1)


def collection_day(session, real_clock: bool = False) -> date:
    """Day a cycle collects for. ``real_clock=True`` pins today (IST) — the
    mode the scheduler uses; the virtual clock (max collection_date + 1) is
    the demo compressor. Same-day re-runs are idempotent via the job key, so
    a real daily run that fires twice is safe."""
    if real_clock:
        return datetime.now(IST).date()
    return next_collection_day(session)


def prune_demo_data(session, keep_days: int = 90) -> dict:
    """Demo retention: drop observation tables older than keep_days (by the
    virtual clock — max collection date, not wall time). IndexValues and the
    newest CalculationRuns are never touched (immutable published results);
    the methodology's base period is never pruned either — every future index
    recomputation needs those observations, so with a long replay window the
    effective floor is base_period_end + 1. In production this is a policy
    decision, not a hardcoded prune.
    # ponytail: whole-window DELETE per cycle; batch if rows > millions.
    """
    newest = session.scalar(select(func.max(FareQuote.collection_date)))
    if newest is None:
        return {"pruned_quotes": 0}
    cutoff = newest - timedelta(days=keep_days)
    base_end = session.scalar(
        select(func.max(MethodologyVersion.base_period_end))
    ) or date.min
    if cutoff <= base_end:
        return {"pruned_quotes": 0}  # nothing prunable without touching the base period

    def older_than(column):
        return (column < cutoff, column > base_end)

    qa_gone = session.execute(delete(QualityAssessment).where(
        QualityAssessment.quote_id.in_(
            select(FareQuote.id).where(*older_than(FareQuote.collection_date))
        )
    )).rowcount
    raw_gone = session.execute(delete(RawObservation).where(
        RawObservation.collected_at < datetime.combine(cutoff, dtime(0, 0), tzinfo=IST),
        RawObservation.collected_at > datetime.combine(
            base_end + timedelta(days=1), dtime(0, 0), tzinfo=IST
        ),
    )).rowcount
    quotes_gone = session.execute(delete(FareQuote).where(
        *older_than(FareQuote.collection_date)
    )).rowcount
    jobs_gone = session.execute(delete(ScrapeJob).where(
        *older_than(ScrapeJob.collection_date)
    )).rowcount
    return {"pruned_quotes": quotes_gone, "raw": raw_gone, "jobs": jobs_gone, "qa": qa_gone}


async def one_cycle(days: int = 1, prune_keep_days: int = 90, real_clock: bool = False) -> None:
    if real_clock:
        days = 1  # a real daily run collects exactly today
    stored_total = 0
    flagged_total = 0
    latest = None
    prev = None
    with session_scope() as session:
        for _ in range(days):
            day = collection_day(session, real_clock)
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
                # Real sources: Yatra SEO route pages (fixture-backed by default,
                # YATRA_LIVE=1 for live). One fetch per route per cycle; the 7-day
                # strip quotes carry their true advance_days (6-13) — the job slot
                # is lead_time=7, the nearest basket bucket (documented convention).
                if route_id in YATRA_ROUTES:
                    quotes = await YatraSource().search(FlightSearchQuery(
                        origin=origin, destination=dest,
                        departure_date=day + timedelta(days=7),
                        advance_days=7,
                    ))
                    result = ingest_quotes(session, JobSpec(
                        source_id="yatra-ota", route_id=route_id,
                        departure_date=day + timedelta(days=7), lead_time=7,
                        collection_date=day, started_at=now,
                    ), quotes)
                    stored_total += result.stored
                # Scrape-portal-demo participates when the local sim portal is up
                # (robots.txt-gated compliant scraping of our demo target).
                try:
                    quotes = await LiveSimPortal().search(FlightSearchQuery(
                        origin=origin, destination=dest,
                        departure_date=day + timedelta(days=7),
                        advance_days=7,
                    ))
                    result = ingest_quotes(session, JobSpec(
                        source_id="scrape-portal-demo", route_id=route_id,
                        departure_date=day + timedelta(days=7), lead_time=7,
                        collection_date=day, started_at=now,
                    ), quotes)
                    stored_total += result.stored
                except SourcePolicyError as exc:
                    print(f"  scrape-portal: policy pause ({exc}) — recorded, not bypassed")
                except ValueError as exc:
                    print(f"  scrape-portal: {exc} — re-seed to register demo sources")
                except (RuntimeError, OSError, httpx.HTTPError):  # ConnectError et al.
                    pass  # portal not running; sim sources carry the cycle
                # JS-rendered portal (Playwright behind the same compliance gate)
                # — PS 26056 "handle JavaScript-rendered pages". Skips cleanly
                # when playwright isn't installed or the portal is down.
                try:
                    from collectors.sources.js_engine import LiveSimPortalJS
                    quotes = await LiveSimPortalJS().search(FlightSearchQuery(
                        origin=origin, destination=dest,
                        departure_date=day + timedelta(days=7),
                        advance_days=7,
                    ))
                    result = ingest_quotes(session, JobSpec(
                        source_id="scrape-portal-js-demo", route_id=route_id,
                        departure_date=day + timedelta(days=7), lead_time=7,
                        collection_date=day, started_at=now,
                    ), quotes)
                    stored_total += result.stored
                except SourcePolicyError as exc:
                    print(f"  scrape-portal-js: policy pause ({exc}) — recorded, not bypassed")
                except ValueError as exc:
                    print(f"  scrape-portal-js: {exc} — re-seed to register demo sources")
                except (RuntimeError, OSError, httpx.HTTPError):
                    pass  # playwright/portal unavailable; other sources carry the cycle
                # Real tariff PDFs (advance-agnostic) — handled once per cycle below.
            # Document-collection jobs (advance-agnostic tariff PDFs, one ingest per day):
            try:
                from collectors.sources.alliance_tariff import load_alliance_tariff
                result = load_alliance_tariff(session, day)
                stored_total += result["stored"]
            except FileNotFoundError:
                pass  # fixture absent — sim sources carry the demo
            except Exception as exc:
                print(f"  alliance tariff: skipped ({type(exc).__name__}: {exc})")
            try:
                from collectors.sources.akasa_tariff import load_akasa_tariff
                stored = await load_akasa_tariff(session, day)
                stored_total += stored
            except FileNotFoundError:
                pass
            except Exception as exc:
                print(f"  akasa tariff: skipped ({type(exc).__name__}: {exc})")
        flagged_total += flag_day_outliers(session, day)
        # Retention: keep the DB bounded in the looping demo (virtual-clock based).
        pruned = prune_demo_data(session, prune_keep_days)
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
        pruned_note = f", pruned={pruned['pruned_quotes']}" if pruned["pruned_quotes"] else ""
        print(f"  quotes stored={stored_total}, outliers flagged={flagged_total}{pruned_note}")


def main() -> None:
    interval = None
    if "--interval" in sys.argv:
        interval = int(sys.argv[sys.argv.index("--interval") + 1])
    days = 1
    if "--days" in sys.argv:
        days = int(sys.argv[sys.argv.index("--days") + 1])
    real_clock = "--real-clock" in sys.argv
    if interval is None:
        asyncio.run(one_cycle(days, real_clock=real_clock))
        return
    print(f"looping every {interval}s ({days} day(s) per cycle) — Ctrl-C to stop")
    while True:
        asyncio.run(one_cycle(days, real_clock=real_clock))
        time.sleep(interval)


if __name__ == "__main__":
    main()
