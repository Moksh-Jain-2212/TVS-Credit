from datetime import date
from pathlib import Path

import pandas as pd

from app.core.database import Base, create_session_factory, create_sqlite_engine
from app.models import Account, Loan, Transaction
from scripts.add_stability_seasonality import (
    INSUFFICIENT_HISTORY,
    add_stability_seasonality,
    build_stability_row,
)


def seed_seasonality_db(db_path: Path) -> None:
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Account(account_id=1, district_id=10, frequency="POPLATEK MESICNE", account_open_date=date(1993, 1, 1)))
        session.add(Loan(loan_id=11, account_id=1, loan_date=date(1994, 1, 15), amount=12000, duration=12, payments=1000.0, status="A"))
        transactions = []
        trans_id = 1
        monthly_inflows = [1000, 900, 800, 700, 600, 500, 600, 700, 900, 1100, 1400, 1600]
        for month, inflow in enumerate(monthly_inflows, start=1):
            transactions.append(
                Transaction(
                    trans_id=trans_id,
                    account_id=1,
                    transaction_date=date(1993, month, 5),
                    type="PRIJEM",
                    operation="VKLAD",
                    amount=float(inflow),
                    balance=float(inflow),
                )
            )
            trans_id += 1
            transactions.append(
                Transaction(
                    trans_id=trans_id,
                    account_id=1,
                    transaction_date=date(1993, month, 15),
                    type="VYDAJ",
                    operation="VYBER",
                    amount=400.0,
                    balance=float(inflow - 400),
                )
            )
            trans_id += 1
        session.add_all(transactions)
        session.commit()
    engine.dispose()


def test_build_stability_row_marks_insufficient_history() -> None:
    history = pd.DataFrame(
        {
            "loan_id": [1, 1],
            "loan_date": pd.to_datetime(["1993-03-01", "1993-03-01"]),
            "transaction_date": pd.to_datetime(["1993-01-01", "1993-02-01"]),
            "type": ["PRIJEM", "PRIJEM"],
            "amount": [1000.0, 900.0],
            "balance": [1000.0, 1900.0],
        }
    )

    row = build_stability_row(1, history)

    assert row["stability_history_status"] == INSUFFICIENT_HISTORY
    assert row["likely_low_income_periods"] == INSUFFICIENT_HISTORY


def test_add_stability_seasonality_appends_features_and_preserves_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    features_path = tmp_path / "nadi_features.csv"
    seed_seasonality_db(db_path)
    features_path.write_text("loan_id,repayment_outcome_known\n11,True\n", encoding="utf-8")

    frame = add_stability_seasonality(db_path, features_path, features_path)
    written = pd.read_csv(features_path)

    assert len(frame) == 1
    assert len(written) == 1
    row = written.iloc[0]
    assert row["stability_history_status"] == "sufficient_history"
    assert row["seasonality_status"] == "sufficient_history"
    assert row["income_stability_score"] > 0
    assert row["cash_flow_stability_score"] > 0
    assert row["phase7_income_trend"] > 0
    assert row["income_seasonality_strength"] > 0
    assert row["likely_low_income_periods"].startswith("Jun,")
    assert row["likely_high_income_periods"] == "Dec,Nov"
