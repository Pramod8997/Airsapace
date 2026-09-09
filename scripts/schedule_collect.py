"""Scheduled daily extraction (PS 26056 "scheduled daily extraction", TRD §11).

    .venv/bin/python scripts/schedule_collect.py [--at 08:00] [--once]

APScheduler (AsyncIOScheduler) fires the daily collection cycle at 08:00
Asia/Kolkata by default. Each run is collect_demo.one_cycle(days=1,
real_clock=True): collect -> ingest -> outlier pass -> index recalculation
for TODAY (real clock, not the demo's virtual clock).

Jobs are idempotent on the TRD §11 job key (source + route + departure_date
+ lead_time + collection_date), so a missed, late or double-firing run is
safe — same-day re-collections are deduplicated, never duplicated.

--once runs one cycle immediately before entering the schedule (handy for
the demo); Ctrl-C stops. Production equivalent in plain cron: `0 8 * * *`.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.app.config import setup_logging
from scripts.collect_demo import one_cycle

IST = ZoneInfo("Asia/Kolkata")
DEFAULT_AT = "08:00"


def parse_at(value: str) -> tuple[int, int]:
    """'HH:MM' -> (hour, minute), validated; SystemExit with a clear message."""
    try:
        hour, minute = (int(p) for p in value.split(":"))
    except ValueError:
        raise SystemExit(f"--at expects HH:MM, got {value!r}")
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise SystemExit(f"--at out of range: {value!r}")
    return hour, minute


async def run_cycle() -> None:
    print(f"[{datetime.now(IST):%Y-%m-%d %H:%M:%S} IST] daily collection cycle starting")
    await one_cycle(days=1, real_clock=True)
    print(f"[{datetime.now(IST):%Y-%m-%d %H:%M:%S} IST] cycle complete")


async def amain() -> None:
    setup_logging("INFO")
    argv = sys.argv[1:]
    at = argv[argv.index("--at") + 1] if "--at" in argv else DEFAULT_AT
    hour, minute = parse_at(at)
    once = "--once" in argv

    scheduler = AsyncIOScheduler(timezone=IST)
    scheduler.add_job(
        run_cycle,
        CronTrigger(hour=hour, minute=minute, timezone=IST),
        id="daily-collect",
        max_instances=1,       # never overlap cycles
        coalesce=True,         # missed fires collapse into one
        misfire_grace_time=3600,  # fire up to 1h late rather than skip
    )
    scheduler.start()
    if once:
        await run_cycle()
    print(
        f"scheduled daily collection at {hour:02d}:{minute:02d} IST — "
        f"next run {scheduler.next_run_time:%Y-%m-%d %H:%M %Z} (Ctrl-C to stop)"
    )
    try:
        await asyncio.Event().wait()  # run forever
    finally:
        scheduler.shutdown(wait=False)


if __name__ == "__main__":
    try:
        asyncio.run(amain())
    except KeyboardInterrupt:
        print("\nstopped")
