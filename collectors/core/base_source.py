"""Source adapter contract (TRD §5).

Every source implements the same interface. Responsibilities: source interaction,
parsing, canonical mapping, source-specific errors. Non-responsibilities: route
weighting, index calculation, outlier deletion.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from collectors.core.models import FlightQuote, FlightSearchQuery, SourceHealth


class SourcePolicyError(RuntimeError):
    """Raised when a source's robots/ToS/policy state forbids collection."""


class FlightSource(ABC):
    """Base class for all airline/OTA adapters. Must not calculate the index."""

    source_id: str
    adapter_version: str = "unversioned"

    @abstractmethod
    async def search(self, query: FlightSearchQuery) -> list[FlightQuote]:
        """Return canonical quotes for the query. Ethical collection only."""

    @abstractmethod
    async def health_check(self) -> SourceHealth:
        """Report whether the source is currently usable."""
