"""Train baseline and challenger repayment risk models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


TARGET_COLUMN = "repayment_default_target"
KNOWN_OUTCOME_COLUMN = "repayment_outcome_known"
MODEL_VERSION = "historical-risk-v1"
FEATURE_SCHEMA_VERSION = "nadi-feature-schema-v1"

LEAKAGE_COLUMNS = {
    "loan_status_target",
    "loan_status_from_source",
    "loan_status_meaning",
    "repayment_outcome_known",
    "repayment_default_target",
    "target_exclusion_reason",
}

IDENTIFIER_COLUMNS = {
    "loan_id",
    "account_id",
    "primary_client_id",
    "primary_client_birth_number",
}

DATE_COLUMNS = {
    "loan_date",
    "account_open_date",
    "pre_loan_first_transaction_date",
    "pre_loan_last_transaction_date",
}

EXCLUDED_COLUMNS = LEAKAGE_COLUMNS | IDENTIFIER_COLUMNS | DATE_COLUMNS


def load_modelling_data(features_path: Path) -> pd.DataFrame:
    if not features_path.exists():
        raise FileNotFoundError(f"Missing feature dataset: {features_path}")
    frame = pd.read_csv(features_path)
    required = {TARGET_COLUMN, KNOWN_OUTCOME_COLUMN, "loan_date"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required modelling columns: {sorted(missing)}")

    known = frame[frame[KNOWN_OUTCOME_COLUMN] == True].copy()
    known[TARGET_COLUMN] = known[TARGET_COLUMN].astype(int)
    known["loan_date"] = pd.to_datetime(known["loan_date"])
    if known[TARGET_COLUMN].nunique() < 2:
        raise ValueError("Known-outcome modelling data must contain both classes")
    return known.sort_values("loan_date").reset_index(drop=True)


def feature_columns(frame: pd.DataFrame) -> list[str]:
    columns = [column for column in frame.columns if column not in EXCLUDED_COLUMNS]
    if not columns:
        raise ValueError("No model feature columns remain after leakage exclusions")
    return columns


def temporal_split(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = frame[frame["loan_date"].dt.year <= 1995].copy()
    validation = frame[frame["loan_date"].dt.year == 1996].copy()
    test = frame[frame["loan_date"].dt.year >= 1997].copy()

    for name, split in {"train": train, "validation": validation, "test": test}.items():
        if split.empty:
            raise ValueError(f"{name} split is empty")
        if split[TARGET_COLUMN].nunique() < 2:
            raise ValueError(f"{name} split must contain both target classes")
    return train, validation, test


def build_preprocessor(frame: pd.DataFrame, columns: list[str]) -> tuple[ColumnTransformer, list[str], list[str]]:
    numeric_columns = [
        column
        for column in columns
        if pd.api.types.is_numeric_dtype(frame[column]) or pd.api.types.is_bool_dtype(frame[column])
    ]
    categorical_columns = [column for column in columns if column not in numeric_columns]
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                numeric_columns,
            ),
            (
                "categorical",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="constant", fill_value="missing")),
                        ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
                    ]
                ),
                categorical_columns,
            ),
        ],
        remainder="drop",
    )
    return preprocessor, numeric_columns, categorical_columns


def build_model_pipeline(model_name: str, preprocessor: ColumnTransformer) -> Pipeline:
    if model_name == "logistic_regression":
        classifier = LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42)
    elif model_name == "gradient_boosting":
        classifier = GradientBoostingClassifier(random_state=42)
    else:
        raise ValueError(f"Unknown model name: {model_name}")
    return Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])


def calibration_bins(y_true: pd.Series, y_prob: np.ndarray, bins: int = 5) -> list[dict[str, float | int]]:
    data = pd.DataFrame({"target": y_true.to_numpy(), "probability": y_prob})
    data["bin"] = pd.cut(data["probability"], bins=np.linspace(0, 1, bins + 1), include_lowest=True)
    rows: list[dict[str, float | int]] = []
    for _, group in data.groupby("bin", observed=True):
        rows.append(
            {
                "count": int(len(group)),
                "mean_predicted_probability": float(group["probability"].mean()),
                "observed_default_rate": float(group["target"].mean()),
            }
        )
    return rows


def evaluate_model(model: Pipeline, split: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    y_true = split[TARGET_COLUMN].astype(int)
    y_prob = model.predict_proba(split[columns])[:, 1]
    y_pred = (y_prob >= 0.5).astype(int)
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, average="binary", zero_division=0
    )
    matrix = confusion_matrix(y_true, y_pred, labels=[0, 1])
    return {
        "roc_auc": float(roc_auc_score(y_true, y_prob)),
        "pr_auc": float(average_precision_score(y_true, y_prob)),
        "brier_score": float(brier_score_loss(y_true, y_prob)),
        "confusion_matrix": matrix.tolist(),
        "risky_loan_recall": float(recall),
        "precision": float(precision),
        "f1": float(f1),
        "calibration": calibration_bins(y_true, y_prob),
    }


def train_models(train: pd.DataFrame, columns: list[str]) -> dict[str, Pipeline]:
    preprocessor, _, _ = build_preprocessor(train, columns)
    models = {
        "logistic_regression": build_model_pipeline("logistic_regression", preprocessor),
        "gradient_boosting": build_model_pipeline("gradient_boosting", preprocessor),
    }
    for model in models.values():
        model.fit(train[columns], train[TARGET_COLUMN].astype(int))
    return models


def choose_model(validation_metrics: dict[str, dict[str, Any]]) -> str:
    return max(validation_metrics, key=lambda name: validation_metrics[name]["pr_auc"])


def build_model_input_doc(columns: list[str], numeric_columns: list[str], categorical_columns: list[str]) -> str:
    return f"""# Repayment Risk Model Inputs

