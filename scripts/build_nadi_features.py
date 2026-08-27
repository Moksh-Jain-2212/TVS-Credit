"""Build interpretable pre-loan financial behavior features."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import create_sqlite_engine


FEATURE_COLUMNS = [
    "months_of_history",
    "mean_monthly_inflow",
    "median_monthly_inflow",
    "p10_monthly_inflow",
    "mean_monthly_outflow",
    "mean_monthly_net_cash_flow",
    "average_monthly_surplus",
    "positive_cash_flow_month_ratio",
    "income_volatility",
    "balance_volatility",
    "average_balance",
    "minimum_balance",
    "transaction_density",
    "recurring_inflow_count",
    "recurring_outflow_count",
    "standing_order_count",
    "standing_order_monthly_burden",
    "income_trend",
    "top_inflow_source_share",
    "top_outflow_destination_share",
]


def load_pre_loan_transactions(db_path: Path) -> pd.DataFrame:
    engine = create_sqlite_engine(db_path)
    query = """
        SELECT
            l.loan_id,
            l.loan_date,
            t.trans_id,
            t.transaction_date,
            t.type,
            t.operation,
            t.amount,
            t.balance,
            t.k_symbol,
            t.bank,
            t.account AS counterparty_account
        FROM loans AS l
        JOIN transactions AS t
            ON t.account_id = l.account_id
           AND t.transaction_date < l.loan_date
        ORDER BY l.loan_id, t.transaction_date, t.trans_id
    """
    frame = pd.read_sql_query(query, engine)
    engine.dispose()
    if frame.empty:
        return frame
    frame["loan_date"] = pd.to_datetime(frame["loan_date"])
    frame["transaction_date"] = pd.to_datetime(frame["transaction_date"])
    leaks = frame[frame["transaction_date"] >= frame["loan_date"]]
    if not leaks.empty:
        loan_ids = ", ".join(str(value) for value in leaks["loan_id"].head(10))
        raise ValueError(f"Temporal leakage detected in feature transactions: {loan_ids}")
    return frame


def load_standing_order_features(db_path: Path) -> pd.DataFrame:
    engine = create_sqlite_engine(db_path)
    query = """
        SELECT
            l.loan_id,
            COUNT(o.order_id) AS standing_order_count,
            COALESCE(SUM(o.amount), 0) AS standing_order_monthly_burden
        FROM loans AS l
        LEFT JOIN standing_orders AS o
            ON o.account_id = l.account_id
        GROUP BY l.loan_id
    """
    frame = pd.read_sql_query(query, engine)
    engine.dispose()
    return frame


def empty_feature_row() -> dict[str, float | int]:
    return {
        "months_of_history": 0.0,
        "mean_monthly_inflow": 0.0,
        "median_monthly_inflow": 0.0,
        "p10_monthly_inflow": 0.0,
        "mean_monthly_outflow": 0.0,
        "mean_monthly_net_cash_flow": 0.0,
        "average_monthly_surplus": 0.0,
        "positive_cash_flow_month_ratio": 0.0,
        "income_volatility": 0.0,
        "balance_volatility": 0.0,
        "average_balance": 0.0,
        "minimum_balance": 0.0,
        "transaction_density": 0.0,
        "recurring_inflow_count": 0,
        "recurring_outflow_count": 0,
        "income_trend": 0.0,
        "top_inflow_source_share": 0.0,
        "top_outflow_destination_share": 0.0,
    }


def counterparty_key(frame: pd.DataFrame) -> pd.Series:
    return (
        frame["bank"].fillna("")
        + "|"
        + frame["counterparty_account"].fillna("")
        + "|"
        + frame["k_symbol"].fillna("")
        + "|"
        + frame["operation"].fillna("")
    )


def top_amount_share(frame: pd.DataFrame) -> float:
    total = float(frame["amount"].sum())
    if total <= 0 or frame.empty:
        return 0.0
    grouped = frame.assign(counterparty=counterparty_key(frame)).groupby("counterparty")["amount"].sum()
    return float(grouped.max() / total)


def recurring_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    recurring_groups = (
        frame.assign(
            month=frame["transaction_date"].dt.to_period("M"),
            rounded_amount=frame["amount"].round(2),
            counterparty=counterparty_key(frame),
        )
        .groupby(["rounded_amount", "counterparty"])["month"]
        .nunique()
    )
    return int((recurring_groups >= 2).sum())


def monthly_series(history: pd.DataFrame) -> pd.DataFrame:
    months = pd.period_range(
        history["transaction_date"].min().to_period("M"),
        history["transaction_date"].max().to_period("M"),
        freq="M",
    )
    monthly = pd.DataFrame(index=months)
    dated = history.assign(month=history["transaction_date"].dt.to_period("M"))
    inflows = dated[dated["type"] == "PRIJEM"].groupby("month")["amount"].sum()
    outflows = dated[dated["type"] != "PRIJEM"].groupby("month")["amount"].sum()
    monthly["inflow"] = inflows.reindex(months, fill_value=0.0)
    monthly["outflow"] = outflows.reindex(months, fill_value=0.0)
    monthly["net_cash_flow"] = monthly["inflow"] - monthly["outflow"]
    return monthly


def income_trend(monthly_inflow: pd.Series) -> float:
    if len(monthly_inflow) < 2:
        return 0.0
    x_values = np.arange(len(monthly_inflow), dtype=float)
    slope = np.polyfit(x_values, monthly_inflow.to_numpy(dtype=float), 1)[0]
    return float(slope)


def build_features_for_loan(history: pd.DataFrame) -> dict[str, float | int]:
    if history.empty:
        return empty_feature_row()

    monthly = monthly_series(history)
    inflow_rows = history[history["type"] == "PRIJEM"]
    outflow_rows = history[history["type"] != "PRIJEM"]
    months_of_history = float(len(monthly))
    mean_inflow = float(monthly["inflow"].mean())
    balance_mean = float(history["balance"].mean())

    features: dict[str, float | int] = {
        "months_of_history": months_of_history,
        "mean_monthly_inflow": mean_inflow,
        "median_monthly_inflow": float(monthly["inflow"].median()),
        "p10_monthly_inflow": float(np.percentile(monthly["inflow"], 10)),
        "mean_monthly_outflow": float(monthly["outflow"].mean()),
        "mean_monthly_net_cash_flow": float(monthly["net_cash_flow"].mean()),
        "average_monthly_surplus": float(monthly["net_cash_flow"].mean()),
        "positive_cash_flow_month_ratio": float((monthly["net_cash_flow"] > 0).mean()),
        "income_volatility": (
            float(monthly["inflow"].std(ddof=0) / mean_inflow) if mean_inflow > 0 else 0.0
        ),
        "balance_volatility": (
            float(history["balance"].std(ddof=0) / balance_mean) if balance_mean > 0 else 0.0
        ),
        "average_balance": balance_mean,
        "minimum_balance": float(history["balance"].min()),
        "transaction_density": float(len(history) / months_of_history),
        "recurring_inflow_count": recurring_count(inflow_rows),
        "recurring_outflow_count": recurring_count(outflow_rows),
        "income_trend": income_trend(monthly["inflow"]),
        "top_inflow_source_share": top_amount_share(inflow_rows),
        "top_outflow_destination_share": top_amount_share(outflow_rows),
    }
    return features


def build_financial_features(transactions: pd.DataFrame, loan_ids: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped = dict(tuple(transactions.groupby("loan_id"))) if not transactions.empty else {}
    for loan_id in loan_ids:
        history = grouped.get(loan_id, pd.DataFrame(columns=transactions.columns))
        rows.append({"loan_id": loan_id, **build_features_for_loan(history)})
    return pd.DataFrame(rows)


def build_nadi_features(
    db_path: Path = Path("data/nadi.db"),
    base_features_path: Path = Path("data/processed/nadi_base_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
) -> pd.DataFrame:
    if not base_features_path.exists():
        raise FileNotFoundError(f"Missing Phase 4 base feature file: {base_features_path}")

    base = pd.read_csv(base_features_path)
    transactions = load_pre_loan_transactions(db_path)
    financial_features = build_financial_features(transactions, base["loan_id"])
    standing_orders = load_standing_order_features(db_path)

    frame = base.merge(financial_features, on="loan_id", how="left")
    frame = frame.merge(standing_orders, on="loan_id", how="left")
    frame["standing_order_count"] = frame["standing_order_count"].fillna(0).astype(int)
    frame["standing_order_monthly_burden"] = frame["standing_order_monthly_burden"].fillna(0.0)

    missing_feature_columns = [column for column in FEATURE_COLUMNS if column not in frame.columns]
    if missing_feature_columns:
        raise ValueError(f"Missing feature columns: {missing_feature_columns}")
    if frame["loan_id"].duplicated().any():
        raise ValueError("Feature dataset contains duplicate loan_id rows")
    if len(frame) != len(base):
        raise ValueError("Feature dataset row count changed from base features")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("data/nadi.db"))
    parser.add_argument(
        "--base-features-path",
        type=Path,
        default=Path("data/processed/nadi_base_features.csv"),
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=Path("data/processed/nadi_features.csv"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = build_nadi_features(args.db_path, args.base_features_path, args.output_path)
    print(f"Wrote {args.output_path} with {len(frame)} loan rows.")
    print("Financial behavior features generated without post-loan transactions.")


if __name__ == "__main__":
    main()
