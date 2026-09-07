"""Live simulation source — real-time-ish fares for the demo (PRD §17 LIVE-DEMO).

Not a scraper and not a paid API: generates plausible fares from the same model
as the replay dataset (route base × lead × DOW × source bias × airline bias ×
noise), but seeded by wall-clock time, so every collection tick yields
genuinely new prices — the dashboard visibly moves between refreshes.

Honesty invariant: source is registered as policy_status=SIMULATED and the
data mode is DEMO, never presented as real observed fares. Swapping in a real
partner API later is a drop-in: implement FlightSource.search the same way.
"""
from __future__ import annotations

import math
import random
import time
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from collectors.core.base_source import FlightSource
from collectors.core.models import Availability, FlightQuote, FlightSearchQuery, SourceHealth

IST = ZoneInfo("Asia/Kolkata")

# Route base fares (INR) — mirrors scripts/generate_replay_data.py ROUTES.
ROUTE_BASE = {
    "DEL-BOM": 5200, "DEL-BLR": 6100, "BOM-BLR": 4900, "DEL-CCU": 5600,
    "BLR-HYD": 3800, "MAA-DEL": 6800, "BOM-DEL": 5200, "BLR-DEL": 6100,
    "HYD-DEL": 5400, "CCU-DEL": 5600,
}
LEAD_MULTIPLIER = {1: 1.55, 7: 1.18, 15: 1.05, 30: 0.95, 45: 0.92}
DOW_MULTIPLIER = {0: 0.98, 1: 0.96, 2: 0.97, 3: 0.99, 4: 1.06, 5: 1.03, 6: 1.06}
SOURCE_BIAS = {
    "sim-airline-6e": 1.00, "sim-airline-ai": 1.02,
    "sim-ota-alpha": 0.98, "sim-ota-beta": 1.03, "sim-ota-gamma": 1.00,
}
AIRLINE_BIAS = {"6E": 0.97, "AI": 1.06, "QP": 0.99, "SG": 0.94}
AIRLINE_ROUTES = {
    "6E": list(ROUTE_BASE),
    "AI": ["DEL-BOM", "BOM-DEL", "DEL-BLR", "BLR-DEL", "DEL-CCU", "CCU-DEL", "MAA-DEL", "HYD-DEL"],
    "QP": ["DEL-BOM", "BOM-DEL", "BOM-BLR", "BLR-HYD"],
    "SG": ["MAA-DEL", "DEL-CCU"],
}
DEP_TIMES = ["06:40", "09:15", "13:05", "17:30", "21:10"]


def _tick_seed() -> int:
    """Seed rotates every ~15s of wall clock: same tick = reproducible, next
    tick = new prices. Two collections within a tick return identical fares
    (idempotent-ish), which is what a real source's cache behaves like."""
    return (SEED_BASE := 26056) * 1000 + int(time.time() // 15)


class LiveSimSource(FlightSource):
    """One adapter that materializes all five simulated sources. Each search()
    call answers for one (source_id, route, lead); the registry rows carry the
    same ids so ingest sees normal per-source jobs."""

    adapter_version = "1.0"

    def __init__(self, source_id: str = "sim-ota-alpha"):
        if source_id not in SOURCE_BIAS:
            raise ValueError(f"unknown sim source {source_id}")
        self.source_id = source_id

    def _price(self, rng: random.Random, route_id: str, dep: date, lead: int, airline: str, slot: int) -> float:
        base = ROUTE_BASE[route_id]
        price = (
            base
            * LEAD_MULTIPLIER.get(lead, 1.0)
            * DOW_MULTIPLIER[dep.weekday()]
            * SOURCE_BIAS[self.source_id]
            * AIRLINE_BIAS.get(airline, 1.0)
            * (1 + 0.04 * slot)
            * math.exp(rng.gauss(0, 0.05))
        )
        return max(price, 900.0)

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        route_id = f"{query.origin}-{query.destination}"
        base = ROUTE_BASE.get(route_id)
        if base is None:
            return []  # off-basket route: no quotes, availability MISSING downstream
        rng = random.Random(_tick_seed() ^ hash((self.source_id, route_id, query.departure_date, query.advance_days)))
        airlines = ([self.source_id.split("-")[2].upper()]
                    if self.source_id.startswith("sim-airline-")
                    else [a for a in AIRLINE_ROUTES if route_id in AIRLINE_ROUTES[a]])
        # collected_at = collection day implied by advance_days (quality checks
        # advance_days against collected_at.date()). The demo driver may run on a
        # virtual future day; deriving it from the query keeps validity intact.
        collected = datetime.combine(
            query.departure_date - timedelta(days=query.advance_days),
            datetime.now(IST).timetz(),
        )
        quotes: list[FlightQuote] = []
        for airline in airlines:
            for slot in range(rng.randint(1, 2)):
                dep_time = DEP_TIMES[(slot + _stable(route_id)) % len(DEP_TIMES)]
                price = self._price(rng, route_id, query.departure_date, query.advance_days, airline, slot)
                sold_out = rng.random() < 0.04
                base_fare = round(price * 0.82)
                taxes = round(base_fare * 0.18)
                mandatory = rng.choice([150, 200, 250, 300, 400])
                quotes.append(FlightQuote(
                    source_id=self.source_id,
                    origin=query.origin,
                    destination=query.destination,
                    departure_date=query.departure_date,
                    departure_time=dep_time,
                    airline=airline,
                    flight_number=f"{airline}{100 + 37 * slot + (_stable(route_id) % 50)}",
                    cabin="economy",
                    fare_class="Q",
                    advance_days=query.advance_days,
                    base_fare=None if sold_out else base_fare,
                    taxes=None if sold_out else taxes,
                    mandatory_fees=None if sold_out else mandatory,
                    total_fare=None if sold_out else base_fare + taxes + mandatory,
                    currency="INR",
                    availability=Availability.SOLD_OUT if sold_out else Availability.AVAILABLE,
                    stops=0,
                    collected_at=collected,
                ))
        return quotes

    async def health_check(self) -> SourceHealth:
        return SourceHealth(
            source_id=self.source_id, ok=True, detail="simulated live feed",
            checked_at=datetime.now(IST),
        )


def _stable(s: str) -> int:
    """Deterministic string hash (built-in hash() is salted per process)."""
    return sum(ord(c) for c in s)


SIM_SOURCE_IDS = list(SOURCE_BIAS)
SIM_SOURCE_META = {  # (name, source_type, reliability) for registry seeding
    sid: (
        "IndiGo direct (simulated live)" if sid == "sim-airline-6e" else
        "Air India direct (simulated live)" if sid == "sim-airline-ai" else
        "OTA Alpha (simulated live)" if sid == "sim-ota-alpha" else
        "OTA Beta (simulated live)" if sid == "sim-ota-beta" else
        "OTA Gamma (simulated live)",
        "AIRLINE" if sid.startswith("sim-airline-") else "OTA",
        0.99 if sid == "sim-airline-6e" else 0.97 if sid == "sim-airline-ai" else
        0.96 if sid == "sim-ota-alpha" else 0.93 if sid == "sim-ota-beta" else 0.95,
    )
    for sid in SIM_SOURCE_IDS
}
