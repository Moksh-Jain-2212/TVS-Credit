from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from app.core.database import Base, create_session_factory, create_sqlite_engine
from app.models import Account, Client, Disposition, Loan, StandingOrder, Transaction
from scripts.build_nadi_base_features import build_base_features
from scripts.build_nadi_features import build_nadi_features, load_pre_loan_transactions


def seed_feature_db(db_path: Path) -> None:
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
                loan_date=date(1993, 4, 15),
                amount=12000,
                duration=12,
                payments=1000.0,
                status="A",
            )
        )
        session.add(StandingOrder(order_id=13, account_id=1, bank_to="YZ", account_to="87144583", amount=250.0, k_symbol="SIPO"))
        session.add_all(
            [
                Transaction(trans_id=1, account_id=1, transaction_date=date(1993, 1, 5), type="PRIJEM", operation="VKLAD", amount=1000.0, balance=1000.0, bank="AA", counterparty_account="income"),
                Transaction(trans_id=2, account_id=1, transaction_date=date(1993, 1, 10), type="VYDAJ", operation="VYBER", amount=200.0, balance=800.0, k_symbol="SIPO"),
                Transaction(trans_id=3, account_id=1, transaction_date=date(1993, 2, 5), type="PRIJEM", operation="VKLAD", amount=1200.0, balance=2000.0, bank="AA", counterparty_account="income"),
                Transaction(trans_id=4, account_id=1, transaction_date=date(1993, 2, 10), type="VYDAJ", operation="VYBER", amount=200.0, balance=1800.0, k_symbol="SIPO"),
                Transaction(trans_id=5, account_id=1, transaction_date=date(1993, 3, 5), type="PRIJEM", operation="VKLAD", amount=1400.0, balance=3200.0, bank="AA", counterparty_account="income"),
                Transaction(trans_id=6, account_id=1, transaction_date=date(1993, 3, 10), type="VYDAJ", operation="VYBER", amount=300.0, balance=2900.0, k_symbol="SIPO"),
                Transaction(trans_id=7, account_id=1, transaction_date=date(1993, 4, 15), type="PRIJEM", operation="VKLAD", amount=5000.0, balance=7900.0),
                Transaction(trans_id=8, account_id=1, transaction_date=date(1993, 4, 16), type="VYDAJ", operation="VYBER", amount=4000.0, balance=3900.0),
            ]
        )
        session.commit()
    engine.dispose()


def test_load_pre_loan_transactions_excludes_same_day_and_future_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    seed_feature_db(db_path)

    transactions = load_pre_loan_transactions(db_path)

    assert set(transactions["trans_id"]) == {1, 2, 3, 4, 5, 6}
    assert transactions["transaction_date"].max() < transactions["loan_date"].min()


def test_build_nadi_features_writes_interpretable_financial_features(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    base_path = tmp_path / "nadi_base_features.csv"
    output_path = tmp_path / "nadi_features.csv"
    seed_feature_db(db_path)
    build_base_features(db_path, base_path)

    frame = build_nadi_features(db_path, base_path, output_path)
    written = pd.read_csv(output_path)

    assert len(frame) == 1
    assert len(written) == 1
    row = written.iloc[0]
    assert row["loan_id"] == 11
    assert row["months_of_history"] == 3
    assert row["mean_monthly_inflow"] == 1200.0
    assert row["median_monthly_inflow"] == 1200.0
    assert row["p10_monthly_inflow"] == 1040.0
    assert row["mean_monthly_outflow"] == pytest.approx(700.0 / 3.0)
    assert row["mean_monthly_net_cash_flow"] == pytest.approx((3600.0 - 700.0) / 3.0)
    assert row["positive_cash_flow_month_ratio"] == 1.0
    assert row["recurring_outflow_count"] == 1
    assert row["standing_order_count"] == 1
    assert row["standing_order_monthly_burden"] == 250.0
    assert row["income_trend"] > 0
