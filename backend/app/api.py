"""REST API v1 — FR-16 endpoints. All read-only GETs; auth lands with the first
write endpoint (deferred per CLAUDE.md §6 priority order).
"""
from __future__ import annotations

import csv
import io
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from backend.app.config import get_settings
from backend.app.db import get_session_factory
from backend.app.models import (
    Airline,
    FareQuote,
    IndexValue,
    MethodologyVersion,
    Route,
    ScrapeJob,
    Source,
)
from backend.app.schemas import (
    AirlineOut,
    BacktestOut,
    FareOut,
    IndexHistoryOut,
    IndexLatestOut,
    IndexPointOut,
    MethodologyOut,
    PaginatedFares,
    QualityOut,
    RouteOut,
    SourceHealthOut,
    SourceOut,
)
from backend.app.services.index_runner import aggregate_frequency

router = APIRouter(prefix="/api/v1", tags=["apix"])

MAX_PAGE_SIZE = 500


def get_db():
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


DbDep = Depends(get_db)


def _latest_methodology(db: Session) -> MethodologyVersion:
    m = db.scalar(
        select(MethodologyVersion)
        .where(MethodologyVersion.published)
        .order_by(MethodologyVersion.created_at.desc())
    )
    if m is None:
        raise HTTPException(503, "no methodology published yet — run scripts/seed.py")
    return m


# ---------------------------------------------------------------- index


def _series(
    db: Session,
    methodology_version: str,
    route_id: str | None,
    lead_time: int | None,
    start: date | None,
    end: date | None,
) -> list[IndexValue]:
    q = select(IndexValue).where(
        IndexValue.methodology_version == methodology_version,
        IndexValue.route_id == route_id,
        IndexValue.lead_time == lead_time,
    ).order_by(IndexValue.index_date)
    if start:
        q = q.where(IndexValue.index_date >= start)
    if end:
        q = q.where(IndexValue.index_date <= end)
    return list(db.scalars(q))


@router.get("/index/latest", response_model=IndexLatestOut)
def index_latest(db: Session = DbDep):
    m = _latest_methodology(db)
    series = _series(db, m.version, None, None, None, None)
    if not series:
        raise HTTPException(404, "no index values yet — run scripts/seed.py")
    latest = series[-1]

    def change_pct(days_back: int) -> float | None:
        target = latest.index_date - timedelta(days=days_back)
        prior = [v for v in series if v.index_date <= target]
        if not prior or prior[-1].value == 0:
            return None
        return round((latest.value / prior[-1].value - 1) * 100, 2)

    return IndexLatestOut(
        index=latest.value,
        base=latest.base,
        index_date=latest.index_date,
        daily_change_pct=change_pct(1),
        weekly_change_pct=change_pct(7),
        monthly_change_pct=change_pct(30),
        methodology_version=latest.methodology_version,
        basket_version=latest.basket_version,
        weight_version=latest.weight_version,
        calculation_run_id=latest.calculation_run_id,
        data_mode=get_settings().data_mode,
    )


@router.get("/index/history", response_model=IndexHistoryOut)
def index_history(
    route_id: str | None = Query(None, pattern=r"^[A-Z]{3}-[A-Z]{3}$"),
    lead_time: int | None = Query(None, ge=1, le=365),
    frequency: str = Query("DAILY", pattern="^(DAILY|WEEKLY|MONTHLY)$"),
    _from: date | None = Query(None, alias="from"),
    to: date | None = None,
    db: Session = DbDep,
):
    m = _latest_methodology(db)
    if route_id and db.get(Route, route_id) is None:
        raise HTTPException(404, f"unknown route {route_id}")
    series = _series(db, m.version, route_id, lead_time, _from, to)
    points = aggregate_frequency([(v.index_date, v.value) for v in series], frequency)
    return IndexHistoryOut(
        route_id=route_id,
        lead_time=lead_time,
        frequency=frequency,
        methodology_version=m.version,
        points=[IndexPointOut(index_date=d, value=v, route_id=route_id, lead_time=lead_time)
                for d, v in points],
    )


