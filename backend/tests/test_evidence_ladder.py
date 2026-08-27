import json
from pathlib import Path

import pandas as pd

from app.services.evidence_ladder import EvidenceLadderPolicy, EvidenceOption, rank_evidence_options
from scripts.add_evidence_ladder import add_evidence_ladder


def policy() -> EvidenceLadderPolicy:
    return EvidenceLadderPolicy(
        min_sufficient_confidence_score=75,
        options=[
            EvidenceOption("additional_bank_history_months", 18, 2, 3, True, "more bank history"),
            EvidenceOption("utility_history", 9, 2, 2, True, "utility repayment consistency"),
        ],
    )


def weak_row() -> pd.Series:
    return pd.Series(
        {
            "loan_id": 1,
            "confidence_score": 45,
            "months_of_history": 2,
            "transaction_density": 1,
            "seasonality_status": "insufficient_history",
        }
    )


def strong_row() -> pd.Series:
    row = weak_row()
    row["loan_id"] = 2
    row["confidence_score"] = 90
    row["months_of_history"] = 18
    return row


def test_rank_evidence_options_recommends_when_confidence_insufficient() -> None:
    result = rank_evidence_options(weak_row(), policy())

    assert result["status"] == "additional_evidence_recommended"
    assert result["recommended_evidence"] == "additional_bank_history_months"
    assert result["expected_confidence_improvement"] > 0
    assert result["friction_level"] in {"low", "medium", "high"}
    assert result["privacy_cost_level"] in {"low", "medium", "high"}
    assert result["rankings"][0]["ranking_score"] >= result["rankings"][1]["ranking_score"]


def test_rank_evidence_options_returns_none_when_confidence_sufficient() -> None:
    result = rank_evidence_options(strong_row(), policy())

    assert result["status"] == "sufficient_confidence"
    assert result["recommended_evidence"] == "none"
    assert result["expected_confidence_improvement"] == 0


def test_add_evidence_ladder_appends_columns_and_is_rerunnable(tmp_path: Path) -> None:
    features_path = tmp_path / "nadi_features.csv"
    policy_path = tmp_path / "evidence_ladder_policy.json"
    pd.DataFrame([weak_row().to_dict(), strong_row().to_dict()]).to_csv(features_path, index=False)
    policy_path.write_text(
        json.dumps(
            {
                "min_sufficient_confidence_score": 75,
                "default_options": [
                    {
                        "name": "additional_bank_history_months",
                        "base_confidence_gain": 18,
                        "friction_cost": 2,
                        "privacy_cost": 3,
                        "mocked_available": True,
                        "reason": "more bank history",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    first = add_evidence_ladder(features_path, features_path, policy_path)
    second = add_evidence_ladder(features_path, features_path, policy_path)

    assert len(first) == 2
    assert len(second) == 2
    assert "recommended_evidence" in second.columns
    assert not any(column.endswith("_x") or column.endswith("_y") for column in second.columns)
