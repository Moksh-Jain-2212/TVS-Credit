"""Build the pre-loan base underwriting dataset without temporal leakage."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
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

from app.core.database import create_session_factory, create_sqlite_engine
from app.models import Account, Client, Disposition, Loan, Transaction


@dataclass(frozen=True)
class PreLoanHistory:
    transaction_count: int
    first_transaction_date: date | None
    last_transaction_date: date | None
    latest_balance: float | None

    @property
    def observed_days(self) -> int:
        if self.first_transaction_date is None or self.last_transaction_date is None:
            return 0
        return (self.last_transaction_date - self.first_transaction_date).days + 1


def get_pre_loan_history(session: Session, account_id: int, loan_date: date) -> PreLoanHistory:
    summary = session.execute(
        select(
            func.count(Transaction.trans_id),
            func.min(Transaction.transaction_date),
            func.max(Transaction.transaction_date),
        ).where(
            Transaction.account_id == account_id,
            Transaction.transaction_date < loan_date,
        )
    ).one()
    transaction_count = int(summary[0] or 0)
    first_transaction_date = summary[1]
    last_transaction_date = summary[2]

    latest_balance = None
    if transaction_count:
        latest_balance = session.scalar(
            select(Transaction.balance)
            .where(
                Transaction.account_id == account_id,
                Transaction.transaction_date < loan_date,
            )
            .order_by(Transaction.transaction_date.desc(), Transaction.trans_id.desc())
            .limit(1)
        )

    return PreLoanHistory(
        transaction_count=transaction_count,
        first_transaction_date=first_transaction_date,
        last_transaction_date=last_transaction_date,
        latest_balance=float(latest_balance) if latest_balance is not None else None,
    )


def get_primary_client(session: Session, account_id: int) -> tuple[Client | None, int, int]:
    dispositions = session.scalars(
        select(Disposition)
        .where(Disposition.account_id == account_id)
        .order_by(Disposition.type.desc(), Disposition.disp_id)
    ).all()
    owner_dispositions = [disp for disp in dispositions if disp.type == "OWNER"]
    primary_disposition = owner_dispositions[0] if owner_dispositions else (dispositions[0] if dispositions else None)
    primary_client = (
        session.get(Client, primary_disposition.client_id) if primary_disposition is not None else None
    )
    return primary_client, len(owner_dispositions), len(dispositions)


def build_loan_row(session: Session, loan: Loan) -> dict[str, Any]:
    account = session.get(Account, loan.account_id)
    if account is None:
        raise ValueError(f"Loan {loan.loan_id} has no account {loan.account_id}")

    history = get_pre_loan_history(session, loan.account_id, loan.loan_date)
    primary_client, owner_client_count, disposition_count = get_primary_client(
        session, loan.account_id
    )

    if history.last_transaction_date is not None and history.last_transaction_date >= loan.loan_date:
        raise ValueError(f"Temporal leakage detected for loan {loan.loan_id}")

    account_age_days = (loan.loan_date - account.account_open_date).days
    return {
        "loan_id": loan.loan_id,
        "account_id": loan.account_id,
        "loan_date": loan.loan_date.isoformat(),
        "requested_amount": loan.amount,
        "duration_months": loan.duration,
        "scheduled_payment": loan.payments,
        "loan_status_target": loan.status,
        "account_open_date": account.account_open_date.isoformat(),
        "account_age_days_at_loan": account_age_days,
        "account_frequency": account.frequency,
        "account_district_id": account.district_id,
        "primary_client_id": primary_client.client_id if primary_client else None,
        "primary_client_birth_number": primary_client.birth_number if primary_client else None,
        "primary_client_district_id": primary_client.district_id if primary_client else None,
        "owner_client_count": owner_client_count,
        "disposition_count": disposition_count,
        "pre_loan_transaction_count": history.transaction_count,
        "pre_loan_first_transaction_date": (
            history.first_transaction_date.isoformat()
            if history.first_transaction_date is not None
            else None
        ),
        "pre_loan_last_transaction_date": (
            history.last_transaction_date.isoformat()
            if history.last_transaction_date is not None
            else None
        ),
        "pre_loan_observed_days": history.observed_days,
        "pre_loan_latest_balance": history.latest_balance,
        "has_pre_loan_transactions": history.transaction_count > 0,
    }


def validate_no_temporal_leakage(frame: pd.DataFrame) -> None:
    dated = frame.dropna(subset=["pre_loan_last_transaction_date"])
    if dated.empty:
        return
    invalid = dated[
        pd.to_datetime(dated["pre_loan_last_transaction_date"])
        >= pd.to_datetime(dated["loan_date"])
    ]
    if not invalid.empty:
        loan_ids = ", ".join(str(value) for value in invalid["loan_id"].head(10))
        raise ValueError(f"Temporal leakage detected in loans: {loan_ids}")


def build_base_features(
    db_path: Path = Path("data/nadi.db"),
    output_path: Path = Path("data/processed/nadi_base_features.csv"),
) -> pd.DataFrame:
    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        loans = session.scalars(select(Loan).order_by(Loan.loan_id)).all()
        rows = [build_loan_row(session, loan) for loan in loans]

    frame = pd.DataFrame(rows)
    if frame["loan_id"].duplicated().any():
        raise ValueError("Base feature dataset contains duplicate loan_id rows")
    validate_no_temporal_leakage(frame)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    engine.dispose()
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("data/nadi.db"))
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("data/processed/nadi_base_features.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = build_base_features(args.db_path, args.output_path)
    print(f"Wrote {args.output_path} with {len(frame)} loan rows.")
    print("Temporal leakage check passed: all transaction history is before loan_date.")


if __name__ == "__main__":
    main()
