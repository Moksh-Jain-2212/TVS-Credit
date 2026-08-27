import json
from pathlib import Path

import pandas as pd

from app.services.adaptive_credit_path import (
    AdaptiveCreditPolicy,
    EventEffect,
    apply_repayment_event,
    simulate_adaptive_path,
    starter_recommendation,
)
from app.services.decision_engine import DecisionPolicy
from app.services.repayment_envelope import RepaymentEnvelopePolicy
from scripts.add_adaptive_credit_path import add_adaptive_credit_path


def adaptive_policy() -> AdaptiveCreditPolicy:
    return AdaptiveCreditPolicy(
        allowed_events={
            "on_time": EventEffect(0.95, 2, 0, -1),
            "late": EventEffect(1.15, -3, -0.25, -1),
            "missed": EventEffect(1.5, -8, -1, 0),
        },
        max_confidence_score=100,
        min_confidence_score=0,
        min_starter_amount=20000,
    )


def envelope_policy() -> RepaymentEnvelopePolicy:
    return RepaymentEnvelopePolicy(
        annual_interest_rate=0.12,
        candidate_amounts=[20000, 30000, 60000],
        candidate_tenures_months=[12, 24],
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


def decision_policy() -> DecisionPolicy:
    return DecisionPolicy(
        approve={"min_confidence_score": 60, "max_risk_probability": 0.35, "max_stress_probability": 0.25},
        safe_to_learn={"min_starter_amount": 20000, "max_risk_probability": 0.55},
        evidence_needed={"min_confidence_score_for_affordability_judgment": 50},
    )


def safe_to_learn_row() -> pd.Series:
    return pd.Series(
        {
            "loan_id": 1,
            "decision_state": "SAFE_TO_LEARN",
            "requested_amount": 100000,
            "maximum_safe_exposure": 30000,
            "recommended_amount": 30000,
            "recommended_tenure": 24,
            "recommended_emi": 1500.0,
            "scheduled_payment": 5000.0,
            "risk_model_probability": 0.2,
            "confidence_score": 70,
            "stress_probability": 0.1,
            "cash_flow_forecast_p10": 4000.0,
            "cash_flow_forecast_p50": 7000.0,
            "cash_flow_forecast_p90": 9000.0,
            "pre_loan_latest_balance": 50000.0,
            "mean_monthly_inflow": 30000.0,
        }
    )


def test_starter_recommendation_uses_safe_envelope() -> None:
    starter = starter_recommendation(safe_to_learn_row(), adaptive_policy())

    assert starter["starter_credit_eligible"] is True
    assert starter["starter_amount"] == 30000
    assert "safe repayment envelope" in starter["starter_reason"]


def test_repayment_event_reruns_underwriting_without_auto_doubling() -> None:
    row = safe_to_learn_row()
    result = apply_repayment_event(
        row,
        "on_time",
        adaptive_policy(),
        envelope_policy(),
        decision_policy(),
    )

    assert result["simulated"] is True
    assert result["updated_risk_probability"] < row["risk_model_probability"]
    assert result["recommended_amount"] in {0, 20000, 30000, 60000}
    assert result["recommended_amount"] != row["recommended_amount"] * 2


def test_simulate_adaptive_path_records_each_observation() -> None:
    path = simulate_adaptive_path(
        safe_to_learn_row(),
        ["on_time", "late", "missed"],
        adaptive_policy(),
        envelope_policy(),
        decision_policy(),
    )

    assert len(path["simulated_observations"]) == 3
    assert path["simulated_observations"][0]["event"] == "on_time"
    assert path["simulated_observations"][2]["event"] == "missed"


def test_add_adaptive_credit_path_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    policy_path = tmp_path / "adaptive_credit_policy.json"
    pd.DataFrame([safe_to_learn_row().to_dict()]).to_csv(features_path, index=False)
    policy_path.write_text(
        json.dumps(
            {
                "allowed_events": {
                    "on_time": {
                        "risk_multiplier": 0.95,
                        "confidence_delta": 2,
                        "cash_flow_delta_multiplier": 0,
                        "buffer_delta_multiplier": -1,
                    }
                },
                "max_confidence_score": 100,
                "min_confidence_score": 0,
                "min_starter_amount": 20000,
            }
        ),
        encoding="utf-8",
    )

    first = add_adaptive_credit_path(features_path, features_path, policy_path, ["on_time"])
    second = add_adaptive_credit_path(features_path, features_path, policy_path, ["on_time"])

    assert len(first) == 1
    assert len(second) == 1
    assert second.loc[0, "starter_credit_eligible"] == True
    assert len(json.loads(second.loc[0, "adaptive_path_observations"])) == 1
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)
