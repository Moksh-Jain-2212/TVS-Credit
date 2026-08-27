"""Add transparent evidence confidence scores to the feature dataset."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.evidence_confidence import POLICY_PATH, load_policy, score_evidence_confidence


OUTPUT_COLUMNS = [
    "confidence_score",
    "confidence_band",
    "confidence_reasons",
    "confidence_components",
    "risk_model_probability",
]


def predict_risk_probabilities(frame: pd.DataFrame, model_path: Path) -> pd.Series:
    if not model_path.exists():
        return pd.Series([pd.NA] * len(frame), index=frame.index)
    artifact = joblib.load(model_path)
    model = artifact["model"]
    feature_columns = artifact["feature_columns"]
    missing = [column for column in feature_columns if column not in frame.columns]
    if missing:
        raise ValueError(f"Feature dataset missing model input columns: {missing}")
    probabilities = model.predict_proba(frame[feature_columns])[:, 1]
    return pd.Series(probabilities, index=frame.index)


def add_evidence_confidence(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    output_path: Path = Path("data/processed/nadi_features.csv"),
    policy_path: Path = POLICY_PATH,
    model_path: Path = Path("models/repayment_risk_model.joblib"),
) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")

    policy = load_policy(policy_path)
    frame = pd.read_csv(features_path)
    frame = frame.drop(columns=[column for column in OUTPUT_COLUMNS if column in frame.columns])
    risk_probabilities = predict_risk_probabilities(frame, model_path)

    scored_rows: list[dict[str, Any]] = []
    for index, row in frame.iterrows():
        risk_probability = risk_probabilities.loc[index]
        risk_value = None if pd.isna(risk_probability) else float(risk_probability)
        scored_rows.append(score_evidence_confidence(row, policy, risk_value))

    frame["confidence_score"] = [row["confidence_score"] for row in scored_rows]
    frame["confidence_band"] = [row["confidence_band"] for row in scored_rows]
    frame["confidence_reasons"] = [json.dumps(row["reasons"]) for row in scored_rows]
    frame["confidence_components"] = [json.dumps(row["components"], sort_keys=True) for row in scored_rows]
    frame["risk_model_probability"] = risk_probabilities

    if frame["confidence_score"].isna().any():
        raise ValueError("Confidence scoring produced missing scores")
    if not frame["confidence_score"].between(0, 100).all():
        raise ValueError("Confidence scores must be between 0 and 100")
    if frame["loan_id"].duplicated().any():
        raise ValueError("Confidence dataset contains duplicate loan_id values")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output_path, index=False, encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--output-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--policy-path", type=Path, default=POLICY_PATH)
    parser.add_argument("--model-path", type=Path, default=Path("models/repayment_risk_model.joblib"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    frame = add_evidence_confidence(
        args.features_path,
        args.output_path,
        args.policy_path,
        args.model_path,
    )
    print(f"Wrote evidence confidence scores to {args.output_path} with {len(frame)} rows.")
    print(f"Confidence band counts: {frame['confidence_band'].value_counts().to_dict()}")


if __name__ == "__main__":
    main()
