"""Add loan-officer and borrower explanations to the feature dataset."""

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

from app.services.explainability import EXPLANATION_COLUMNS, build_explanations


def add_explanations(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in EXPLANATION_COLUMNS if column in frame.columns])
    explanations = [build_explanations(row) for _, row in frame.iterrows()]
    frame["loan_officer_explanation"] = [
        json.dumps(item["loan_officer"], sort_keys=True) for item in explanations
    ]
    frame["borrower_explanation"] = [
        json.dumps(item["borrower"], sort_keys=True) for item in explanations
    ]

    if frame["loan_id"].duplicated().any():
        raise ValueError("Explanation dataset contains duplicate loan_id values")
    if frame["loan_officer_explanation"].isna().any() or frame["borrower_explanation"].isna().any():
        raise ValueError("Explanation columns cannot contain missing values")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = add_explanations(args.features_path, args.output_path)
    print(f"Wrote explanations to {args.output_path} with {len(frame)} rows.")
    print("Explanation views: loan_officer_explanation, borrower_explanation")


if __name__ == "__main__":
    main()
