"""Akasa Air fare-sheet adapter — airline-published tariff PDF.

Compliance (researched 2026-09, verified live):
- akasaair.com robots.txt has ZERO Disallow lines (fully permissive).
- The airline publishes a fare-sheet PDF at
  https://a.storyblok.com/f/159922/x/c1ce86c83e/fare-sheet-akasa-air.pdf
  (plain HTTP 200, no anti-bot).

What it is: filed tariffs per market — a grid of Minimum/Maximum rows for
15 fare levels (Fare_Level_1..15), fuel charge (YQ) and stops — NOT
transaction prices. Honest labeling: quotes from this source are tariff floors
(lower bound of what the airline may charge), never "observed sold fares".
``POLICY_STATUS = "PUBLISHED_TARIFF_PDF"`` says so on every registry row.

Fare mapping (documented choices):
- base_fare = the Minimum row's Fare_Level_1 — the lowest filed tariff for the
  market. "Minimum fare" here is the row TYPE, its Fare_Level_1 value IS the
  minimum fare; anything higher is a booking class/RBD bucket, not a floor.
  Maximum rows and levels 2..15 are not collected (they are fare ceilings
  per RBD — a different statistic than the index's consumer price).
- taxes = fuel charge (YQ); mandatory_fees = 0 (not filed in the sheet);
  convenience_fee = 0 (airline direct, none published).
- advance_days = 1 (tariffs are advance-agnostic; the smallest sane lead so the
  observation lands on an index-tracked lead bucket). departure_date =
  collection day + 1.
- fare_class = "FARE_LEVEL_1" — a tariff bucket label, not an RBD.
- airline = "QP" (Akasa Air IATA code).
"""
from __future__ import annotations

import logging
import os
import re
import subprocess
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from collectors.core.base_source import FlightSource
from collectors.core.models import Availability, FlightQuote, FlightSearchQuery, SourceHealth
from collectors.sources.scrape_engine import ScrapeEngine

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures" / "akasa_faresheet.pdf"
PDF_URL = "https://a.storyblok.com/f/159922/x/c1ce86c83e/fare-sheet-akasa-air.pdf"
POLICY_STATUS = "PUBLISHED_TARIFF_PDF"
ADVANCE_DAYS = 1  # documented convention: tariff is advance-agnostic

# Market city name (PDF) -> IATA, restricted to basket airports.
CITY_TO_IATA = {
    "Bengaluru": "BLR", "Mumbai": "BOM", "New Delhi": "DEL",
    "Kolkata": "CCU", "Hyderabad": "HYD",
    "Navi Mumbai": "BOM",  # BLR-NaviMumbai row: same market as BLR-BOM (Akasa
    # serves both Mumbai-area airports; Navi Mumbai keeps its own tariff row.
    # Mapped to BOM so the basket route BLR-BOM is covered, fare_class carries
    # the original market).
}

MARKET_ROW_RE = re.compile(
    r"^([A-Za-z() .-]+?)\s+Minimum\s+(\d+)\s+([\d,]+)\s+([\d,]+)"
)
EFFECTIVE_RE = re.compile(r"Updated on:\s*(\d{1,2})-([A-Za-z]{3})-(\d{2})\b")


def _month_num(name: str) -> int | None:
    try:
        return datetime.strptime(name, "%b").month
    except ValueError:
        return None


def parse_effective_date(text: str) -> date | None:
    m = EFFECTIVE_RE.search(text)
    if not m:
        return None
    month = _month_num(m.group(2))
    if month is None:
        return None
    return date(2000 + int(m.group(3)), month, int(m.group(1)))


def parse_fare_sheet(text: str, query: FlightSearchQuery,
                     collected_date: date | None = None) -> list[FlightQuote]:
    """Parse `pdftotext -layout` output of the Akasa fare sheet.

    One FlightQuote per market row that matches the queried route (city names
    mapped to basket IATA codes). Collection day defaults to today; the
    document's effective date is carried on each quote via ``fare_class``
    provenance-free — see ``effective_date_of`` for the module-level copy.
    """
    collected_date = collected_date or date.today()
    collected_at = datetime.combine(collected_date, dtime(8, 0), tzinfo=IST)
    dest_iata = query.destination
    origin_iata = query.origin
    if not dest_iata or not origin_iata:
        return []

    quotes: list[FlightQuote] = []
    for line in text.splitlines():
        m = MARKET_ROW_RE.match(line)
        if not m:
            continue
        market, stops, yq, level1 = m.groups()
        origin_city, _, dest_city = market.partition(" - ")
        if CITY_TO_IATA.get(origin_city.strip()) != origin_iata:
            continue
        if CITY_TO_IATA.get(dest_city.strip()) != dest_iata:
            continue
        base = float(level1.replace(",", ""))
        taxes = float(yq.replace(",", ""))
        quotes.append(FlightQuote(
            source_id="akasa-tariff",
            origin=query.origin,
            destination=query.destination,
            departure_date=collected_date + timedelta(days=ADVANCE_DAYS),
            departure_time=None,
            airline="QP",
            flight_number=None,
            cabin="economy",
            fare_class="FARE_LEVEL_1",
            advance_days=ADVANCE_DAYS,
            base_fare=base,
            taxes=taxes,
            mandatory_fees=0.0,
            convenience_fee=0.0,
            other_fee=0.0,
            total_fare=base + taxes,
            currency="INR",
            availability=Availability.AVAILABLE,
            stops=int(stops),
            collected_at=collected_at,
        ))
    return quotes


