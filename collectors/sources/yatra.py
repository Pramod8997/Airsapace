"""Yatra OTA adapter — compliant live fares from sitemap-published SEO route pages.

Compliance (researched 2026-09, verified live):
- robots.txt: ``User-agent: * / Allow: /`` — only legacy/affiliate paths are
  disallowed.
- The ``/cheap-flights/search/<city1>-to-<city2>-flights`` pages are sitemap-
  published (https://www.yatra.com/sitemap/cheap-flights/search/sitemap.xml).
  These are server-rendered SEO landing pages, NOT the interactive search
  funnel, so no query/API simulation is involved.
- ToS contains no anti-bot clause.

What is collected: the server-rendered 7-day cheapest-fare strip on each route
page — one aggregate cheapest fare per departure day, airline="MULTI" (it is
not attributable to a single carrier). Per-flight prices are JS-rendered and
absent from the HTML we fetch, so they are never collected — and never
fabricated.

Fare semantics: the strip fare is a single all-in consumer price; the
base/taxes split is not published. ``statistical_engine.normalization`` derives
consumer_payable_fare from base+taxes+mandatory_fees (None if any component is
missing), so the all-in figure is carried as ``base_fare`` with
``taxes=0, mandatory_fees=0`` — consumer_payable == total_fare exactly, and no
component split is invented.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, time as dtime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

from collectors.core.base_source import FlightSource
from collectors.core.models import Availability, FlightQuote, FlightSearchQuery, SourceHealth
from collectors.sources.scrape_engine import ScrapeEngine

IST = ZoneInfo("Asia/Kolkata")
FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"
USER_AGENT = "AirStatIndia-Research/1.0 (SIH 26056)"
POLITENESS_SLEEP_S = 10.0  # engine rate-limit interval between live route fetches
POLICY_STATUS = "ROBOTS_ALLOWED_SEO"

# IATA -> city slug used in yatra.com route-page URLs (basket cities).
CITY_NAMES = {
    "DEL": "delhi", "BOM": "mumbai", "BLR": "bangalore",
    "CCU": "kolkata", "HYD": "hyderabad", "MAA": "chennai",
}

# Day-strip line: "1.   Mon, 14 Sep₹6,500 " (flight blocks use "Tue, Sep 15, 2026"
# — month before day with a year — which cannot match this pattern).
STRIP_RE = re.compile(r"(Mon|Tue|Wed|Thu|Fri|Sat|Sun), (\d{1,2}) ([A-Za-z]{3})₹([\d,]+)")
VERIFIED_RE = re.compile(r"Fares verified on (\d{1,2}) ([A-Za-z]+) (\d{4})")


def _month_num(name: str) -> int | None:
    for fmt in ("%b", "%B"):
        try:
            return datetime.strptime(name, fmt).month
        except ValueError:
            continue
    return None


def parse_yatra_page(text: str, query: FlightSearchQuery) -> list[FlightQuote]:
    """Parse a yatra.com route page into day-strip quotes.

    Collection date comes from the page's own "Fares verified on <date>" line
    (fallback: today). Day-strip dates carry no year; the year is derived from
    the collection date, rolling forward one year if the day has already passed
    (e.g. "14 Sep" seen in December departs Sep next year).
    """
    collected_date = date.today()
    if (v := VERIFIED_RE.search(text)):
        month = _month_num(v.group(2))
        if month:
            try:
                collected_date = date(int(v.group(3)), month, int(v.group(1)))
            except ValueError:
                pass
    collected_at = datetime.combine(collected_date, dtime(8, 0), tzinfo=IST)

    quotes: list[FlightQuote] = []
    for m in STRIP_RE.finditer(text):
        day, month = int(m.group(2)), _month_num(m.group(3))
        if month is None:
            continue
        try:
            dep = date(collected_date.year, month, day)
            if dep < collected_date:
                dep = dep.replace(year=dep.year + 1)
        except ValueError:  # Feb 29 in a non-leap candidate year
            continue
        fare = float(m.group(4).replace(",", ""))
        quotes.append(FlightQuote(
            source_id="yatra-ota",
            origin=query.origin,
            destination=query.destination,
            departure_date=dep,
            departure_time=None,
            airline="MULTI",  # aggregated cheapest fare, not a specific carrier
            flight_number=None,
            cabin="economy",
            fare_class=None,
            advance_days=(dep - collected_date).days,
            base_fare=fare,
            taxes=0.0,
            mandatory_fees=0.0,
            convenience_fee=0.0,
            other_fee=0.0,
            total_fare=fare,
            currency="INR",
            availability=Availability.AVAILABLE,
            stops=0,
            collected_at=collected_at,
        ))
    return quotes


class YatraSource(FlightSource):
    """Collect the 7-day cheapest-fare strip from a Yatra route page.

    Default mode reads saved fixtures (data/fixtures/yatra_<orig>_<dest>.txt) so
    tests and the demo never depend on live scraping. Set ``YATRA_LIVE=1`` to
    fetch the real pages through the shared compliance engine — robots.txt
    gate, rate limit (10s), anti-bot/CAPTCHA detection, bounded retry — the
    same path every other source goes through.
    """

    source_id = "yatra-ota"
    adapter_version = "1.0"

    def __init__(self, engine: ScrapeEngine | None = None):
        self._engine = engine or ScrapeEngine(min_interval_s=POLITENESS_SLEEP_S)

    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        text = await self._fetch(query)
        if text is None:
            return []
        return parse_yatra_page(text, query)

    async def health_check(self) -> SourceHealth:
        if os.environ.get("YATRA_LIVE") != "1":
            fixtures = list(FIXTURE_DIR.glob("yatra_*.txt"))
            return SourceHealth(
                source_id=self.source_id, ok=bool(fixtures),
                detail=f"{POLICY_STATUS}; {len(fixtures)} saved fixture page(s)",
                checked_at=datetime.now(IST),
            )
        try:
            resp = httpx.get(
                "https://www.yatra.com/robots.txt",
                headers={"User-Agent": USER_AGENT}, timeout=10.0,
            )
            ok = resp.status_code == 200
            detail = f"{POLICY_STATUS}; robots.txt probe HTTP {resp.status_code}"
        except httpx.HTTPError as exc:
            ok, detail = False, f"probe failed: {exc}"
        return SourceHealth(
            source_id=self.source_id, ok=ok, detail=detail,
            checked_at=datetime.now(IST),
        )

    async def _fetch(self, query: FlightSearchQuery) -> str | None:
        if os.environ.get("YATRA_LIVE") != "1":
            path = FIXTURE_DIR / f"yatra_{query.origin.lower()}_{query.destination.lower()}.txt"
            return path.read_text(encoding="utf-8") if path.exists() else None

        origin_city = CITY_NAMES.get(query.origin)
        dest_city = CITY_NAMES.get(query.destination)
        if not origin_city or not dest_city:
            return None  # route not covered by URL scheme
        url = f"https://www.yatra.com/cheap-flights/search/{origin_city}-to-{dest_city}-flights"
        return await self._engine.fetch_page(url)
