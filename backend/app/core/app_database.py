"""Database helpers for the NADI application platform state."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_APP_DB_PATH = REPO_ROOT / "data" / "nadi_app.db"


class AppBase(DeclarativeBase):
    """Base class for application-platform ORM models."""


def app_sqlite_url(db_path: Path = DEFAULT_APP_DB_PATH) -> str:
    return f"sqlite:///{db_path}"


def create_app_sqlite_engine(db_path: Path = DEFAULT_APP_DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(app_sqlite_url(db_path), future=True)

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_app_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def app_database_path() -> Path:
    configured = Path(os.getenv("APP_DATABASE_PATH", str(DEFAULT_APP_DB_PATH)))
    return configured if configured.is_absolute() else REPO_ROOT / configured


@lru_cache(maxsize=8)
def get_app_engine(db_path: str) -> Engine:
    return create_app_sqlite_engine(Path(db_path))


def reset_app_engine_cache() -> None:
    get_app_engine.cache_clear()


def get_app_session() -> Generator[Session, None, None]:
    engine = get_app_engine(str(app_database_path()))
    session_factory = create_app_session_factory(engine)
    with session_factory() as session:
        yield session
