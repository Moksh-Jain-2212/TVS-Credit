from datetime import date
from pathlib import Path

import pandas as pd

from app.core.database import Base, create_session_factory, create_sqlite_engine
from app.models import Account, Client, Disposition, Loan, Transaction
from scripts.build_nadi_base_features import build_base_features, get_pre_loan_history


def seed_underwriting_db(db_path: Path) -> None:
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Account(account_id=1, district_id=10, frequency="POPLATEK MESICNE", account_open_date=date(1993, 1, 1)))
        session.add(Client(client_id=3, birth_number="706213", district_id=10))
        session.add(Disposition(disp_id=7, client_id=3, account_id=1, type="OWNER"))
        session.add(
            Loan(
                loan_id=11,
                account_id=1,
                loan_date=date(1993, 7, 5),
                amount=96396,
                duration=12,
                payments=8033.0,
                status="B",
            )
        )
        session.add_all(
            [
                Transaction(
                    trans_id=17,
                    account_id=1,
                    transaction_date=date(1993, 7, 4),
                    type="PRIJEM",
                    operation="VKLAD",
                    amount=700.0,
                    balance=700.0,
                ),
                Transaction(
                    trans_id=18,
                    account_id=1,
                    transaction_date=date(1993, 7, 5),
                    type="VYDAJ",
                    operation="VYBER",
                    amount=100.0,
                    balance=600.0,
                ),
                Transaction(
                    trans_id=19,
                    account_id=1,
                    transaction_date=date(1993, 7, 6),
                    type="VYDAJ",
                    operation="VYBER",
                    amount=200.0,
                    balance=400.0,
                ),
            ]
        )
        session.commit()
    engine.dispose()


def test_pre_loan_history_excludes_same_day_and_future_transactions(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    seed_underwriting_db(db_path)
    engine = create_sqlite_engine(db_path)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        history = get_pre_loan_history(session, account_id=1, loan_date=date(1993, 7, 5))

    assert history.transaction_count == 1
    assert history.last_transaction_date == date(1993, 7, 4)
    assert history.latest_balance == 700.0


def test_build_base_features_writes_one_row_per_loan_without_leakage(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    output_path = tmp_path / "nadi_base_features.csv"
    seed_underwriting_db(db_path)

    frame = build_base_features(db_path, output_path)
    written = pd.read_csv(output_path)

    assert len(frame) == 1
    assert len(written) == 1
    assert written.loc[0, "loan_id"] == 11
    assert written.loc[0, "pre_loan_transaction_count"] == 1
    assert written.loc[0, "pre_loan_last_transaction_date"] == "1993-07-04"
    assert written.loc[0, "loan_date"] == "1993-07-05"
    assert written.loc[0, "primary_client_id"] == 3
    assert written.loc[0, "loan_status_target"] == "B"
