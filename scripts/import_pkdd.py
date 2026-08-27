"""Import cleaned PKDD CSV files into SQLite and validate joins."""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import Base, create_session_factory, create_sqlite_engine
from app.models import Account, Client, Disposition, Loan, StandingOrder, Transaction


CSV_IMPORTS = (
    ("accounts.csv", Account, ("account_open_date",), None),
    ("clients.csv", Client, (), None),
    ("dispositions.csv", Disposition, (), None),
    ("loans.csv", Loan, ("loan_date",), None),
    ("orders.csv", StandingOrder, (), None),
    ("transactions.csv", Transaction, ("transaction_date",), {"account": "counterparty_account"}),
)

EXPECTED_COUNTS = {
    "accounts.csv": Account,
    "clients.csv": Client,
    "dispositions.csv": Disposition,
    "loans.csv": Loan,
    "orders.csv": StandingOrder,
    "transactions.csv": Transaction,
}


def parse_iso_date(value: Any) -> date:
    if pd.isna(value):
        raise ValueError("Date value cannot be missing")
    return date.fromisoformat(str(value))


def normalize_row(row: dict[str, Any], date_columns: tuple[str, ...], renames: dict[str, str] | None) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        output_key = renames.get(key, key) if renames else key
        if pd.isna(value):
            normalized[output_key] = None
        elif key in date_columns:
            normalized[output_key] = parse_iso_date(value)
        else:
            normalized[output_key] = value
    return normalized


def import_csv_table(
    session: Session,
    processed_dir: Path,
    file_name: str,
    model: type,
    date_columns: tuple[str, ...],
    renames: dict[str, str] | None,
) -> int:
    csv_path = processed_dir / file_name
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing cleaned PKDD file: {csv_path}")

    total_rows = 0
    for chunk in pd.read_csv(csv_path, keep_default_na=True, chunksize=100_000):
        records = [
            normalize_row(row, date_columns, renames)
            for row in chunk.to_dict(orient="records")
        ]
        if records:
            session.bulk_insert_mappings(model, records)
            total_rows += len(records)
    return total_rows


def load_csv_row_counts(processed_dir: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for file_name in EXPECTED_COUNTS:
        csv_path = processed_dir / file_name
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing cleaned PKDD file: {csv_path}")
        counts[file_name] = sum(1 for _ in csv_path.open("r", encoding="utf-8")) - 1
    return counts


def import_pkdd(
    processed_dir: Path = Path("data/processed/pkdd"),
    db_path: Path = Path("data/nadi.db"),
    recreate: bool = True,
) -> dict[str, Any]:
    engine = create_sqlite_engine(db_path)
    if recreate:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    session_factory = create_session_factory(engine)
    imported_counts: dict[str, int] = {}
    with session_factory() as session:
        for file_name, model, date_columns, renames in CSV_IMPORTS:
            imported_counts[file_name] = import_csv_table(
                session, processed_dir, file_name, model, date_columns, renames
            )
            session.commit()
        validation = validate_import(session, processed_dir)
    engine.dispose()
    return {"imported_counts": imported_counts, "validation": validation}


def count_model(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def validate_row_counts(session: Session, processed_dir: Path) -> dict[str, dict[str, int]]:
    csv_counts = load_csv_row_counts(processed_dir)
    results: dict[str, dict[str, int]] = {}
    for file_name, model in EXPECTED_COUNTS.items():
        db_count = count_model(session, model)
        csv_count = csv_counts[file_name]
        if db_count != csv_count:
            raise ValueError(f"{file_name} imported {db_count} rows, expected {csv_count}")
        results[file_name] = {"csv_rows": csv_count, "db_rows": db_count}
    return results


def validate_orphans(session: Session) -> dict[str, int]:
    checks = {
        "transactions_without_account": (
            select(func.count())
            .select_from(Transaction)
            .outerjoin(Account, Transaction.account_id == Account.account_id)
            .where(Account.account_id.is_(None))
        ),
        "loans_without_account": (
            select(func.count())
            .select_from(Loan)
            .outerjoin(Account, Loan.account_id == Account.account_id)
            .where(Account.account_id.is_(None))
        ),
        "orders_without_account": (
            select(func.count())
            .select_from(StandingOrder)
            .outerjoin(Account, StandingOrder.account_id == Account.account_id)
            .where(Account.account_id.is_(None))
        ),
        "dispositions_without_account": (
            select(func.count())
            .select_from(Disposition)
            .outerjoin(Account, Disposition.account_id == Account.account_id)
            .where(Account.account_id.is_(None))
        ),
        "dispositions_without_client": (
            select(func.count())
            .select_from(Disposition)
            .outerjoin(Client, Disposition.client_id == Client.client_id)
            .where(Client.client_id.is_(None))
        ),
    }
    results = {name: int(session.scalar(statement) or 0) for name, statement in checks.items()}
    failures = {name: count for name, count in results.items() if count}
    if failures:
        raise ValueError(f"Foreign-key validation failed: {failures}")
    return results


def validate_required_joins(session: Session) -> dict[str, int]:
    account_transaction_joins = int(
        session.scalar(
            select(func.count())
            .select_from(Account)
            .join(Transaction, Account.account_id == Transaction.account_id)
        )
        or 0
    )
    account_loan_joins = int(
        session.scalar(
            select(func.count())
            .select_from(Account)
            .join(Loan, Account.account_id == Loan.account_id)
        )
        or 0
    )
    client_account_joins = int(
        session.scalar(
            select(func.count())
            .select_from(Client)
            .join(Disposition, Client.client_id == Disposition.client_id)
            .join(Account, Disposition.account_id == Account.account_id)
        )
        or 0
    )
    if not account_transaction_joins:
        raise ValueError("account -> transaction join returned zero rows")
    if not account_loan_joins:
        raise ValueError("account -> loan join returned zero rows")
    if not client_account_joins:
        raise ValueError("client -> disposition -> account join returned zero rows")
    return {
        "account_transaction_rows": account_transaction_joins,
        "account_loan_rows": account_loan_joins,
        "client_disposition_account_rows": client_account_joins,
    }


def validate_import(session: Session, processed_dir: Path) -> dict[str, Any]:
    return {
        "row_counts": validate_row_counts(session, processed_dir),
        "foreign_keys": validate_orphans(session),
        "joins": validate_required_joins(session),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--processed-dir", type=Path, default=Path("data/processed/pkdd"))
    parser.add_argument("--db-path", type=Path, default=Path("data/nadi.db"))
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to the existing database instead of recreating PKDD tables.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = import_pkdd(args.processed_dir, args.db_path, recreate=not args.append)
    print(f"Imported cleaned PKDD data into {args.db_path}.")
    for file_name, count in result["imported_counts"].items():
        print(f"- {file_name}: {count} rows")
    joins = result["validation"]["joins"]
    print(f"- account -> transaction join rows: {joins['account_transaction_rows']}")
    print(f"- account -> loan join rows: {joins['account_loan_rows']}")
    print(
        "- client -> disposition -> account join rows: "
        f"{joins['client_disposition_account_rows']}"
    )


if __name__ == "__main__":
    main()
