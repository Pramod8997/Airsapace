"""API tests against the seeded in-memory DB (TRD §15: API → DB)."""
from __future__ import annotations


def test_health(api_client):
    r = api_client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_security_headers_present(api_client):
    r = api_client.get("/health")
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Frame-Options"] == "DENY"
    assert "default-src 'none'" in r.headers["Content-Security-Policy"]


def test_index_latest(api_client):
    r = api_client.get("/api/v1/index/latest")
    assert r.status_code == 200
    body = r.json()
    assert body["base"] == 100
    assert body["index"] > 0
    assert body["methodology_version"] == "APIX-v1.0"
    assert body["data_mode"] in ("LIVE", "DEMO", "REPLAY")
    assert "daily_change_pct" in body and "calculation_run_id" in body


def test_index_history_daily_and_weekly(api_client):
    daily = api_client.get("/api/v1/index/history").json()
    assert daily["frequency"] == "DAILY"
    assert len(daily["points"]) >= 7

    weekly = api_client.get("/api/v1/index/history?frequency=WEEKLY").json()
    assert len(weekly["points"]) < len(daily["points"])
    assert weekly["points"][0]["value"] > 0


def test_index_history_lead_time_and_route_filter(api_client):
    r = api_client.get("/api/v1/index/history?lead_time=1&route_id=DEL-BOM").json()
    assert r["lead_time"] == 1 and r["route_id"] == "DEL-BOM"
    assert r["points"]

    bad = api_client.get("/api/v1/index/history?route_id=XXX-YYY")
    assert bad.status_code == 404


def test_index_route_endpoint(api_client):
    r = api_client.get("/api/v1/index/route/DEL-BLR")
    assert r.status_code == 200
    assert all(p["route_id"] == "DEL-BLR" for p in r.json()["points"])


def test_fares_pagination_and_filters(api_client):
    r = api_client.get("/api/v1/fares?page_size=5")
    body = r.json()
    assert body["page_size"] == 5 and len(body["items"]) <= 5
    assert body["total"] > 5

    r2 = api_client.get("/api/v1/fares?origin=DEL&destination=BOM&lead_time=1&availability=AVAILABLE")
    for item in r2.json()["items"]:
        assert item["origin"] == "DEL" and item["destination"] == "BOM"
        assert item["advance_days"] == 1 and item["availability"] == "AVAILABLE"

    assert api_client.get("/api/v1/fares?page_size=9999").status_code == 422  # max page size enforced
    assert api_client.get("/api/v1/fares?availability=BOGUS").status_code == 422


def test_fares_csv_export(api_client):
    r = api_client.get("/api/v1/fares.csv?limit=10")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert len(lines) == 11  # header + 10 rows


def test_registries(api_client):
    routes = api_client.get("/api/v1/routes").json()
    assert len(routes) == 10
    assert {r["id"] for r in routes} >= {"DEL-BOM", "BOM-DEL", "MAA-DEL"}
    assert abs(sum(r["weight"] for r in routes) - 1.0) < 1e-6

    airlines = api_client.get("/api/v1/airlines").json()
    assert {"6E", "AI"} <= {a["iata"] for a in airlines}

    sources = api_client.get("/api/v1/sources").json()
    assert len(sources) == 10  # 5 replay + 5 simulated live
    sim = [s for s in sources if s["id"].startswith("sim-")]
    assert len(sim) == 5 and all(s["policy_status"] == "SIMULATED" for s in sim)


def test_quality_metrics(api_client):
    body = api_client.get("/api/v1/quality?window_days=365").json()
    assert body["total_observations"] > 0
    assert 0 <= body["completeness"] <= 1
    assert body["imputation_rate"] == 0.0  # documented policy: no imputation
    assert len(body["source_health"]) == 2  # the two sources present in test data


def test_methodology(api_client):
    body = api_client.get("/api/v1/methodology").json()
    assert body["version"] == "APIX-v1.0"
    assert "Σ(w_i" in body["formula"]
    assert body["base_value"] == 100.0
    assert body["lead_times"] == [1, 7, 15, 30, 45]
    assert len(body["basket_routes"]) == 10
    assert body["missing_data_policy"]


def test_backtests_list(api_client):
    body = api_client.get("/api/v1/backtests").json()
    assert isinstance(body, list)
    if body:
        metrics = body[0]["metrics"]
        assert {"mae", "rmse", "mape", "correlation", "trend_direction_accuracy"} <= set(metrics)


def test_rate_limit_enforced():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from backend.app.middleware import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limit="3/minute")

    @app.get("/x")
    def x():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 200
    assert client.get("/x").status_code == 429
