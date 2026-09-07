"""Route basket and weights (FR-02, FR-11).

Weights are versioned and must sum to a positive total. The prototype weights
are placeholders derived from route importance; production weights must come
from authoritative passenger-traffic data (PRD §14, open question in memory.md).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

SpecWeightKey = tuple[str, int]  # (route_id, lead_time)


class BasketError(ValueError):
    """Raised when a basket/weight configuration is invalid."""


@dataclass
class Basket:
    basket_version: str
    weight_version: str
    weight_source: str
    base_period_start: date
    base_period_end: date
    weights: dict[SpecWeightKey, float] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.weights:
            raise BasketError("basket has no weights")
        for (route_id, lead), w in self.weights.items():
            if w < 0:
                raise BasketError(f"negative weight for {route_id}@T+{lead}")
            if lead not in (1, 7, 15, 30, 45):
                raise BasketError(f"unsupported lead time {lead}")
        if sum(self.weights.values()) <= 0:
            raise BasketError("total weight must be positive")

    def weights_for(self, route_id: str | None = None, lead_time: int | None = None) -> dict[SpecWeightKey, float]:
        """Subset of weights matching a cut (route and/or lead time)."""
        return {
            (r, l): w
            for (r, l), w in self.weights.items()
            if (route_id is None or r == route_id) and (lead_time is None or l == lead_time)
        }

    def route_ids(self) -> list[str]:
        return sorted({r for r, _ in self.weights})
