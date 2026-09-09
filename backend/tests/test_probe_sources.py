"""PS-named source probe tests — honest registry statuses from frozen research."""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from scripts.probe_sources import (
    PROBED_SOURCES,
    probe_fixture_payload,
    register_probed_sources,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
ROBOTS_DIR = REPO_ROOT / "data" / "fixtures" / "robots"

EXPECTED = {
    "indigo-portal": "RESTRICTED_DOCUMENTED",
    "airindia-portal": "RESTRICTED_DOCUMENTED",
    "aix-portal": "RESTRICTED_DOCUMENTED",
    "spicejet-portal": "RESTRICTED_DOCUMENTED",
    "mmt-portal": "REJECTED_ROBOTS_OR_TOS",
    "goibibo-portal": "REJECTED_ROBOTS_OR_TOS",
    "easemytrip-portal": "RESTRICTED_DOCUMENTED",
    "cleartrip-portal": "REJECTED_ROBOTS_OR_TOS",
    "ixigo-portal": "REJECTED_ROBOTS_OR_TOS",
}


def test_every_ps_named_portal_is_probed_exactly_once():
    ids = [row["source_id"] for row in PROBED_SOURCES]
    assert set(ids) == set(EXPECTED)
    assert len(ids) == len(set(ids)) == 9


def test_verdicts_match_the_frozen_research_matrix():
    """docs/research_sources.md §2 is the source of truth — the table must not
    drift from it silently."""
    for row in PROBED_SOURCES:
        assert row["policy_status"] == EXPECTED[row["source_id"]], row["source_id"]


def test_referenced_robots_fixtures_exist():
    for row in PROBED_SOURCES:
        assert (ROBOTS_DIR / row["robots_fixture"]).exists(), row["robots_fixture"]


def test_decisive_evidence_lines_are_verbatim_in_the_fixtures():
    """The cited disallow lines must actually appear in the saved robots.txt
    evidence — statuses are claims, fixtures are proof."""
    for row in PROBED_SOURCES:
        if row["robots_status"] != "DISALLOWS_SEARCH":
            continue
        line = row["robots_evidence"].split(" (")[0].split(" + ")[0]
        body = (ROBOTS_DIR / row["robots_fixture"]).read_text(encoding="utf-8")
        assert line in body, f"{row['source_id']}: evidence line missing from fixture"


def test_fixture_payload_shape():
    payload = probe_fixture_payload()
    assert "research_sources.md" in payload["_meta"]["generated_from"]
    assert len(payload["sources"]) == 9
    for row in payload["sources"]:
        assert row["policy_status"] and row["robots_status"] and row["robots_evidence"]


def test_register_is_idempotent(seeded_db):
    """Second registration must not duplicate rows or flip statuses."""
    from backend.app.db import session_scope
    from backend.app.models import Source

    with session_scope() as session:
        first = register_probed_sources(session)
        again = register_probed_sources(session)
        rows = session.scalars(select(Source).where(Source.id.in_(EXPECTED))).all()
        assert first == again == 9
        assert len(rows) == 9
        for row in rows:
            assert row.active is False  # never collected
            assert row.policy_status == EXPECTED[row.id]
            assert row.rate_limit_per_hour == 0
