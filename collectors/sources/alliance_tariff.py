"""Alliance Air tariff-sheet adapter — REAL data source (TRD §5).

Parses the published public PDF (data/fixtures/alliance_air_tariff_15MAR23.pdf)
— a genuine airline fare document, no scraping, no API key, no ToS concerns.
Two tables are used:

  Table 1: per-sector basic fares by fare class (18 fare levels, INSTANT
           PURCHASE + ADVANCE PURCHASE columns; "SECTOR & V.V." = both
           directions listed)
  Table 2: per-station taxes/fees (AUDF, DVF, CUTE, UDF, PSF, ASF) + GST rate

Mapping to the canonical FlightQuote:
  base_fare       = Table 1 basic fare for the level
  taxes           = GST on base (station GST rate)
  mandatory_fees  = CUTE + UDF + PSF + ASF + AUDF + DVF for both stations
  convenience_fee = 350 (documented convenience charge — excluded from the
                    index per methodology, kept in the row for transparency)
  fare_class      = "LEVEL<n>" label

Honest limitations (stated, not hidden):
  - Tariff = filed/ceiling fares per class, not observed transaction prices.
    A legitimate published price signal, but not equivalent to scraped sold
    fares. The registry marks the source PUBLISHED_TARIFF_PDF so the index
    can be segmented by source type.
  - One snapshot (15MAR23, recovered via Wayback). A real pipeline collects
    each new sheet; this one anchors the demo in real numbers.
  - Tariff routes are mostly not the 10-basket metro routes (Alliance Air
    flies regional sectors). The loader only ingests registry routes and
    reports the rest as skipped.
"""
from __future__ import annotations

import logging
import re
import subprocess
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from collectors.core.base_source import FlightSource
from collectors.core.models import (
    Availability,
    FlightQuote,
    FlightSearchQuery,
    SourceHealth,
)

log = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")

PDF_PATH = Path("data/fixtures/alliance_air_tariff_15MAR23.pdf")
SOURCE_ID = "alliance-tariff"
EFF_DATE = date(2023, 3, 15)
CONVENIENCE_FEE = 350.0

# City-name (as printed) -> IATA, for basket routes only.
CITY_TO_IATA = {
    "Delhi": "DEL", "Kolkata": "CCU", "Mumbai": "BOM", "Bengaluru": "BLR",
    "Chennai": "MAA", "Hyderabad": "HYD", "Ahmedabad": "AMD",
    "Jaipur": "JAI", "Goa": "GOI", "Varanasi": "VNS", "Lucknow": "LKO",
    "Pune": "PNQ", "Patna": "PAT", "Guwahati": "GAU", "Kochi": "COK",
}

FEE_COLUMNS = ("AUDF", "DVF", "CUTE", "UDF", "PSF", "ASF", "GST")

SECTOR_RE = re.compile(
    r"^\s*(?P<sn>\d+)\s+(?P<origin>[A-Z][A-Za-z .]+?)\s+(?P<dest>[A-Z][A-Za-z .]+?)\s+"
    r"(?P<routing>Direct|Via|Direct\s*/\s*Via)\s+(?P<fares>.+)$"
)
STATION_RE = re.compile(
    r"^\s*(?P<sn>\d+)\s+(?P<station>[A-Z][A-Za-z .]+?)\s+(?P<fees>.+?%)?\s*$"
)
NUM_RE = re.compile(r"^\d+(\.\d+)?$")


def _pdftotext(pdf: Path) -> str:
    out = subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True, timeout=30, check=True,
    )
    return out.stdout


def _parse_money(tok: str) -> float | None:
    """'2500' -> 2500.0; '2500 / 2600' -> 2500.0 (first/lowest); '-'/'NA' -> None."""
    tok = tok.strip()
    if not tok or tok in {"-", "NA", "NA / NA"}:
        return None
    first = tok.split("/")[0].strip()
    if not NUM_RE.match(first):
        return None
    return float(first)


def _parse_station_fees(tok: str) -> tuple[float, ...] | None:
    """One Table-2 fee token -> (AUDF, DVF, CUTE, UDF, PSF, ASF, GST_pct)."""
    parts = tok.split()
    if not parts or not parts[-1].endswith("%"):
        return None
    vals: list[float] = []
    for p in parts[:-1]:
        v = _parse_money(p.replace("**", ""))
        if v is None:
            return None
        vals.append(v)
    if len(vals) != 6:
        return None
    gst = float(parts[-1].rstrip("%"))
    return tuple(vals) + (gst,)


def parse_tariff(pdf: Path = PDF_PATH) -> tuple[dict, dict]:
    """PDF -> (sector_fares, station_fees).

    sector_fares: {(origin_iata, dest_iata): [level1..levelN floats, None gaps]}
    station_fees: {station_name: (AUDF, DVF, CUTE, UDF, PSF, ASF, GST)}
    """
    text = _pdftotext(pdf)
    sector_fares: dict[tuple[str, str], list[float]] = {}
    station_fees: dict[str, tuple] = {}
    mode: str | None = None

    for line in text.splitlines():
        if line.startswith("Table 2:"):
            mode = "fees"
            continue
        if line.startswith("Table 3:"):
            mode = None
            continue
        if line.startswith("Table 1:") or "ALLIANCE AIR DOMESTIC ONE-WAY" in line:
            mode = "fares"
            continue

        if mode == "fares":
            m = SECTOR_RE.match(line)
            if not m:
                continue
            origin = CITY_TO_IATA.get(m.group("origin").strip())
            dest = CITY_TO_IATA.get(m.group("dest").strip())
            if not origin or not dest:
                continue  # not a basket-relevant city pair
            levels = [_parse_money(t) for t in m.group("fares").split()]
            levels = [v for v in levels if v is not None]
            if levels:
                key = (origin, dest)
                if key not in sector_fares or levels[0] < sector_fares[key][0]:
                    sector_fares[key] = levels
        elif mode == "fees":
            # Tokens by position (verified on the rendered layout):
            # sn, station, AUDF, DVF, CUTE, UDF, PSF, ASF, GST% — split on 2+ spaces.
            if len(line) < 100 or not line.rstrip().endswith("%"):
                continue
            parts = re.split(r"\s{2,}", line.strip())
            if len(parts) != 9 or not parts[0].isdigit():
                continue
            station = parts[1].strip()
            vals = []
            for p in parts[2:8]:
                p = p.replace("**", "").strip()
                if p in {"-", "", "NA"}:
                    vals.append(0.0)  # '-' = fee not applicable at this station
                    continue
                v = _parse_money(p)
                if v is None:
                    vals = None
                    break
                vals.append(v)
            if vals is None:
                continue
            gst = float(parts[8].rstrip("%"))
            station_fees[station] = tuple(vals) + (gst,)

    return sector_fares, station_fees


