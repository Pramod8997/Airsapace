"""Environment-driven configuration. No secrets or magic constants in code."""
from __future__ import annotations

import json
import logging
import sys
from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_env: str = "development"  # development | production
    data_mode: str = "REPLAY"  # LIVE | DEMO | REPLAY (PRD §17)
    database_url: str = "sqlite:///data/airstat.db"
    cors_origins: str = ""  # comma-separated allowlist; empty = same-origin only
    log_level: str = "INFO"
    api_rate_limit: str = "120/minute"  # SECURITY.md §7
    raw_storage_path: str = "data/raw"

    # Outlier business bounds (INR) — flags, never deletes (PRD §13)
    min_payable_fare: float = 500.0
    max_payable_fare: float = 100000.0

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        entry = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
