"""Anomaly detection tests (UI_UX_DESIGN.md §20, statistical_engine/anomaly.py)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from statistical_engine.anomaly import ANOMALY_MODEL_VERSION, detect_anomalies


@dataclass
class Row:
    route_id: str
    origin: str
    destination: str
    advance_days: int
    collection_date: date
    consumer_payable_fare: float
    availability: str = "AVAILABLE"
    source_id: str = "airline-6e-demo"
    outlier_flag: bool = False


START = date(2026, 8, 1)


def rows_stable(n_days=10, price=5000.0, sources=("s1", "s2", "s3")) -> list[Row]:
    return [
        Row("DEL-BOM", "DEL", "BOM", 1, START + timedelta(days=i), price * (1 + 0.001 * i), source_id=s)
        for i in range(n_days) for s in sources
    ]


def test_version_is_pinned():
    assert ANOMALY_MODEL_VERSION == "ANOMALY-v1"


def test_clear_shock_flags_with_severity():
    rows = rows_stable()
    shock_day = START + timedelta(days=10)
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, shock_day, 9500.0, source_id=s) for s in ("s1", "s2", "s3")]
    out = detect_anomalies(rows, window_days=30, threshold_pct=25)
    assert len(out) == 1
    rec = out[0]
    assert rec.route_id == "DEL-BOM" and rec.lead_time == 1
    assert rec.severity == "SHOCK"          # ~+90% >> 2*25
    assert rec.change_pct > 50
    assert rec.source_confirmations == 3 and rec.sources_seen == 3
    assert rec.current_date == shock_day
    assert "T+1 booking window" in rec.explanation["lead_window"]
    assert rec.explanation["comparison"] == "vs 30-day route median"


def test_stable_route_not_flagged():
    out = detect_anomalies(rows_stable(), window_days=30, threshold_pct=25)
    assert out == []


def test_elevated_and_dip_tiers():
    base = rows_stable()
    day = START + timedelta(days=10)
    # +35% -> ELEVATED (>= threshold, < 2*threshold)
    up = base + [Row("DEL-BOM", "DEL", "BOM", 1, day, 6800.0, source_id=s) for s in ("s1", "s2", "s3")]
    # -30% -> DIP
    down = base + [Row("DEL-BOM", "DEL", "BOM", 1, day, 3400.0, source_id=s) for s in ("s1", "s2", "s3")]
    assert detect_anomalies(up)[0].severity == "ELEVATED"
    assert detect_anomalies(down)[0].severity == "DIP"


def test_no_source_consensus_not_flagged():
    """2 sources: only one moves (1/2 = 50% < 60%) and <3 sources -> no flag."""
    rows = rows_stable(n_days=10, sources=("s1", "s2"))
    day = START + timedelta(days=10)
    # s1 spikes, s2 unchanged -> overall median ~ +2.5%... force group median up:
    # use 3 rows from s1 spiked so current_median itself rises past threshold.
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 9000.0, source_id="s1") for _ in range(3)]
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 5000.0, source_id="s2")]
    out = detect_anomalies(rows, window_days=30, threshold_pct=25)
    # s1 confirms (1/1 sources with history), s2 seen but flat -> confirmations=1 of 2
    assert out == []


def test_single_source_no_flag_even_if_huge():
    """1 source only: below the 3-source floor and no consensus share."""
    rows = rows_stable(n_days=10, sources=("s1",))
    day = START + timedelta(days=10)
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 12000.0, source_id="s1")]
    assert detect_anomalies(rows, window_days=30, threshold_pct=25) == []


def test_sold_out_share_and_exclusion():
    rows = rows_stable()
    day = START + timedelta(days=10)
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 9500.0, source_id=s) for s in ("s1", "s2", "s3")]
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 0.0, availability="SOLD_OUT", source_id="s4")
             for _ in range(1)]
    out = detect_anomalies(rows, window_days=30, threshold_pct=25)
    rec = out[0]
    assert rec.sold_out_share == 1 / 4
    assert "sold out" in rec.explanation["availability"]


def test_outlier_and_sold_out_rows_excluded_from_medians():
    rows = rows_stable()
    day = START + timedelta(days=10)
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 9500.0, source_id=s) for s in ("s1", "s2", "s3")]
    # An outlier-flagged 999999 on a window day must not drag the window median.
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day - timedelta(days=1), 999999.0,
                 source_id="s1", outlier_flag=True)]
    out = detect_anomalies(rows, window_days=30, threshold_pct=25)
    assert len(out) == 1 and out[0].severity == "SHOCK"


def test_records_sorted_by_abs_change():
    rows = rows_stable()
    day = START + timedelta(days=10)
    rows += [Row("DEL-BOM", "DEL", "BOM", 1, day, 7000.0, source_id=s) for s in ("s1", "s2", "s3")]
    rows += [Row("DEL-BLR", "DEL", "BLR", 1, day, 12000.0, source_id=s) for s in ("s1", "s2", "s3")]
    rows += [Row("DEL-BLR", "DEL", "BLR", 1, START + timedelta(days=i), 5000.0, source_id=s)
             for i in range(10) for s in ("s1", "s2", "s3")]
    out = detect_anomalies(rows, window_days=30, threshold_pct=25)
    assert [r.route_id for r in out] == ["DEL-BLR", "DEL-BOM"]


# ---------------------------------------------------------------- API


def test_anomalies_endpoint_validation(api_client):
    assert api_client.get("/api/v1/anomalies?window_days=3").status_code == 422
    assert api_client.get("/api/v1/anomalies?window_days=400").status_code == 422
    assert api_client.get("/api/v1/anomalies?threshold_pct=1").status_code == 422
    assert api_client.get("/api/v1/anomalies?threshold_pct=101").status_code == 422
    assert api_client.get("/api/v1/anomalies?route_id=XXX-YYY").status_code == 404


def test_anomalies_endpoint_shape(api_client):
    body = api_client.get("/api/v1/anomalies?window_days=30").json()
    assert body["model_version"] == "ANOMALY-v1"
    assert body["as_of"]
    assert "not part of the index calculation" in body["disclaimer"]
    for a in body["anomalies"]:
        assert a["severity"] in ("SHOCK", "ELEVATED", "DIP")
        assert a["change_pct"] == 0 or abs(a["change_pct"]) >= 25
        assert set(a["explanation"]) >= {"lead_window", "source_confirmation", "availability", "comparison"}
        assert a["source_confirmations"] <= a["sources_seen"]


def test_anomalies_endpoint_high_threshold_empty(api_client):
    """Gently trending seed data: a 100% threshold must yield an honest empty list."""
    body = api_client.get("/api/v1/anomalies?threshold_pct=100").json()
    assert body["anomalies"] == []
    assert body["model_version"] == "ANOMALY-v1"
