import json
from pathlib import Path

import pandas as pd

from app.services.decision_engine import DecisionPolicy, make_decision
from scripts.add_decisions import add_decisions


def policy() -> DecisionPolicy:
    return DecisionPolicy(
        approve={
            "min_confidence_score": 60,
            "max_risk_probability": 0.35,
            "max_stress_probability": 0.25,
        },
        safe_to_learn={
            "min_starter_amount": 20000,
            "max_risk_probability": 0.55,
        },
        evidence_needed={"min_confidence_score_for_affordability_judgment": 50},
    )


def base_row() -> pd.Series:
    return pd.Series(
        {
            "loan_id": 1,
            "requested_amount": 50000,
            "maximum_safe_exposure": 50000,
            "recommended_amount": 50000,
            "recommended_tenure": 12,
            "recommended_emi": 4600.0,
            "confidence_score": 80,
            "risk_model_probability": 0.1,
            "stress_probability": 0.1,
        }
    )


def test_decision_approve() -> None:
    assert make_decision(base_row(), policy())["decision_state"] == "APPROVE"


def test_decision_safe_to_learn() -> None:
    row = base_row()
    row["requested_amount"] = 100000
    row["maximum_safe_exposure"] = 50000
    row["recommended_amount"] = 50000

    decision = make_decision(row, policy())

    assert decision["decision_state"] == "SAFE_TO_LEARN"
    assert decision["decision_recommended_amount"] == 50000


def test_decision_evidence_needed() -> None:
    row = base_row()
    row["confidence_score"] = 30
    row["maximum_safe_exposure"] = 0
    row["recommended_amount"] = 0

    assert make_decision(row, policy())["decision_state"] == "EVIDENCE_NEEDED"


def test_decision_not_currently_affordable() -> None:
    row = base_row()
    row["risk_model_probability"] = 0.9
    row["maximum_safe_exposure"] = 0
    row["recommended_amount"] = 0

    assert make_decision(row, policy())["decision_state"] == "NOT_CURRENTLY_AFFORDABLE"


def test_add_decisions_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    policy_path = tmp_path / "decision_policy.json"
    pd.DataFrame([base_row().to_dict()]).to_csv(features_path, index=False)
    policy_path.write_text(
        json.dumps(
            {
                "approve": policy().approve,
                "safe_to_learn": policy().safe_to_learn,
                "evidence_needed": policy().evidence_needed,
            }
        ),
        encoding="utf-8",
    )

    first = add_decisions(features_path, features_path, policy_path)
    second = add_decisions(features_path, features_path, policy_path)

    assert len(first) == 1
    assert len(second) == 1
    assert second.loc[0, "decision_state"] == "APPROVE"
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)
