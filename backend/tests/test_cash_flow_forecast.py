from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.database import Base, create_session_factory, create_sqlite_engine
from app.models import Account, Loan, Transaction
from scripts.add_cash_flow_forecast import (
    INSUFFICIENT_HISTORY,
    add_cash_flow_forecast,
    evaluate_forecasts,
    forecast_monthly_cash_flow,
)


def test_forecast_returns_insufficient_history_for_sparse_months() -> None:
    monthly = pd.DataFrame({"net_cash_flow": [100.0, 200.0]})

    forecast = forecast_monthly_cash_flow(monthly)

    assert forecast["cash_flow_forecast_status"] == INSUFFICIENT_HISTORY
    assert np.isnan(forecast["cash_flow_forecast_p50"])


def test_forecast_returns_ordered_quantiles() -> None:
    monthly = pd.DataFrame({"net_cash_flow": [100.0, 200.0, 300.0, 400.0]})

    forecast = forecast_monthly_cash_flow(monthly)

    assert forecast["cash_flow_forecast_status"] == "forecast_available"
    assert forecast["cash_flow_forecast_p10"] <= forecast["cash_flow_forecast_p50"]
    assert forecast["cash_flow_forecast_p50"] <= forecast["cash_flow_forecast_p90"]


def seed_forecast_db(db_path: Path) -> None:
    engine = create_sqlite_engine(db_path)
    Base.metadata.create_all(bind=engine)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        session.add(Account(account_id=1, district_id=10, frequency="POPLATEK MESICNE", account_open_date=date(1993, 1, 1)))
        session.add(Loan(loan_id=11, account_id=1, loan_date=date(1993, 6, 15), amount=10000, duration=12, payments=900.0, status="A"))
        transactions = []
        trans_id = 1
        for month, inflow in enumerate([1000, 1100, 1200, 1300, 1400], start=1):
            transactions.append(Transaction(trans_id=trans_id, account_id=1, transaction_date=date(1993, month, 5), type="PRIJEM", operation="VKLAD", amount=float(inflow), balance=float(inflow)))
            trans_id += 1
            transactions.append(Transaction(trans_id=trans_id, account_id=1, transaction_date=date(1993, month, 20), type="VYDAJ", operation="VYBER", amount=500.0, balance=float(inflow - 500)))
            trans_id += 1
        transactions.append(Transaction(trans_id=trans_id, account_id=1, transaction_date=date(1993, 6, 15), type="PRIJEM", operation="VKLAD", amount=9000.0, balance=9000.0))
        session.add_all(transactions)
        session.commit()
    engine.dispose()


def test_add_cash_flow_forecast_appends_columns_without_same_day_leakage(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    features_path = tmp_path / "nadi_features.csv"
    evaluation_path = tmp_path / "cash_flow_forecast_evaluation.md"
    seed_forecast_db(db_path)
    features_path.write_text("loan_id,confidence_score\n11,80\n", encoding="utf-8")

    frame = add_cash_flow_forecast(db_path, features_path, features_path, evaluation_path)

    assert len(frame) == 1
    row = frame.iloc[0]
    assert row["cash_flow_forecast_status"] == "forecast_available"
    assert row["cash_flow_forecast_history_months"] == 5
    assert row["cash_flow_forecast_p50"] == 700.0
    assert evaluation_path.exists()


def test_evaluate_forecasts_reports_metrics(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi.db"
    seed_forecast_db(db_path)
    from scripts.build_nadi_features import load_pre_loan_transactions

    transactions = load_pre_loan_transactions(db_path)
    metrics = evaluate_forecasts(transactions)

    assert metrics["evaluated_loans"] == 1
    assert metrics["mae_p50"] >= 0
    assert 0 <= metrics["prediction_interval_coverage_p10_p90"] <= 1