def build_quotes(
    sector_fares: dict, station_fees: dict, collection_day: date | None = None,
) -> tuple[list[FlightQuote], int]:
    """Quotes for basket-relevant sectors; returns (quotes, skipped_sectors)."""
    day = collection_day or date.today()
    collected = datetime.combine(day, datetime.min.time().replace(hour=10), tzinfo=IST)
    quotes: list[FlightQuote] = []
    for (origin, dest), levels in sector_fares.items():
        o_fees = station_fees.get(_iata_to_city(origin))
        d_fees = station_fees.get(_iata_to_city(dest))
        if not o_fees or not d_fees:
            continue
        for li, base in enumerate(levels[:3], start=1):  # collect the 3 lowest levels
            gst_rate = max(o_fees[6], d_fees[6]) / 100.0
            taxes = round(base * gst_rate, 2)
            mandatory = round(sum(o_fees[:6]) + sum(d_fees[:6]), 2)
            total = round(base + taxes + mandatory + CONVENIENCE_FEE, 2)
            quotes.append(FlightQuote(
                source_id=SOURCE_ID,
                origin=origin, destination=dest,
                departure_date=day + timedelta(days=1),
                departure_time=None,
                airline="9I",  # Alliance Air IATA code
                flight_number=None,
                advance_days=1,  # tariff is advance-agnostic; documented convention
                base_fare=base,
                taxes=taxes,
                mandatory_fees=mandatory,
                convenience_fee=CONVENIENCE_FEE,
                total_fare=total,
                availability=Availability.AVAILABLE,
                fare_class=f"LEVEL{li}",
                collected_at=collected,
            ))
    return quotes, max(0, len(sector_fares) - len(quotes) // 3)


_IATA_TO_CITY = {v: k for k, v in CITY_TO_IATA.items()}


def _iata_to_city(iata: str) -> str | None:
    return _IATA_TO_CITY.get(iata)


class AllianceTariffSource(FlightSource):
    """FlightSource over the published tariff PDF (fixture-backed)."""

    source_id = SOURCE_ID
    adapter_version = "1.0"

    def __init__(self, pdf: Path = PDF_PATH):
        self._pdf = pdf
        self._cache: tuple[dict, dict] | None = None

    def _parsed(self) -> tuple[dict, dict]:
        if self._cache is None:
            if not self._pdf.exists():
                raise FileNotFoundError(f"tariff fixture missing: {self._pdf}")
            self._cache = parse_tariff(self._pdf)
        return self._cache

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        sector_fares, station_fees = self._parsed()
        quotes, _ = build_quotes(sector_fares, station_fees, query.departure_date - timedelta(days=1))
        return [
            q for q in quotes
            if q.origin == query.origin and q.destination == query.destination
        ]

    async def health_check(self) -> SourceHealth:
        try:
            self._parsed()
            ok, detail = True, f"tariff parsed (eff {EFF_DATE})"
        except Exception as exc:
            ok, detail = False, str(exc)
        return SourceHealth(
            source_id=self.source_id, ok=ok, detail=detail,
            checked_at=datetime.now(IST),
        )


def load_alliance_tariff(session: Session, collection_day: date) -> dict:
    """Ingest tariff quotes through the canonical pipeline. Idempotent via job key.

    Only registry routes are ingested; other parsed sectors are reported as
    skipped (they're kept out of the index rather than failing the load).
    """
    from backend.app.models import Route  # local import avoids cycle
    from backend.app.services.pipeline import JobSpec, ingest_quotes

    sector_fares, station_fees = parse_tariff(PDF_PATH)
    quotes, _ = build_quotes(sector_fares, station_fees, collection_day)
    now = datetime.combine(collection_day, datetime.min.time().replace(hour=10), tzinfo=IST)

    registry_routes = set(session.scalars(select(Route.id)))
    routes = {q.origin + "-" + q.destination for q in quotes} & registry_routes
    skipped = len({q.origin + "-" + q.destination for q in quotes}) - len(routes)

    stored = failed = 0
    for route_id in sorted(routes):
        o, d = route_id.split("-")
        route_quotes = [q for q in quotes if q.origin == o and q.destination == d]
        result = ingest_quotes(
            session,
            JobSpec(
                source_id=SOURCE_ID, route_id=route_id,
                departure_date=route_quotes[0].departure_date,
                lead_time=1, collection_date=collection_day, started_at=now,
            ),
            route_quotes,
        )
        stored += result.stored
        failed += result.status == "FAILED"
    log.info("alliance_tariff_loaded", extra={"stored": stored, "skipped_sectors": skipped})
    return {"stored": stored, "skipped_sectors": skipped, "failed_jobs": failed}
