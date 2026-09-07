"""The APIx index engine (FR-11, FR-12). Deterministic Laspeyres-style index.

    I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100

w_i = specification weight (route × lead time), P_i,t = current spec price,
P_i,0 = base-period spec price. Specs with no valid observation on day t drop
out of BOTH numerator and denominator (reweighting, not imputation) — the
documented missing-data policy for methodology APIX-v1.0.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from statistical_engine.aggregation import SpecPrices
from statistical_engine.basket import Basket, SpecWeightKey


class IndexCalculationError(RuntimeError):
    """Raised when an index cannot be computed from the given inputs."""


@dataclass(frozen=True)
class IndexPoint:
    index_date: date
    route_id: str | None  # None = national
    lead_time: int | None  # None = combined across lead times
    value: float


def laspeyres_index(
    prices: dict[SpecWeightKey, float],
    base_prices: dict[SpecWeightKey, float],
    weights: dict[SpecWeightKey, float],
) -> float | None:
    """Deterministic index over the specs present in `prices`. None if empty."""
    numerator = 0.0
    denominator = 0.0
    for spec, w in weights.items():
        if w <= 0:
            continue
        p_t = prices.get(spec)
        p_0 = base_prices.get(spec)
        if p_t is None or p_0 is None or p_0 <= 0:
            continue
        numerator += w * (p_t / p_0)
        denominator += w
    if denominator <= 0:
        return None
    return round(numerator / denominator * 100.0, 4)


def _day_prices(spec_prices: SpecPrices, day: date) -> dict[SpecWeightKey, float]:
    return {(r, l): p for (d, r, l), p in spec_prices.items() if d == day}


def compute_index_series(
    spec_prices: SpecPrices,
    base_prices: dict[SpecWeightKey, float],
    basket: Basket,
    days: Iterable[date],
) -> list[IndexPoint]:
    """Compute every index cut: national combined, national per lead time,
    per-route combined, per-route per lead time (FR-13)."""
    points: list[IndexPoint] = []
    for day in sorted(days):
        day_prices = _day_prices(spec_prices, day)
        cuts: list[tuple[str | None, int | None]] = [(None, None)]
        cuts += [(None, lead) for lead in (1, 7, 15, 30, 45)]
        cuts += [(route, None) for route in basket.route_ids()]
        cuts += [(route, lead) for route in basket.route_ids() for lead in (1, 7, 15, 30, 45)]
        for route_id, lead in cuts:
            weights = basket.weights_for(route_id, lead)
            value = laspeyres_index(day_prices, base_prices, weights)
            if value is not None:
                points.append(IndexPoint(day, route_id, lead, value))
    return points


def input_fingerprint(
    spec_prices: SpecPrices,
    base_prices: dict[SpecWeightKey, float],
    basket: Basket,
) -> str:
    """SHA-256 over the normalized calculation input (SECURITY.md §16).

    Deterministic ordering makes the fingerprint a reproducibility token: same
    snapshot + weights -> same hash -> same index.
    """
    import hashlib
    import json

    payload = {
        "basket_version": basket.basket_version,
        "weight_version": basket.weight_version,
        "base_period": [basket.base_period_start.isoformat(), basket.base_period_end.isoformat()],
        "weights": {f"{r}@{l}": w for (r, l), w in sorted(basket.weights.items())},
        "base_prices": {f"{r}@{l}": p for (r, l), p in sorted(base_prices.items())},
        "spec_prices": {f"{d.isoformat()}|{r}@{l}": p for (d, r, l), p in sorted(spec_prices.items())},
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()
