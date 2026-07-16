from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import get_settings


def build_session_factory() -> sessionmaker[Session]:
    engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@lru_cache
def _cached_session_factory() -> sessionmaker[Session]:
    return build_session_factory()


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards."""
    session = _cached_session_factory()()
    try:
        yield session
    finally:
        session.close()
