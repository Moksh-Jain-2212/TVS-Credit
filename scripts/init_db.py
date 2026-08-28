"""Create the NADI SQLite database schema."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import DEFAULT_DB_PATH, Base, create_sqlite_engine
from app.models import Account, Client, Disposition, Loan, StandingOrder, Transaction


MODELS = (Account, Client, Disposition, Loan, StandingOrder, Transaction)


def init_db(db_path: Path = DEFAULT_DB_PATH, drop_existing: bool = False) -> None:
    engine = create_sqlite_engine(db_path)
    if drop_existing:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument(
        "--drop-existing",
        action="store_true",
        help="Drop existing PKDD tables before creating the schema.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    init_db(args.db_path, drop_existing=args.drop_existing)
    print(f"Initialized SQLite database at {args.db_path}.")


if __name__ == "__main__":
    main()
