"""Create the NADI application-platform SQLite database schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.app_database import DEFAULT_APP_DB_PATH, AppBase, create_app_sqlite_engine, ensure_app_database
from app.models import (  # noqa: F401
    AdminDecision,
    AuditLog,
    LoanApplication,
    OtpVerification,
    RefreshSession,
    UnderwritingResult,
    User,
)


def init_app_db(db_path: Path = DEFAULT_APP_DB_PATH, drop_existing: bool = False) -> None:
    if not drop_existing:
        ensure_app_database(db_path)
        return
    engine = create_app_sqlite_engine(db_path)
    AppBase.metadata.drop_all(bind=engine)
    AppBase.metadata.create_all(bind=engine)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_APP_DB_PATH)
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing application-platform tables before creating the schema.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_app_db(args.db_path, drop_existing=args.drop_existing)
    print(f"Initialized NADI application database at {args.db_path}.")


if __name__ == "__main__":
    main()
