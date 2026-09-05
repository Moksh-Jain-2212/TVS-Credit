"""Train baseline and challenger repayment risk models."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import ExtraTreesClassifier, GradientBoostingClassifier, StackingClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    fbeta_score,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ml.denoising import DenoisingAutoencoderRiskClassifier


TARGET_COLUMN = "repayment_default_target"
KNOWN_OUTCOME_COLUMN = "repayment_outcome_known"
MODEL_VERSION = "historical-risk-ensemble-v2"
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


def optional_tree_estimators() -> tuple[dict[str, Any], dict[str, bool]]:
    """Load specialised libraries lazily so a baseline remains runnable in CI."""
    estimators: dict[str, Any] = {}
    availability = {"lightgbm": False, "xgboost": False, "catboost": False}
    try:
        from lightgbm import LGBMClassifier
        estimators["lightgbm"] = LGBMClassifier(n_estimators=180, learning_rate=0.05, num_leaves=15, class_weight="balanced", random_state=42, verbosity=-1)
        availability["lightgbm"] = True
    except ImportError:
        pass
    try:
        from xgboost import XGBClassifier
        estimators["xgboost"] = XGBClassifier(n_estimators=180, max_depth=4, learning_rate=0.05, subsample=0.9, colsample_bytree=0.9, eval_metric="logloss", random_state=42, n_jobs=1)
        availability["xgboost"] = True
    except ImportError:
        pass
    try:
        from catboost import CatBoostClassifier
        estimators["catboost"] = CatBoostClassifier(iterations=180, depth=5, learning_rate=0.05, auto_class_weights="Balanced", random_seed=42, verbose=False, allow_writing_files=False)
        availability["catboost"] = True
    except ImportError:
        pass
    return estimators, availability


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
    elif model_name == "extra_trees":
        classifier = ExtraTreesClassifier(n_estimators=300, class_weight="balanced", random_state=42, n_jobs=-1)
    elif model_name == "dae_neural_network":
        classifier = DenoisingAutoencoderRiskClassifier()
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


def evaluate_model(
    model: Any, split: pd.DataFrame, columns: list[str], threshold: float = 0.5
) -> dict[str, Any]:
    y_true = split[TARGET_COLUMN].astype(int)
    y_prob = model.predict_proba(split[columns])[:, 1]
    y_pred = (y_prob >= threshold).astype(int)
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
        "operating_threshold": float(threshold),
        "review_rate": float(y_pred.mean()),
        "calibration": calibration_bins(y_true, y_prob),
    }


def choose_operating_threshold(y_true: pd.Series, probabilities: np.ndarray) -> float:
    """Choose a validation-only review threshold that prioritises default recall.

    The cap avoids sending every borrower to manual review. This is an
    operational review threshold, not an automatic decline threshold.
    """
    y = y_true.to_numpy(dtype=int)
    candidates = sorted(
        {0.01, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50,
         *(float(value) for value in probabilities if float(value) <= 0.50)}
    )
    options: list[tuple[float, float, float, float]] = []
    for threshold in candidates:
        predicted = (probabilities >= threshold).astype(int)
        review_rate = float(predicted.mean())
        if review_rate == 0.0 or review_rate > 0.40:
            continue
        precision, recall, _, _ = precision_recall_fscore_support(y, predicted, average="binary", zero_division=0)
        f2 = fbeta_score(y, predicted, beta=2, zero_division=0)
        options.append((float(f2), float(recall), float(precision), float(threshold)))
    if not options:
        return 0.5
    # F2 weights recall more than precision; ties favour higher precision and
    # a higher threshold, reducing unnecessary manual reviews.
    return max(options, key=lambda item: (item[0], item[1], item[2], item[3]))[3]


def train_models(train: pd.DataFrame, columns: list[str]) -> tuple[dict[str, Pipeline], dict[str, bool]]:
    preprocessor, _, _ = build_preprocessor(train, columns)
    models: dict[str, Pipeline] = {
        "logistic_regression": build_model_pipeline("logistic_regression", preprocessor),
        "extra_trees": build_model_pipeline("extra_trees", preprocessor),
        "dae_neural_network": build_model_pipeline("dae_neural_network", preprocessor),
        # Kept as a deterministic challenger when optional native libraries are unavailable.
        "gradient_boosting_fallback": build_model_pipeline("gradient_boosting", preprocessor),
    }
    specialised, availability = optional_tree_estimators()
    for name, classifier in specialised.items():
        models[name] = Pipeline(steps=[("preprocessor", preprocessor), ("classifier", classifier)])

    # Level 1 base models -> logistic meta-learner.  This produces the final
    # probability of default while retaining each constituent model for audit.
    stack_members = [(name, model) for name, model in models.items() if name != "gradient_boosting_fallback"]
    class_counts = train[TARGET_COLUMN].value_counts()
    cv = min(3, int(class_counts.min()))
    if cv >= 2:
        models["stacked_ensemble"] = StackingClassifier(
            estimators=stack_members,
            final_estimator=LogisticRegression(max_iter=1000, class_weight="balanced", random_state=42),
            stack_method="predict_proba",
            cv=cv,
            n_jobs=1,
        )
    for model in models.values():
        model.fit(train[columns], train[TARGET_COLUMN].astype(int))
    return models, availability


def choose_model(validation_metrics: dict[str, dict[str, Any]]) -> str:
    return max(validation_metrics, key=lambda name: validation_metrics[name]["pr_auc"])


def build_model_input_doc(columns: list[str], numeric_columns: list[str], categorical_columns: list[str]) -> str:
    return f"""# Repayment Risk Model Inputs

