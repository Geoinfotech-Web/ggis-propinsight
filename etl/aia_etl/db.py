"""Synchronous SQLAlchemy engine for ETL tasks."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection

from aia_etl.config import get_settings

_settings = get_settings()
engine = create_engine(_settings.sync_sqlalchemy_url, pool_pre_ping=True, future=True)


@contextmanager
def connect() -> Iterator[Connection]:
    """A transactional connection; commits on success, rolls back on error."""
    with engine.begin() as conn:
        yield conn
