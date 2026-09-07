"""Fare normalization (FR-09).

Primary comparison metric is the consumer-payable fare; components stay stored
separately. Convenience fees are avoidable (book direct) and excluded.
"""
from __future__ import annotations

from collectors.core.models import Availability, FlightQuote

CONSISTENCY_TOLERANCE_INR = 5.0


def consumer_payable_fare(
    base_fare: float | None,
    taxes: float | None,
    mandatory_fees: float | None,
) -> float | None:
    """base + taxes + mandatory fees. None if any component is missing."""
    if base_fare is None or taxes is None or mandatory_fees is None:
        return None
    payable = round(base_fare + taxes + mandatory_fees, 2)
    return payable if payable > 0 else None


def quote_payable_fare(quote: FlightQuote) -> float | None:
    return consumer_payable_fare(quote.base_fare, quote.taxes, quote.mandatory_fees)


def fare_components_consistent(quote: FlightQuote, tolerance: float = CONSISTENCY_TOLERANCE_INR) -> bool:
    """total_fare must reconcile with its components within tolerance."""
    payable = consumer_payable_fare(quote.base_fare, quote.taxes, quote.mandatory_fees)
    if payable is None or quote.total_fare is None:
        return False
    return abs(quote.total_fare - payable) <= tolerance


def is_priceable(quote: FlightQuote) -> bool:
    """True when the quote carries a usable price (not sold-out/missing/invalid)."""
    return quote.availability == Availability.AVAILABLE and quote_payable_fare(quote) is not None
