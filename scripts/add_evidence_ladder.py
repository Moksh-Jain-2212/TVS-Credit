"""Add ranked additional-evidence recommendations."""

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

from app.services.evidence_ladder import POLICY_PATH, load_evidence_ladder_policy, rank_evidence_options


EVIDENCE_LADDER_COLUMNS = [
    "evidence_ladder_status",
    "recommended_evidence",
    "expected_confidence_improvement",
    "evidence_reason",
    "evidence_friction_level",
    "evidence_privacy_cost_level",
    "evidence_ladder_rankings",
]


def add_evidence_ladder(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
    policy_path: Path = POLICY_PATH,
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    policy = load_evidence_ladder_policy(policy_path)
    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in EVIDENCE_LADDER_COLUMNS if column in frame.columns])

    ladders = [rank_evidence_options(row, policy) for _, row in frame.iterrows()]
    frame["evidence_ladder_status"] = [item["status"] for item in ladders]
    frame["recommended_evidence"] = [item["recommended_evidence"] for item in ladders]
    frame["expected_confidence_improvement"] = [
        item["expected_confidence_improvement"] for item in ladders
    ]
    frame["evidence_reason"] = [item["reason"] for item in ladders]
    frame["evidence_friction_level"] = [item["friction_level"] for item in ladders]
    frame["evidence_privacy_cost_level"] = [item["privacy_cost_level"] for item in ladders]
    frame["evidence_ladder_rankings"] = [
        json.dumps(item["rankings"], sort_keys=True) for item in ladders
    ]

    if frame["loan_id"].duplicated().any():
        raise ValueError("Evidence ladder dataset contains duplicate loan_id values")
    if (frame["expected_confidence_improvement"] < 0).any():
        raise ValueError("Expected confidence improvement cannot be negative")

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
    frame = add_evidence_ladder(args.features_path, args.output_path, args.policy_path)
    print(f"Wrote evidence ladder outputs to {args.output_path} with {len(frame)} rows.")
    print(f"Ladder status counts: {frame['evidence_ladder_status'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
