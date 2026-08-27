"""Four-state NADI decision engine."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "decision_policy.json"

DecisionState = Literal[
    "APPROVE",
    "SAFE_TO_LEARN",
    "EVIDENCE_NEEDED",
    "NOT_CURRENTLY_AFFORDABLE",
]


@dataclass(frozen=True)
class DecisionPolicy:
    approve: dict[str, float]
    safe_to_learn: dict[str, float]
    evidence_needed: dict[str, float]


def load_decision_policy(path: Path = POLICY_PATH) -> DecisionPolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    return DecisionPolicy(
        approve={key: float(value) for key, value in data["approve"].items()},
        safe_to_learn={key: float(value) for key, value in data["safe_to_learn"].items()},
        evidence_needed={key: float(value) for key, value in data["evidence_needed"].items()},
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def decision_reasons(
    decision: DecisionState,
    requested_amount: float,
    maximum_safe_exposure: float,
    confidence_score: float,
    risk_probability: float,
) -> list[str]:
    if decision == "APPROVE":
        return ["requested amount is within the safe repayment envelope"]
    if decision == "SAFE_TO_LEARN":
        return [
            "requested amount exceeds the safe repayment envelope",
            f"starter exposure available up to {maximum_safe_exposure:.0f}",
        ]
    if decision == "EVIDENCE_NEEDED":
        return [
            "evidence confidence is insufficient for even a starter exposure",
            f"confidence score {confidence_score:.0f}",
        ]
    return [
        "evidence is sufficient but requested credit is not currently affordable",
        f"risk probability {risk_probability:.3f}",
        f"maximum safe exposure {maximum_safe_exposure:.0f}",
    ]


def make_decision(row: pd.Series, policy: DecisionPolicy) -> dict[str, Any]:
    requested_amount = safe_float(row.get("requested_amount"), 0.0)
    maximum_safe_exposure = safe_float(row.get("maximum_safe_exposure"), 0.0)
    recommended_amount = safe_float(row.get("recommended_amount"), 0.0)
    confidence_score = safe_float(row.get("confidence_score"), 0.0)
    risk_probability = safe_float(row.get("risk_model_probability"), 1.0)
    stress_probability = safe_float(row.get("stress_probability"), 1.0)

    approve_policy = policy.approve
    safe_to_learn_policy = policy.safe_to_learn
    evidence_policy = policy.evidence_needed

    approve_ready = (
        confidence_score >= approve_policy["min_confidence_score"]
        and risk_probability <= approve_policy["max_risk_probability"]
        and stress_probability <= approve_policy["max_stress_probability"]
    )
    requested_inside_envelope = maximum_safe_exposure >= requested_amount > 0
    starter_available = (
        recommended_amount >= safe_to_learn_policy["min_starter_amount"]
        and risk_probability <= safe_to_learn_policy["max_risk_probability"]
    )

    if approve_ready and requested_inside_envelope:
        decision: DecisionState = "APPROVE"
    elif starter_available and maximum_safe_exposure < requested_amount:
        decision = "SAFE_TO_LEARN"
    elif confidence_score < evidence_policy["min_confidence_score_for_affordability_judgment"]:
        decision = "EVIDENCE_NEEDED"
    else:
        decision = "NOT_CURRENTLY_AFFORDABLE"

    return {
        "decision_state": decision,
        "decision_recommended_amount": recommended_amount if decision == "SAFE_TO_LEARN" else requested_amount if decision == "APPROVE" else 0.0,
        "decision_recommended_tenure": row.get("recommended_tenure") if decision in {"APPROVE", "SAFE_TO_LEARN"} else pd.NA,
        "decision_recommended_emi": row.get("recommended_emi") if decision in {"APPROVE", "SAFE_TO_LEARN"} else pd.NA,
        "decision_reasons": decision_reasons(
            decision,
            requested_amount,
            maximum_safe_exposure,
            confidence_score,
            risk_probability,
        ),
    }
