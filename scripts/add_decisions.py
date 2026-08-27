"""Add four-state NADI decisions to the feature dataset."""

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

from app.services.decision_engine import POLICY_PATH, load_decision_policy, make_decision


DECISION_COLUMNS = [
    "decision_state",
    "decision_recommended_amount",
    "decision_recommended_tenure",
    "decision_recommended_emi",
    "decision_reasons",
]


def add_decisions(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
    policy_path: Path = POLICY_PATH,
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    policy = load_decision_policy(policy_path)
    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in DECISION_COLUMNS if column in frame.columns])

    decisions = [make_decision(row, policy) for _, row in frame.iterrows()]
    frame["decision_state"] = [item["decision_state"] for item in decisions]
    frame["decision_recommended_amount"] = [item["decision_recommended_amount"] for item in decisions]
    frame["decision_recommended_tenure"] = [item["decision_recommended_tenure"] for item in decisions]
    frame["decision_recommended_emi"] = [item["decision_recommended_emi"] for item in decisions]
    frame["decision_reasons"] = [json.dumps(item["decision_reasons"]) for item in decisions]

    allowed = {"APPROVE", "SAFE_TO_LEARN", "EVIDENCE_NEEDED", "NOT_CURRENTLY_AFFORDABLE"}
    if set(frame["decision_state"]) - allowed:
        raise ValueError("Decision engine produced an unsupported state")
    if frame["loan_id"].duplicated().any():
        raise ValueError("Decision dataset contains duplicate loan_id values")

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
    frame = add_decisions(args.features_path, args.output_path, args.policy_path)
    print(f"Wrote NADI decisions to {args.output_path} with {len(frame)} rows.")
    print(f"Decision counts: {frame['decision_state'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