Generated by `scripts/train_risk_model.py`.

## Target

`repayment_default_target` on known final outcomes only: `0` for status A and `1` for status B.

## Methodology

Rows with running loan statuses C/D are excluded from supervised training and evaluation. Splits are temporal by `loan_date`: train through 1995, validation in 1996, and test from 1997 onward.

## Excluded Leakage Columns

{', '.join(f'`{column}`' for column in sorted(EXCLUDED_COLUMNS))}

## Numeric Inputs

{', '.join(f'`{column}`' for column in numeric_columns)}

## Categorical Inputs

{', '.join(f'`{column}`' for column in categorical_columns)}

## All Model Inputs

{', '.join(f'`{column}`' for column in columns)}
"""


def train_risk_model(
    features_path: Path = Path("data/processed/nadi_features.csv"),
    model_dir: Path = Path("models"),
    docs_path: Path = Path("docs/risk_model_inputs.md"),
) -> dict[str, Any]:
    data = load_modelling_data(features_path)
    columns = feature_columns(data)
    train, validation, test = temporal_split(data)
    preprocessor, numeric_columns, categorical_columns = build_preprocessor(train, columns)
    models = {
        "logistic_regression": build_model_pipeline("logistic_regression", preprocessor),
        "gradient_boosting": build_model_pipeline("gradient_boosting", preprocessor),
    }

    metrics: dict[str, dict[str, dict[str, Any]]] = {}
    for name, model in models.items():
        model.fit(train[columns], train[TARGET_COLUMN].astype(int))
        metrics[name] = {
            "validation": evaluate_model(model, validation, columns),
            "test": evaluate_model(model, test, columns),
        }

    selected_model_name = choose_model({name: item["validation"] for name, item in metrics.items()})
    selected_model = models[selected_model_name]
    warning = None
    if metrics[selected_model_name]["validation"]["roc_auc"] >= 0.98:
        warning = "Validation ROC-AUC is very high; inspect for leakage before trusting the model."

    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "repayment_risk_model.joblib"
    metrics_path = model_dir / "repayment_risk_metrics.json"
    joblib.dump(
        {
            "model_name": selected_model_name,
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model": selected_model,
            "feature_columns": columns,
            "target_column": TARGET_COLUMN,
        },
        model_path,
    )

    split_summary = {
        "train": {"rows": int(len(train)), "bad_rate": float(train[TARGET_COLUMN].mean())},
        "validation": {
            "rows": int(len(validation)),
            "bad_rate": float(validation[TARGET_COLUMN].mean()),
        },
        "test": {"rows": int(len(test)), "bad_rate": float(test[TARGET_COLUMN].mean())},
    }
    result = {
        "selected_model": selected_model_name,
        "model_version": MODEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_path": str(model_path),
        "split_summary": split_summary,
        "metrics": metrics,
        "warning": warning,
    }
    metrics_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(
        build_model_input_doc(columns, numeric_columns, categorical_columns),
        encoding="utf-8",
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--docs-path", type=Path, default=Path("docs/risk_model_inputs.md"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = train_risk_model(args.features_path, args.model_dir, args.docs_path)
    print(f"Selected model: {result['selected_model']}")
    print(f"Saved model: {result['model_path']}")
    print(f"Split summary: {result['split_summary']}")
    print(f"Validation metrics: {result['metrics'][result['selected_model']]['validation']}")
    print(f"Test metrics: {result['metrics'][result['selected_model']]['test']}")
    if result["warning"]:
        print(f"Warning: {result['warning']}")


if __name__ == "__main__":
    main()
