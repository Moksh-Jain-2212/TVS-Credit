"""Train a compact, auditable default-risk model from Home Credit features."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split


TARGET = "TARGET"
IDENTIFIERS = {"SK_ID_CURR", TARGET}
FAIRNESS_COLUMNS = ("CODE_GENDER",)


def fairness_slices(frame: pd.DataFrame, y_true: pd.Series, probability: np.ndarray) -> dict:
    report = {}
    for column in FAIRNESS_COLUMNS:
        if column not in frame:
            continue
        rows = []
        for value, group in frame.assign(_actual=y_true.to_numpy(), _probability=probability).groupby(column, dropna=False):
            if len(group) < 100 or group._actual.nunique() < 2:
                continue
            rows.append({"group": "missing" if pd.isna(value) else str(value), "count": int(len(group)), "default_rate": float(group._actual.mean()), "roc_auc": float(roc_auc_score(group._actual, group._probability))})
        report[column] = rows
    return report


def train(features_path: Path, model_path: Path, metrics_path: Path) -> dict:
    frame = pd.read_csv(features_path)
    if TARGET not in frame:
        raise ValueError(f"{features_path} must contain {TARGET}")
    feature_columns = [column for column in frame.columns if column not in IDENTIFIERS and column not in FAIRNESS_COLUMNS and pd.api.types.is_numeric_dtype(frame[column])]
    if not feature_columns:
        raise ValueError("No numeric Home Credit features available")
    x_train, x_test, y_train, y_test = train_test_split(
        frame[feature_columns], frame[TARGET].astype(int), test_size=0.2, random_state=42, stratify=frame[TARGET]
    )
    logistic = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("classifier", LogisticRegression(max_iter=1000, class_weight="balanced", n_jobs=1)),
    ])
    gradient = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("classifier", HistGradientBoostingClassifier(max_iter=160, learning_rate=0.08, max_leaf_nodes=20, l2_regularization=1.0, random_state=42)),
    ])
    models = {"logistic_regression": logistic, "hist_gradient_boosting": gradient}
    comparison = {}
    fitted = {}
    for name, model in models.items():
        model.fit(x_train, y_train)
        probability = model.predict_proba(x_test)[:, 1]
        calibration = []
        buckets = pd.qcut(probability, q=10, duplicates="drop")
        for _, group in pd.DataFrame({"actual": y_test.to_numpy(), "prediction": probability, "bucket": buckets}).groupby("bucket", observed=True):
            calibration.append({"count": int(len(group)), "mean_prediction": float(group.prediction.mean()), "observed_default_rate": float(group.actual.mean())})
        comparison[name] = {"roc_auc": float(roc_auc_score(y_test, probability)), "pr_auc": float(average_precision_score(y_test, probability)), "brier_score": float(brier_score_loss(y_test, probability)), "calibration": calibration, "fairness_slices": fairness_slices(frame.loc[x_test.index], y_test, probability)}
        fitted[name] = model
    selected_name = max(comparison, key=lambda name: comparison[name]["pr_auc"])
    selected_model = fitted[selected_name]
    logistic_coefficients = logistic.named_steps["classifier"].coef_[0]
    importance = sorted(({"feature": feature, "absolute_standardized_coefficient": float(abs(value))} for feature, value in zip(feature_columns, logistic_coefficients)), key=lambda item: item["absolute_standardized_coefficient"], reverse=True)[:25]
    metrics = {
        "selected_model": selected_name,
        "comparison": comparison,
        "feature_importance_logistic": importance,
        "train_rows": int(len(x_train)), "test_rows": int(len(x_test)),
        "default_rate": float(frame[TARGET].mean()),
    }
    artifact = {
        "model_name": selected_name, "model_version": "home-credit-risk-v2",
        "feature_schema_version": "home-credit-aggregate-v1", "trained_at": datetime.now(timezone.utc).isoformat(),
        "source_dataset": "Home Credit Default Risk", "target_column": TARGET,
        "feature_columns": feature_columns, "model": selected_model,
        "serving_note": "Offline benchmark only; do not score NADI applications without feature-provenance mapping.",
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, model_path)
    metrics_path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/home_credit_features.csv"))
    parser.add_argument("--model-path", type=Path, default=Path("models/home_credit_risk_model.joblib"))
    parser.add_argument("--metrics-path", type=Path, default=Path("models/home_credit_risk_metrics.json"))
    args = parser.parse_args()
    print(json.dumps(train(args.features_path, args.model_path, args.metrics_path), indent=2))


if __name__ == "__main__":
    main()
