"""Add SAFE_TO_LEARN starter recommendations and simulated adaptive paths."""

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

from app.services.adaptive_credit_path import (
    POLICY_PATH,
    load_adaptive_credit_policy,
    simulate_adaptive_path,
    starter_recommendation,
)
from app.services.decision_engine import load_decision_policy
from app.services.repayment_envelope import load_envelope_policy


ADAPTIVE_COLUMNS = [
    "starter_credit_eligible",
    "starter_amount",
    "starter_tenure",
    "starter_emi",
    "starter_reason",
    "adaptive_path_simulated",
    "adaptive_path_events",
    "adaptive_path_observations",
    "adaptive_path_final_decision",
    "adaptive_path_final_recommended_amount",
]


def add_adaptive_credit_path(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
    adaptive_policy_path: Path = POLICY_PATH,
    simulated_events: list[str] | None = None,
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    events = simulated_events or ["on_time", "late", "missed"]
    adaptive_policy = load_adaptive_credit_policy(adaptive_policy_path)
    envelope_policy = load_envelope_policy()
    decision_policy = load_decision_policy()
    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in ADAPTIVE_COLUMNS if column in frame.columns])

    starters = [starter_recommendation(row, adaptive_policy) for _, row in frame.iterrows()]
    paths = [
        simulate_adaptive_path(row, events, adaptive_policy, envelope_policy, decision_policy)
        if row.get("decision_state") == "SAFE_TO_LEARN"
        else {
            "simulated_observations": [],
            "final_decision_state": row.get("decision_state"),
            "final_recommended_amount": 0.0,
        }
        for _, row in frame.iterrows()
    ]

    frame["starter_credit_eligible"] = [item["starter_credit_eligible"] for item in starters]
    frame["starter_amount"] = [item["starter_amount"] for item in starters]
    frame["starter_tenure"] = [item["starter_tenure"] for item in starters]
    frame["starter_emi"] = [item["starter_emi"] for item in starters]
    frame["starter_reason"] = [item["starter_reason"] for item in starters]
    frame["adaptive_path_simulated"] = [bool(item["simulated_observations"]) for item in paths]
    frame["adaptive_path_events"] = [
        json.dumps(events if item["simulated_observations"] else []) for item in paths
    ]
    frame["adaptive_path_observations"] = [
        json.dumps(item["simulated_observations"], sort_keys=True) for item in paths
    ]
    frame["adaptive_path_final_decision"] = [item["final_decision_state"] for item in paths]
    frame["adaptive_path_final_recommended_amount"] = [
        item["final_recommended_amount"] for item in paths
    ]

    if frame["loan_id"].duplicated().any():
        raise ValueError("Adaptive path dataset contains duplicate loan_id values")
    if (frame["starter_amount"] < 0).any():
        raise ValueError("Starter amount cannot be negative")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--adaptive-policy-path", type=Path, default=POLICY_PATH)
    parser.add_argument(
        "--simulated-events",
        nargs="*",
        default=["on_time", "late", "missed"],
        help="Clearly labelled simulated repayment events to apply to SAFE_TO_LEARN rows.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = add_adaptive_credit_path(
        args.features_path,
        args.output_path,
        args.adaptive_policy_path,
        args.simulated_events,
    )
    print(f"Wrote adaptive credit paths to {args.output_path} with {len(frame)} rows.")
    print(f"Starter eligible rows: {int(frame['starter_credit_eligible'].sum())}")
    print(f"Simulated path rows: {int(frame['adaptive_path_simulated'].sum())}")


if __name__ == "__main__":
    main()
