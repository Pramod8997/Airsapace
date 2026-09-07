"""SQLAlchemy models — the full PRD §10 data model.

Layering: RAW (RawObservation, immutable) -> PROCESSED (FareQuote + QualityAssessment)
-> INDEX (IndexValue, versioned, idempotent). Raw is never overwritten with
cleaned values (CLAUDE.md invariant).
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from statistical_engine.outliers import OUTLIER_METHOD_VERSION
from statistical_engine.quality import QUALITY_MODEL_VERSION


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# --------------------------------------------------------------------------
# Registries (FR-01, FR-02, FR-03)
# --------------------------------------------------------------------------


class Airport(Base):
    __tablename__ = "airports"

    code: Mapped[str] = mapped_column(String(3), primary_key=True)  # IATA
    city: Mapped[str] = mapped_column(String(120))
    state: Mapped[str] = mapped_column(String(120))


class Airline(Base):
    __tablename__ = "airlines"

    iata: Mapped[str] = mapped_column(String(2), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    source_mapping: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(String(60), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(20))  # AIRLINE | OTA
    url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    adapter_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    adapter_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    policy_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    robots_status: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    rate_limit_per_hour: Mapped[int] = mapped_column(Integer, default=60)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    reliability: Mapped[float] = mapped_column(Float, default=1.0)  # quality input
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Route(Base):
    __tablename__ = "routes"

    id: Mapped[str] = mapped_column(String(10), primary_key=True)  # e.g. "DEL-BOM"
    origin: Mapped[str] = mapped_column(String(3), ForeignKey("airports.code"))
    destination: Mapped[str] = mapped_column(String(3), ForeignKey("airports.code"))
    origin_city: Mapped[str] = mapped_column(String(120))
    destination_city: Mapped[str] = mapped_column(String(120))
    # Current weight (denormalized copy for the registry view). The versioned
    # source of truth used in calculation is IndexWeight.
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    weight_source: Mapped[str] = mapped_column(String(200), default="prototype-placeholder")
    weight_version: Mapped[str] = mapped_column(String(40), default="unversioned")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


# --------------------------------------------------------------------------
# Collection (FR-05, FR-06)
# --------------------------------------------------------------------------


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"
    __table_args__ = (
        # TRD §11 job key -> idempotent scheduling
        UniqueConstraint(
            "source_id", "route_id", "departure_date", "lead_time", "collection_date",
            name="uq_scrape_job_key",
        ),
        Index("ix_scrape_jobs_status_started", "status", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[str] = mapped_column(String(60), ForeignKey("sources.id"))
    route_id: Mapped[str] = mapped_column(String(10), ForeignKey("routes.id"))
    departure_date: Mapped[date] = mapped_column(Date)
    lead_time: Mapped[int] = mapped_column(Integer)
    collection_date: Mapped[date] = mapped_column(Date)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # SUCCESS | PARTIAL | FAILED | SKIPPED
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, default=0)
    error_class: Mapped[str | None] = mapped_column(String(30), nullable=True)

    raw_observations: Mapped[list[RawObservation]] = relationship()


class RawObservation(Base):
    """Immutable raw record. Never updated after insert."""

    __tablename__ = "raw_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("scrape_jobs.id"))
    source_id: Mapped[str] = mapped_column(String(60), ForeignKey("sources.id"))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    parser_version: Mapped[str] = mapped_column(String(40))
    request_meta: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON: canonical quote as received


# --------------------------------------------------------------------------
# Processed observations (FR-07, FR-08, FR-09, FR-10, PRD §13)
# --------------------------------------------------------------------------


class FareQuote(Base):
    __tablename__ = "fare_quotes"
    __table_args__ = (
        # Dedup: same source quoting the same flight+cabin at the same instant
        # collected once is the same observation. (NULL-bearing columns make
        # this constraint best-effort on engines treating NULLs as distinct.)
        UniqueConstraint(
            "source_id", "origin", "destination", "departure_date", "departure_time",
            "airline", "flight_number", "cabin", "fare_class", "advance_days", "collected_at",
            name="uq_fare_quote_natural",
        ),
        Index("ix_fare_quotes_route_date", "origin", "destination", "departure_date"),
        Index("ix_fare_quotes_collected_at", "collected_at"),
        Index("ix_fare_quotes_source_id", "source_id"),
        Index("ix_fare_quotes_advance_days", "advance_days"),
        Index("ix_fare_quotes_collection_date", "collection_date", "route_id", "advance_days"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raw_observation_id: Mapped[int | None] = mapped_column(ForeignKey("raw_observations.id"), nullable=True)
    source_id: Mapped[str] = mapped_column(String(60), ForeignKey("sources.id"))
    route_id: Mapped[str] = mapped_column(String(10), ForeignKey("routes.id"))
    origin: Mapped[str] = mapped_column(String(3))
    destination: Mapped[str] = mapped_column(String(3))
    departure_date: Mapped[date] = mapped_column(Date)
    departure_time: Mapped[str | None] = mapped_column(String(5), nullable=True)
    airline: Mapped[str] = mapped_column(String(3))
    flight_number: Mapped[str | None] = mapped_column(String(8), nullable=True)
    cabin: Mapped[str] = mapped_column(String(20))
    fare_class: Mapped[str | None] = mapped_column(String(2), nullable=True)
    advance_days: Mapped[int] = mapped_column(Integer)
    base_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    taxes: Mapped[float | None] = mapped_column(Float, nullable=True)
    mandatory_fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    convenience_fee: Mapped[float] = mapped_column(Float, default=0.0)
    other_fee: Mapped[float] = mapped_column(Float, default=0.0)
    total_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    consumer_payable_fare: Mapped[float | None] = mapped_column(Float, nullable=True)  # FR-09
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    availability: Mapped[str] = mapped_column(String(12))  # PRD §12 states
    stops: Mapped[int] = mapped_column(Integer, default=0)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collection_date: Mapped[date] = mapped_column(Date)  # collected_at.date(), indexed
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    outlier_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    outlier_reason: Mapped[str | None] = mapped_column(String(40), nullable=True)
    outlier_method_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    raw_observation: Mapped[RawObservation | None] = relationship()
    quality_assessment: Mapped[QualityAssessment | None] = relationship(back_populates="quote")


class QualityAssessment(Base):
    """Component-level breakdown behind a quote's quality score (FR-10)."""

    __tablename__ = "quality_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("fare_quotes.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(20), default=QUALITY_MODEL_VERSION)
    score: Mapped[float] = mapped_column(Float)
    components: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON

    quote: Mapped[FareQuote] = relationship(back_populates="quality_assessment")


