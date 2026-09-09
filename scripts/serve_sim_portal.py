"""Local fare-portal simulator — the demo scraping target.

Serves a tiny site the scraper is ALLOWED to collect from (robots.txt
permits the flight-search paths, disallows /admin to prove the gate works):
  GET /robots.txt
  GET /health
  GET /flights/search?origin=DEL&destination=BOM&date=2026-09-15 -> server-rendered HTML rows
  GET /flights/search-data?... -> the same rows as JSON (for the JS page)
  GET /flights/search-js?...    -> an empty HTML shell whose inline script
                                   fetches search-data and injects the rows
                                   client-side — the JS-rendering demo target
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
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from collectors.sources.live_sim import (
    AIRLINE_BIAS,
    AIRLINE_ROUTES,
    DOW_MULTIPLIER,
    LEAD_MULTIPLIER,
    ROUTE_BASE,
)

IST = ZoneInfo("Asia/Kolkata")

app = FastAPI(title="sim-fare-portal")

ROBOTS = (
    "User-agent: *\nAllow: /flights/search\nAllow: /flights/search-js\n"
    "Allow: /flights/search-data\nDisallow: /admin\n"
)


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots() -> str:
    return ROBOTS


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ts": datetime.now(IST).isoformat()}


@app.get("/admin", response_class=PlainTextResponse)
def admin() -> PlainTextResponse:
    return PlainTextResponse("admin area — disallowed by robots.txt", status_code=403)


def search_payload(origin: str, destination: str, date_: str | None) -> tuple[int, str, list[dict]]:
    """Shared fare computation for the static, JSON and JS-rendered endpoints.

    Returns (http_status, kind, rows) with kind in {"rows", "captcha", "blocked"}.
    Same seed logic as before: occasional CAPTCHA (3%) / 403 (2%) so the
    compliance engine's pause-don't-bypass behavior stays demonstrable.
    """
    route_id = f"{origin}-{destination}"
    if route_id not in ROUTE_BASE:
        return 200, "rows", []
    rng = random.Random(f"{route_id}|{date_}|{datetime.now(IST):%H%M%S}")
    roll = rng.random()
    if roll < 0.03:
        return 200, "captcha", []
    if roll < 0.05:
        return 403, "blocked", []
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
        rows.append({
            "airline": airline,
            "price": f"{price:.2f}",
            "soldout": 1 if rng.random() < 0.1 else 0,
            "time": ["06:40", "09:15", "13:05"][slot],
            "flight": f"{airline}{100 + 37 * slot}",
            "origin": origin,
            "destination": destination,
        })
    return 200, "rows", rows


@app.get("/flights/search", response_class=HTMLResponse)
def search(origin: str = Query(..., min_length=3, max_length=3),
           destination: str = Query(..., min_length=3, max_length=3),
           date_: str = Query(None, alias="date")) -> HTMLResponse:
    status, kind, rows = search_payload(origin, destination, date_)
    if kind == "captcha":
        return HTMLResponse(
            "<html><body>please verify you are human: CAPTCHA</body></html>",
            status_code=200,
        )
    if kind == "blocked":
        return HTMLResponse("blocked", status_code=403)
    html_rows = "\n".join(
        f'<div class="fare-row" data-airline="{r["airline"]}" data-price="{r["price"]}" '
        f'data-soldout="{r["soldout"]}" data-time="{r["time"]}" data-flight="{r["flight"]}"> '
        f'{r["airline"]} {r["origin"]}-{r["destination"]} {r["time"]}</div>'
        for r in rows
    )
    return HTMLResponse("<html><body><h1>results</h1>" + html_rows + "</body></html>")


@app.get("/flights/search-data", response_class=JSONResponse)
def search_data(origin: str = Query(..., min_length=3, max_length=3),
                destination: str = Query(..., min_length=3, max_length=3),
                date_: str = Query(None, alias="date")) -> JSONResponse:
    """JSON fare rows — fetched by the /flights/search-js page's script."""
    status, kind, rows = search_payload(origin, destination, date_)
    if kind == "captcha":
        return JSONResponse({"captcha": True}, status_code=200)
    if kind == "blocked":
        return JSONResponse({"blocked": True}, status_code=403)
    return JSONResponse({"rows": rows})


@app.get("/flights/search-js", response_class=HTMLResponse)
def search_js(origin: str = Query(..., min_length=3, max_length=3),
              destination: str = Query(..., min_length=3, max_length=3),
              date_: str = Query(None, alias="date")) -> HTMLResponse:
    """JS-rendered demo target: the shell contains NO fares server-side —
    the browser's script fetches /flights/search-data and injects the rows.
    A static httpx fetch of this URL sees only the empty shell; that is the
    point (PS 26056: handle JavaScript-rendered pages)."""
    return HTMLResponse(
        "<html><body><h1>results</h1><div id='results'></div>\n"
        "<script>\n"
        f"fetch('/flights/search-data?origin={origin}&destination={destination}&date={date_ or ''}')\n"
        "  .then(function (r) { return r.json(); })\n"
        "  .then(function (data) {\n"
        "    document.getElementById('results').innerHTML = data.rows.map(function (r) {\n"
        "      return '<div class=\"fare-row\" data-airline=\"' + r.airline + '\" "
        "data-price=\"' + r.price + '\" data-soldout=\"' + r.soldout + '\" "
        "data-time=\"' + r.time + '\" data-flight=\"' + r.flight + '\"> ' +\n"
        "        r.airline + ' ' + r.origin + '-' + r.destination + ' ' + r.time + '</div>';\n"
        "    }).join('\\n');\n"
        "  });\n"
        "</script></body></html>"
    )


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8811
    print(f"sim fare portal on http://127.0.0.1:{port} (robots allows the flight-search paths)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
