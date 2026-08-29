"""Database helpers for the NADI application platform state."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from collections.abc import Generator

from sqlalchemy.exc import DatabaseError
from sqlalchemy import create_engine, event, inspect, text
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
    engine = create_engine(
        app_sqlite_url(db_path),
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def enable_sqlite_foreign_keys(dbapi_connection: object, _: object) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


def create_app_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def app_database_is_healthy(db_path: Path) -> bool:
    if not db_path.exists():
        return True
    try:
        with sqlite3.connect(db_path) as connection:
            result = connection.execute("PRAGMA integrity_check;").fetchone()
    except sqlite3.DatabaseError:
        return False
    return result is not None and result[0] == "ok"


def quarantine_malformed_app_database(db_path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    quarantine_path = db_path.with_name(f"{db_path.name}.malformed-{timestamp}")
    db_path.replace(quarantine_path)
    return quarantine_path


def ensure_app_database(db_path: Path | None = None, *, recover_malformed: bool = True) -> Path | None:
    target_path = db_path or app_database_path()
    quarantined_path: Path | None = None
    if not app_database_is_healthy(target_path):
        if not recover_malformed:
            raise DatabaseError("PRAGMA integrity_check", {}, "application database is malformed")
        quarantined_path = quarantine_malformed_app_database(target_path)
        reset_app_engine_cache()
    engine = create_app_sqlite_engine(target_path)
    AppBase.metadata.create_all(bind=engine)
    ensure_sqlite_app_schema_columns(engine)
    return quarantined_path


def ensure_sqlite_app_schema_columns(engine: Engine) -> None:
    """Small local-development bridge until Alembic migrations are applied."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    additions = {
        "underwriting_results": {
            "model_version": "VARCHAR(128)",
            "feature_schema_version": "VARCHAR(128)",
            "underwriting_engine_version": "VARCHAR(64)",
            "evidence_mode": "VARCHAR(64)",
            "governance_metadata_json": "JSON",
        },
        "loan_applications": {
            "borrower_segment": "VARCHAR(32)",
        },
        "admin_decisions": {
            "override_metadata_json": "JSON",
            "second_review_required": "BOOLEAN NOT NULL DEFAULT 0",
        },
        "behavioral_risk_assessments": {
            "behavioral_score_band": "VARCHAR(64)",
            "behavioral_probability_calibration_status": "VARCHAR(64) NOT NULL DEFAULT 'POLICY_HEURISTIC'",
        },
    }
    with engine.begin() as connection:
        for table, columns in additions.items():
            if table not in existing_tables:
                continue
            existing_columns = {column["name"] for column in inspector.get_columns(table)}
            for column, ddl in columns.items():
                if column not in existing_columns:
                    connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))


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