# --------------------------------------------------------------------------
# Index construction (FR-11, FR-12, TRD §9)
# --------------------------------------------------------------------------


class MethodologyVersion(Base):
    __tablename__ = "methodology_versions"

    version: Mapped[str] = mapped_column(String(40), primary_key=True)  # e.g. APIX-v1.0
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    base_period_start: Mapped[date] = mapped_column(Date)
    base_period_end: Mapped[date] = mapped_column(Date)
    outlier_policy: Mapped[str] = mapped_column(Text, default="")
    missing_data_policy: Mapped[str] = mapped_column(Text, default="")
    quality_model_version: Mapped[str] = mapped_column(String(20), default=QUALITY_MODEL_VERSION)
    outlier_method_version: Mapped[str] = mapped_column(String(40), default=OUTLIER_METHOD_VERSION)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IndexBasket(Base):
    __tablename__ = "index_baskets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basket_version: Mapped[str] = mapped_column(String(40))
    weight_version: Mapped[str] = mapped_column(String(40))
    weight_source: Mapped[str] = mapped_column(String(200))
    methodology_version: Mapped[str] = mapped_column(String(40), ForeignKey("methodology_versions.version"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    weights: Mapped[list[IndexWeight]] = relationship(back_populates="basket")


class IndexWeight(Base):
    __tablename__ = "index_weights"
    __table_args__ = (UniqueConstraint("basket_id", "route_id", "lead_time", name="uq_index_weight"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    basket_id: Mapped[int] = mapped_column(ForeignKey("index_baskets.id"))
    route_id: Mapped[str] = mapped_column(String(10), ForeignKey("routes.id"))
    lead_time: Mapped[int] = mapped_column(Integer)  # 1|7|15|30|45
    weight: Mapped[float] = mapped_column(Float)

    basket: Mapped[IndexBasket] = relationship(back_populates="weights")


class CalculationRun(Base):
    """One deterministic execution of the pipeline (SECURITY.md §16)."""

    __tablename__ = "calculation_runs"

    id: Mapped[str] = mapped_column(Integer, primary_key=True)
    run_type: Mapped[str] = mapped_column(String(20))  # INDEX | BACKTEST
    processor_version: Mapped[str] = mapped_column(String(40))
    methodology_version: Mapped[str] = mapped_column(String(40))
    basket_version: Mapped[str] = mapped_column(String(40))
    weight_version: Mapped[str] = mapped_column(String(40))
    input_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    observation_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IndexValue(Base):
    """Immutable, versioned index output. Never overwritten (SECURITY.md §24)."""

    __tablename__ = "index_values"
    __table_args__ = (
        UniqueConstraint(
            "index_date", "route_id", "lead_time", "methodology_version", "basket_version",
            name="uq_index_value",
        ),
        Index("ix_index_values_date", "index_date"),
        Index("ix_index_values_route_date", "route_id", "index_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    index_date: Mapped[date] = mapped_column(Date)
    route_id: Mapped[str | None] = mapped_column(String(10), nullable=True)  # None = national
    lead_time: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = combined
    value: Mapped[float] = mapped_column(Float)
    base: Mapped[float] = mapped_column(Float, default=100.0)
    methodology_version: Mapped[str] = mapped_column(String(40))
    basket_version: Mapped[str] = mapped_column(String(40))
    weight_version: Mapped[str] = mapped_column(String(40))
    calculation_run_id: Mapped[int] = mapped_column(ForeignKey("calculation_runs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# --------------------------------------------------------------------------
# Validation & audit
# --------------------------------------------------------------------------


class BacktestRun(Base):
    __tablename__ = "backtest_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    calculation_run_id: Mapped[int | None] = mapped_column(ForeignKey("calculation_runs.id"), nullable=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    methodology_version: Mapped[str] = mapped_column(String(40))
    basket_version: Mapped[str] = mapped_column(String(40))
    reference_series: Mapped[str] = mapped_column(String(200))  # name/source of reference
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)  # JSON: mae/rmse/mape/corr/trend
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Argon2id when auth lands
    role: Mapped[str] = mapped_column(String(20), default="VIEWER")  # SECURITY.md §5
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(60))  # SECURITY.md §17 events
    resource: Mapped[str] = mapped_column(String(120))
    resource_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    before: Mapped[dict] = mapped_column(JSON, default=dict)
    after: Mapped[dict] = mapped_column(JSON, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(60), nullable=True)
