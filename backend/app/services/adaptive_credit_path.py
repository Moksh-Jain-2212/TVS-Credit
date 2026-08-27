"""Adaptive credit path simulation with re-underwriting after each event."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pandas as pd

from app.services.decision_engine import DecisionPolicy, make_decision
from app.services.repayment_envelope import RepaymentEnvelopePolicy, generate_repayment_envelope


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "adaptive_credit_policy.json"
RepaymentEvent = Literal["on_time", "late", "missed"]


@dataclass(frozen=True)
class EventEffect:
    risk_multiplier: float
    confidence_delta: float
    cash_flow_delta_multiplier: float
    buffer_delta_multiplier: float


@dataclass(frozen=True)
class AdaptiveCreditPolicy:
    allowed_events: dict[str, EventEffect]
    max_confidence_score: float
    min_confidence_score: float
    min_starter_amount: float


def load_adaptive_credit_policy(path: Path = POLICY_PATH) -> AdaptiveCreditPolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    events = {
        name: EventEffect(
            risk_multiplier=float(values["risk_multiplier"]),
            confidence_delta=float(values["confidence_delta"]),
            cash_flow_delta_multiplier=float(values["cash_flow_delta_multiplier"]),
            buffer_delta_multiplier=float(values["buffer_delta_multiplier"]),
        )
        for name, values in data["allowed_events"].items()
    }
    return AdaptiveCreditPolicy(
        allowed_events=events,
        max_confidence_score=float(data["max_confidence_score"]),
        min_confidence_score=float(data["min_confidence_score"]),
        min_starter_amount=float(data["min_starter_amount"]),
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def starter_recommendation(row: pd.Series, policy: AdaptiveCreditPolicy) -> dict[str, Any]:
    if row.get("decision_state") != "SAFE_TO_LEARN":
        return {
            "starter_credit_eligible": False,
            "starter_amount": 0.0,
            "starter_tenure": pd.NA,
            "starter_emi": pd.NA,
            "starter_reason": "current decision is not SAFE_TO_LEARN",
        }
    starter_amount = safe_float(row.get("recommended_amount"), 0.0)
    return {
        "starter_credit_eligible": starter_amount >= policy.min_starter_amount,
        "starter_amount": starter_amount,
        "starter_tenure": row.get("recommended_tenure"),
        "starter_emi": row.get("recommended_emi"),
        "starter_reason": "starter exposure comes from the current safe repayment envelope",
    }


def apply_repayment_event(
    row: pd.Series,
    event: RepaymentEvent,
    adaptive_policy: AdaptiveCreditPolicy,
    envelope_policy: RepaymentEnvelopePolicy,
    decision_policy: DecisionPolicy,
) -> dict[str, Any]:
    if event not in adaptive_policy.allowed_events:
        raise ValueError(f"Unsupported repayment event: {event}")

    updated = row.copy()
    effect = adaptive_policy.allowed_events[event]
    emi = safe_float(updated.get("recommended_emi"), safe_float(updated.get("scheduled_payment"), 0.0))

    updated["simulated_repayment_event_count"] = safe_float(updated.get("simulated_repayment_event_count"), 0.0) + 1
    updated[f"simulated_{event}_count"] = safe_float(updated.get(f"simulated_{event}_count"), 0.0) + 1
    for event_name in adaptive_policy.allowed_events:
        column = f"simulated_{event_name}_count"
        if column not in updated.index:
            updated[column] = safe_float(updated.get(column), 0.0)

    updated["risk_model_probability"] = min(
        1.0,
        max(0.0, safe_float(updated.get("risk_model_probability"), 0.5) * effect.risk_multiplier),
    )
    updated["confidence_score"] = min(
        adaptive_policy.max_confidence_score,
        max(
            adaptive_policy.min_confidence_score,
            safe_float(updated.get("confidence_score"), 0.0) + effect.confidence_delta,
        ),
    )
    updated["cash_flow_forecast_p10"] = safe_float(updated.get("cash_flow_forecast_p10"), 0.0) + (
        emi * effect.cash_flow_delta_multiplier
    )
    updated["cash_flow_forecast_p50"] = safe_float(updated.get("cash_flow_forecast_p50"), 0.0) + (
        emi * effect.cash_flow_delta_multiplier
    )
    updated["cash_flow_forecast_p90"] = safe_float(updated.get("cash_flow_forecast_p90"), 0.0) + (
        emi * effect.cash_flow_delta_multiplier
    )
    updated["pre_loan_latest_balance"] = safe_float(updated.get("pre_loan_latest_balance"), 0.0) + (
        emi * effect.buffer_delta_multiplier
    )

    envelope = generate_repayment_envelope(updated, envelope_policy)
    updated["maximum_safe_exposure"] = envelope["maximum_safe_exposure"]
    updated["recommended_amount"] = envelope["recommended_amount"]
    updated["recommended_tenure"] = envelope["recommended_tenure"]
    updated["recommended_emi"] = envelope["recommended_emi"]
    decision = make_decision(updated, decision_policy)

    return {
        "event": event,
        "simulated": True,
        "updated_risk_probability": float(updated["risk_model_probability"]),
        "updated_confidence_score": float(updated["confidence_score"]),
        "maximum_safe_exposure": envelope["maximum_safe_exposure"],
        "recommended_amount": envelope["recommended_amount"],
        "recommended_tenure": envelope["recommended_tenure"],
        "recommended_emi": envelope["recommended_emi"],
        "decision_state": decision["decision_state"],
        "decision_reasons": decision["decision_reasons"],
    }


def simulate_adaptive_path(
    row: pd.Series,
    events: list[RepaymentEvent],
    adaptive_policy: AdaptiveCreditPolicy,
    envelope_policy: RepaymentEnvelopePolicy,
    decision_policy: DecisionPolicy,
) -> dict[str, Any]:
    current = row.copy()
    starter = starter_recommendation(current, adaptive_policy)
    observations: list[dict[str, Any]] = []
    for event in events:
        result = apply_repayment_event(
            current,
            event,
            adaptive_policy,
            envelope_policy,
            decision_policy,
        )
        observations.append(result)
        for key in (
            "updated_risk_probability",
            "updated_confidence_score",
            "maximum_safe_exposure",
            "recommended_amount",
            "recommended_tenure",
            "recommended_emi",
            "decision_state",
        ):
            target_key = {
                "updated_risk_probability": "risk_model_probability",
                "updated_confidence_score": "confidence_score",
            }.get(key, key)
            current[target_key] = result[key]
    return {
        "starter_recommendation": starter,
        "simulated_observations": observations,
        "final_decision_state": observations[-1]["decision_state"] if observations else current.get("decision_state"),
        "final_recommended_amount": observations[-1]["recommended_amount"] if observations else starter["starter_amount"],
    }
