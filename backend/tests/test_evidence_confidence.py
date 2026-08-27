import json
from pathlib import Path

import pandas as pd

from app.services.evidence_confidence import load_policy, score_evidence_confidence
from scripts.add_evidence_confidence import add_evidence_confidence


def strong_evidence_row() -> pd.Series:
    return pd.Series(
        {
            "months_of_history": 18.0,
            "transaction_density": 8.0,
            "pre_loan_transaction_count": 120,
            "mean_monthly_inflow": 2500.0,
            "mean_monthly_outflow": 900.0,
            "average_balance": 5000.0,
            "minimum_balance": 1200.0,
            "income_stability_score": 0.9,
            "cash_flow_stability_score": 0.8,
            "stability_history_status": "sufficient_history",
            "seasonality_status": "sufficient_history",
            "standing_order_count": 1,
        }
    )


def weak_evidence_row() -> pd.Series:
    return pd.Series(
        {
            "months_of_history": 1.0,
            "transaction_density": 0.2,
            "pre_loan_transaction_count": 1,
            "mean_monthly_inflow": pd.NA,
            "mean_monthly_outflow": pd.NA,
            "average_balance": pd.NA,
            "minimum_balance": pd.NA,
            "income_stability_score": pd.NA,
            "cash_flow_stability_score": pd.NA,
            "stability_history_status": "insufficient_history",
            "seasonality_status": "insufficient_history",
            "standing_order_count": 0,
        }
    )


def test_confidence_score_is_not_risk_score_and_uses_bands() -> None:
    policy = load_policy()

    strong = score_evidence_confidence(strong_evidence_row(), policy, risk_probability=0.9)
    weak = score_evidence_confidence(weak_evidence_row(), policy, risk_probability=0.1)

    assert strong["confidence_score"] > weak["confidence_score"]
    assert strong["confidence_band"] in {"medium", "high"}
    assert weak["confidence_band"] == "low"
    assert "reasons" in strong


def test_add_evidence_confidence_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    pd.DataFrame(
        [
            {"loan_id": 1, **strong_evidence_row().to_dict()},
            {"loan_id": 2, **weak_evidence_row().to_dict()},
        ]
    ).to_csv(features_path, index=False)

    first = add_evidence_confidence(features_path, features_path, model_path=tmp_path / "missing.joblib")
    second = add_evidence_confidence(features_path, features_path, model_path=tmp_path / "missing.joblib")

    assert len(first) == 2
    assert len(second) == 2
    assert "confidence_score" in second.columns
    assert second["confidence_score"].between(0, 100).all()
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)
    reasons = json.loads(second.loc[0, "confidence_reasons"])
    assert isinstance(reasons, list)
