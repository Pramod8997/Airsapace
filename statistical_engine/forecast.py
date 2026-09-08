"""Holt's linear exponential smoothing forecast for the APIx national series.

Forecast — model extrapolation, NOT an observed price. Forecasts are produced by
an auxiliary model that NEVER participates in the official index calculation
(CLAUDE.md invariant: the index engine is deterministic; forecasting is a
read-only layer on top of published IndexValues). Uncertainty is real: results
are shown with an explicit disclaimer on the API and dashboard.

FORECAST_MODEL_VERSION pins the method; any change to the grid, initialization
or error metric bumps it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable

FORECAST_MODEL_VERSION = "FORECAST-v1"
FORECAST_DISCLAIMER = (
    "Forecast — model extrapolation, not an observed price. "
    "Not used in index calculation."
)

_GRID = [round(0.1 * k, 1) for k in range(1, 10)]  # 0.1..0.9 — fixed, no randomness
_MIN_POINTS = 20
_DEFAULT_VALIDATE = 14


@dataclass
class ForecastResult:
    model_version: str
    fitted: list[tuple[date, float]]  # one-step in-sample fit (chart overlay)
    forecast: list[tuple[date, float]]  # h points after the last observed day
    horizon_days: int
    params: tuple[float, float]  # (alpha, beta)
    in_sample_rmse: float
    holdout_rmse: float | None
    method: str = "Holt linear exponential smoothing (grid-searched)"


def holt_forecast(points: list[tuple[date, float]], horizon_days: int = 7,
                  validate: int = _DEFAULT_VALIDATE) -> ForecastResult:
    """Fit Holt's linear exponential smoothing on daily (date, value) points.

    Alpha/beta are grid-searched over {0.1..0.9 step 0.1} minimizing in-sample
    one-step-ahead MSE; the last `validate` points are held out to report an
    honest holdout RMSE (model refit on the full series for the final forecast).

    Refuses fewer than 20 points (ValueError).
    """
    pts = sorted(points, key=lambda p: p[0])
    if len(pts) < _MIN_POINTS:
        raise ValueError(
            f"need at least {_MIN_POINTS} index points for a forecast, got {len(pts)}"
        )
    if horizon_days < 1:
        raise ValueError(f"horizon_days must be >= 1, got {horizon_days}")
    values = [p[1] for p in pts]

    def fit(vs: list[float]) -> tuple[float, float, list[float]]:
        """Best (alpha, beta) by one-step MSE; return (alpha, beta, fitted)."""
        best: tuple[float, float, list[float]] | None = None
        best_mse = math.inf
        for alpha in _GRID:
            for beta in _GRID:
                fitted, sq_errors = _holt_fit(vs, alpha, beta)
                mse = sum(sq_errors) / len(sq_errors)
                if mse < best_mse:
                    best_mse, best = mse, (alpha, beta, fitted)
        assert best is not None  # 81 combos, always set
        return best

    alpha, beta, fitted = fit(values)
    in_rmse = _rmse(values, fitted)

    holdout_rmse: float | None = None
    split = len(values) - validate
    if split >= _MIN_POINTS:
        _, _, hold_fitted = fit(values[:split])
        holdout_rmse = _rmse(values[split:], hold_fitted[-validate:])

    level, trend = _holt_state(values, alpha, beta)
    last_date = pts[-1][0]
    forecast = [
        (last_date + timedelta(days=h), round(level + h * trend, 4))
        for h in range(1, horizon_days + 1)
    ]
    return ForecastResult(
        model_version=FORECAST_MODEL_VERSION,
        fitted=[(pts[i][0], round(f, 4)) for i, f in enumerate(fitted)],
        forecast=forecast,
        horizon_days=horizon_days,
        params=(alpha, beta),
        in_sample_rmse=round(in_rmse, 4),
        holdout_rmse=round(holdout_rmse, 4) if holdout_rmse is not None else None,
    )


def _holt_fit(values: list[float], alpha: float, beta: float) -> tuple[list[float], list[float]]:
    """One-step-ahead fits; init level = first value, trend = first difference."""
    fitted: list[float] = []
    errors: list[float] = []
    level = values[0]
    trend = values[1] - values[0] if len(values) > 1 else 0.0
    fitted.append(level)  # t=0 forecast is the initial level itself
    for t in range(1, len(values)):
        pred = level + trend
        fitted.append(pred)
        errors.append(values[t] - pred)
        prev_level = level
        level = alpha * values[t] + (1 - alpha) * pred
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return fitted, [e * e for e in errors]


def _holt_state(values: list[float], alpha: float, beta: float) -> tuple[float, float]:
    """Run the recursion to the end; return final (level, trend)."""
    level = values[0]
    trend = values[1] - values[0] if len(values) > 1 else 0.0
    for t in range(1, len(values)):
        pred = level + trend
        prev_level = level
        level = alpha * values[t] + (1 - alpha) * pred
        trend = beta * (level - prev_level) + (1 - beta) * trend
    return level, trend


def _rmse(actual: Iterable[float], pred: Iterable[float]) -> float:
    errors = [a - p for a, p in zip(actual, pred)]
    return math.sqrt(sum(e * e for e in errors) / len(errors)) if errors else 0.0


if __name__ == "__main__":  # pragma: no cover — quick self-check
    start = date(2026, 1, 1)
    line = [(start + timedelta(days=t), 100.0 + 2.0 * t) for t in range(30)]
    res = holt_forecast(line, horizon_days=5)
    for d, v in res.forecast:
        expected = 100.0 + 2.0 * ((d - start).days)
        assert abs(v - expected) < 0.5, (v, expected)
    print(res.params, res.in_sample_rmse, res.forecast[-1])
