from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from .config import Settings, get_settings
from .models import Base


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    return create_engine(settings.database_url, future=True)


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope() -> Session:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    engine = get_engine()
    with engine.begin() as connection:
        if settings.database_url.startswith("postgresql"):
            connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        Base.metadata.create_all(bind=connection)


def assert_database_connection(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    engine = get_engine()
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(
            f"Database connection failed for DATABASE_URL='{settings.database_url}'. "
            "Refusing to run the ingestion or analysis pipeline until the database is reachable."
        ) from exc
