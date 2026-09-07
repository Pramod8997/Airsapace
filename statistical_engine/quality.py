"""Versioned data-quality scoring (FR-10).

Score components: completeness, consistency, validity, source reliability,
timestamp validity, non-duplication. The scoring model is versioned; any change
to weights or component logic bumps QUALITY_MODEL_VERSION.
"""
from __future__ import annotations

from datetime import datetime, timezone

from collectors.core.models import (
    VALID_CABINS,
    VALID_CURRENCIES,
    Availability,
    FlightQuote,
)
from statistical_engine.normalization import fare_components_consistent

QUALITY_MODEL_VERSION = "QS-v1"

# Fields counted for completeness. Core identification fields weigh more by
# being required in the canonical schema already; these are the optional-but-
# analytically valuable ones.
COMPLETENESS_FIELDS = (
    "departure_time",
    "flight_number",
    "fare_class",
    "base_fare",
    "taxes",
    "mandatory_fees",
    "total_fare",
)

COMPONENT_WEIGHTS = {
    "completeness": 0.30,
    "consistency": 0.25,
    "validity": 0.20,
    "source_reliability": 0.10,
    "timestamp_validity": 0.10,
    "non_duplicate": 0.05,
}


class QualityResult:
    def __init__(self, score: float, components: dict[str, float]):
        self.score = score
        self.components = components

    def __repr__(self) -> str:  # pragma: no cover
        return f"QualityResult(score={self.score:.3f})"


def assess_quality(
    quote: FlightQuote,
    source_reliability: float = 1.0,
    is_duplicate: bool = False,
    now: datetime | None = None,
) -> QualityResult:
    now = now or datetime.now(timezone.utc)

    filled = sum(1 for f in COMPLETENESS_FIELDS if getattr(quote, f) is not None)
    completeness = filled / len(COMPLETENESS_FIELDS)

    has_price = quote.base_fare is not None
    consistency = 1.0 if (has_price and fare_components_consistent(quote)) else (0.0 if has_price else 0.5)

    validity = _validity(quote, now)

    timestamp_validity = 1.0 if _timestamp_ok(quote.collected_at, now) else 0.0

    components = {
        "completeness": completeness,
        "consistency": consistency,
        "validity": validity,
        "source_reliability": max(0.0, min(1.0, source_reliability)),
        "timestamp_validity": timestamp_validity,
        "non_duplicate": 0.0 if is_duplicate else 1.0,
    }
    score = round(sum(COMPONENT_WEIGHTS[k] * v for k, v in components.items()), 3)
    return QualityResult(score, components)


def _validity(quote: FlightQuote, now: datetime) -> float:
    """Fraction of validity rules passed. Failures classify the quote INVALID."""
    checks = [
        quote.origin.isalpha() and len(quote.origin) == 3,
        quote.destination.isalpha() and len(quote.destination) == 3,
        quote.cabin in VALID_CABINS,
        quote.currency in VALID_CURRENCIES,
        quote.stops >= 0,
        quote.advance_days >= 0,
        _advance_days_matches(quote),
        _fares_non_negative(quote),
    ]
    return sum(1 for c in checks if c) / len(checks)


def _advance_days_matches(quote: FlightQuote) -> bool:
    delta = (quote.departure_date - quote.collected_at.date()).days
    return delta == quote.advance_days


def _fares_non_negative(quote: FlightQuote) -> bool:
    for v in (quote.base_fare, quote.taxes, quote.mandatory_fees, quote.total_fare):
        if v is not None and v < 0:
            return False
    return True


def _timestamp_ok(collected_at: datetime, now: datetime) -> bool:
    if collected_at.tzinfo is None:
        return False  # naive timestamps are not comparable; treat as invalid
    return collected_at <= now


def is_valid_observation(quality: QualityResult, availability: Availability) -> bool:
    """Hard INVALID classification: any validity-rule failure or unusable price."""
    if availability in (Availability.SOLD_OUT, Availability.MISSING):
        return True  # not an error — a market state, keep the row
    return quality.components["validity"] == 1.0 and quality.components["consistency"] > 0.0
