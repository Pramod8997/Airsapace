"""Index calculation runner: DB -> pure engine -> versioned IndexValues.

Every run is recorded (CalculationRun) with a SHA-256 input fingerprint, so any
index value can be traced to methodology version, basket/weight versions, run id
and exact calculation input (FR-18, SECURITY.md §16, TRD §9.4).
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    BacktestRun,
    CalculationRun,
    FareQuote,
    IndexBasket,
    IndexValue,
    IndexWeight,
    MethodologyVersion,
)
from statistical_engine.aggregation import QuotePriceRow, base_period_prices, build_spec_prices
from statistical_engine.backtest import SeriesPoint, compute_metrics
from statistical_engine.basket import Basket
from statistical_engine.index import compute_index_series, input_fingerprint

log = logging.getLogger(__name__)

PROCESSOR_VERSION = "processor-1.0.0"


def load_basket(session: Session, methodology: MethodologyVersion) -> Basket:
    basket_row = session.scalar(
        select(IndexBasket)
        .where(IndexBasket.methodology_version == methodology.version)
        .order_by(IndexBasket.id.desc())
    )
    if basket_row is None:
        raise ValueError(f"no basket for methodology {methodology.version}")
    weight_rows = session.scalars(select(IndexWeight).where(IndexWeight.basket_id == basket_row.id))
    basket = Basket(
        basket_version=basket_row.basket_version,
        weight_version=basket_row.weight_version,
        weight_source=basket_row.weight_source,
        base_period_start=methodology.base_period_start,
        base_period_end=methodology.base_period_end,
        weights={(w.route_id, w.lead_time): w.weight for w in weight_rows},
    )
    basket.validate()
    return basket


def run_index_calculation(
    session: Session,
    methodology_version: str | None = None,
) -> CalculationRun:
    """Compute and persist all index cuts. Idempotent: existing (date, route,
    lead, methodology, basket) values are never duplicated or overwritten."""
    if methodology_version:
        methodology = session.get(MethodologyVersion, methodology_version)
        if methodology is None:
            raise ValueError(f"unknown methodology {methodology_version}")
    else:
        methodology = session.scalar(
            select(MethodologyVersion)
            .where(MethodologyVersion.published)
            .order_by(MethodologyVersion.created_at.desc())
        )
        if methodology is None:
            raise ValueError("no published methodology version")

    basket = load_basket(session, methodology)

    rows = session.execute(
        select(
            FareQuote.collection_date,
            FareQuote.route_id,
            FareQuote.advance_days,
            FareQuote.consumer_payable_fare,
            FareQuote.availability,
            FareQuote.outlier_flag,
        )
    ).all()
    spec_prices = build_spec_prices(QuotePriceRow(*r) for r in rows)
    base_prices = base_period_prices(
        spec_prices, methodology.base_period_start, methodology.base_period_end
    )
    if not base_prices:
        raise ValueError("no observations in base period — cannot compute index")

    days = sorted({d for (d, _, _) in spec_prices})
    points = compute_index_series(spec_prices, base_prices, basket, days)

    run = CalculationRun(
        run_type="INDEX",
        processor_version=PROCESSOR_VERSION,
        methodology_version=methodology.version,
        basket_version=basket.basket_version,
        weight_version=basket.weight_version,
        input_hash=input_fingerprint(spec_prices, base_prices, basket),
        observation_count=len(rows),
        status="SUCCESS",
    )
    session.add(run)
    session.flush()

    existing = {
        (v.index_date, v.route_id, v.lead_time, v.methodology_version, v.basket_version): v.id
        for v in session.scalars(
            select(IndexValue).where(IndexValue.methodology_version == methodology.version)
        )
    }
    added = 0
    for p in points:
        key = (p.index_date, p.route_id, p.lead_time, methodology.version, basket.basket_version)
        if key in existing:
            continue  # immutable: never overwrite a published value
        session.add(IndexValue(
            index_date=p.index_date,
            route_id=p.route_id,
            lead_time=p.lead_time,
            value=p.value,
            base=100.0,
            methodology_version=methodology.version,
            basket_version=basket.basket_version,
            weight_version=basket.weight_version,
            calculation_run_id=run.id,
        ))
        added += 1

    log.info("index_run", extra={
        "run_id": run.id, "points": len(points), "added": added,
        "methodology": methodology.version, "input_hash": run.input_hash,
    })
    return run


def national_series(session: Session, methodology_version: str) -> list[SeriesPoint]:
    """APIx combined (national) series from persisted IndexValues."""
    values = session.scalars(
        select(IndexValue).where(
            IndexValue.methodology_version == methodology_version,
            IndexValue.route_id.is_(None),
            IndexValue.lead_time.is_(None),
        ).order_by(IndexValue.index_date)
    ).all()
    return [SeriesPoint(v.index_date, v.value) for v in values]


def run_backtest(
    session: Session,
    reference: list[SeriesPoint],
    reference_name: str,
    period_start: date,
    period_end: date,
    methodology_version: str | None = None,
    actual_series: list[SeriesPoint] | None = None,
) -> BacktestRun:
    """Compare the national combined APIx against a reference series.

    actual_series: pre-resampled APIx points (e.g. monthly means) to compare
    against a monthly reference; defaults to the daily national series.

    NOTE (statistical honesty): correlation validates co-movement only; it does
    not establish methodological equivalence with the reference producer.
    """
    if methodology_version is None:
        methodology_version = session.scalar(
            select(MethodologyVersion.version)
            .where(MethodologyVersion.published)
            .order_by(MethodologyVersion.created_at.desc())
        )
    actual = actual_series or national_series(session, methodology_version)
    actual = [p for p in actual if period_start <= p.date <= period_end]
    metrics = compute_metrics(actual, reference)

    run = CalculationRun(
        run_type="BACKTEST",
        processor_version=PROCESSOR_VERSION,
        methodology_version=methodology_version,
        basket_version="-",
        weight_version="-",
        observation_count=metrics.n_points,
        status="SUCCESS",
    )
    session.add(run)
    session.flush()

    bt = BacktestRun(
        calculation_run_id=run.id,
        period_start=period_start,
        period_end=period_end,
        methodology_version=methodology_version,
        basket_version="-",
        reference_series=reference_name,
        metrics=metrics.as_dict(),
    )
    session.add(bt)
    session.flush()
    log.info("backtest_run", extra={"id": bt.id, **metrics.as_dict()})
    return bt


def aggregate_frequency(points: list[tuple[date, float]], frequency: str) -> list[tuple[date, float]]:
    """DAILY as-is; WEEKLY/MONTHLY = mean of daily values per ISO week / month."""
    if frequency == "DAILY":
        return sorted(points)
    buckets: dict[date, list[float]] = defaultdict(list)
    for day, value in points:
        if frequency == "WEEKLY":
            key = day - timedelta(days=day.weekday())
        elif frequency == "MONTHLY":
            key = day.replace(day=1)
        else:
            raise ValueError(f"unsupported frequency {frequency}")
        buckets[key].append(value)
    return sorted((k, round(sum(v) / len(v), 4)) for k, v in buckets.items())
