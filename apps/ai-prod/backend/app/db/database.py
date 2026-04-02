from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """SQLAlchemy 基类。"""


@lru_cache(maxsize=1)
def get_engine():
    settings = get_settings()
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{settings.database_path}",
        connect_args={"check_same_thread": False},
    )


@lru_cache(maxsize=1)
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


def reset_database_cache() -> None:
    try:
        engine = get_engine()
    except Exception:
        engine = None
    if engine is not None:
        engine.dispose()
    get_session_factory.cache_clear()
    get_engine.cache_clear()
