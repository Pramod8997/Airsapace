"""Local fare-portal simulator — the demo scraping target.

Serves a tiny site the scraper is ALLOWED to collect from (robots.txt
permits /flights/search, disallows /admin to prove the gate works):
  GET /robots.txt
  GET /health
  GET /flights/search?origin=DEL&destination=BOM&date=2026-09-15 -> HTML rows
Occasionally returns 403 or a CAPTCHA page (deterministic by seed) so the
engine's pause-don't-bypass behavior is demonstrable.

Run: .venv/bin/python scripts/serve_sim_portal.py [port]
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from collectors.sources.live_sim import (
    AIRLINE_BIAS,
    AIRLINE_ROUTES,
    DOW_MULTIPLIER,
    LEAD_MULTIPLIER,
    ROUTE_BASE,
)

IST = ZoneInfo("Asia/Kolkata")

app = FastAPI(title="sim-fare-portal")

ROBOTS = "User-agent: *\nAllow: /flights/search\nDisallow: /admin\n"


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return ROBOTS


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ts": datetime.now(IST).isoformat()}


@app.get("/admin", response_class=PlainTextResponse)
def admin() -> PlainTextResponse:
    return PlainTextResponse("admin area — disallowed by robots.txt", status_code=403)


@app.get("/flights/search", response_class=HTMLResponse)
def search(origin: str = Query(..., min_length=3, max_length=3),
           destination: str = Query(..., min_length=3, max_length=3),
           date_: str = Query(None, alias="date")) -> HTMLResponse:
    route_id = f"{origin}-{destination}"
    if route_id not in ROUTE_BASE:
        return HTMLResponse("<html><body>no results</body></html>")
    rng = random.Random(f"{route_id}|{date_}|{datetime.now(IST):%H%M%S}")
    roll = rng.random()
    if roll < 0.03:
        return HTMLResponse(
            "<html><body>please verify you are human: CAPTCHA</body></html>",
            status_code=200,
        )
    if roll < 0.05:
        return HTMLResponse("blocked", status_code=403)
    dep = date.fromisoformat(date_) if date_ else date.today()
    airlines = [a for a in AIRLINE_ROUTES if route_id in AIRLINE_ROUTES[a]]
    rows = []
    for slot, airline in enumerate(airlines[:3]):
        price = (
            ROUTE_BASE[route_id]
            * LEAD_MULTIPLIER.get(7, 1)
            * DOW_MULTIPLIER[dep.weekday()]
            * AIRLINE_BIAS.get(airline, 1)
            * (1 + 0.04 * slot)
        )
        price = max(price, 900)
        price = round(price * 2.718 ** rng.gauss(0, 0.05), 0)
        sold = 1 if rng.random() < 0.1 else 0
        dep_time = ["06:40", "09:15", "13:05"][slot]
        rows.append(
            f'<div class="fare-row" data-airline="{airline}" data-price="{price:.2f}" '
            f'data-soldout="{sold}" data-time="{dep_time}" data-flight="{airline}{100 + 37 * slot}"> '
            f"{airline} {origin}-{destination} {dep_time}</div>"
        )
    return HTMLResponse(
        "<html><body><h1>results</h1>" + "\n".join(rows) + "</body></html>"
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8811
    print(f"sim fare portal on http://127.0.0.1:{port} (robots allows /flights/search)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
