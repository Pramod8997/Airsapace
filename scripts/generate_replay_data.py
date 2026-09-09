"""Deterministic replay dataset generator (PRD §17 REPLAY mode).

Produces data/fixtures/replay_quotes.jsonl: one line per collection job with
canonical quotes. Seeded — identical output on every run, so the demo never
depends on live sources and the pipeline is reproducible from a fixed snapshot.

The dataset deliberately contains sold-out results, source outages, job
failures, duplicates, schema violations, fare-arithmetic errors and fat-finger
outliers so the cleaning pipeline's behavior is demonstrable.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")
SEED = 26056
START = date(2025, 8, 25)
DAYS = 379  # 2025-08-25 .. 2026-09-07; first 30 days = base period.
# Window chosen so every CPI Airfare fixture month (2025-10 .. 2026-07, the
# full public series) is covered by replay monthly means — the backtest
# aligns on all 6 official points instead of 2.
OUT_PATH = Path("data/fixtures/replay_quotes.jsonl")

AIRPORTS = {
    "DEL": ("New Delhi", "Delhi"),
    "BOM": ("Mumbai", "Maharashtra"),
    "BLR": ("Bengaluru", "Karnataka"),
    "CCU": ("Kolkata", "West Bengal"),
    "HYD": ("Hyderabad", "Telangana"),
    "MAA": ("Chennai", "Tamil Nadu"),
}

# PRD §14 basket. Base payable fares are plausible synthetic anchors (INR).
ROUTES: dict[str, float] = {
    "DEL-BOM": 5200, "DEL-BLR": 6100, "BOM-BLR": 4900, "DEL-CCU": 5600,
    "BLR-HYD": 3800, "MAA-DEL": 6800, "BOM-DEL": 5200, "BLR-DEL": 6100,
    "HYD-DEL": 5400, "CCU-DEL": 5600,
}

AIRLINES = {"6E": "IndiGo", "AI": "Air India", "QP": "Akasa Air", "SG": "SpiceJet"}

SOURCES = {
    "airline-6e-demo": ("IndiGo direct (synthetic)", "AIRLINE", 0.99, 0.985),
    "airline-ai-demo": ("Air India direct (synthetic)", "AIRLINE", 0.97, 0.975),
    "ota-alpha-demo": ("OTA Alpha (synthetic)", "OTA", 0.96, 0.99),
    "ota-beta-demo": ("OTA Beta (synthetic)", "OTA", 0.93, 0.97),
    "ota-gamma-demo": ("OTA Gamma (synthetic)", "OTA", 0.95, 0.98),
}
SOURCE_BIAS = {
    "airline-6e-demo": 1.00, "airline-ai-demo": 1.02,
    "ota-alpha-demo": 0.98, "ota-beta-demo": 1.03, "ota-gamma-demo": 1.00,
}

LEAD_MULTIPLIER = {1: 1.55, 7: 1.18, 15: 1.05, 30: 0.95, 45: 0.92}
LEAD_SOLDOUT_PROB = {1: 0.12, 7: 0.05, 15: 0.03, 30: 0.015, 45: 0.01}

DOW_MULTIPLIER = {0: 0.98, 1: 0.96, 2: 0.97, 3: 0.99, 4: 1.06, 5: 1.03, 6: 1.06}

AIRLINE_ROUTES = {
    "6E": list(ROUTES),
    "AI": ["DEL-BOM", "BOM-DEL", "DEL-BLR", "BLR-DEL", "DEL-CCU", "CCU-DEL", "MAA-DEL", "HYD-DEL"],
    "QP": ["DEL-BOM", "BOM-DEL", "BOM-BLR", "BLR-HYD"],
    "SG": ["MAA-DEL", "DEL-CCU"],
}
AIRLINE_BIAS = {"6E": 0.97, "AI": 1.06, "QP": 0.99, "SG": 0.94}

OTA_SOURCES = ["ota-alpha-demo", "ota-beta-demo", "ota-gamma-demo"]
SOURCE_DOWN: dict[str, list[date]] = {
    # full outage window — jobs recorded as FAILED/SOURCE_DOWN
    "ota-beta-demo": [date(2026, 8, 3), date(2026, 8, 4), date(2026, 8, 5)],
}

EVENT_SPIKE = (date(2026, 8, 12), date(2026, 8, 18))  # Independence Day travel


def _stable(s: str) -> int:
    """Deterministic string hash (built-in hash() is salted per process)."""
    return sum(ord(c) for c in s)


def route_sources(route_id: str) -> list[str]:
    srcs = ["ota-alpha-demo", OTA_SOURCES[_stable(route_id) % 2 + 1]]
    if route_id in AIRLINE_ROUTES["AI"]:
        srcs.append("airline-ai-demo")
    srcs.append("airline-6e-demo")
    return srcs


def event_multiplier(dep: date) -> float:
    lo, hi = EVENT_SPIKE
    if lo <= dep <= hi:
        edge = dep in (lo, hi)
        return 1.06 if edge else 1.15
    return 1.0


def route_walk(rng: random.Random, n_days: int) -> list[float]:
    """Slow AR(1) wander per route — realistic medium-horizon drift."""
    walk, x = [], 1.0
    for _ in range(n_days):
        x = 0.97 * x + 0.03 + rng.gauss(0, 0.012)
        walk.append(x)
    return walk


def quote_fare(rng: random.Random, route_id: str, dep: date, lead: int, day_idx: int,
               walk: list[float], source_id: str, airline: str, flight_slot: int) -> dict:
    base = ROUTES[route_id]
    price = (
        base
        * LEAD_MULTIPLIER[lead]
        * DOW_MULTIPLIER[dep.weekday()]
        * (1 + 0.0008) ** day_idx
        * event_multiplier(dep)
        * walk[day_idx]
        * SOURCE_BIAS[source_id]
        * AIRLINE_BIAS[airline]
        * (1 + 0.04 * flight_slot)  # later departures cost a bit more
        * (2.718 ** rng.gauss(0, 0.05))
    )
    price = max(price, 900.0)
    base_fare = round(price * 0.82)
    taxes = round(base_fare * 0.18)
    mandatory = rng.choice([150, 200, 250, 300, 400])
    total = base_fare + taxes + mandatory
    convenience = 0 if source_id.startswith("airline-") else rng.choice([250, 350, 450])
    return {
        "base_fare": base_fare, "taxes": taxes, "mandatory_fees": mandatory,
        "convenience_fee": convenience, "other_fee": 0, "total_fare": total,
    }


def generate() -> None:
    rng = random.Random(SEED)
    walks = {r: route_walk(rng, DAYS) for r in ROUTES}
    flight_no = {(a, r, i): f"{a}{100 + 37 * i + (_stable(r) % 50)}"
                 for a in AIRLINES for r in ROUTES for i in range(2)}
    dep_times = ["06:40", "09:15", "13:05", "17:30", "21:10"]

    lines: list[dict] = []
    stats = {"jobs": 0, "quotes": 0, "sold_out": 0, "missing": 0, "failed_jobs": 0,
             "duplicates": 0, "malformed": 0, "fare_errors": 0, "fat_finger": 0}

    for day_idx in range(DAYS):
        day = START + timedelta(days=day_idx)
        collected = datetime(day.year, day.month, day.day, 8, 0, tzinfo=IST)
        for route_id in ROUTES:
            origin, dest = route_id.split("-")
            for lead in (1, 7, 15, 30, 45):
                dep = day + timedelta(days=lead)
                for source_id in route_sources(route_id):
                    stats["jobs"] += 1
                    job_time = collected + timedelta(minutes=rng.randint(0, 90))

                    # source outage window
                    if day in SOURCE_DOWN.get(source_id, []):
                        lines.append({"job": _job(day, dep, lead, route_id, source_id, job_time),
                                      "status": "FAILED", "error_class": "SOURCE_DOWN", "quotes": []})
                        stats["failed_jobs"] += 1
                        continue
                    # sporadic job failures
                    if rng.random() < 0.01:
                        err = rng.choice(["TIMEOUT", "PARSER_ERROR", "CAPTCHA"])
                        lines.append({"job": _job(day, dep, lead, route_id, source_id, job_time),
                                      "status": "FAILED", "error_class": err, "quotes": []})
                        stats["failed_jobs"] += 1
                        continue

                    airlines_on_route = [a for a in AIRLINES if route_id in AIRLINE_ROUTES[a]]
                    if source_id.startswith("airline-"):
                        picked = [source_id.split("-")[1].upper()]
                    else:
                        picked = airlines_on_route
                    quotes = []
                    for airline in picked:
                        for slot in range(rng.randint(1, 2)):
                            quote_time = job_time + timedelta(minutes=rng.randint(0, 5))
                            q = {
                                "source_id": source_id,
                                "origin": origin, "destination": dest,
                                "departure_date": dep.isoformat(),
                                "departure_time": dep_times[(slot + lead) % len(dep_times)],
                                "airline": airline,
                                "flight_number": flight_no[(airline, route_id, slot)],
                                "cabin": "economy",
                                "fare_class": rng.choice(["Q", "S", "L", "E", "V"]),
                                "advance_days": lead,
                                "currency": "INR",
                                "stops": 0,
                                "collected_at": quote_time.isoformat(),
                                "availability": "AVAILABLE",
                            }
                            q.update(quote_fare(rng, route_id, dep, lead, day_idx,
                                                walks[route_id], source_id, airline, slot))

                            roll = rng.random()
                            if roll < LEAD_SOLDOUT_PROB[lead]:
                                q["availability"] = "SOLD_OUT"
                                stats["sold_out"] += 1
                            elif roll < LEAD_SOLDOUT_PROB[lead] + 0.005:
                                q["availability"] = "MISSING"
                                stats["missing"] += 1

                            quotes.append(q)

                    # inject dirty data at low rates (deterministic because rng order is fixed)
                    if quotes and rng.random() < 0.004:
                        bad = rng.choice(quotes)
                        if rng.random() < 0.5:
                            bad["total_fare"] = bad["base_fare"] + bad["taxes"] + 999  # arithmetic error
                        else:
                            bad["base_fare"] = -abs(bad["base_fare"])  # negative fare
                        stats["fare_errors"] += 1
                    if quotes and rng.random() < 0.003:
                        bad = dict(rng.choice(quotes))
                        bad.pop("origin")  # schema violation -> REJECTED (raw-only)
                        quotes.append(bad)
                        stats["malformed"] += 1
                    if quotes and rng.random() < 0.003:
                        dup = dict(rng.choice(quotes))  # exact duplicate
                        quotes.append(dup)
                        stats["duplicates"] += 1
                    if quotes and rng.random() < 0.0025:
                        bad = rng.choice(quotes)
                        bad["total_fare"] = bad["total_fare"] * rng.choice([10, 12, 15])
                        bad["base_fare"] = bad["base_fare"] * 10
                        stats["fat_finger"] += 1

                    stats["quotes"] += len(quotes)
                    lines.append({"job": _job(day, dep, lead, route_id, source_id, job_time),
                                  "status": "SUCCESS", "quotes": quotes})

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w") as f:
        for line in lines:
            f.write(json.dumps(line) + "\n")
    print(f"wrote {len(lines)} jobs, {stats['quotes']} quotes -> {OUT_PATH}")
    print(json.dumps(stats, indent=2))


def _job(day: date, dep: date, lead: int, route_id: str, source_id: str, started: datetime) -> dict:
    return {
        "source_id": source_id,
        "route_id": route_id,
        "departure_date": dep.isoformat(),
        "lead_time": lead,
        "collection_date": day.isoformat(),
        "started_at": started.isoformat(),
    }


if __name__ == "__main__":
    generate()