def extract_pdf_text(pdf_path: Path) -> str:
    """Run pdftotext -layout. Raises FileNotFoundError if the binary is absent."""
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return proc.stdout


def extract_pdf_text(pdf_path: Path) -> str:
    """Run pdftotext -layout. Raises FileNotFoundError if the binary is absent."""
    proc = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True, text=True, timeout=60, check=True,
    )
    return proc.stdout


async def fetch_pdf(engine: ScrapeEngine | None = None) -> Path:
    """Refetch the live fare sheet into the fixture path. AKASA_LIVE=1 only.

    Goes through the shared compliance engine (robots gate, rate limit, bounded
    retry) via fetch_bytes — same path as every other live fetch."""
    engine = engine or ScrapeEngine(min_interval_s=10.0)
    content = await engine.fetch_bytes(PDF_URL)
    if not content[:5].startswith(b"%PDF"):
        raise ValueError("response is not a PDF")
    FIXTURE_PATH.write_bytes(content)
    log.info("akasa fare sheet refreshed", extra={"bytes": len(content)})
    return FIXTURE_PATH


class AkasaTariffSource(FlightSource):
    """Collect the Akasa Air published fare sheet (filed tariffs, not sold fares)."""

    source_id = "akasa-tariff"
    adapter_version = "1.0"

    def __init__(self, engine: ScrapeEngine | None = None):
        self._engine = engine

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        try:
            text = await self._text()
        except Exception as exc:
            log.warning("akasa sheet unreadable: %s", exc)
            return []
        return parse_fare_sheet(text, query)

    async def health_check(self) -> SourceHealth:
        effective = None
        try:
            effective = parse_effective_date(await self._text())
            ok, detail = True, f"{POLICY_STATUS}; effective {effective}"
        except Exception as exc:
            ok, detail = False, f"fixture unreadable: {exc}"
        return SourceHealth(
            source_id=self.source_id, ok=ok, detail=detail,
            checked_at=datetime.now(IST),
        )

    async def _text(self) -> str:
        if os.environ.get("AKASA_LIVE") == "1":
            await fetch_pdf(self._engine)
        if not FIXTURE_PATH.exists():
            raise FileNotFoundError(f"missing fixture {FIXTURE_PATH}")
        return extract_pdf_text(FIXTURE_PATH)


async def load_akasa_tariff(session, collection_day: date) -> int:
    """Ingest the Akasa fare sheet for every registry route it covers.

    Follows the alliance loader's pattern: iterate the Route registry, skip
    routes with no matching market rows in the sheet.
    Returns the number of quotes stored. Requires the source/route registry rows
    (seed integration).
    """
    from sqlalchemy import select

    from backend.app.models import Route  # local import avoids cycle
    from backend.app.services.pipeline import JobSpec, ingest_quotes

    text = await AkasaTariffSource()._text()
    now = datetime.combine(collection_day, dtime(8, 0), tzinfo=IST)
    stored = 0
    registry_routes = set(session.scalars(select(Route.id)))
    for route_id in sorted(registry_routes):
        origin, dest = route_id.split("-")
        query = FlightSearchQuery(
            origin=origin, destination=dest,
            departure_date=collection_day + timedelta(days=ADVANCE_DAYS),
            advance_days=ADVANCE_DAYS,
        )
        quotes = parse_fare_sheet(text, query, collected_date=collection_day)
        if not quotes:
            continue
        result = ingest_quotes(session, JobSpec(
            source_id="akasa-tariff", route_id=route_id,
            departure_date=query.departure_date, lead_time=ADVANCE_DAYS,
            collection_date=collection_day, started_at=now,
        ), quotes)
        stored += result.stored
    return stored

