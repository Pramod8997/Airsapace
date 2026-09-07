"""Pydantic API schemas (FR-16 response contracts)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field


class IndexLatestOut(BaseModel):
    index: float
    base: float = 100.0
    index_date: date
    daily_change_pct: Optional[float] = None
    weekly_change_pct: Optional[float] = None
    monthly_change_pct: Optional[float] = None
    methodology_version: str
    basket_version: str
    weight_version: str
    calculation_run_id: int
    data_mode: str  # LIVE | DEMO | REPLAY — honesty about what produced this


class IndexPointOut(BaseModel):
    index_date: date
    value: float
    route_id: Optional[str] = None
    lead_time: Optional[int] = None


class IndexHistoryOut(BaseModel):
    route_id: Optional[str] = None
    lead_time: Optional[int] = None
    frequency: str
    methodology_version: str
    points: list[IndexPointOut]


class FareOut(BaseModel):
    id: int
    source_id: str
    route_id: str
    origin: str
    destination: str
    departure_date: date
    departure_time: Optional[str] = None
    airline: str
    flight_number: Optional[str] = None
    cabin: str
    fare_class: Optional[str] = None
    advance_days: int
    base_fare: Optional[float] = None
    taxes: Optional[float] = None
    mandatory_fees: Optional[float] = None
    convenience_fee: float = 0.0
    total_fare: Optional[float] = None
    consumer_payable_fare: Optional[float] = None
    currency: str
    availability: str
    stops: int
    collected_at: datetime
    quality_score: Optional[float] = None
    outlier_flag: bool
    outlier_reason: Optional[str] = None


class PaginatedFares(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[FareOut]


class RouteOut(BaseModel):
    id: str
    origin: str
    destination: str
    origin_city: str
    destination_city: str
    weight: float
    weight_source: str
    weight_version: str
    active: bool


class AirlineOut(BaseModel):
    iata: str
    name: str
    active: bool


class SourceOut(BaseModel):
    id: str
    name: str
    source_type: str
    policy_status: str
    robots_status: str
    rate_limit_per_hour: int
    active: bool
    reliability: float
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None


class SourceHealthOut(BaseModel):
    source_id: str
    observations: int
    availability_rate: float  # fraction of quotes priceable
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None


class QualityOut(BaseModel):
    window_days: int
    total_observations: int
    available: int
    sold_out: int
    invalid: int
    rejected: int
    completeness: float
    duplicate_count: int
    duplicate_rate: float
    rejection_rate: float
    imputation_rate: float
    outlier_rate: float
    source_health: list[SourceHealthOut]


class MethodologyOut(BaseModel):
    version: str
    name: str
    description: str
    base_period_start: date
    base_period_end: date
    base_value: float = 100.0
    formula: str
    outlier_policy: str
    missing_data_policy: str
    quality_model_version: str
    outlier_method_version: str
    basket_version: str
    weight_version: str
    weight_source: str
    published: bool
    lead_times: list[int]
    basket_routes: list[RouteOut]


class BacktestOut(BaseModel):
    id: int
    period_start: date
    period_end: date
    methodology_version: str
    basket_version: str
    reference_series: str
    metrics: dict
    created_at: datetime


class HealthOut(BaseModel):
    status: str
    data_mode: str
    app_env: str
    database: str
