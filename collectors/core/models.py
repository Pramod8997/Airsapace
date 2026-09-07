"""Canonical data contract (TRD §6) shared by collectors, pipeline and replay."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Availability(str, Enum):
    """Observation availability states (PRD §12). Missing/sold-out is never zero."""

    AVAILABLE = "AVAILABLE"
    SOLD_OUT = "SOLD_OUT"
    MISSING = "MISSING"
    INVALID = "INVALID"
    IMPUTED = "IMPUTED"
    REJECTED = "REJECTED"


class FailureClass(str, Enum):
    """Explicit failure classification (TRD §12)."""

    TIMEOUT = "TIMEOUT"
    BLOCKED = "BLOCKED"
    CAPTCHA = "CAPTCHA"
    ROBOTS_DENIED = "ROBOTS_DENIED"
    PARSER_ERROR = "PARSER_ERROR"
    SCHEMA_ERROR = "SCHEMA_ERROR"
    SOURCE_DOWN = "SOURCE_DOWN"
    UNKNOWN = "UNKNOWN"


CABIN_ECONOMY = "economy"
VALID_CABINS = {CABIN_ECONOMY}
VALID_CURRENCIES = {"INR"}  # prototype: domestic India only
LEAD_TIMES = (1, 7, 15, 30, 45)  # PRD frozen decision


class FlightSearchQuery(BaseModel):
    """What a collection job asks a source for (FR-04)."""

    origin: str = Field(min_length=3, max_length=3)
    destination: str = Field(min_length=3, max_length=3)
    departure_date: date
    advance_days: int = Field(ge=0, le=365)
    cabin: str = CABIN_ECONOMY
    passengers: int = Field(default=1, ge=1, le=9)
    trip_type: str = "one-way"
    nonstop_only: bool = True


class FlightQuote(BaseModel):
    """Canonical normalized fare observation (TRD §6). Adapters must emit these."""

    source_id: str
    origin: str
    destination: str
    departure_date: date
    departure_time: Optional[str] = None
    airline: str
    flight_number: Optional[str] = None
    cabin: str = CABIN_ECONOMY
    fare_class: Optional[str] = None
    advance_days: int
    base_fare: Optional[float] = None
    taxes: Optional[float] = None
    mandatory_fees: Optional[float] = None
    convenience_fee: float = 0.0
    other_fee: float = 0.0
    total_fare: Optional[float] = None
    currency: str = "INR"
    availability: Availability = Availability.AVAILABLE
    stops: int = 0
    collected_at: datetime


class SourceHealth(BaseModel):
    source_id: str
    ok: bool
    detail: str = ""
    checked_at: datetime
