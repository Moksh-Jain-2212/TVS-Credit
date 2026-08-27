"""Add configurable financial stress simulation outputs."""

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

from app.services.stress_simulator import POLICY_PATH, load_stress_policy, simulate_borrower_stress


STRESS_COLUMNS = [
    "stress_scenario_survival",
    "stress_probability",
    "stress_minimum_remaining_cash_buffer",
    "stress_worst_scenario",
    "stress_worst_projected_period",
    "stress_scenario_results",
]


def add_stress_simulation(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
    policy_path: Path = POLICY_PATH,
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    policy = load_stress_policy(policy_path)
    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in STRESS_COLUMNS if column in frame.columns])

    simulations = [simulate_borrower_stress(row, policy) for _, row in frame.iterrows()]
    frame["stress_scenario_survival"] = [
        json.dumps(item["scenario_survival"], sort_keys=True) for item in simulations
    ]
    frame["stress_probability"] = [item["stress_probability"] for item in simulations]
    frame["stress_minimum_remaining_cash_buffer"] = [
        item["minimum_remaining_cash_buffer"] for item in simulations
    ]
    frame["stress_worst_scenario"] = [item["worst_scenario"] for item in simulations]
    frame["stress_worst_projected_period"] = [
        item["worst_projected_period"] for item in simulations
    ]
    frame["stress_scenario_results"] = [
        json.dumps(item["scenario_results"], sort_keys=True) for item in simulations
    ]

    if frame["loan_id"].duplicated().any():
        raise ValueError("Stress dataset contains duplicate loan_id values")
    if not frame["stress_probability"].between(0, 1).all():
        raise ValueError("Stress probabilities must be between 0 and 1")

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
    frame = add_stress_simulation(args.features_path, args.output_path, args.policy_path)
    print(f"Wrote stress simulation outputs to {args.output_path} with {len(frame)} rows.")
    print(f"Worst scenario counts: {frame['stress_worst_scenario'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
