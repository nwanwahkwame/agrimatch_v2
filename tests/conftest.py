"""
Pytest configuration for AgriMatch tests.

The PostgreSQL-specific column types (JSONB, ARRAY) are patched to their
SQLite-compatible equivalents HERE, at module load time, before any project
model is imported.  pytest loads conftest.py before test files, so the patch
is in place when db.models runs its top-level Column() definitions.
"""

# ── Dialect patch — MUST come before any db.* imports ────────────────────────
import sqlalchemy as _sa
import sqlalchemy.dialects.postgresql as _pg
from sqlalchemy import Integer as _Integer, JSON as _JSON

# SQLite only creates an auto-increment rowid alias when the column type is
# exactly "INTEGER PRIMARY KEY".  "BIGINT PRIMARY KEY" does not qualify, so
# the id column gets NULL on INSERT.  Patching BigInteger -> Integer before
# db.models is imported makes every BigInteger PK work correctly on SQLite.
_sa.BigInteger = _Integer

_pg.JSONB = _JSON          # JSONB -> JSON (stored as text on SQLite)


class _ARRAY(_JSON):
    """Stand-in for pg.ARRAY that persists arrays as JSON on SQLite."""
    def __init__(self, item_type=None, **_):
        super().__init__()


_pg.ARRAY = _ARRAY
# ─────────────────────────────────────────────────────────────────────────────

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.models import Base   # safe to import now — patch is already applied

# Single in-memory SQLite database shared across the test session.
# StaticPool keeps one connection alive so all sessions see the same data.
_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
Base.metadata.create_all(_engine)
_SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@pytest.fixture
def db_session():
    """Yield a session backed by the SQLite test database.

    All rows are deleted after each test so tests are fully isolated.
    """
    session = _SessionFactory()
    yield session
    session.rollback()                          # discard any uncommitted work
    for table in reversed(Base.metadata.sorted_tables):
        session.execute(table.delete())         # wipe committed rows
    session.commit()
    session.close()


@pytest.fixture
def patch_get_session(db_session, monkeypatch):
    """Replace get_session in ingestion.transformers with a test-safe version.

    The fake context manager yields the same db_session that the test uses
    for assertions, and commits on clean exit (mirroring the real behaviour).
    """
    @contextmanager
    def _fake():
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    monkeypatch.setattr("ingestion.transformers.get_session", _fake)
