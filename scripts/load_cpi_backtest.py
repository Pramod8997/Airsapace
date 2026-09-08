"""Backtest APIx against the MoSPI CPI "Airfare" sub-index (FR-14).

    .venv/bin/python scripts/load_cpi_backtest.py [--live]

Default: load data/fixtures/cpi_airfare.json, resample APIx daily national
series to monthly means, and run the backtest over the CPI-covered months.
--live: fetch from the MoSPI eSankhyiki API first and refresh the fixture.

Honesty: monthly CPI item vs monthly-mean APIx — correlation/trend-direction
co-movement only, never methodological equivalence.
"""
from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import get_settings, setup_logging
from backend.app.db import session_scope
from backend.app.services.index_runner import run_backtest
from collectors.sources.mospi_cpi import (
    CPI_REFERENCE_NAME,
    cpi_fixture_path,
    fetch_cpi_airfare,
    load_cpi_from_fixture,
    national_monthly_series,
    save_cpi_fixture,
)
from scripts.seed import METHODOLOGY_VERSION


def main() -> None:
    setup_logging(get_settings().log_level)
    if "--live" in sys.argv:
        points = asyncio.run(fetch_cpi_airfare([2025, 2026]))
        save_cpi_fixture(points)
        print(f"live fetch: {len(points)} months -> {cpi_fixture_path()}")
    else:
        points = load_cpi_from_fixture()
        print(f"fixture: {len(points)} months ({cpi_fixture_path()})")
    if not points:
        print("no CPI reference points — aborting")
        return

    with session_scope() as session:
        actual = national_monthly_series(session, METHODOLOGY_VERSION)
        if not actual:
            print("no APIx index series — run scripts/seed.py first")
            return
        period_start = max(
            min(p.date for p in actual), min(p.date for p in points))
        period_end = min(max(p.date for p in actual), max(p.date for p in points))
        bt = run_backtest(
            session, points, CPI_REFERENCE_NAME,
            period_start, period_end, METHODOLOGY_VERSION,
            actual_series=actual,
        )
    print(f"backtest #{bt.id} ({CPI_REFERENCE_NAME})")
    print(f"metrics: {json.dumps(bt.metrics)}")


if __name__ == "__main__":
    main()
