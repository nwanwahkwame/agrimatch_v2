from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config.settings import DATABASE_URL

# Engine and session factory created once at import time.
# pool_size=10 keeps connections warm across requests; pool_pre_ping
# silently reconnects if Railway drops an idle connection.
_engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=5,
    pool_pre_ping=True,
    pool_recycle=1800,
)

# Backward-compatible alias used by alert_engine and other modules
def get_engine():
    return _engine

_SessionFactory = sessionmaker(bind=_engine, autoflush=False, autocommit=False)


@contextmanager
def get_session() -> Generator[Session, None, None]:
    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
