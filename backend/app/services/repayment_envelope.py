"""Repayment envelope generation for candidate loan combinations."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.finance import estimate_emi
from app.services.stress_simulator import load_stress_policy, simulate_borrower_stress


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "repayment_envelope_policy.json"


@dataclass(frozen=True)
class RepaymentEnvelopePolicy:
    annual_interest_rate: float
    candidate_amounts: list[int]
    candidate_tenures_months: list[int]
    safe: dict[str, float]
    borderline: dict[str, float]


def load_envelope_policy(path: Path = POLICY_PATH) -> RepaymentEnvelopePolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    return RepaymentEnvelopePolicy(
        annual_interest_rate=float(data["annual_interest_rate"]),
        candidate_amounts=[int(value) for value in data["candidate_amounts"]],
        candidate_tenures_months=[int(value) for value in data["candidate_tenures_months"]],
        safe={key: float(value) for key, value in data["safe"].items()},
        borderline={key: float(value) for key, value in data["borderline"].items()},
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def scenario_stress_probability(
    latest_buffer: float,
    expected_cash_flow: float,
    conservative_cash_flow: float,
    income: float,
    emi: float,
    tenure: int,
) -> tuple[float, float]:
    scenarios = [
        expected_cash_flow,
        expected_cash_flow - income * 0.10,
        expected_cash_flow - income * 0.20,
        expected_cash_flow - income * 0.30,
        expected_cash_flow - 5000.0,
        conservative_cash_flow,
        conservative_cash_flow - income * 0.20 - 5000.0,
    ]
    min_buffer = latest_buffer
    failed = 0
    for cash_flow in scenarios:
        projected = latest_buffer
        scenario_min = projected
        for _ in range(tenure):
            projected += cash_flow - emi
            scenario_min = min(scenario_min, projected)
        min_buffer = min(min_buffer, scenario_min)
        if scenario_min < 0:
            failed += 1
    return failed / len(scenarios), float(min_buffer)


def classify_candidate(candidate: dict[str, float], policy: RepaymentEnvelopePolicy) -> str:
    safe = policy.safe
    borderline = policy.borderline
    if (
        candidate["risk_probability"] <= safe["max_risk_probability"]
        and candidate["confidence_score"] >= safe["min_confidence_score"]
        and candidate["stress_probability"] <= safe["max_stress_probability"]
        and candidate["minimum_projected_buffer"] >= safe["min_projected_buffer"]
        and candidate["emi_to_expected_cash_flow"] <= safe["max_emi_to_expected_cash_flow"]
    ):
        return "SAFE"
    if (
        candidate["risk_probability"] <= borderline["max_risk_probability"]
        and candidate["confidence_score"] >= borderline["min_confidence_score"]
        and candidate["stress_probability"] <= borderline["max_stress_probability"]
        and candidate["minimum_projected_buffer"] >= borderline["min_projected_buffer"]
        and candidate["emi_to_expected_cash_flow"] <= borderline["max_emi_to_expected_cash_flow"]
    ):
        return "BORDERLINE"
    return "UNSAFE"


def classification_reasons(candidate: dict[str, float], policy: RepaymentEnvelopePolicy) -> list[str]:
    classification = str(candidate["classification"])
    if classification == "SAFE":
        return ["meets safe thresholds for risk, confidence, stress survival, buffer, and EMI load"]

    policy_band = policy.safe if classification == "BORDERLINE" else policy.borderline
    band_name = "safe" if classification == "BORDERLINE" else "borderline"
    checks = [
        (
            candidate["risk_probability"] > policy_band["max_risk_probability"],
            f"risk probability {candidate['risk_probability']:.3f} exceeds {band_name} limit {policy_band['max_risk_probability']:.2f}",
        ),
        (
            candidate["confidence_score"] < policy_band["min_confidence_score"],
            f"confidence score {candidate['confidence_score']:.0f} is below {band_name} minimum {policy_band['min_confidence_score']:.0f}",
        ),
        (
            candidate["stress_probability"] > policy_band["max_stress_probability"],
            f"stress failure probability {candidate['stress_probability']:.2f} exceeds {band_name} limit {policy_band['max_stress_probability']:.2f}",
        ),
        (
            candidate["minimum_projected_buffer"] < policy_band["min_projected_buffer"],
            f"minimum projected buffer {candidate['minimum_projected_buffer']:.0f} is below {band_name} floor {policy_band['min_projected_buffer']:.0f}",
        ),
        (
            candidate["emi_to_expected_cash_flow"] > policy_band["max_emi_to_expected_cash_flow"],
            f"EMI load {candidate['emi_to_expected_cash_flow']:.2f}x exceeds {band_name} limit {policy_band['max_emi_to_expected_cash_flow']:.2f}x",
        ),
    ]
    reasons = [reason for failed, reason in checks if failed]
    if reasons:
        return reasons
    return [f"meets {band_name} thresholds but not all safe thresholds"]


def build_candidate(row: pd.Series, amount: int, tenure: int, policy: RepaymentEnvelopePolicy) -> dict[str, Any]:
    emi = estimate_emi(amount, tenure, policy.annual_interest_rate)
    expected_cash_flow = safe_float(row.get("cash_flow_forecast_p50"), 0.0)
    conservative_cash_flow = safe_float(row.get("cash_flow_forecast_p10"), expected_cash_flow)
    latest_buffer = safe_float(row.get("pre_loan_latest_balance"), 0.0)
    income = safe_float(row.get("mean_monthly_inflow"), 0.0)
    stressed_row = row.copy()
    stressed_row["scheduled_payment"] = emi
    stressed_row["duration_months"] = tenure
    stress = simulate_borrower_stress(stressed_row, load_stress_policy())
    stress_probability = float(stress["stress_probability"])
    minimum_projected_buffer = float(stress["minimum_remaining_cash_buffer"])
    candidate = {
        "amount": amount,
        "tenure_months": tenure,
        "estimated_emi": emi,
        "capacity": max(0.0, expected_cash_flow),
        "risk_probability": safe_float(row.get("risk_model_probability"), 0.5),
        "cash_flow_forecast_p10": conservative_cash_flow,
        "cash_flow_forecast_p50": expected_cash_flow,
        "stress_probability": stress_probability,
        "minimum_projected_buffer": minimum_projected_buffer,
        "confidence_score": safe_float(row.get("confidence_score"), 0.0),
        "emi_to_expected_cash_flow": emi / max(abs(expected_cash_flow), 1.0),
    }
    candidate["classification"] = classify_candidate(candidate, policy)
    candidate["classification_reasons"] = classification_reasons(candidate, policy)
    return candidate


def generate_repayment_envelope(row: pd.Series, policy: RepaymentEnvelopePolicy) -> dict[str, Any]:
    combinations = [
        build_candidate(row, amount, tenure, policy)
        for amount in policy.candidate_amounts
        for tenure in policy.candidate_tenures_months
    ]
    safe_combinations = [
        candidate for candidate in combinations if candidate["classification"] == "SAFE"
    ]
    if safe_combinations:
        recommended = max(
            safe_combinations,
            key=lambda item: (item["amount"], -item["estimated_emi"], item["tenure_months"]),
        )
        recommendation_basis = "SAFE"
    else:
        # Medium-risk/medium-confidence profiles can still have excellent capacity and
        # stress survival. They must not be approved at the requested amount, but a
        # smallest-available, longer-tenure BORDERLINE candidate is a conservative
        # starter exposure for SAFE_TO_LEARN. This remains unavailable to APPROVE
        # because the decision engine separately enforces stricter approval limits.
        borderline_combinations = [
            candidate for candidate in combinations if candidate["classification"] == "BORDERLINE"
        ]
        recommended = min(
            borderline_combinations,
            key=lambda item: (item["amount"], -item["tenure_months"], item["estimated_emi"]),
        ) if borderline_combinations else None
        recommendation_basis = "CONSERVATIVE_STARTER" if recommended else "NONE"
    return {
        "all_evaluated_combinations": combinations,
        "safe_combinations": safe_combinations,
        "maximum_safe_exposure": recommended["amount"] if recommended else 0,
        "recommended_amount": recommended["amount"] if recommended else 0,
        "recommended_tenure": recommended["tenure_months"] if recommended else None,
        "recommended_emi": recommended["estimated_emi"] if recommended else None,
        "recommendation_basis": recommendation_basis,
    }
