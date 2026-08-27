"""Add pre-loan stability and seasonality features."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.build_nadi_features import load_pre_loan_transactions, monthly_series


INSUFFICIENT_HISTORY = "insufficient_history"
MIN_STABILITY_MONTHS = 3
MIN_SEASONALITY_MONTHS = 12

STABILITY_SEASONALITY_COLUMNS = [
    "stability_history_status",
    "income_stability_score",
    "cash_flow_stability_score",
    "phase7_income_trend",
    "seasonality_status",
    "income_seasonality_strength",
    "likely_low_income_periods",
    "likely_high_income_periods",
]


def bounded_stability_score(values: pd.Series) -> float:
    mean_abs = float(values.abs().mean())
    if mean_abs <= 0:
        return 0.0
    coefficient_variation = float(values.std(ddof=0) / mean_abs)
    return float(1.0 / (1.0 + coefficient_variation))


def trend_slope(values: pd.Series) -> float:
    if len(values) < 2:
        return 0.0
    x_values = np.arange(len(values), dtype=float)
    return float(np.polyfit(x_values, values.to_numpy(dtype=float), 1)[0])


def month_names(period_index: pd.PeriodIndex) -> pd.Series:
    return pd.Series(
        [period.to_timestamp().strftime("%b") for period in period_index],
        index=period_index,
    )


def seasonality_strength(monthly_inflow: pd.Series) -> float:
    total_variance = float(monthly_inflow.var(ddof=0))
    if total_variance <= 0:
        return 0.0
    month_number = monthly_inflow.index.month
    month_means = monthly_inflow.groupby(month_number).transform("mean")
    seasonal_variance = float(month_means.var(ddof=0))
    return float(max(0.0, min(1.0, seasonal_variance / total_variance)))


def low_high_income_periods(monthly_inflow: pd.Series) -> tuple[str, str]:
    month_number = monthly_inflow.index.month
    month_average = monthly_inflow.groupby(month_number).mean().sort_values()
    low_months = month_average.head(2).index
    high_months = month_average.tail(2).sort_values(ascending=False).index
    month_lookup = {
        number: pd.Timestamp(year=2000, month=int(number), day=1).strftime("%b")
        for number in month_average.index
    }
    low = ",".join(month_lookup[number] for number in low_months)
    high = ",".join(month_lookup[number] for number in high_months)
    return low, high


def insufficient_row(loan_id: Any) -> dict[str, Any]:
    return {
        "loan_id": loan_id,
        "stability_history_status": INSUFFICIENT_HISTORY,
        "income_stability_score": np.nan,
        "cash_flow_stability_score": np.nan,
        "phase7_income_trend": np.nan,
        "seasonality_status": INSUFFICIENT_HISTORY,
        "income_seasonality_strength": np.nan,
        "likely_low_income_periods": INSUFFICIENT_HISTORY,
        "likely_high_income_periods": INSUFFICIENT_HISTORY,
    }


def build_stability_row(loan_id: Any, history: pd.DataFrame) -> dict[str, Any]:
    if history.empty:
        return insufficient_row(loan_id)

    monthly = monthly_series(history)
    if len(monthly) < MIN_STABILITY_MONTHS:
        return insufficient_row(loan_id)

    row: dict[str, Any] = {
        "loan_id": loan_id,
        "stability_history_status": "sufficient_history",
        "income_stability_score": bounded_stability_score(monthly["inflow"]),
        "cash_flow_stability_score": bounded_stability_score(monthly["net_cash_flow"]),
        "phase7_income_trend": trend_slope(monthly["inflow"]),
    }

    if len(monthly) < MIN_SEASONALITY_MONTHS:
        row.update(
            {
                "seasonality_status": INSUFFICIENT_HISTORY,
                "income_seasonality_strength": np.nan,
                "likely_low_income_periods": INSUFFICIENT_HISTORY,
                "likely_high_income_periods": INSUFFICIENT_HISTORY,
            }
        )
        return row

    low_periods, high_periods = low_high_income_periods(monthly["inflow"])
    row.update(
        {
            "seasonality_status": "sufficient_history",
            "income_seasonality_strength": seasonality_strength(monthly["inflow"]),
            "likely_low_income_periods": low_periods,
            "likely_high_income_periods": high_periods,
        }
    )
    return row


def build_stability_features(transactions: pd.DataFrame, loan_ids: pd.Series) -> pd.DataFrame:
    grouped = dict(tuple(transactions.groupby("loan_id"))) if not transactions.empty else {}
    rows = [
        build_stability_row(loan_id, grouped.get(loan_id, pd.DataFrame(columns=transactions.columns)))
        for loan_id in loan_ids
    ]
    return pd.DataFrame(rows)


def add_stability_seasonality(
    db_path: Path = Path("data/nadi.db"),
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    features = pd.read_csv(features_path)
    features = features.drop(
        columns=[column for column in STABILITY_SEASONALITY_COLUMNS if column in features.columns]
    )
    transactions = load_pre_loan_transactions(db_path)
    stability = build_stability_features(transactions, features["loan_id"])
    frame = features.merge(stability, on="loan_id", how="left")

    if len(frame) != len(features):
        raise ValueError("Stability merge changed feature row count")
    if frame["loan_id"].duplicated().any():
        raise ValueError("Stability feature dataset contains duplicate loan_id values")
    missing = [column for column in STABILITY_SEASONALITY_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"Missing stability columns: {missing}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=Path("data/nadi.db"))
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = add_stability_seasonality(args.db_path, args.features_path, args.output_path)
    stability_counts = frame["stability_history_status"].value_counts().to_dict()
    seasonality_counts = frame["seasonality_status"].value_counts().to_dict()
    print(f"Wrote stability and seasonality features to {args.output_path} with {len(frame)} rows.")
    print(f"Stability status counts: {stability_counts}")
    print(f"Seasonality status counts: {seasonality_counts}")


if __name__ == "__main__":
    main()
