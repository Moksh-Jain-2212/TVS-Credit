import json
from pathlib import Path

import pandas as pd

from app.services.explainability import borrower_view, build_explanations, loan_officer_view
from scripts.add_explanations import add_explanations


def safe_to_learn_row() -> pd.Series:
    return pd.Series(
        {
            "loan_id": 1,
            "decision_state": "SAFE_TO_LEARN",
            "requested_amount": 100000,
            "maximum_safe_exposure": 30000,
            "decision_recommended_amount": 30000,
            "decision_recommended_tenure": 12,
            "decision_recommended_emi": 2800.0,
            "starter_credit_eligible": True,
            "starter_amount": 30000,
            "risk_model_probability": 0.2,
            "confidence_score": 68,
            "confidence_band": "medium",
            "cash_flow_forecast_p10": 2000.0,
            "cash_flow_forecast_p50": 5000.0,
            "scheduled_payment": 8000.0,
            "stress_probability": 0.2,
            "stress_minimum_remaining_cash_buffer": 1000.0,
            "stress_worst_scenario": "income_minus_20",
            "months_of_history": 8,
            "mean_monthly_net_cash_flow": 3000.0,
            "seasonality_status": "insufficient_history",
            "confidence_reasons": '["weaker evidence from history_length"]',
            "decision_reasons": '["requested amount exceeds the safe repayment envelope"]',
            "evidence_ladder_status": "additional_evidence_recommended",
            "recommended_evidence": "additional_bank_history_months",
        }
    )


def test_loan_officer_view_contains_required_fields() -> None:
    view = loan_officer_view(safe_to_learn_row())

    assert view["decision"] == "SAFE_TO_LEARN"
    assert view["requested_amount"] == 100000
    assert view["safe_amount"] == 30000
    assert view["risk"]["band"] == "low"
    assert view["evidence_confidence"]["score"] == 68
    assert view["recommended"]["amount"] == 30000
    assert view["safe_to_learn_reason"]


def test_borrower_view_uses_plain_language_without_model_jargon() -> None:
    text = json.dumps(borrower_view(safe_to_learn_row())).lower()

    assert "starter amount" in text
    assert "additional_bank_history_months" in text
    assert "shap" not in text
    assert "probability" not in text


def test_add_explanations_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    pd.DataFrame([safe_to_learn_row().to_dict()]).to_csv(features_path, index=False)

    first = add_explanations(features_path, features_path)
    second = add_explanations(features_path, features_path)
    officer = json.loads(second.loc[0, "loan_officer_explanation"])
    borrower = json.loads(second.loc[0, "borrower_explanation"])

    assert len(first) == 1
    assert len(second) == 1
    assert officer["decision"] == "SAFE_TO_LEARN"
    assert "what_was_decided" in borrower
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)


def test_build_explanations_returns_two_levels() -> None:
    explanations = build_explanations(safe_to_learn_row())

    assert set(explanations) == {"loan_officer", "borrower"}
