"""Read-only application access over the generated NADI feature dataset."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import HTTPException

from app.services.adaptive_credit_path import (
    load_adaptive_credit_policy,
    simulate_adaptive_path,
)
from app.services.decision_engine import load_decision_policy, make_decision
from app.services.evidence_ladder import load_evidence_ladder_policy, rank_evidence_options
from app.services.repayment_envelope import generate_repayment_envelope, load_envelope_policy
from app.services.stress_simulator import load_stress_policy, simulate_borrower_stress


FEATURES_PATH = Path(__file__).resolve().parents[3] / "data" / "processed" / "nadi_features.csv"


@lru_cache(maxsize=1)
def load_features() -> pd.DataFrame:
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Missing generated features: {FEATURES_PATH}")
    return pd.read_csv(FEATURES_PATH)


def clean_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def parse_json(value: Any, fallback: Any) -> Any:
    if not isinstance(value, str) or not value.strip():
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def row_to_dict(row: pd.Series) -> dict[str, Any]:
    return {key: clean_value(value) for key, value in row.to_dict().items()}


def get_application_row(application_id: int) -> pd.Series:
    frame = load_features()
    matches = frame[frame["loan_id"] == application_id]
    if matches.empty:
        raise HTTPException(status_code=404, detail="Application not found")
    return matches.iloc[0]


def list_borrowers(limit: int = 100) -> list[dict[str, Any]]:
    frame = load_features()
    borrowers = (
        frame.sort_values("loan_date")
        .groupby("account_id", as_index=False)
        .agg(
            loan_count=("loan_id", "count"),
            latest_loan_id=("loan_id", "last"),
            latest_decision=("decision_state", "last"),
            latest_confidence_score=("confidence_score", "last"),
        )
        .head(limit)
    )
    return [row_to_dict(row) for _, row in borrowers.iterrows()]


def get_borrower(account_id: int) -> dict[str, Any]:
    frame = load_features()
    matches = frame[frame["account_id"] == account_id].sort_values("loan_date")
    if matches.empty:
        raise HTTPException(status_code=404, detail="Borrower not found")
    return {
        "account_id": account_id,
        "applications": [
            {
                "application_id": int(row["loan_id"]),
                "loan_date": row["loan_date"],
                "requested_amount": clean_value(row["requested_amount"]),
                "decision_state": row["decision_state"],
            }
            for _, row in matches.iterrows()
        ],
    }


def create_application_reference(loan_id: int | None, account_id: int | None) -> dict[str, Any]:
    frame = load_features()
    if loan_id is not None:
        row = get_application_row(loan_id)
    elif account_id is not None:
        matches = frame[frame["account_id"] == account_id].sort_values("loan_date")
        if matches.empty:
            raise HTTPException(status_code=404, detail="Borrower not found")
        row = matches.iloc[-1]
    else:
        raise HTTPException(status_code=400, detail="loan_id or account_id is required")
    return {
        "application_id": int(row["loan_id"]),
        "account_id": int(row["account_id"]),
        "source": "existing_generated_pkdd_application",
        "mock_created": False,
    }


def financial_profile(application_id: int) -> dict[str, Any]:
    row = get_application_row(application_id)
    return {
        "application_id": application_id,
        "bureau_available": False,
        "bureau_status": "not_available_in_pkdd_dataset",
        "months_of_history": clean_value(row.get("months_of_history")),
        "mean_monthly_inflow": clean_value(row.get("mean_monthly_inflow")),
        "mean_monthly_outflow": clean_value(row.get("mean_monthly_outflow")),
        "mean_monthly_net_cash_flow": clean_value(row.get("mean_monthly_net_cash_flow")),
        "positive_cash_flow_month_ratio": clean_value(row.get("positive_cash_flow_month_ratio")),
        "income_volatility": clean_value(row.get("income_volatility")),
        "balance_volatility": clean_value(row.get("balance_volatility")),
        "income_trend": clean_value(row.get("income_trend")),
        "stability_history_status": clean_value(row.get("stability_history_status")),
        "income_stability_score": clean_value(row.get("income_stability_score")),
        "cash_flow_stability_score": clean_value(row.get("cash_flow_stability_score")),
        "phase7_income_trend": clean_value(row.get("phase7_income_trend")),
        "average_balance": clean_value(row.get("average_balance")),
        "minimum_balance": clean_value(row.get("minimum_balance")),
        "transaction_density": clean_value(row.get("transaction_density")),
        "confidence_score": clean_value(row.get("confidence_score")),
        "confidence_band": clean_value(row.get("confidence_band")),
    }


def forecast(application_id: int) -> dict[str, Any]:
    row = get_application_row(application_id)
    return {
        "application_id": application_id,
        "status": row.get("cash_flow_forecast_status"),
        "method": row.get("cash_flow_forecast_method"),
        "history_months": clean_value(row.get("cash_flow_forecast_history_months")),
        "p10_conservative": clean_value(row.get("cash_flow_forecast_p10")),
        "p50_expected": clean_value(row.get("cash_flow_forecast_p50")),
        "p90_optimistic": clean_value(row.get("cash_flow_forecast_p90")),
    }


def stress_test(application_id: int) -> dict[str, Any]:
    row = get_application_row(application_id)
    return {
        "application_id": application_id,
        "scenario_survival": parse_json(row.get("stress_scenario_survival"), {}),
        "stress_probability": clean_value(row.get("stress_probability")),
        "minimum_remaining_cash_buffer": clean_value(row.get("stress_minimum_remaining_cash_buffer")),
        "worst_scenario": clean_value(row.get("stress_worst_scenario")),
        "worst_projected_period": clean_value(row.get("stress_worst_projected_period")),
        "scenario_results": parse_json(row.get("stress_scenario_results"), []),
    }


def repayment_envelope(application_id: int) -> dict[str, Any]:
    row = get_application_row(application_id)
    return {
        "application_id": application_id,
        "all_evaluated_combinations": parse_json(row.get("repayment_all_evaluated_combinations"), []),
        "safe_combinations": parse_json(row.get("repayment_safe_combinations"), []),
        "maximum_safe_exposure": clean_value(row.get("maximum_safe_exposure")),
        "recommended_amount": clean_value(row.get("recommended_amount")),
        "recommended_tenure": clean_value(row.get("recommended_tenure")),
        "recommended_emi": clean_value(row.get("recommended_emi")),
    }


def decision(application_id: int) -> dict[str, Any]:
    row = get_application_row(application_id)
    return {
        "application_id": application_id,
        "decision_state": row.get("decision_state"),
        "requested_amount": clean_value(row.get("requested_amount")),
        "recommended_amount": clean_value(row.get("decision_recommended_amount")),
        "recommended_tenure": clean_value(row.get("decision_recommended_tenure")),
        "recommended_emi": clean_value(row.get("decision_recommended_emi")),
        "reasons": parse_json(row.get("decision_reasons"), []),
        "loan_officer_explanation": parse_json(row.get("loan_officer_explanation"), {}),
        "borrower_explanation": parse_json(row.get("borrower_explanation"), {}),
    }


def credit_path(application_id: int) -> dict[str, Any]:
    row = get_application_row(application_id)
    return {
        "application_id": application_id,
        "starter_credit_eligible": clean_value(row.get("starter_credit_eligible")),
        "starter_amount": clean_value(row.get("starter_amount")),
        "starter_tenure": clean_value(row.get("starter_tenure")),
        "starter_emi": clean_value(row.get("starter_emi")),
        "starter_reason": clean_value(row.get("starter_reason")),
        "simulated_events": parse_json(row.get("adaptive_path_events"), []),
        "simulated_observations": parse_json(row.get("adaptive_path_observations"), []),
        "final_decision": clean_value(row.get("adaptive_path_final_decision")),
        "final_recommended_amount": clean_value(row.get("adaptive_path_final_recommended_amount")),
    }


def analyze_application(application_id: int) -> dict[str, Any]:
    return {
        "application_id": application_id,
        "financial_profile": financial_profile(application_id),
        "forecast": forecast(application_id),
        "stress_test": stress_test(application_id),
        "repayment_envelope": repayment_envelope(application_id),
        "decision": decision(application_id),
        "credit_path": credit_path(application_id),
    }


def simulate_repayment_event(application_id: int, event: str) -> dict[str, Any]:
    row = get_application_row(application_id)
    adaptive_policy = load_adaptive_credit_policy()
    envelope_policy = load_envelope_policy()
    decision_policy = load_decision_policy()
    path = simulate_adaptive_path(
        row,
        [event],
        adaptive_policy,
        envelope_policy,
        decision_policy,
    )
    return {
        "application_id": application_id,
        "mock_simulation": True,
        "event": event,
        "result": path["simulated_observations"][0] if path["simulated_observations"] else None,
    }


def find_emergency_expense_amount() -> float:
    policy = load_stress_policy()
    for scenario in policy.scenarios:
        if scenario.name == "one_off_expense_shock":
            return float(scenario.expense_shock)
    return 5000.0


def recompute_demo_result(row: pd.Series, action: str, adjustments: dict[str, Any]) -> dict[str, Any]:
    updated = row.copy()
    stress = simulate_borrower_stress(updated, load_stress_policy())
    updated["stress_probability"] = stress["stress_probability"]
    updated["stress_minimum_remaining_cash_buffer"] = stress["minimum_remaining_cash_buffer"]
    updated["stress_worst_scenario"] = stress["worst_scenario"]

    envelope = generate_repayment_envelope(updated, load_envelope_policy())
    updated["maximum_safe_exposure"] = envelope["maximum_safe_exposure"]
    updated["recommended_amount"] = envelope["recommended_amount"]
    updated["recommended_tenure"] = envelope["recommended_tenure"]
    updated["recommended_emi"] = envelope["recommended_emi"]
    decision_result = make_decision(updated, load_decision_policy())

    return {
        "application_id": int(row["loan_id"]),
        "mock_simulation": True,
        "action": action,
        "applied_adjustments": adjustments,
        "result": {
            "decision_state": decision_result["decision_state"],
            "recommended_amount": clean_value(decision_result["decision_recommended_amount"]),
            "recommended_tenure": clean_value(decision_result["decision_recommended_tenure"]),
            "recommended_emi": clean_value(decision_result["decision_recommended_emi"]),
            "maximum_safe_exposure": clean_value(envelope["maximum_safe_exposure"]),
            "updated_confidence_score": clean_value(updated.get("confidence_score")),
            "updated_risk_probability": clean_value(updated.get("risk_model_probability")),
            "stress_probability": clean_value(stress["stress_probability"]),
            "stress_survival": clean_value(1.0 - stress["stress_probability"]),
            "minimum_remaining_cash_buffer": clean_value(stress["minimum_remaining_cash_buffer"]),
            "reason": decision_result["decision_reasons"][0],
            "decision_reasons": decision_result["decision_reasons"],
        },
    }


def run_demo_simulation(application_id: int, action: str) -> dict[str, Any]:
    row = get_application_row(application_id)
    if action in {"on_time", "late", "missed"}:
        simulated = simulate_repayment_event(application_id, action)
        result = simulated["result"] or {}
        return {
            "application_id": application_id,
            "mock_simulation": True,
            "action": action,
            "applied_adjustments": {"repayment_event": action},
            "result": {
                "decision_state": result.get("decision_state"),
                "recommended_amount": clean_value(result.get("recommended_amount")),
                "recommended_tenure": clean_value(result.get("recommended_tenure")),
                "recommended_emi": clean_value(result.get("recommended_emi")),
                "maximum_safe_exposure": clean_value(result.get("maximum_safe_exposure")),
                "updated_confidence_score": clean_value(result.get("updated_confidence_score")),
                "updated_risk_probability": clean_value(result.get("updated_risk_probability")),
                "stress_probability": None,
                "stress_survival": None,
                "minimum_remaining_cash_buffer": None,
                "reason": (result.get("decision_reasons") or ["re-underwritten after repayment observation"])[0],
                "decision_reasons": result.get("decision_reasons") or [],
            },
        }

    updated = row.copy()
    if action == "income_shock_20":
        income_loss = safe_float(updated.get("mean_monthly_inflow"), 0.0) * 0.20
        updated["mean_monthly_inflow"] = max(0.0, safe_float(updated.get("mean_monthly_inflow"), 0.0) - income_loss)
        updated["mean_monthly_net_cash_flow"] = safe_float(updated.get("mean_monthly_net_cash_flow"), 0.0) - income_loss
        for column in ("cash_flow_forecast_p10", "cash_flow_forecast_p50", "cash_flow_forecast_p90"):
            updated[column] = safe_float(updated.get(column), 0.0) - income_loss
        return recompute_demo_result(updated, action, {"income_multiplier": 0.8, "monthly_income_loss": income_loss})

    if action == "emergency_expense":
        expense = find_emergency_expense_amount()
        updated["pre_loan_latest_balance"] = safe_float(updated.get("pre_loan_latest_balance"), 0.0) - expense
        return recompute_demo_result(updated, action, {"one_off_expense": expense})

    if action == "additional_evidence":
        ladder = rank_evidence_options(updated, load_evidence_ladder_policy())
        gain = safe_float(ladder.get("expected_confidence_improvement"), 0.0)
        updated["confidence_score"] = min(100.0, safe_float(updated.get("confidence_score"), 0.0) + gain)
        return recompute_demo_result(
            updated,
            action,
            {
                "recommended_evidence": ladder.get("recommended_evidence"),
                "expected_confidence_improvement": gain,
            },
        )

    raise HTTPException(status_code=400, detail="Unsupported demo simulation action")


def additional_evidence(application_id: int, evidence_type: str | None) -> dict[str, Any]:
    row = get_application_row(application_id)
    rankings = parse_json(row.get("evidence_ladder_rankings"), [])
    selected = None
    if evidence_type is not None:
        selected = next((item for item in rankings if item.get("evidence") == evidence_type), None)
    if selected is None and rankings:
        selected = rankings[0]
    return {
        "application_id": application_id,
        "mock_external_retrieval": True,
        "recommended_evidence": row.get("recommended_evidence"),
        "selected_evidence": selected,
        "rankings": rankings,
    }
