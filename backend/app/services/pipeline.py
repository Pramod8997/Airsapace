"""Ingest & cleaning pipeline (FR-05..FR-10).

Flow per job: create ScrapeJob -> store immutable RawObservations -> classify
each quote (validate -> dedup -> quality-score) -> persist FareQuote +
QualityAssessment. Raw is never modified. Adapters never call the index engine.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.models import (
    FareQuote,
    QualityAssessment,
    RawObservation,
    Route,
    ScrapeJob,
    Source,
)
from collectors.core.models import Availability, FlightQuote
from statistical_engine.normalization import quote_payable_fare
from statistical_engine.outliers import OUTLIER_METHOD_VERSION, flag_outliers
from statistical_engine.quality import QUALITY_MODEL_VERSION, assess_quality, is_valid_observation

log = logging.getLogger(__name__)

PARSER_VERSION = "canonical-v1"


@dataclass
class JobSpec:
    """TRD §11 job key + timing."""

    source_id: str
    route_id: str
    departure_date: date
    lead_time: int
    collection_date: date
    started_at: datetime


@dataclass
class IngestResult:
    job_id: int | None
    status: str  # SUCCESS | PARTIAL | FAILED | SKIPPED
    received: int = 0
    stored: int = 0
    duplicates: int = 0
    invalid: int = 0
    sold_out: int = 0
    raw_only: int = 0  # REJECTED: could not map to canonical schema
    notes: list[str] = field(default_factory=list)


def _natural_key(q: FlightQuote) -> tuple:
    """Identity of an observation: same source, same flight/cabin/class, same
    collection instant. A second record with this exact key is a duplicate
    (re-collection or replay overlap), regardless of price fields."""
    return (
        q.source_id, q.origin, q.destination, q.departure_date, q.departure_time,
        q.airline, q.flight_number, q.cabin, q.fare_class, q.advance_days, q.collected_at,
    )


def ingest_quotes(
    session: Session,
    job_spec: JobSpec,
    quotes: list[FlightQuote],
    rejected_payloads: list[dict] | None = None,
    error_class: str | None = None,
) -> IngestResult:
    """Persist one collection job. Idempotent on the job key."""
    rejected_payloads = rejected_payloads or []

    existing = session.scalar(
        select(ScrapeJob).where(
            ScrapeJob.source_id == job_spec.source_id,
            ScrapeJob.route_id == job_spec.route_id,
            ScrapeJob.departure_date == job_spec.departure_date,
            ScrapeJob.lead_time == job_spec.lead_time,
            ScrapeJob.collection_date == job_spec.collection_date,
        )
    )
    if existing is not None:
        return IngestResult(existing.id, "SKIPPED", notes=["job key already ingested"])

    source = session.get(Source, job_spec.source_id)
    if source is None:
        raise ValueError(f"unknown source {job_spec.source_id}")
    route = session.get(Route, job_spec.route_id)
    if route is None:
        raise ValueError(f"unknown route {job_spec.route_id}")

    result = IngestResult(job_id=None, status="SUCCESS", received=len(quotes) + len(rejected_payloads))
    job = ScrapeJob(
        source_id=job_spec.source_id,
        route_id=job_spec.route_id,
        departure_date=job_spec.departure_date,
        lead_time=job_spec.lead_time,
        collection_date=job_spec.collection_date,
        started_at=job_spec.started_at,
        finished_at=job_spec.started_at,
        status="SUCCESS",
    )
    session.add(job)
    session.flush()  # job.id

    # REJECTED payloads: keep the raw record, no canonical row.
    for payload in rejected_payloads:
        session.add(RawObservation(
            job_id=job.id,
            source_id=job_spec.source_id,
            collected_at=job_spec.started_at,
            parser_version=PARSER_VERSION,
            request_meta={"outcome": "REJECTED"},
            payload=payload,
        ))
        result.raw_only += 1

    seen_keys: set[tuple] = set()
    for q in quotes:
        raw = RawObservation(
            job_id=job.id,
            source_id=q.source_id,
            collected_at=q.collected_at,
            parser_version=PARSER_VERSION,
            request_meta={},
            payload=q.model_dump(mode="json"),
        )
        session.add(raw)
        session.flush()

        k = _natural_key(q)
        if k in seen_keys:
            result.duplicates += 1
            continue  # raw record kept for audit; no second FareQuote row
        seen_keys.add(k)

        quality = assess_quality(q, source_reliability=source.reliability)
        route_matches = route.origin == q.origin and route.destination == q.destination

        if q.availability in (Availability.SOLD_OUT, Availability.MISSING):
            availability = q.availability.value
        elif not route_matches or not is_valid_observation(quality, q.availability):
            availability = Availability.INVALID.value
            result.invalid += 1
        else:
            availability = Availability.AVAILABLE.value

        quote_row = FareQuote(
            raw_observation_id=raw.id,
            source_id=q.source_id,
            route_id=job_spec.route_id,
            origin=q.origin,
            destination=q.destination,
            departure_date=q.departure_date,
            departure_time=q.departure_time,
            airline=q.airline,
            flight_number=q.flight_number,
            cabin=q.cabin,
            fare_class=q.fare_class,
            advance_days=q.advance_days,
            base_fare=q.base_fare,
            taxes=q.taxes,
            mandatory_fees=q.mandatory_fees,
            convenience_fee=q.convenience_fee,
            other_fee=q.other_fee,
            total_fare=q.total_fare,
            consumer_payable_fare=quote_payable_fare(q),
            currency=q.currency,
            availability=availability,
            stops=q.stops,
            collected_at=q.collected_at,
            collection_date=q.collected_at.date(),
            quality_score=quality.score,
        )
        if availability == Availability.SOLD_OUT.value:
            result.sold_out += 1
        session.add(quote_row)
        session.flush()
        result.stored += 1
        session.add(QualityAssessment(
            quote_id=quote_row.id,
            model_version=QUALITY_MODEL_VERSION,
            score=quality.score,
            components=quality.components,
        ))

    job.result_count = result.stored
    job.duplicate_count = result.duplicates
    if error_class:
        job.status = result.status = "FAILED"
        job.error_class = error_class
    elif result.invalid or result.raw_only:
        job.status = result.status = "PARTIAL"

    if job.status == "FAILED":
        source.last_failure_at = job_spec.started_at
    else:
        source.last_success_at = job_spec.started_at

    result.job_id = job.id
    log.info("ingest", extra={"job": job.id, "status": result.status, "received": result.received})
    return result


def flag_day_outliers(session: Session, collection_date: date) -> int:
    """MAD outlier pass over one collection day, grouped by (route, lead time).

    Also applies configurable business bounds. Flags only — never deletes.
    """
    settings = get_settings()
    rows = session.scalars(
        select(FareQuote).where(
            FareQuote.collection_date == collection_date,
            FareQuote.availability == Availability.AVAILABLE.value,
            FareQuote.consumer_payable_fare.is_not(None),
        )
    ).all()

    groups: dict[tuple[str, int], list[FareQuote]] = {}
    for row in rows:
        groups.setdefault((row.route_id, row.advance_days), []).append(row)

    flagged = 0
    for (route_id, lead), group in sorted(groups.items()):
        values = [r.consumer_payable_fare for r in group]
        flags = flag_outliers(values)
        for row, is_flagged, reason in zip(group, flags.flagged, flags.reasons):
            bound_reason = None
            if row.consumer_payable_fare is not None and (
                row.consumer_payable_fare < settings.min_payable_fare
                or row.consumer_payable_fare > settings.max_payable_fare
            ):
                bound_reason = "business_bounds"
            if bound_reason or is_flagged:
                row.outlier_flag = True
                row.outlier_reason = bound_reason or reason
                row.outlier_method_version = OUTLIER_METHOD_VERSION
                flagged += 1
    session.flush()
    return flagged
