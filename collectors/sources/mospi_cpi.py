"""MoSPI CPI "Airfare" sub-index reference loader (SIH 26056 backtest, FR-14).

NOT a FlightSource adapter: this produces SeriesPoint reference data for
run_backtest only. It never feeds the index calculation.

Series: CPI (2024=100), All India, Combined, item "Airfare"
(code 07.3.3.1.2.01 / eSankhyiki item_code 294), monthly, Current series.
Coverage 2025-01 → present. This is the exact CPI component APIx is designed
to augment — a co-movement check, never an equivalence claim.

Honesty: APIx is a daily national index over route x lead-time fares; the CPI
item is a monthly All-India consumer price index. compute_metrics reports
correlation/trend-direction only, which is co-movement, not methodological
equivalence (statistical_engine/backtest.py header).
"""
from __future__ import annotations

import asyncio
import json
import ssl
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from statistical_engine.backtest import SeriesPoint

CPI_REFERENCE_NAME = (
    "MoSPI CPI Airfare sub-index (2024=100, All India Combined) — "
    "official eSanklyiki series"
)

_API_BASE = "https://api.mospi.gov.in/api/cpi"
_ITEM_CODE = 294  # Airfare (2024 base)
_TIMEOUT_S = 30
_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def _legacy_ssl_context() -> ssl.SSLContext:
    """api.mospi.gov.in requires legacy SSL renegotiation (curl fails with
    'unsafe legacy renegotiation'); set SSL_OP_LEGACY_SERVER_CONNECT."""
    ctx = ssl.create_default_context()
    ctx.options |= 0x4
    return ctx


def _api_url(year: int) -> str:
    return (f"{_API_BASE}/getCpiData?base_year=2024&level=Item"
            f"&item_code={_ITEM_CODE}&state_code=1&year={year}&series=Current")


def _parse_rows(payload: dict, year: int) -> list[SeriesPoint]:
    """Combined-sector rows only, month name -> (year, month, 1)."""
    points = []
    for row in payload.get("data", []):
        if row.get("sector") != "Combined":
            continue
        month = _MONTHS.get(str(row.get("month", "")).strip().lower())
        if month is None or not row.get("index"):
            continue
        points.append(SeriesPoint(date(year, month, 1), float(row["index"])))
    return points


async def fetch_cpi_airfare(years: list[int]) -> list[SeriesPoint]:
    """Fetch the Combined All-India monthly Airfare index for each year.

    Retries each year twice with backoff on network errors.
    Raises RuntimeError if a year cannot be fetched.
    """
    async def _fetch_year(year: int) -> list[SeriesPoint]:
        last_err: Exception | None = None
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    _api_url(year), headers={"Accept": "application/json"})
                with urllib.request.urlopen(
                    req, timeout=_TIMEOUT_S, context=_legacy_ssl_context()
                ) as resp:
                    payload = json.loads(resp.read())
                points = _parse_rows(payload, year)
                if not points:
                    raise RuntimeError(
                        f"MoSPI CPI: no Combined rows for item 294 in {year}")
                return points
            except (urllib.error.URLError, OSError, ValueError,
                    json.JSONDecodeError) as e:
                last_err = e
                if attempt < 2:
                    await asyncio.sleep(2.0 * (attempt + 1))
        raise RuntimeError(
            f"MoSPI CPI fetch failed for {year}: {last_err}") from last_err

    results = [await _fetch_year(y) for y in years]
    return sorted((p for pts in results for p in pts), key=lambda p: p.date)


# --- Fixture persistence -----------------------------------------------------

def cpi_fixture_path() -> Path:
    # repo root is two levels above this file's package (collectors/sources)
    return Path(__file__).resolve().parents[2] / "data" / "fixtures" / "cpi_airfare.json"


def save_cpi_fixture(points: list[SeriesPoint]) -> Path:
    path = cpi_fixture_path()
    payload = {
        "_meta": {
            "name": CPI_REFERENCE_NAME,
            "fields": "date (YYYY-MM-01), value (CPI index)",
        },
        "points": [
            {"date": p.date.isoformat(), "value": round(p.value, 2)}
            for p in sorted(points, key=lambda p: p.date)
        ],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n")
    return path


def load_cpi_from_fixture() -> list[SeriesPoint]:
    path = cpi_fixture_path()
    payload = json.loads(path.read_text())
    points = payload.get("points", payload)  # tolerate a bare list
    return [
        SeriesPoint(date.fromisoformat(r["date"]), float(r["value"]))
        for r in points
    ]


# --- APIx monthly side -------------------------------------------------------

def national_monthly_series(
    session: Session, methodology_version: str
) -> list[SeriesPoint]:
    """APIx daily national series resampled to monthly means, so both sides
    are monthly before compute_metrics aligns them."""
    from backend.app.services.index_runner import national_series

    daily = national_series(session, methodology_version)
    buckets: dict[date, list[float]] = defaultdict(list)
    for p in daily:
        buckets[p.date.replace(day=1)].append(p.value)
    return [
        SeriesPoint(month, round(sum(v) / len(v), 4))
        for month, v in sorted(buckets.items())
    ]
