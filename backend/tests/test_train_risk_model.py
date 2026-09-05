from pathlib import Path

import joblib
import pandas as pd

from scripts.train_risk_model import (
    EXCLUDED_COLUMNS,
    feature_columns,
    load_modelling_data,
    train_risk_model,
)


def write_risk_features(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    loan_id = 1
    for year, bad_count, good_count in [(1995, 3, 8), (1996, 2, 6), (1997, 2, 6)]:
        for index in range(bad_count):
            rows.append(
                {
                    "loan_id": loan_id,
                    "loan_date": f"{year}-01-{index + 1:02d}",
                    "requested_amount": 20000 + index,
                    "duration_months": 24,
                    "scheduled_payment": 1200.0,
                    "mean_monthly_inflow": 900.0,
                    "income_volatility": 0.8,
                    "account_frequency": "monthly",
                    "stability_history_status": "sufficient_history",
                    "loan_status_target": "B",
                    "loan_status_from_source": "B",
                    "repayment_outcome_known": True,
                    "repayment_default_target": 1,
                }
            )
            loan_id += 1
        for index in range(good_count):
            rows.append(
                {
                    "loan_id": loan_id,
                    "loan_date": f"{year}-02-{index + 1:02d}",
                    "requested_amount": 10000 + index,
                    "duration_months": 12,
                    "scheduled_payment": 800.0,
                    "mean_monthly_inflow": 2500.0,
                    "income_volatility": 0.2,
                    "account_frequency": "monthly",
                    "stability_history_status": "sufficient_history",
                    "loan_status_target": "A",
                    "loan_status_from_source": "A",
                    "repayment_outcome_known": True,
                    "repayment_default_target": 0,
                }
            )
            loan_id += 1
    rows.append(
        {
            "loan_id": loan_id,
            "loan_date": "1997-03-01",
            "requested_amount": 30000,
            "duration_months": 36,
            "scheduled_payment": 1500.0,
            "mean_monthly_inflow": 2000.0,
            "income_volatility": 0.4,
            "account_frequency": "monthly",
            "stability_history_status": "sufficient_history",
            "loan_status_target": "C",
            "loan_status_from_source": "C",
            "repayment_outcome_known": False,
            "repayment_default_target": "",
        }
    )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_feature_columns_exclude_target_and_status_leakage(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    write_risk_features(features_path)

    data = load_modelling_data(features_path)
    columns = feature_columns(data)

    assert not EXCLUDED_COLUMNS.intersection(columns)
    assert "mean_monthly_inflow" in columns
    assert data["repayment_default_target"].nunique() == 2


def test_train_risk_model_saves_model_metrics_and_input_doc(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    model_dir = tmp_path / "models"
    docs_path = tmp_path / "risk_model_inputs.md"
    write_risk_features(features_path)

    result = train_risk_model(features_path, model_dir, docs_path)

    model_path = model_dir / "repayment_risk_model.joblib"
    metrics_path = model_dir / "repayment_risk_metrics.json"
    artifact = joblib.load(model_path)

    assert result["selected_model"].endswith("_calibrated")
    assert "algorithm_availability" in result
    assert 0 < result["operating_threshold"] <= 0.5
    assert model_path.exists()
    assert metrics_path.exists()
    assert docs_path.exists()
    assert artifact["target_column"] == "repayment_default_target"
    assert artifact["selection_criterion"] == "highest validation PR-AUC"
    assert "loan_status_target" not in artifact["feature_columns"]
    assert "Validation metrics" not in docs_path.read_text(encoding="utf-8")