@router.get("/index/route/{route_id}", response_model=IndexHistoryOut)
def index_route(route_id: str, frequency: str = Query("DAILY", pattern="^(DAILY|WEEKLY|MONTHLY)$"),
                db: Session = DbDep):
    if db.get(Route, route_id) is None:
        raise HTTPException(404, f"unknown route {route_id}")
    m = _latest_methodology(db)
    series = _series(db, m.version, route_id, None, None, None)
    points = aggregate_frequency([(v.index_date, v.value) for v in series], frequency)
    return IndexHistoryOut(
        route_id=route_id, lead_time=None, frequency=frequency,
        methodology_version=m.version,
        points=[IndexPointOut(index_date=d, value=v, route_id=route_id) for d, v in points],
    )


# ---------------------------------------------------------------- fares


@router.get("/fares", response_model=PaginatedFares)
def fares(
    origin: str | None = Query(None, min_length=3, max_length=3),
    destination: str | None = Query(None, min_length=3, max_length=3),
    date: date | None = None,
    source: str | None = Query(None, max_length=60),
    airline: str | None = Query(None, min_length=2, max_length=3),
    lead_time: int | None = Query(None, ge=0, le=365),
    availability: str | None = Query(None, pattern="^(AVAILABLE|SOLD_OUT|MISSING|INVALID|IMPUTED|REJECTED)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=MAX_PAGE_SIZE),
    db: Session = DbDep,
):
    q = select(FareQuote)
    if origin:
        q = q.where(FareQuote.origin == origin.upper())
    if destination:
        q = q.where(FareQuote.destination == destination.upper())
    if date:
        q = q.where(FareQuote.departure_date == date)
    if source:
        q = q.where(FareQuote.source_id == source)
    if airline:
        q = q.where(FareQuote.airline == airline.upper())
    if lead_time is not None:
        q = q.where(FareQuote.advance_days == lead_time)
    if availability:
        q = q.where(FareQuote.availability == availability)

    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(
        q.order_by(FareQuote.collected_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return PaginatedFares(
        page=page, page_size=page_size, total=total or 0,
        items=[FareOut.model_validate(r, from_attributes=True) for r in rows],
    )


@router.get("/fares.csv", response_class=PlainTextResponse, tags=["export"])
def fares_csv(db: Session = DbDep, limit: int = Query(1000, ge=1, le=MAX_PAGE_SIZE * 10)):
    """CSV export (FR-17). Capped; use filters + pagination for full extracts."""
    rows = db.scalars(select(FareQuote).order_by(FareQuote.collected_at.desc()).limit(limit)).all()
    buf = io.StringIO()
    if rows:
        writer = csv.DictWriter(buf, fieldnames=list(FareOut.model_fields))
        writer.writeheader()
        for r in rows:
            writer.writerow(FareOut.model_validate(r, from_attributes=True).model_dump(mode="json"))
    return PlainTextResponse(buf.getvalue(), media_type="text/csv")


# ---------------------------------------------------------------- registries


@router.get("/routes", response_model=list[RouteOut])
def routes(db: Session = DbDep):
    return [RouteOut.model_validate(r, from_attributes=True)
            for r in db.scalars(select(Route).order_by(Route.id))]


@router.get("/airlines", response_model=list[AirlineOut])
def airlines(db: Session = DbDep):
    return [AirlineOut.model_validate(a, from_attributes=True)
            for a in db.scalars(select(Airline).order_by(Airline.iata))]


@router.get("/sources", response_model=list[SourceOut])
def sources(db: Session = DbDep):
    return [SourceOut.model_validate(s, from_attributes=True)
            for s in db.scalars(select(Source).order_by(Source.id))]


# ---------------------------------------------------------------- quality


@router.get("/quality", response_model=QualityOut)
def quality(window_days: int = Query(30, ge=1, le=365), db: Session = DbDep):
    since = date.today() - timedelta(days=window_days)
    counts = dict(
        db.execute(
            select(FareQuote.availability, func.count())
            .where(FareQuote.collection_date >= since)
            .group_by(FareQuote.availability)
        ).all()
    )
    total = sum(counts.values())
    duplicates = db.scalar(
        select(func.coalesce(func.sum(ScrapeJob.duplicate_count), 0))
        .where(ScrapeJob.collection_date >= since)
    ) or 0
    outliers = db.scalar(
        select(func.count())
        .select_from(FareQuote)
        .where(FareQuote.collection_date >= since, FareQuote.outlier_flag)
    ) or 0

    per_source = db.execute(
        select(
            FareQuote.source_id,
            func.count(),
            func.sum(case((FareQuote.availability == "AVAILABLE", 1), else_=0)),
            func.max(Source.last_success_at),
            func.max(Source.last_failure_at),
        )
        .join(Source, Source.id == FareQuote.source_id)
        .where(FareQuote.collection_date >= since)
        .group_by(FareQuote.source_id)
    ).all()

    invalid_n = counts.get("INVALID", 0) + counts.get("REJECTED", 0)
    available_n = counts.get("AVAILABLE", 0)
    return QualityOut(
        window_days=window_days,
        total_observations=total,
        available=available_n,
        sold_out=counts.get("SOLD_OUT", 0),
        invalid=counts.get("INVALID", 0),
        rejected=counts.get("REJECTED", 0),
        completeness=round(available_n / total, 4) if total else 0.0,
        duplicate_count=duplicates,
        duplicate_rate=round(duplicates / (total + duplicates), 4) if total + duplicates else 0.0,
        rejection_rate=round(invalid_n / total, 4) if total else 0.0,
        imputation_rate=0.0,  # no imputation in APIX-v1.0 (documented policy)
        outlier_rate=round(outliers / total, 4) if total else 0.0,
        source_health=[
            SourceHealthOut(
                source_id=sid,
                observations=n,
                availability_rate=round(available / n, 4) if n else 0.0,
                last_success_at=last_ok,
                last_failure_at=last_fail,
            )
            for sid, n, available, last_ok, last_fail in per_source
        ],
    )


# ---------------------------------------------------------------- methodology


@router.get("/methodology", response_model=MethodologyOut)
def methodology(db: Session = DbDep):
    from backend.app.models import IndexBasket

    m = _latest_methodology(db)
    basket = db.scalar(
        select(IndexBasket)
        .where(IndexBasket.methodology_version == m.version)
        .order_by(IndexBasket.id.desc())
    )
    basket_routes = [RouteOut.model_validate(r, from_attributes=True)
                     for r in db.scalars(select(Route).where(Route.active).order_by(Route.id))]
    return MethodologyOut(
        version=m.version,
        name=m.name,
        description=m.description,
        base_period_start=m.base_period_start,
        base_period_end=m.base_period_end,
        base_value=100.0,
        formula="I_t = [ Σ(w_i × P_i,t / P_i,0) / Σw_i ] × 100",
        outlier_policy=m.outlier_policy,
        missing_data_policy=m.missing_data_policy,
        quality_model_version=m.quality_model_version,
        outlier_method_version=m.outlier_method_version,
        basket_version=basket.basket_version if basket else "",
        weight_version=basket.weight_version if basket else "",
        weight_source=basket.weight_source if basket else "",
        published=m.published,
        lead_times=[1, 7, 15, 30, 45],
        basket_routes=basket_routes,
    )


# ---------------------------------------------------------------- backtests


@router.get("/backtests", response_model=list[BacktestOut])
def backtests(db: Session = DbDep):
    from backend.app.models import BacktestRun

    runs = db.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())).all()
    return [BacktestOut(
        id=b.id, period_start=b.period_start, period_end=b.period_end,
        methodology_version=b.methodology_version, basket_version=b.basket_version,
        reference_series=b.reference_series, metrics=b.metrics, created_at=b.created_at,
    ) for b in runs]
