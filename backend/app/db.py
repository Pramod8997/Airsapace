"""Database engine/session. PostgreSQL-ready via DATABASE_URL; SQLite for local
development (dev-only substitution — production remains PostgreSQL per TRD §2.3).
"""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.config import get_settings
from backend.app.models import Base

_engine = None
_session_factory: sessionmaker | None = None


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        url = get_settings().database_url
        kwargs: dict = {"future": True}
        if url.startswith("sqlite"):
            kwargs["connect_args"] = {"check_same_thread": False}
            if ":memory:" in url or url.endswith("://"):
                kwargs["poolclass"] = StaticPool  # share one in-memory DB across sessions
        _engine = create_engine(url, **kwargs)
        _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    return _engine


def create_all() -> None:
    Base.metadata.create_all(get_engine())


def drop_all() -> None:
    Base.metadata.drop_all(get_engine())


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commit on success, rollback on error."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session_factory() -> sessionmaker:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def reset_engine_for_tests() -> None:
    """Tests swap DATABASE_URL; drop cached engine so it takes effect."""
    global _engine, _session_factory
    _engine = None
    _session_factory = None
