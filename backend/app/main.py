"""FastAPI application entrypoint.

Run from the repo root:
    .venv/bin/uvicorn backend.app.main:app --reload
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.app.api import router
from backend.app.config import get_settings, setup_logging
from backend.app.db import create_all, get_engine
from backend.app.middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from backend.app.schemas import HealthOut


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)

    app = FastAPI(
        title="AirStat India — APIx",
        description=(
            "Real-time Airfare Price Index (SIH 2026, PS 26056, MoSPI/DIID). "
            "Analytical prototype — not official CPI. "
            f"Data mode: {settings.data_mode}."
        ),
        version="0.1.0",
    )

    # CORS: empty allowlist = same-origin only (SECURITY.md §12)
    if settings.cors_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origin_list,
            allow_methods=["GET"],
            allow_headers=[],
        )
    app.add_middleware(RateLimitMiddleware, limit=settings.api_rate_limit)
    app.add_middleware(SecurityHeadersMiddleware)

    app.include_router(router)

    @app.get("/health", response_model=HealthOut, tags=["meta"])
    def health() -> HealthOut:
        db_ok = True
        try:
            with get_engine().connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception:
            db_ok = False
        return HealthOut(
            status="ok" if db_ok else "degraded",
            data_mode=settings.data_mode,
            app_env=settings.app_env,
            database="ok" if db_ok else "error",
        )

    @app.on_event("startup")
    def on_startup() -> None:
        create_all()  # prototype: create_all; Alembic migrations once schema stabilises

    return app


app = create_app()
