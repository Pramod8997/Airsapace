"""Forecast module tests: Holt linear extrapolation, determinism, API contract.

Forecast — model extrapolation, not an observed price, never part of the index
calculation (CLAUDE.md invariant; disclaimer surfaced by the API).
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from statistical_engine.forecast import FORECAST_MODEL_VERSION, holt_forecast

START = date(2026, 1, 1)


def _linear(n: int, intercept: float = 100.0, slope: float = 2.0):
    return [(START + timedelta(days=t), intercept + slope * t) for t in range(n)]


def _constant(n: int, value: float = 120.0):
    return [(START + timedelta(days=t), value) for t in range(n)]


def test_linear_series_forecast_continues_the_line():
    n, h = 40, 7
    res = holt_forecast(_linear(n), horizon_days=h)
    for d, v in res.forecast:
        t = (d - START).days
        assert abs(v - (100.0 + 2.0 * t)) < 1e-2
    assert res.model_version == FORECAST_MODEL_VERSION
    assert res.horizon_days == h
    assert 0.1 <= res.params[0] <= 0.9 and 0.1 <= res.params[1] <= 0.9
    assert res.holdout_rmse is not None


def test_constant_series_flat_forecast():
    res = holt_forecast(_constant(30), horizon_days=5)
    values = [v for _, v in res.forecast]
    assert all(abs(v - 120.0) < 1e-6 for v in values)
    assert abs(values[-1] - values[0]) < 1e-6  # trend ~ 0
    assert res.in_sample_rmse < 1e-6


def test_too_few_points_raises():
    with pytest.raises(ValueError, match="20"):
        holt_forecast(_linear(19))


def test_determinism_same_input_identical_output():
    pts = [(START + timedelta(days=t), 100.0 + 2.0 * t + (t % 3) * 0.5) for t in range(30)]
    a, b = holt_forecast(pts), holt_forecast(pts)
    assert a == b  # dataclass equality: params, fitted, forecast, metrics all equal


# ---------------------------------------------------------------- API


def test_forecast_endpoint(api_client):
    r = api_client.get("/api/v1/forecast")
    assert r.status_code == 200
    body = r.json()
    assert body["model_version"] == FORECAST_MODEL_VERSION
    assert len(body["forecast"]) == body["horizon_days"] == 7
    assert {"alpha", "beta"} <= set(body["params"])
    assert "Forecast" in body["disclaimer"] and "not an observed price" in body["disclaimer"]
    assert body["in_sample_rmse"] >= 0 and body["history"]
    assert body["fitted"] and body["method"].startswith("Holt")


def test_forecast_endpoint_horizon_validation(api_client):
    assert api_client.get("/api/v1/forecast?horizon_days=99").status_code == 422
    assert api_client.get("/api/v1/forecast?horizon_days=0").status_code == 422
