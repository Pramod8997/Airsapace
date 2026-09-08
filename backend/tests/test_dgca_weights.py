"""Tests for the DGCA-derived route weights (scripts/load_dgca_weights.py and
the seed weight-loading path)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.generate_replay_data import ROUTES
from scripts.load_dgca_weights import (
    OUT_PATH,
    XLSX_PATH,
    compute_weights,
    route_pax_from_workbook,
    write_fixture,
)
from scripts.seed import load_route_weights

pytestmark = pytest.mark.skipif(
    not XLSX_PATH.exists(), reason="DGCA city-pair XLSX fixture not present"
)


def test_parser_covers_all_basket_routes_with_directional_pax():
    pax = route_pax_from_workbook(XLSX_PATH)
    for route in ROUTES:
        assert pax.get(route, 0) > 0, f"no passengers parsed for {route}"
    # Directional columns: DEL-BOM aggregates Mumbai + Navi Mumbai rows and
    # differs from BOM-DEL.
    assert pax["DEL-BOM"] != pax["BOM-DEL"]


def test_weights_sum_to_one_and_are_positive():
    weights = compute_weights(route_pax_from_workbook(XLSX_PATH))
    assert set(weights) == set(ROUTES)
    assert all(w > 0 for w in weights.values())
    assert abs(sum(weights.values()) - 1.0) <= 0.001


def test_fixture_round_trip(tmp_path: Path):
    out = write_fixture(tmp_path / "dgca_citypair_weights.json")
    assert out["source"].startswith("DGCA DOM city-pair data July 2026")
    assert out["url"].startswith("https://public-prd-dgca.s3")
    assert set(out["route_weights"]) == set(ROUTES)
    assert set(out["route_pax"]) == set(ROUTES)
    assert abs(sum(out["route_weights"].values()) - 1.0) <= 0.001
    # round-trip: what's on disk parses back to the same numbers
    disk = json.loads((tmp_path / "dgca_citypair_weights.json").read_text())
    assert disk == out


def test_seed_uses_dgca_weights_when_fixture_present():
    """The fixture committed at OUT_PATH is what seed.py actually reads."""
    assert OUT_PATH.exists()
    weights = load_route_weights()
    fixture = json.loads(OUT_PATH.read_text())["route_weights"]
    assert weights == fixture
    assert abs(sum(weights.values()) - 1.0) <= 0.001


def test_seed_falls_back_to_placeholder_without_fixture(tmp_path: Path, monkeypatch):
    from scripts import seed

    monkeypatch.chdir(tmp_path)  # no fixture in a bare tmp dir
    assert not (tmp_path / "data/fixtures/dgca_citypair_weights.json").exists()
    weights = seed.load_route_weights()
    assert weights == seed.PLACEHOLDER_ROUTE_WEIGHTS
    assert abs(sum(weights.values()) - 1.0) <= 0.001


def test_seed_rejects_corrupt_fixture(tmp_path: Path, monkeypatch, caplog):
    from scripts import seed

    bad = tmp_path / "bad_weights.json"
    bad.write_text(json.dumps({"route_weights": {"DEL-BOM": 0.5}}))
    monkeypatch.setattr(seed, "DGCA_WEIGHTS_PATH", bad)
    with pytest.raises(ValueError, match="invalid"):
        seed.load_route_weights()
