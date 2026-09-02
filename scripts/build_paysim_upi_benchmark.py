"""Build privacy-preserving UPI-like benchmark profiles from PaySim.

PaySim is a synthetic mobile-money/fraud dataset. This script is for offline
feature benchmarking only; its output is never loaded by live NADI underwriting.
"""

from __future__ import annotations

import argparse
import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "step", "type", "amount", "nameOrig", "nameDest", "oldbalanceOrg", "newbalanceOrig",
}
UPI_EQUIVALENT_TYPES = {
    "PAYMENT": "MERCHANT_PAYMENT",
    "TRANSFER": "P2P_TRANSFER",
    "CASH_IN": "ACCOUNT_CREDIT",
    "CASH_OUT": "CASH_OR_DEBIT_OUTFLOW",
    "DEBIT": "SCHEDULED_DEBIT",
}


def stable_bucket(value: str, modulus: int) -> int:
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:12], 16) % modulus


def safe_profile_id(value: str) -> str:
    return f"paysim_profile_{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"


def _empty_stats() -> dict[str, Any]:
    return {
        "outgoing_count": 0,
        "incoming_count": 0,
        "outgoing_amount": 0.0,
        "incoming_amount": 0.0,
        "merchant_count": 0,
        "p2p_count": 0,
        "credit_count": 0,
        "debit_count": 0,
        "steps": set(),
        "amounts": [],
    }


def _add_outgoing(stats: dict[str, Any], transaction_type: str, amount: float, step: int) -> None:
    stats["outgoing_count"] += 1
    stats["outgoing_amount"] += amount
    stats["steps"].add(step)
    stats["amounts"].append(amount)
    if transaction_type == "PAYMENT":
        stats["merchant_count"] += 1
    elif transaction_type == "TRANSFER":
        stats["p2p_count"] += 1
    elif transaction_type == "CASH_IN":
        stats["credit_count"] += 1
    else:
        stats["debit_count"] += 1


def _add_incoming(stats: dict[str, Any], transaction_type: str, amount: float, step: int) -> None:
    if transaction_type not in {"TRANSFER", "CASH_IN"}:
        return
    stats["incoming_count"] += 1
    stats["incoming_amount"] += amount
    stats["steps"].add(step)
    stats["amounts"].append(amount)


def activity_regularity(steps: set[int]) -> float:
    if len(steps) < 2:
        return 0.0
    ordered = sorted(steps)
    gaps = [right - left for left, right in zip(ordered, ordered[1:])]
    mean_gap = sum(gaps) / len(gaps)
    if mean_gap <= 0:
        return 1.0
    variance = sum((gap - mean_gap) ** 2 for gap in gaps) / len(gaps)
    return round(max(0.0, min(1.0, 1.0 - (variance**0.5 / mean_gap))), 4)


def build_profiles(
    csv_path: Path,
    *,
    sample_modulus: int = 1_000,
    max_profiles: int = 500,
    min_transactions: int = 3,
    chunksize: int = 200_000,
) -> pd.DataFrame:
    """Stream PaySim and retain only a deterministic, small profile sample."""
    if sample_modulus < 1 or max_profiles < 1 or min_transactions < 1:
        raise ValueError("sample_modulus, max_profiles, and min_transactions must be positive")
    header = pd.read_csv(csv_path, nrows=0)
    missing = REQUIRED_COLUMNS - set(header.columns)
    if missing:
        raise ValueError(f"PaySim CSV is missing required columns: {sorted(missing)}")

    profiles: dict[str, dict[str, Any]] = {}
    columns = ["step", "type", "amount", "nameOrig", "nameDest"]
    for chunk in pd.read_csv(csv_path, usecols=columns, chunksize=chunksize):
        chunk = chunk[chunk["type"].isin(UPI_EQUIVALENT_TYPES)]
        for row in chunk.itertuples(index=False):
            origin = str(row.nameOrig)
            destination = str(row.nameDest)
            candidates = [(origin, True), (destination, False)]
            for account, outgoing in candidates:
                if account.startswith("M") or stable_bucket(account, sample_modulus) != 0:
                    continue
                stats = profiles.setdefault(account, _empty_stats())
                if outgoing:
                    _add_outgoing(stats, str(row.type), float(row.amount), int(row.step))
                else:
                    _add_incoming(stats, str(row.type), float(row.amount), int(row.step))

    output = []
    for account, stats in profiles.items():
        transactions = stats["outgoing_count"] + stats["incoming_count"]
        if transactions < min_transactions:
            continue
        total_amount = stats["outgoing_amount"] + stats["incoming_amount"]
        output.append(
            {
                "benchmark_profile_id": safe_profile_id(account),
                "benchmark_origin": "PAYSIM_SYNTHETIC_UPI_LIKE",
                "transaction_count": transactions,
                "active_hour_count": len(stats["steps"]),
                "activity_regularity": activity_regularity(stats["steps"]),
                "average_ticket_size": round(total_amount / transactions, 2),
                "median_ticket_size": round(float(pd.Series(stats["amounts"]).median()), 2),
                "merchant_payment_ratio": round(stats["merchant_count"] / max(1, stats["outgoing_count"]), 4),
                "p2p_transfer_ratio": round(stats["p2p_count"] / max(1, stats["outgoing_count"]), 4),
                "account_credit_ratio": round(stats["credit_count"] / max(1, stats["outgoing_count"]), 4),
                "debit_outflow_ratio": round(stats["debit_count"] / max(1, stats["outgoing_count"]), 4),
                "aggregate_inflow_amount": round(stats["incoming_amount"], 2),
                "aggregate_outflow_amount": round(stats["outgoing_amount"], 2),
            }
        )
    if not output:
        return pd.DataFrame()
    frame = pd.DataFrame(output)
    # The benchmark is more useful when it compares real activity patterns,
    # not single isolated events. No original account identifier is retained.
    return frame.sort_values(["transaction_count", "benchmark_profile_id"], ascending=[False, True]).head(max_profiles).reset_index(drop=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build aggregate PaySim UPI-like benchmark profiles")
    parser.add_argument("--input-path", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/paysim_upi_benchmark_profiles.csv"))
    parser.add_argument("--sample-modulus", type=int, default=1_000)
    parser.add_argument("--max-profiles", type=int, default=500)
    parser.add_argument("--min-transactions", type=int, default=3)
    parser.add_argument("--chunksize", type=int, default=200_000)
    args = parser.parse_args()
    frame = build_profiles(
        args.input_path,
        sample_modulus=args.sample_modulus,
        max_profiles=args.max_profiles,
        min_transactions=args.min_transactions,
        chunksize=args.chunksize,
    )
    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(args.output_path, index=False)
    print(f"Wrote {len(frame)} aggregate benchmark profiles to {args.output_path}")
    print("PaySim is synthetic benchmark data only; this output is not used in live NADI underwriting.")


if __name__ == "__main__":
    main()
