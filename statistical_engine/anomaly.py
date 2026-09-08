"""Rule-based anomaly (candidate price-shock) detection — UI_UX_DESIGN.md §20.

HONESTY: this flags *candidate* shocks with supporting evidence (lead window,
availability change, source consensus). It does NOT prove causation — a flagged
fare may be demand, capacity, data timing, or a short-lived quote. It is
ML-adjacent analysis over stored data and is NEVER part of the official index
calculation (CLAUDE.md invariant: index engine stays deterministic and
statistics-only).

Deterministic and versioned: same rows + parameters -> same records; any change
to thresholds, windows, or consensus logic bumps ANOMALY_MODEL_VERSION.
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

ANOMALY_MODEL_VERSION = "ANOMALY-v1"

MIN_WINDOW_QUOTES = 3       # below this the trailing median is meaningless
MIN_CURRENT_QUOTES = 1      # need at least one usable quote today
MIN_SOURCES_FOR_CONSENSUS = 3
CONSENSUS_SHARE = 0.60      # >=60% of seen sources moving the same way


@dataclass
class AnomalyRecord:
    route_id: str
    origin: str
    destination: str
    lead_time: int
    current_date: object          # datetime.date of the latest collection day
    current_median: float
    window_median: float
    change_pct: float
    source_confirmations: int     # sources whose latest-day median moved the same way
    sources_seen: int             # distinct sources quoting on the latest day
    sold_out_share: float         # SOLD_OUT / total quotes for (route, lead) latest day
    severity: str                 # SHOCK | ELEVATED | DIP
    explanation: dict


def _usable(row) -> bool:
    return (
        getattr(row, "availability", None) == "AVAILABLE"
        and not getattr(row, "outlier_flag", False)
        and getattr(row, "consumer_payable_fare", None) is not None
    )


def _severity(change_pct: float, threshold_pct: float) -> str:
    if abs(change_pct) >= 2 * threshold_pct:
        return "SHOCK"
    return "ELEVATED" if change_pct > 0 else "DIP"


def detect_anomalies(rows, window_days: int = 30, threshold_pct: float = 25.0) -> list[AnomalyRecord]:
    """Detect candidate fare anomalies per (route_id, lead time).

    rows: duck-typed FareQuote-shaped objects (route_id, advance_days,
    collection_date, consumer_payable_fare, availability, source_id, origin,
    destination). Returns records sorted by |change_pct| descending.
    """
    groups: dict[tuple[str, int], list] = defaultdict(list)
    for row in rows:
        groups[(row.route_id, row.advance_days)].append(row)

    records: list[AnomalyRecord] = []
    for (route_id, lead), group in groups.items():
        latest_day = max(r.collection_date for r in group)
        window_start = latest_day - timedelta(days=window_days)

        current = [r for r in group if r.collection_date == latest_day and _usable(r)]
        window = [
            r for r in group
            if window_start <= r.collection_date < latest_day and _usable(r)
        ]
        if len(current) < MIN_CURRENT_QUOTES or len(window) < MIN_WINDOW_QUOTES:
            continue

        current_median = statistics.median(r.consumer_payable_fare for r in current)
        window_median = statistics.median(r.consumer_payable_fare for r in window)
        if not window_median:
            continue

        change_pct = (current_median / window_median - 1) * 100
        if abs(change_pct) < threshold_pct:
            continue

        # Source consensus: per source, did its own latest-day median move the
        # same way as the overall change?
        by_source_current: dict[str, list[float]] = defaultdict(list)
        by_source_window: dict[str, list[float]] = defaultdict(list)
        for r in current:
            by_source_current[r.source_id].append(r.consumer_payable_fare)
        for r in window:
            by_source_window[r.source_id].append(r.consumer_payable_fare)

        sources_seen = len(by_source_current)
        confirmations = sum(
            1
            for sid, values in by_source_current.items()
            if sid in by_source_window
            and (statistics.median(values) - statistics.median(by_source_window[sid]))
            * change_pct > 0
        )
        consensus = (
            sources_seen >= MIN_SOURCES_FOR_CONSENSUS
            # share branch needs >=2 sources: 1/1 is trivial "consensus", not corroboration
            or (sources_seen >= 2 and confirmations / sources_seen >= CONSENSUS_SHARE)
        )
        if not consensus:
            continue

        latest_rows = [r for r in group if r.collection_date == latest_day]
        sold_out = sum(1 for r in latest_rows if r.availability == "SOLD_OUT")
        sold_out_share = sold_out / len(latest_rows) if latest_rows else 0.0

        any_row = group[0]
        records.append(AnomalyRecord(
            route_id=route_id,
            origin=any_row.origin,
            destination=any_row.destination,
            lead_time=lead,
            current_date=latest_day,
            current_median=round(current_median, 2),
            window_median=round(window_median, 2),
            change_pct=round(change_pct, 2),
            source_confirmations=confirmations,
            sources_seen=sources_seen,
            sold_out_share=round(sold_out_share, 4),
            severity=_severity(change_pct, threshold_pct),
            explanation={
                "lead_window": f"T+{lead} booking window",
                "source_confirmation": f"{confirmations}/{sources_seen} source confirmation",
                "availability": f"{sold_out_share:.0%} sold out on latest day",
                "comparison": f"vs {window_days}-day route median",
            },
        ))

    records.sort(key=lambda rec: abs(rec.change_pct), reverse=True)
    return records
