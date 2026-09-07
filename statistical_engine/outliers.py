"""Robust outlier flagging (PRD §13).

An expensive fare is NOT automatically an outlier. Median/MAD robust z-score per
(route, lead time, collection date) peer group, plus a fat-finger business rule.
Observations are flagged, never silently deleted.
"""
from __future__ import annotations

import statistics

OUTLIER_METHOD_VERSION = "MAD-z3.5-v1"
MIN_GROUP_SIZE = 4          # below this, peer comparison is meaningless
Z_THRESHOLD = 3.5           # standard robust-z cut (Iglewicz & Hoaglin)
FAT_FINGER_FACTOR = 10.0    # >10x peer median is a data-entry error


class OutlierFlags:
    """Result for a group of values, index-aligned with the input."""

    def __init__(self, flagged: list[bool], reasons: list[str | None]):
        self.flagged = flagged
        self.reasons = reasons

    def __repr__(self) -> str:  # pragma: no cover
        return f"OutlierFlags(flagged={sum(self.flagged)}/{len(self.flagged)})"


def flag_outliers(values: list[float | None]) -> OutlierFlags:
    """Flag outliers among priceable values; None values are never flagged."""
    n = len(values)
    flagged = [False] * n
    reasons: list[str | None] = [None] * n

    present = [v for v in values if v is not None]
    if len(present) < MIN_GROUP_SIZE:
        return OutlierFlags(flagged, reasons)

    med = statistics.median(present)
    abs_dev = [abs(v - med) for v in present]
    mad = statistics.median(abs_dev)

    for i, v in enumerate(values):
        if v is None:
            continue
        if v > med * FAT_FINGER_FACTOR or v < med / FAT_FINGER_FACTOR:
            flagged[i], reasons[i] = True, "fat_finger"
        elif mad > 0 and abs(0.6745 * (v - med) / mad) > Z_THRESHOLD:
            flagged[i], reasons[i] = True, "robust_z"
    return OutlierFlags(flagged, reasons)