Generated by `scripts/train_risk_model.py`.

## Target

`repayment_default_target` on known final outcomes only: `0` for status A and `1` for status B.

## Methodology

Rows with running loan statuses C/D are excluded from supervised training and evaluation. Splits are temporal by `loan_date`: train through 1995, validation in 1996, and test from 1997 onward.

The production score is a level-2 stacked ensemble: Logistic Regression,
LightGBM, XGBoost, CatBoost, ExtraTrees, and a denoising-autoencoder neural
contributor feed a Logistic Regression meta-model. LightGBM, XGBoost and
CatBoost are used when their optional packages are installed; the artifact
records their availability. The selected stack is calibrated on the temporal
validation period with sigmoid calibration and evaluated only on the later
test period.

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
    models, algorithm_availability = train_models(train, columns)

    metrics: dict[str, dict[str, dict[str, Any]]] = {}
    for name, model in models.items():
        model.fit(train[columns], train[TARGET_COLUMN].astype(int))
        metrics[name] = {
            "validation": evaluate_model(model, validation, columns),
            "test": evaluate_model(model, test, columns),
        }

    # Select the validation champion instead of assuming the most complex
    # ensemble always wins. PR-AUC is the primary criterion because observed
    # defaults are rare in the historical data.
    selected_model_name = choose_model({name: item["validation"] for name, item in metrics.items()})
    selected_model = models[selected_model_name]
    calibrated_model = CalibratedClassifierCV(FrozenEstimator(selected_model), method="sigmoid", cv=2)
    calibrated_model.fit(validation[columns], validation[TARGET_COLUMN].astype(int))
    operating_threshold = choose_operating_threshold(
        validation[TARGET_COLUMN].astype(int),
        calibrated_model.predict_proba(validation[columns])[:, 1],
    )
    deployed_model_name = f"{selected_model_name}_calibrated"
    metrics[deployed_model_name] = {
        "test": evaluate_model(calibrated_model, test, columns, threshold=operating_threshold),
        "calibration_method": "sigmoid",
        "calibration_period": "validation_1996",
        "operating_threshold_selection": "validation_f2_max_with_40_percent_review_cap",
        "operating_threshold": operating_threshold,
    }
    warning = None
    if metrics[selected_model_name]["validation"]["roc_auc"] >= 0.98:
        warning = "Validation ROC-AUC is very high; inspect for leakage before trusting the model."
    if int(test[TARGET_COLUMN].sum()) < 20:
        warning = ((warning + " ") if warning else "") + (
            f"Test split contains only {int(test[TARGET_COLUMN].sum())} observed defaults; "
            "treat performance metrics as directional."
        )

    model_dir.mkdir(parents=True, exist_ok=True)
    model_path = model_dir / "repayment_risk_model.joblib"
    metrics_path = model_dir / "repayment_risk_metrics.json"
    joblib.dump(
        {
            "model_name": deployed_model_name,
            "model_version": MODEL_VERSION,
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "model": calibrated_model,
            "feature_columns": columns,
            "target_column": TARGET_COLUMN,
            "architecture": "benchmark candidates including stacked ensemble -> validation PR-AUC champion -> calibrated probability of default",
            "algorithm_availability": algorithm_availability,
            "selection_criterion": "highest validation PR-AUC",
            "operating_threshold": operating_threshold,
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
        "selected_model": deployed_model_name,
        "model_version": MODEL_VERSION,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "model_path": str(model_path),
        "split_summary": split_summary,
        "metrics": metrics,
        "algorithm_availability": algorithm_availability,
        "selection_criterion": "highest validation PR-AUC",
        "operating_threshold": operating_threshold,
        "warning": warning,
    }
    metrics_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(
        build_model_input_doc(columns, numeric_columns, categorical_columns),
        encoding="utf-8",
    )
    return result


def print_debug_report(result: dict[str, Any]) -> None:
    """Print an auditable, terminal-friendly model-comparison report."""
    print("\n=== NADI RISK MODEL DEBUG REPORT ===")
    print(f"Deployed model: {result['selected_model']}")
    print(f"Model version: {result['model_version']}")
    print(f"Algorithm availability: {result['algorithm_availability']}")
    print(f"Validation-selected review threshold: {result['operating_threshold']:.3f}")
    print("Selection criterion: highest validation PR-AUC; review threshold maximises validation F2 under a 40% review cap.")
    print("\nModel                         Val ROC   Val PR    Test ROC  Test PR   Test Brier")
    print("-" * 84)
    validation_rows: list[tuple[str, dict[str, Any]]] = []
    test_rows: list[tuple[str, dict[str, Any]]] = []
    for name, item in result["metrics"].items():
        validation = item.get("validation")
        test = item.get("test")
        if validation:
            validation_rows.append((name, validation))
        if test:
            test_rows.append((name, test))
        val_roc = f"{validation['roc_auc']:.3f}" if validation else "-"
        val_pr = f"{validation['pr_auc']:.3f}" if validation else "-"
        test_roc = f"{test['roc_auc']:.3f}" if test else "-"
        test_pr = f"{test['pr_auc']:.3f}" if test else "-"
        brier = f"{test['brier_score']:.3f}" if test else "-"
        deployed = " *" if name == result["selected_model"] else ""
        print(f"{name:<29} {val_roc:>7}   {val_pr:>7}   {test_roc:>7}   {test_pr:>7}   {brier:>10}{deployed}")

    if validation_rows:
        best_val_roc = max(validation_rows, key=lambda item: item[1]["roc_auc"])[0]
        best_val_pr = max(validation_rows, key=lambda item: item[1]["pr_auc"])[0]
        print(f"\nBest validation ROC-AUC: {best_val_roc}")
        print(f"Best validation PR-AUC:  {best_val_pr}")
    if test_rows:
        best_test_brier = min(test_rows, key=lambda item: item[1]["brier_score"])[0]
        print(f"Best test calibration (lowest Brier): {best_test_brier}")
    print("* = deployed calibrated model")
    if result.get("warning"):
        print(f"Data warning: {result['warning']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features-path", type=Path, default=Path("data/processed/nadi_features.csv"))
    parser.add_argument("--model-dir", type=Path, default=Path("models"))
    parser.add_argument("--docs-path", type=Path, default=Path("docs/risk_model_inputs.md"))
    parser.add_argument("--debug", action="store_true", help="Print per-model benchmark metrics after training")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = train_risk_model(args.features_path, args.model_dir, args.docs_path)
    base_selected_model_name = result["selected_model"].removesuffix("_calibrated")
    print(f"Selected model: {result['selected_model']}")
    print(f"Saved model: {result['model_path']}")
    print(f"Split summary: {result['split_summary']}")
    print(f"Validation metrics: {result['metrics'][base_selected_model_name]['validation']}")
    print(f"Calibrated test metrics: {result['metrics'][result['selected_model']]['test']}")
    if result["warning"]:
        print(f"Warning: {result['warning']}")
    if args.debug:
        print_debug_report(result)


if __name__ == "__main__":
    main()
