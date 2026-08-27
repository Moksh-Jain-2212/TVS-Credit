"""Add repayment envelope outputs to the feature dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.repayment_envelope import POLICY_PATH, generate_repayment_envelope, load_envelope_policy


ENVELOPE_COLUMNS = [
    "repayment_all_evaluated_combinations",
    "repayment_safe_combinations",
    "maximum_safe_exposure",
    "recommended_amount",
    "recommended_tenure",
    "recommended_emi",
]


def add_repayment_envelope(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
    policy_path: Path = POLICY_PATH,
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    policy = load_envelope_policy(policy_path)
    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in ENVELOPE_COLUMNS if column in frame.columns])

    envelopes = [generate_repayment_envelope(row, policy) for _, row in frame.iterrows()]
    frame["repayment_all_evaluated_combinations"] = [
        json.dumps(item["all_evaluated_combinations"], sort_keys=True) for item in envelopes
    ]
    frame["repayment_safe_combinations"] = [
        json.dumps(item["safe_combinations"], sort_keys=True) for item in envelopes
    ]
    frame["maximum_safe_exposure"] = [item["maximum_safe_exposure"] for item in envelopes]
    frame["recommended_amount"] = [item["recommended_amount"] for item in envelopes]
    frame["recommended_tenure"] = [item["recommended_tenure"] for item in envelopes]
    frame["recommended_emi"] = [item["recommended_emi"] for item in envelopes]

    if frame["loan_id"].duplicated().any():
        raise ValueError("Envelope dataset contains duplicate loan_id values")
    if (frame["maximum_safe_exposure"] < 0).any():
        raise ValueError("Maximum safe exposure cannot be negative")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--policy-path", type=Path, default=POLICY_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = add_repayment_envelope(args.features_path, args.output_path, args.policy_path)
    safe_count = int((frame["maximum_safe_exposure"] > 0).sum())
    print(f"Wrote repayment envelopes to {args.output_path} with {len(frame)} rows.")
    print(f"Borrowers with at least one safe combination: {safe_count}")


if __name__ == "__main__":
    main()
