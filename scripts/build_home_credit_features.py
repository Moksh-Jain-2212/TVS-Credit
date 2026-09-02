"""Build a compact, reproducible Home Credit risk-training dataset.

The Home Credit tables are linked through ``SK_ID_CURR``.  This script keeps
the application row as the point-in-time decision record and aggregates prior
credit records into borrower-level features.  It deliberately avoids copying
raw history into the live NADI database.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


APPLICATION_COLUMNS = [
    "SK_ID_CURR", "TARGET", "AMT_INCOME_TOTAL", "AMT_CREDIT", "AMT_ANNUITY",
    "AMT_GOODS_PRICE", "CNT_CHILDREN", "DAYS_BIRTH", "DAYS_EMPLOYED",
    "REGION_POPULATION_RELATIVE", "CNT_FAM_MEMBERS", "OWN_CAR_AGE",
    "OBS_30_CNT_SOCIAL_CIRCLE", "DEF_30_CNT_SOCIAL_CIRCLE",
    "AMT_REQ_CREDIT_BUREAU_YEAR",
    # Retained only for held-out fairness evaluation; never used for training.
    "CODE_GENDER",
]


def safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    return numerator.div(denominator.replace(0, np.nan)).replace([np.inf, -np.inf], np.nan)


def aggregate_bureau(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=lambda column: column in {
        "SK_ID_CURR", "CREDIT_ACTIVE", "CREDIT_DAY_OVERDUE", "AMT_CREDIT_SUM",
        "AMT_CREDIT_SUM_DEBT", "AMT_CREDIT_SUM_OVERDUE", "CNT_CREDIT_PROLONG", "DAYS_CREDIT",
    })
    frame["bureau_active_count"] = (frame["CREDIT_ACTIVE"] == "Active").astype(int)
    frame["bureau_active_credit_days"] = frame["DAYS_CREDIT"].where(frame["CREDIT_ACTIVE"] == "Active")
    frame["bureau_overdue_account_count"] = (frame["CREDIT_DAY_OVERDUE"].fillna(0) > 0).astype(int)
    return frame.groupby("SK_ID_CURR", as_index=False).agg(
        bureau_account_count=("CREDIT_ACTIVE", "size"),
        bureau_active_count=("bureau_active_count", "sum"),
        bureau_total_credit=("AMT_CREDIT_SUM", "sum"),
        bureau_total_debt=("AMT_CREDIT_SUM_DEBT", "sum"),
        bureau_total_overdue=("AMT_CREDIT_SUM_OVERDUE", "sum"),
        bureau_overdue_account_count=("bureau_overdue_account_count", "sum"),
        bureau_credit_prolongations=("CNT_CREDIT_PROLONG", "sum"),
        bureau_most_recent_active_credit_days=("bureau_active_credit_days", "max"),
    )


def aggregate_bureau_balance(bureau_path: Path, balance_path: Path, chunksize: int) -> pd.DataFrame:
    """Summarise bureau repayment status without loading the full balance file."""
    mapping = pd.read_csv(bureau_path, usecols=["SK_ID_BUREAU", "SK_ID_CURR"])
    parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(balance_path, usecols=["SK_ID_BUREAU", "MONTHS_BALANCE", "STATUS"], chunksize=chunksize):
        chunk = chunk.merge(mapping, on="SK_ID_BUREAU", how="inner")
        chunk["bureau_dpd_status"] = pd.to_numeric(chunk["STATUS"], errors="coerce").fillna(0)
        chunk["bureau_delinquent_month"] = (chunk["bureau_dpd_status"] > 0).astype(int)
        recent = chunk[chunk["MONTHS_BALANCE"] >= -12]
        for label, filtered in (("all", chunk), ("recent_12m", recent)):
            if filtered.empty:
                continue
            summary = filtered.groupby("SK_ID_CURR", as_index=False).agg(
                bureau_balance_months=("STATUS", "size"),
                bureau_delinquent_months=("bureau_delinquent_month", "sum"),
                bureau_max_dpd_status=("bureau_dpd_status", "max"),
            )
            parts.append(summary.rename(columns={column: f"{label}_{column}" for column in summary.columns if column != "SK_ID_CURR"}))
    result: pd.DataFrame | None = None
    for label in ("all", "recent_12m"):
        matching = [part for part in parts if f"{label}_bureau_balance_months" in part.columns]
        if matching:
            combined = pd.concat(matching).groupby("SK_ID_CURR", as_index=False).sum(numeric_only=True)
            result = combined if result is None else result.merge(combined, on="SK_ID_CURR", how="outer")
    return result if result is not None else pd.DataFrame(columns=["SK_ID_CURR"])


def aggregate_previous(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, usecols=lambda column: column in {
        "SK_ID_CURR", "NAME_CONTRACT_STATUS", "AMT_APPLICATION", "AMT_CREDIT",
        "AMT_ANNUITY", "AMT_DOWN_PAYMENT", "CNT_PAYMENT", "DAYS_DECISION",
    })
    frame["previous_approved_count"] = (frame["NAME_CONTRACT_STATUS"] == "Approved").astype(int)
    frame["previous_refused_count"] = (frame["NAME_CONTRACT_STATUS"] == "Refused").astype(int)
    base = frame.groupby("SK_ID_CURR", as_index=False).agg(
        previous_application_count=("NAME_CONTRACT_STATUS", "size"),
        previous_approved_count=("previous_approved_count", "sum"),
        previous_refused_count=("previous_refused_count", "sum"),
        previous_mean_credit=("AMT_CREDIT", "mean"),
        previous_mean_annuity=("AMT_ANNUITY", "mean"),
        previous_mean_payments=("CNT_PAYMENT", "mean"),
        previous_mean_down_payment=("AMT_DOWN_PAYMENT", "mean"),
        previous_latest_decision_days=("DAYS_DECISION", "max"),
    )
    # DAYS_DECISION is negative; values closest to zero are most recent.
    recent = frame.sort_values(["SK_ID_CURR", "DAYS_DECISION"]).groupby("SK_ID_CURR", group_keys=False).tail(5)
    for count in (3, 5):
        subset = recent.groupby("SK_ID_CURR", group_keys=False).tail(count)
        summary = subset.groupby("SK_ID_CURR", as_index=False).agg(
            **{f"previous_last_{count}_mean_credit": ("AMT_CREDIT", "mean"),
               f"previous_last_{count}_mean_annuity": ("AMT_ANNUITY", "mean"),
               f"previous_last_{count}_mean_down_payment": ("AMT_DOWN_PAYMENT", "mean")}
        )
        base = base.merge(summary, on="SK_ID_CURR", how="left")
    latest = recent.sort_values(["SK_ID_CURR", "DAYS_DECISION"]).groupby("SK_ID_CURR").tail(1)
    latest["previous_latest_approved"] = (latest["NAME_CONTRACT_STATUS"] == "Approved").astype(int)
    latest["previous_latest_refused"] = (latest["NAME_CONTRACT_STATUS"] == "Refused").astype(int)
    return base.merge(latest[["SK_ID_CURR", "previous_latest_approved", "previous_latest_refused"]], on="SK_ID_CURR", how="left")


def aggregate_installments(path: Path, chunksize: int) -> pd.DataFrame:
    """Aggregate payment behaviour in chunks so the 700MB file stays usable."""
    parts: list[pd.DataFrame] = []
    recent_parts: list[pd.DataFrame] = []
    for chunk in pd.read_csv(path, usecols=["SK_ID_CURR", "DAYS_INSTALMENT", "DAYS_ENTRY_PAYMENT", "AMT_INSTALMENT", "AMT_PAYMENT"], chunksize=chunksize):
        chunk["days_late"] = (chunk["DAYS_ENTRY_PAYMENT"] - chunk["DAYS_INSTALMENT"]).clip(lower=0).fillna(0)
        chunk["late"] = (chunk["days_late"] > 0).astype(int)
        chunk["shortfall"] = (chunk["AMT_INSTALMENT"].fillna(0) - chunk["AMT_PAYMENT"].fillna(0)).clip(lower=0)
        for label, filtered in [("all", chunk), *[(f"recent_{days}", chunk[chunk["DAYS_INSTALMENT"] >= -days]) for days in (60, 90, 180, 365)]]:
            if filtered.empty:
                continue
            grouped = filtered.groupby("SK_ID_CURR", as_index=False).agg(
                payment_count=("SK_ID_CURR", "size"), late_count=("late", "sum"),
                late_days=("days_late", "sum"), max_days_late=("days_late", "max"),
                payment_shortfall=("shortfall", "sum"), scheduled_amount=("AMT_INSTALMENT", "sum"), paid_amount=("AMT_PAYMENT", "sum"),
            )
            grouped = grouped.rename(columns={column: f"installment_{label}_{column}" for column in grouped.columns if column != "SK_ID_CURR"})
            parts.append(grouped)
        recent_parts.append(chunk.sort_values(["SK_ID_CURR", "DAYS_INSTALMENT"]).groupby("SK_ID_CURR", group_keys=False).tail(5))
    result: pd.DataFrame | None = None
    for label in ("all", "recent_60", "recent_90", "recent_180", "recent_365"):
        matching = [part for part in parts if f"installment_{label}_payment_count" in part.columns]
        if not matching:
            continue
        stacked = pd.concat(matching)
        aggregation = {column: ("max" if "max_days_late" in column else "sum") for column in stacked.columns if column != "SK_ID_CURR"}
        combined = stacked.groupby("SK_ID_CURR", as_index=False).agg(aggregation)
        result = combined if result is None else result.merge(combined, on="SK_ID_CURR", how="outer")
    if result is None:
        return pd.DataFrame(columns=["SK_ID_CURR"])
    latest = pd.concat(recent_parts).sort_values(["SK_ID_CURR", "DAYS_INSTALMENT"]).groupby("SK_ID_CURR", group_keys=False).tail(5)
    for count in (2, 3, 5):
        subset = latest.groupby("SK_ID_CURR", group_keys=False).tail(count)
        summary = subset.groupby("SK_ID_CURR", as_index=False).agg(
            **{f"installment_last_{count}_late_ratio": ("late", "mean"), f"installment_last_{count}_mean_days_late": ("days_late", "mean"), f"installment_last_{count}_payment_coverage": ("AMT_PAYMENT", "sum")}
        )
        scheduled = subset.groupby("SK_ID_CURR", as_index=False)["AMT_INSTALMENT"].sum().rename(columns={"AMT_INSTALMENT": "scheduled"})
        summary = summary.merge(scheduled, on="SK_ID_CURR", how="left")
        summary[f"installment_last_{count}_payment_coverage"] = safe_ratio(summary[f"installment_last_{count}_payment_coverage"], summary["scheduled"])
        result = result.merge(summary.drop(columns="scheduled"), on="SK_ID_CURR", how="left")
    return result


def build_features(raw_dir: Path, output_path: Path, *, include_installments: bool = False, chunksize: int = 200_000) -> pd.DataFrame:
    applications_path = raw_dir / "application_train.csv"
    required = [applications_path, raw_dir / "bureau.csv", raw_dir / "previous_application.csv"]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing Home Credit files: {', '.join(missing)}")
    applications = pd.read_csv(applications_path, usecols=APPLICATION_COLUMNS)
    features = applications.merge(aggregate_bureau(raw_dir / "bureau.csv"), on="SK_ID_CURR", how="left")
    balance_path = raw_dir / "bureau_balance.csv"
    if balance_path.exists():
        features = features.merge(aggregate_bureau_balance(raw_dir / "bureau.csv", balance_path, chunksize), on="SK_ID_CURR", how="left")
    features = features.merge(aggregate_previous(raw_dir / "previous_application.csv"), on="SK_ID_CURR", how="left")
    if include_installments:
        installment_path = raw_dir / "installments_payments.csv"
        if not installment_path.exists():
            raise FileNotFoundError(f"Missing Home Credit installments file: {installment_path}")
        features = features.merge(aggregate_installments(installment_path, chunksize), on="SK_ID_CURR", how="left")
        features["installment_late_payment_ratio"] = safe_ratio(features["installment_all_late_count"], features["installment_all_payment_count"])
        features["installment_average_days_late"] = safe_ratio(features["installment_all_late_days"], features["installment_all_late_count"])
        features["installment_payment_shortfall_ratio"] = safe_ratio(features["installment_all_payment_shortfall"], features["installment_all_scheduled_amount"])
        features["installment_payment_coverage"] = safe_ratio(features["installment_all_paid_amount"], features["installment_all_scheduled_amount"])
        for days in (60, 90, 180, 365):
            prefix = f"installment_recent_{days}"
            features[f"{prefix}_late_ratio"] = safe_ratio(features[f"{prefix}_late_count"], features[f"{prefix}_payment_count"])
            features[f"{prefix}_payment_coverage"] = safe_ratio(features[f"{prefix}_paid_amount"], features[f"{prefix}_scheduled_amount"])
    features["bureau_debt_to_credit_ratio"] = safe_ratio(features["bureau_total_debt"], features["bureau_total_credit"])
    features["bureau_overdue_to_credit_ratio"] = safe_ratio(features["bureau_total_overdue"], features["bureau_total_credit"])
    features["requested_annuity_to_income_ratio"] = safe_ratio(features["AMT_ANNUITY"], features["AMT_INCOME_TOTAL"])
    features["requested_credit_to_income_ratio"] = safe_ratio(features["AMT_CREDIT"], features["AMT_INCOME_TOTAL"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(output_path, index=False)
    return features


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/home_credit_features.csv"))
    parser.add_argument("--include-installments", action="store_true")
    parser.add_argument("--chunksize", type=int, default=200_000)
    args = parser.parse_args()
    features = build_features(args.raw_dir, args.output_path, include_installments=args.include_installments, chunksize=args.chunksize)
    print(f"Wrote {len(features):,} labelled Home Credit rows to {args.output_path}.")


if __name__ == "__main__":
    main()
