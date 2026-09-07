"""Backtesting metrics (FR-14): MAE, RMSE, MAPE, correlation, trend-direction.

Correlation validates co-movement; it does NOT prove methodological equivalence
with DGCA's series (statistical honesty invariant — surfaced in the API too).
"""
from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeriesPoint:
    date: date
    value: float


@dataclass
class BacktestMetrics:
    n_points: int
    mae: float | None
    rmse: float | None
    mape: float | None
    correlation: float | None
    trend_direction_accuracy: float | None

    def as_dict(self) -> dict:
        return {
            "n_points": self.n_points,
            "mae": self.mae,
            "rmse": self.rmse,
            "mape": self.mape,
            "correlation": self.correlation,
            "trend_direction_accuracy": self.trend_direction_accuracy,
        }


def align_series(a: list[SeriesPoint], b: list[SeriesPoint]) -> list[tuple[float, float]]:
    """Inner join on date, both sides ordered by date."""
    bmap = {p.date: p.value for p in b}
    return [(p.value, bmap[p.date]) for p in sorted(a, key=lambda p: p.date) if p.date in bmap]


def compute_metrics(actual: list[SeriesPoint], reference: list[SeriesPoint]) -> BacktestMetrics:
    pairs = align_series(actual, reference)
    n = len(pairs)
    if n == 0:
        return BacktestMetrics(0, None, None, None, None, None)

    errors = [a - r for a, r in pairs]
    mae = round(sum(abs(e) for e in errors) / n, 4)
    rmse = round(math.sqrt(sum(e * e for e in errors) / n), 4)

    # MAPE over reference denominators; skip zero-reference points.
    pct = [abs(a - r) / r for a, r in pairs if r != 0]
    mape = round(100.0 * sum(pct) / len(pct), 4) if pct else None

    xs = [a for a, _ in pairs]
    ys = [r for _, r in pairs]
    correlation = round(statistics.correlation(xs, ys), 4) if n >= 2 and _spread(xs) and _spread(ys) else None

    direction = _trend_direction_accuracy(actual, reference)
    return BacktestMetrics(n, mae, rmse, mape, correlation, direction)


def _trend_direction_accuracy(actual: list[SeriesPoint], reference: list[SeriesPoint]) -> float | None:
    """Fraction of day-over-day changes where both series move the same way."""
    ref_map = {p.date: p.value for p in reference}
    a_sorted = sorted(actual, key=lambda p: p.date)
    agree = 0
    total = 0
    for prev, curr in zip(a_sorted, a_sorted[1:]):
        rp, rc = ref_map.get(prev.date), ref_map.get(curr.date)
        if rp is None or rc is None:
            continue
        da, dr = curr.value - prev.value, rc - rp
        if da == 0 or dr == 0:
            continue
        total += 1
        if (da > 0) == (dr > 0):
            agree += 1
    return round(agree / total, 4) if total else None


def _spread(values: list[float]) -> bool:
    return max(values) != min(values)
