"""Aggregation of quotes into route-specification prices (FR-13).

A specification is (route_id, lead_time). The spec price for a collection date
is the median consumer-payable fare over AVAILABLE, non-outlier-flagged quotes —
robust to residual contamination. Missing specs stay missing (never zero, never
imputed in v1); the index reweights around them (documented missing-data policy).
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Iterable

SpecKey = tuple[date, str, int]  # (collection_date, route_id, lead_time)
SpecPrices = dict[SpecKey, float]


@dataclass(frozen=True)
class QuotePriceRow:
    """Minimal projection of a FareQuote for aggregation."""

    collection_date: date
    route_id: str
    lead_time: int
    payable_fare: float
    availability: str
    outlier_flag: bool


def build_spec_prices(rows: Iterable[QuotePriceRow]) -> SpecPrices:
    """Median payable fare per (collection_date, route, lead_time) spec."""
    groups: dict[SpecKey, list[float]] = defaultdict(list)
    for row in rows:
        if row.availability != "AVAILABLE" or row.outlier_flag:
            continue
        groups[(row.collection_date, row.route_id, row.lead_time)].append(row.payable_fare)
    return {spec: round(statistics.median(vals), 2) for spec, vals in groups.items() if vals}


def base_period_prices(
    spec_prices: SpecPrices,
    start: date,
    end: date,
) -> dict[tuple[str, int], float]:
    """P_i,0: mean spec price over the base period [start, end] inclusive."""
    sums: dict[tuple[str, int], float] = defaultdict(float)
    counts: dict[tuple[str, int], int] = defaultdict(int)
    for (day, route_id, lead), price in spec_prices.items():
        if start <= day <= end:
            sums[(route_id, lead)] += price
            counts[(route_id, lead)] += 1
    return {spec: round(sums[spec] / counts[spec], 2) for spec in sums}
