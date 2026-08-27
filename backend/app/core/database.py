"""Database helpers for the NADI backend."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


DEFAULT_DB_PATH = Path("data/nadi.db")


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


def sqlite_url(db_path: Path = DEFAULT_DB_PATH) -> str:
    return f"sqlite:///{db_path}"


def create_sqlite_engine(db_path: Path = DEFAULT_DB_PATH) -> Engine:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(sqlite_url(db_path), future=True)

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
