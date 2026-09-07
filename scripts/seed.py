"""Seed the database and run the full pipeline from the replay dataset.

    .venv/bin/python scripts/seed.py [--fresh] [--keep]

--fresh (default) drops and recreates all tables. Registry weights are prototype
placeholders; production weights must come from authoritative passenger-traffic
data (PRD §14, open question in memory.md §9).
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.config import get_settings, setup_logging
from backend.app.db import create_all, drop_all, session_scope
from backend.app.models import (
    Airline,
    Airport,
    IndexBasket,
    IndexWeight,
    MethodologyVersion,
    Route,
    Source,
)
from backend.app.services.index_runner import national_series, run_backtest, run_index_calculation
from backend.app.services.pipeline import JobSpec, ingest_quotes, flag_day_outliers
from collectors.core.models import FlightQuote
from scripts.generate_replay_data import AIRLINES, AIRPORTS, ROUTES, SOURCES

REPLAY_PATH = Path("data/fixtures/replay_quotes.jsonl")

METHODOLOGY_VERSION = "APIX-v1.0"
BASKET_VERSION = "BASKET-2026.09"
WEIGHT_VERSION = "WB-2026.09-prototype"
WEIGHT_SOURCE = "prototype placeholder (production: DGCA passenger traffic)"
BASE_PERIOD_START = date(2026, 6, 25)
BASE_PERIOD_END = date(2026, 7, 24)  # first 30 days (TRD §9.1)

# Route weights: placeholder importance shares summing to 1.0.
ROUTE_WEIGHTS = {
    "DEL-BOM": 0.16, "BOM-DEL": 0.16, "DEL-BLR": 0.12, "BLR-DEL": 0.12,
    "BOM-BLR": 0.10, "DEL-CCU": 0.08, "CCU-DEL": 0.08, "BLR-HYD": 0.07,
    "MAA-DEL": 0.06, "HYD-DEL": 0.05,
}
# Lead-time weights: booking-distribution placeholder summing to 1.0.
LEAD_WEIGHTS = {1: 0.30, 7: 0.30, 15: 0.20, 30: 0.15, 45: 0.05}

OUTLIER_POLICY = (
    "Business-rule validation, then median/MAD robust z-score (|z|>3.5) per "
    "(route, lead time, collection date) peer group, plus fat-finger (>10x median) "
    "and configurable business bounds. Observations are flagged and kept, never "
    "silently deleted. Flagged quotes are excluded from aggregation."
)
MISSING_DATA_POLICY = (
    "Missing and sold-out observations are never zero and never imputed in APIX-v1.0. "
    "Specifications without a valid observation on a day are dropped from both "
    "numerator and denominator of that day's index (implicit reweighting). "
    "Imputation rates are reported as 0."
)


def seed_registries(session, base_start: date = BASE_PERIOD_START, base_end: date = BASE_PERIOD_END) -> None:
    for code, (city, state) in AIRPORTS.items():
        session.add(Airport(code=code, city=city, state=state))
    for iata, name in AIRLINES.items():
        session.add(Airline(iata=iata, name=name, active=True))
    for sid, (name, stype, reliability, _bias) in SOURCES.items():
        session.add(Source(
            id=sid, name=name, source_type=stype,
            adapter_name="demo-replay", adapter_version="1.0",
            policy_status="SYNTHETIC_DATA", robots_status="N/A_SYNTHETIC",
            rate_limit_per_hour=120, active=True, reliability=reliability,
        ))
    # Simulated live feed for the realtime demo (collectors/sources/live_sim.py).
    # Honest labeling: SIMULATED, never presented as real observed fares.
    from collectors.sources.live_sim import SIM_SOURCE_META
    for sid, (name, stype, reliability) in SIM_SOURCE_META.items():
        session.add(Source(
            id=sid, name=name, source_type=stype,
            adapter_name="live-sim", adapter_version="1.0",
            policy_status="SIMULATED", robots_status="N/A_SIM",
            rate_limit_per_hour=120, active=True, reliability=reliability,
        ))
    for route_id in ROUTES:
        origin, dest = route_id.split("-")
        session.add(Route(
            id=route_id, origin=origin, destination=dest,
            origin_city=AIRPORTS[origin][0], destination_city=AIRPORTS[dest][0],
            weight=ROUTE_WEIGHTS[route_id], weight_source=WEIGHT_SOURCE,
            weight_version=WEIGHT_VERSION, active=True,
        ))

    methodology = MethodologyVersion(
        version=METHODOLOGY_VERSION,
        name="APIx v1.0 — Laspeyres prototype",
        description=(
            "I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100 over route × lead-time "
            "specifications. P_i,t is the median consumer-payable fare "
            "(base + taxes + mandatory fees; convenience fees excluded). "
            "Deterministic: same input snapshot + methodology + weights => same index."
        ),
        base_period_start=base_start,
        base_period_end=base_end,
        outlier_policy=OUTLIER_POLICY,
        missing_data_policy=MISSING_DATA_POLICY,
        published=True,
    )
    session.add(methodology)
    session.flush()

    basket = IndexBasket(
        basket_version=BASKET_VERSION,
        weight_version=WEIGHT_VERSION,
        weight_source=WEIGHT_SOURCE,
        methodology_version=METHODOLOGY_VERSION,
    )
    session.add(basket)
    session.flush()
    for route_id, rw in ROUTE_WEIGHTS.items():
        for lead, lw in LEAD_WEIGHTS.items():
            session.add(IndexWeight(
                basket_id=basket.id, route_id=route_id, lead_time=lead,
                weight=round(rw * lw, 6),
            ))


def load_replay(session) -> dict:
    """Ingest every job from the JSONL, then run the outlier pass per day."""
    totals = {"jobs": 0, "skipped": 0, "failed": 0, "stored": 0,
              "duplicates": 0, "invalid": 0, "sold_out": 0, "raw_only": 0}
    days: set[date] = set()
    with REPLAY_PATH.open() as f:
        for line in f:
            rec = json.loads(line)
            j = rec["job"]
            quotes, rejected = [], []
            for q in rec["quotes"]:
                try:
                    quotes.append(FlightQuote(**q))
                except Exception:
                    rejected.append(q)
            result = ingest_quotes(
                session,
                JobSpec(
                    source_id=j["source_id"], route_id=j["route_id"],
                    departure_date=date.fromisoformat(j["departure_date"]),
                    lead_time=j["lead_time"],
                    collection_date=date.fromisoformat(j["collection_date"]),
                    started_at=datetime.fromisoformat(j["started_at"]),
                ),
                quotes,
                rejected_payloads=rejected,
                error_class=rec.get("error_class") if rec["status"] == "FAILED" else None,
            )
            totals["jobs"] += 1
            totals["skipped"] += result.status == "SKIPPED"
            totals["failed"] += result.status == "FAILED"
            totals["stored"] += result.stored
            totals["duplicates"] += result.duplicates
            totals["invalid"] += result.invalid
            totals["sold_out"] += result.sold_out
            totals["raw_only"] += result.raw_only
            days.add(date.fromisoformat(j["collection_date"]))
            if totals["jobs"] % 2000 == 0:
                session.commit()
                print(f"  ... {totals['jobs']} jobs ingested")

    flagged = 0
    for day in sorted(days):
        flagged += flag_day_outliers(session, day)
    totals["outlier_flagged"] = flagged
    return totals


def make_reference_and_backtest(session) -> None:
    """Synthetic reference series for the demo (clearly labeled). Replaced by a
    real DGCA series when the dataset question (memory.md §9) resolves."""
    actual = national_series(session, METHODOLOGY_VERSION)
    if not actual:
        print("no index series — skipping backtest")
        return
    rng = random.Random(42)
    reference = [
        type(actual[0])(p.date, round(p.value * (1 + rng.gauss(0, 0.012)), 4))
        for p in actual
    ]
    period_start = max(p.date for p in actual) - timedelta(days=44)
    period_end = max(p.date for p in actual)
    bt = run_backtest(
        session, reference, "synthetic-reference-demo (not DGCA)",
        period_start, period_end, METHODOLOGY_VERSION,
    )
    print(f"backtest #{bt.id}: {json.dumps(bt.metrics)}")


def main() -> None:
    setup_logging(get_settings().log_level)
    fresh = "--keep" not in sys.argv
    if fresh:
        drop_all()
    create_all()
    with session_scope() as session:
        seed_registries(session)
        print("registries seeded")
    with session_scope() as session:
        totals = load_replay(session)
        print(f"replay ingested: {json.dumps(totals)}")
    with session_scope() as session:
        run = run_index_calculation(session, METHODOLOGY_VERSION)
        print(f"index run #{run.id} (input hash {run.input_hash[:16]}…)")
    with session_scope() as session:
        make_reference_and_backtest(session)
    print("seed complete — start the API with: .venv/bin/uvicorn backend.app.main:app")


if __name__ == "__main__":
    main()
