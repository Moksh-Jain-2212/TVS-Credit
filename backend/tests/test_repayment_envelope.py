import json
from pathlib import Path

import pandas as pd

from app.services.repayment_envelope import (
    RepaymentEnvelopePolicy,
    estimate_emi,
    generate_repayment_envelope,
)
from scripts.add_repayment_envelope import add_repayment_envelope


def policy() -> RepaymentEnvelopePolicy:
    return RepaymentEnvelopePolicy(
        annual_interest_rate=0.12,
        candidate_amounts=[20000, 50000],
        candidate_tenures_months=[6, 12],
        safe={
            "max_risk_probability": 0.35,
            "min_confidence_score": 60,
            "max_stress_probability": 0.25,
            "min_projected_buffer": 0,
            "max_emi_to_expected_cash_flow": 0.8,
        },
        borderline={
            "max_risk_probability": 0.55,
            "min_confidence_score": 45,
            "max_stress_probability": 0.5,
            "min_projected_buffer": -5000,
            "max_emi_to_expected_cash_flow": 1.0,
        },
    )


def strong_row() -> pd.Series:
    return pd.Series(
        {
            "cash_flow_forecast_p10": 7000.0,
            "cash_flow_forecast_p50": 9000.0,
            "pre_loan_latest_balance": 50000.0,
            "mean_monthly_inflow": 30000.0,
            "risk_model_probability": 0.1,
            "confidence_score": 85,
        }
    )


def weak_row() -> pd.Series:
    row = strong_row()
    row["cash_flow_forecast_p50"] = 100.0
    row["cash_flow_forecast_p10"] = -1000.0
    row["pre_loan_latest_balance"] = 0.0
    row["risk_model_probability"] = 0.8
    return row


def test_estimate_emi_is_positive() -> None:
    assert estimate_emi(20000, 12, 0.12) > 0


def test_generate_repayment_envelope_recommends_from_safe_candidates() -> None:
    envelope = generate_repayment_envelope(strong_row(), policy())

    assert len(envelope["all_evaluated_combinations"]) == 4
    assert envelope["maximum_safe_exposure"] > 0
    assert envelope["recommended_amount"] == envelope["maximum_safe_exposure"]
    assert envelope["recommended_emi"] is not None
    assert envelope["all_evaluated_combinations"][0]["classification_reasons"]


def test_generate_repayment_envelope_can_return_no_safe_candidates() -> None:
    envelope = generate_repayment_envelope(weak_row(), policy())

    assert envelope["maximum_safe_exposure"] == 0
    assert envelope["recommended_amount"] == 0
    assert envelope["recommended_tenure"] is None
    assert "risk probability" in envelope["all_evaluated_combinations"][0]["classification_reasons"][0]


def test_add_repayment_envelope_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    policy_path = tmp_path / "repayment_envelope_policy.json"
    pd.DataFrame([{"loan_id": 1, **strong_row().to_dict()}]).to_csv(features_path, index=False)
    policy_path.write_text(
        json.dumps(
            {
                "annual_interest_rate": 0.12,
                "candidate_amounts": [20000],
                "candidate_tenures_months": [12],
                "safe": policy().safe,
                "borderline": policy().borderline,
            }
        ),
        encoding="utf-8",
    )

    first = add_repayment_envelope(features_path, features_path, policy_path)
    second = add_repayment_envelope(features_path, features_path, policy_path)

    assert len(first) == 1
    assert len(second) == 1
    assert "repayment_all_evaluated_combinations" in second.columns
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)
