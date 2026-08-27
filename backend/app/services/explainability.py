"""Human-readable explanations for NADI decisions."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd


EXPLANATION_COLUMNS = [
    "loan_officer_explanation",
    "borrower_explanation",
]


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def parse_json_list(value: Any) -> list[Any]:
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_json_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def risk_band(risk_probability: float) -> str:
    if risk_probability <= 0.2:
        return "low"
    if risk_probability <= 0.5:
        return "medium"
    return "high"


def stress_result(stress_probability: float) -> str:
    if stress_probability <= 0.25:
        return "passes"
    if stress_probability <= 0.5:
        return "borderline"
    return "fails"


def positive_factors(row: pd.Series) -> list[str]:
    factors: list[str] = []
    if safe_float(row.get("confidence_score")) >= 75:
        factors.append("strong evidence confidence")
    if safe_float(row.get("months_of_history")) >= 12:
        factors.append("at least 12 months of account history")
    if safe_float(row.get("risk_model_probability"), 1.0) <= 0.2:
        factors.append("low estimated repayment risk")
    if safe_float(row.get("mean_monthly_net_cash_flow")) > 0:
        factors.append("positive average monthly cash flow")
    if safe_float(row.get("maximum_safe_exposure")) > 0:
        factors.append("a safe repayment envelope is available")
    return factors or ["no strong positive factor identified"]


def negative_factors(row: pd.Series) -> list[str]:
    factors: list[str] = []
    if safe_float(row.get("confidence_score")) < 50:
        factors.append("limited evidence confidence")
    if safe_float(row.get("risk_model_probability")) > 0.5:
        factors.append("elevated estimated repayment risk")
    if safe_float(row.get("stress_probability")) > 0.5:
        factors.append("stress scenarios show weak survival")
    if safe_float(row.get("cash_flow_forecast_p50")) <= 0:
        factors.append("expected cash-flow forecast is not positive")
    if safe_float(row.get("maximum_safe_exposure")) < safe_float(row.get("requested_amount")):
        factors.append("requested amount exceeds current safe envelope")
    return factors or ["no major negative factor identified"]


def uncertainty_items(row: pd.Series) -> list[str]:
    items: list[str] = []
    if row.get("seasonality_status") == "insufficient_history":
        items.append("seasonality could not be estimated with enough history")
    if safe_float(row.get("confidence_score")) < 75:
        items.extend(parse_json_list(row.get("confidence_reasons")))
    if row.get("evidence_ladder_status") == "additional_evidence_recommended":
        items.append(f"additional evidence may help: {row.get('recommended_evidence')}")
    return items or ["main uncertainty is stress performance under adverse scenarios"]


def loan_officer_view(row: pd.Series) -> dict[str, Any]:
    risk_probability = safe_float(row.get("risk_model_probability"), 1.0)
    confidence_score = safe_float(row.get("confidence_score"))
    stress_probability = safe_float(row.get("stress_probability"), 1.0)
    return {
        "decision": row.get("decision_state"),
        "requested_amount": safe_float(row.get("requested_amount")),
        "safe_amount": safe_float(row.get("maximum_safe_exposure")),
        "risk": {
            "probability": risk_probability,
            "band": risk_band(risk_probability),
        },
        "evidence_confidence": {
            "score": confidence_score,
            "band": row.get("confidence_band"),
        },
        "capacity": {
            "expected_monthly_cash_flow": safe_float(row.get("cash_flow_forecast_p50")),
            "conservative_monthly_cash_flow": safe_float(row.get("cash_flow_forecast_p10")),
            "scheduled_payment": safe_float(row.get("scheduled_payment")),
        },
        "stress_test_result": {
            "status": stress_result(stress_probability),
            "stress_probability": stress_probability,
            "minimum_remaining_cash_buffer": safe_float(row.get("stress_minimum_remaining_cash_buffer")),
            "worst_scenario": row.get("stress_worst_scenario"),
        },
        "positive_factors": positive_factors(row),
        "negative_factors": negative_factors(row),
        "uncertainty": uncertainty_items(row),
        "recommended": {
            "amount": safe_float(row.get("decision_recommended_amount")),
            "tenure": row.get("decision_recommended_tenure"),
            "emi": row.get("decision_recommended_emi"),
        },
        "safe_to_learn_reason": (
            parse_json_list(row.get("decision_reasons"))
            if row.get("decision_state") == "SAFE_TO_LEARN"
            else []
        ),
    }


def borrower_decision_sentence(row: pd.Series) -> str:
    decision = row.get("decision_state")
    if decision == "APPROVE":
        return "Your requested loan fits within the amount that looks affordable from the information available."
    if decision == "SAFE_TO_LEARN":
        amount = safe_float(row.get("starter_amount"), safe_float(row.get("decision_recommended_amount")))
        return f"The full requested amount is not supported yet, but a starter amount of about {amount:.0f} is available."
    if decision == "EVIDENCE_NEEDED":
        return "There is not enough information yet to offer a useful starter amount."
    return "The current information suggests the requested loan is not affordable right now."


def borrower_view(row: pd.Series) -> dict[str, Any]:
    decision = row.get("decision_state")
    evidence = row.get("recommended_evidence")
    starter_available = bool(row.get("starter_credit_eligible")) if not pd.isna(row.get("starter_credit_eligible")) else False
    strong_info = [
        item.replace("estimated repayment risk", "repayment outlook")
        for item in positive_factors(row)
        if item != "no strong positive factor identified"
    ]
    uncertainty = [
        item.replace("stress scenarios", "difficult months")
        for item in uncertainty_items(row)
    ]
    view = {
        "what_was_decided": borrower_decision_sentence(row),
        "why": negative_factors(row)[:3],
        "what_information_was_strong": strong_info or ["the available account history was reviewed"],
        "what_uncertainty_remains": uncertainty,
        "what_evidence_may_help": (
            evidence
            if row.get("evidence_ladder_status") == "additional_evidence_recommended"
            else "no extra evidence is needed for confidence right now"
        ),
        "starter_credit_path": (
            f"A starter path is available at about {safe_float(row.get('starter_amount')):.0f}."
            if starter_available or decision == "SAFE_TO_LEARN"
            else "No starter-credit path is available from the current safe envelope."
        ),
    }
    return view


def build_explanations(row: pd.Series) -> dict[str, dict[str, Any]]:
    return {
        "loan_officer": loan_officer_view(row),
        "borrower": borrower_view(row),
    }
