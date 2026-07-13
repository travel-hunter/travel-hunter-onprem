from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def require_database_url() -> str:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is required when using the database layer.")
    return settings.database_url


@lru_cache
def get_engine() -> Engine:
    return create_engine(require_database_url(), pool_pre_ping=True)


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def get_optional_db() -> Generator[Session | None, None, None]:
    if not settings.database_url:
        yield None
        return

    yield from get_db()


def check_database_connection() -> str:
    if not settings.database_url:
        return "not_configured"

    try:
        with get_engine().connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return "unavailable"

    return "connected"
