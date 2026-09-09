"""Register the PS-26056-named airline/OTA portals with honest policy statuses.

    .venv/bin/python scripts/probe_sources.py [--live]

The problem statement names IndiGo, Air India, Air India Express, Akasa Air,
SpiceJet and the leading OTAs (MakeMyTrip, Yatra, EaseMyTrip, Cleartrip, Ixigo,
Goibibo). Three of those have real adapters (Akasa, Alliance*, Yatra — *Alliance
isn't PS-named but is real). This script registers the REST with the verdict
from the frozen compliance research (docs/research_sources.md, 2026-09-09) and
the saved robots.txt evidence (data/fixtures/robots/), so the dashboard's
Sources page documents WHY each named portal is absent — absence becomes
documented diligence, never silence.

Offline by design: the demo never depends on live probes. ``--live`` only
re-fetches robots.txt into the fixtures dir (evidence refresh); verdict changes
are a research-doc decision, never automatic.

Registered rows are ``active=False`` — never collected, only accounted for.

Status vocabulary (extends the honest-labeling set used by seed.py):
- RESTRICTED_DOCUMENTED — robots and/or ToS restrict automated access; documented, not collected.
- REJECTED_ROBOTS_OR_TOS — an explicit robots disallow or ToS bot ban covers exactly the fare-search paths we would need.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.db import session_scope
from backend.app.models import Source

ROBOTS_DIR = Path("data/fixtures/robots")
FIXTURE_PATH = Path("data/fixtures/source_probe.json")
USER_AGENT = "AirStatIndia-Research/1.0 (SIH 26056)"

# Verdicts mirror docs/research_sources.md §2 (frozen 2026-09-09); evidence
# lines are verbatim from the committed robots fixtures.
PROBED_SOURCES: tuple[dict[str, str], ...] = (
    dict(
        source_id="indigo-portal", name="IndiGo (goindigo.in)", source_type="AIRLINE",
        url="https://www.goindigo.in", robots_fixture="robots_goindigo.txt",
        robots_evidence="Disallow: /search.html",
        robots_status="DISALLOWS_SEARCH", policy_status="RESTRICTED_DOCUMENTED",
    ),
    dict(
        source_id="airindia-portal", name="Air India (airindia.com)", source_type="AIRLINE",
        url="https://www.airindia.com", robots_fixture="robots_airindia.txt",
        robots_evidence="no fare-path disallow in robots.txt, but ToS prohibits automated extraction — ToS wins",
        robots_status="PERMISSIVE_TOS_WINS", policy_status="RESTRICTED_DOCUMENTED",
    ),
    dict(
        source_id="aix-portal", name="Air India Express (airindiaexpress.com)", source_type="AIRLINE",
        url="https://www.airindiaexpress.com", robots_fixture="robots_aix2.txt",
        robots_evidence="Disallow: /flight-availability",
        robots_status="DISALLOWS_SEARCH", policy_status="RESTRICTED_DOCUMENTED",
    ),
    dict(
        source_id="spicejet-portal", name="SpiceJet (spicejet.com)", source_type="AIRLINE",
        url="https://www.spicejet.com", robots_fixture="robots_spicejet.txt",
        robots_evidence="robots.txt has no Disallow lines; ToS restricts automated access + PerimeterX",
        robots_status="PERMISSIVE_TOS_WINS", policy_status="RESTRICTED_DOCUMENTED",
    ),
    dict(
        source_id="mmt-portal", name="MakeMyTrip (makemytrip.com)", source_type="OTA",
        url="https://www.makemytrip.com", robots_fixture="robots_mmt.txt",
        robots_evidence="Disallow: /flight/search*",
        robots_status="DISALLOWS_SEARCH", policy_status="REJECTED_ROBOTS_OR_TOS",
    ),
    dict(
        source_id="goibibo-portal", name="Goibibo (goibibo.com)", source_type="OTA",
        url="https://www.goibibo.com", robots_fixture="robots_goibibo.com.txt",
        robots_evidence="Disallow: /flights/*?mode=* (MMT-family rules)",
        robots_status="DISALLOWS_SEARCH", policy_status="REJECTED_ROBOTS_OR_TOS",
    ),
    dict(
        source_id="easemytrip-portal", name="EaseMyTrip (easemytrip.com)", source_type="OTA",
        url="https://www.easemytrip.com", robots_fixture="robots_easemytrip.com.txt",
        robots_evidence="Disallow: /flight-search/listing*",
        robots_status="DISALLOWS_SEARCH", policy_status="RESTRICTED_DOCUMENTED",
    ),
    dict(
        source_id="cleartrip-portal", name="Cleartrip (cleartrip.com)", source_type="OTA",
        url="https://www.cleartrip.com", robots_fixture="robots_cleartrip.com.txt",
        robots_evidence="Disallow: /flights/search*",
        robots_status="DISALLOWS_SEARCH", policy_status="REJECTED_ROBOTS_OR_TOS",
    ),
    dict(
        source_id="ixigo-portal", name="Ixigo (ixigo.com)", source_type="OTA",
        url="https://www.ixigo.com", robots_fixture="robots_ixigo.com.txt",
        robots_evidence="Disallow: /flights/search + ToS bans automated access outright",
        robots_status="DISALLOWS_SEARCH", policy_status="REJECTED_ROBOTS_OR_TOS",
    ),
)


def register_probed_sources(session) -> int:
    """Idempotent upsert of the probed-source rows (never collected)."""
    for row in PROBED_SOURCES:
        source = session.get(Source, row["source_id"])
        if source is None:
            source = Source(id=row["source_id"])
            session.add(source)
        source.name = row["name"]
        source.source_type = row["source_type"]
        source.url = row["url"]
        source.adapter_name = None
        source.adapter_version = None
        source.policy_status = row["policy_status"]
        source.robots_status = row["robots_status"]
        source.rate_limit_per_hour = 0
        source.active = False  # registered for honest accounting only
        source.reliability = 0.0
    session.flush()
    return len(PROBED_SOURCES)


def probe_fixture_payload() -> dict:
    """Deterministic fixture payload (no wall-clock content)."""
    return {
        "_meta": {
            "name": "PS 26056 source probe — honest registry statuses",
            "generated_from": (
                "docs/research_sources.md (frozen 2026-09-09) + data/fixtures/robots/"
            ),
            "note": (
                "Offline evidence; scripts/probe_sources.py --live re-fetches robots.txt "
                "to refresh the saved fixtures. Verdicts change only via the research doc."
            ),
        },
        "sources": [dict(row) for row in PROBED_SOURCES],
    }


def write_probe_fixture() -> Path:
    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(probe_fixture_payload(), indent=2) + "\n")
    return FIXTURE_PATH


def refresh_robots_fixtures() -> None:
    """--live: re-fetch each portal's robots.txt into data/fixtures/robots/
    (declared UA, 15s timeout, 10s politeness gap). Evidence refresh only —
    the verdicts above are never changed automatically."""
    import time

    import httpx

    for i, row in enumerate(PROBED_SOURCES):
        robots_url = row["url"].rstrip("/") + "/robots.txt"
        try:
            resp = httpx.get(
                robots_url, headers={"User-Agent": USER_AGENT},
                timeout=15.0, follow_redirects=True,
            )
        except httpx.HTTPError as exc:
            print(f"  {row['source_id']}: fetch failed ({exc}) — fixture unchanged")
            continue
        if resp.status_code == 200:
            (ROBOTS_DIR / row["robots_fixture"]).write_text(resp.text)
            print(f"  {row['source_id']}: robots.txt refreshed ({len(resp.text)} bytes)")
        else:
            print(f"  {row['source_id']}: HTTP {resp.status_code} — fixture unchanged")
        if i < len(PROBED_SOURCES) - 1:
            time.sleep(10.0)


def main() -> None:
    if "--live" in sys.argv:
        print("refreshing robots.txt evidence (10s politeness gap per portal)…")
        refresh_robots_fixtures()

    with session_scope() as session:
        count = register_probed_sources(session)
    fixture = write_probe_fixture()
    print(f"registered {count} probed sources (active=False) — fixture: {fixture}")
    for row in PROBED_SOURCES:
        print(f"  {row['source_id']:<20} {row['policy_status']:<22} robots={row['robots_status']}")
    print("evidence: docs/research_sources.md + data/fixtures/robots/")


if __name__ == "__main__":
    main()
