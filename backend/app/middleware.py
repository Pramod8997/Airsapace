"""API middleware: security headers (SECURITY.md §11) and per-IP rate limiting
(SECURITY.md §7, T10). Stdlib token bucket — no extra dependency for the
prototype; the reverse proxy takes over in production.
"""
from __future__ import annotations

import re
import threading
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.app.config import get_settings

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        for header, value in SECURITY_HEADERS.items():
            response.headers.setdefault(header, value)
        if get_settings().app_env == "production":
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Token bucket per client IP. 'N/minute' or 'N/second' from API_RATE_LIMIT."""

    def __init__(self, app, limit: str):  # type: ignore[no-untyped-def]
        super().__init__(app)
        match = re.fullmatch(r"(\d+)\s*/\s*(minute|second|hour)", limit.strip())
        if not match:
            raise ValueError(f"bad API_RATE_LIMIT: {limit!r}")
        n, unit = int(match.group(1)), match.group(2)
        self.capacity = n
        self.window = {"second": 1, "minute": 60, "hour": 3600}[unit]
        self.buckets: dict[str, tuple[float, float]] = {}  # ip -> (tokens, last_refill)
        self.lock = threading.Lock()

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/health"):
            return await call_next(request)
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        with self.lock:
            tokens, last = self.buckets.get(ip, (float(self.capacity), now))
            tokens = min(self.capacity, tokens + (now - last) * self.capacity / self.window)
            allowed = tokens >= 1.0
            if allowed:
                tokens -= 1.0
            self.buckets[ip] = (tokens, now)
        if not allowed:
            return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
        return await call_next(request)
