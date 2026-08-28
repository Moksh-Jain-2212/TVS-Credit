"""Bridge live platform applications into existing NADI underwriting services."""

from __future__ import annotations

import json
from pathlib import Path
from decimal import Decimal
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import utc_now
from app.models import ApplicationStatus, AuditLog, LoanApplication, UnderwritingResult, User
from app.services import application_repository
from app.services.adaptive_credit_path import load_adaptive_credit_policy, starter_recommendation
from app.services.decision_engine import load_decision_policy, make_decision
from app.services.evidence_confidence import load_policy as load_evidence_confidence_policy
from app.services.evidence_confidence import score_evidence_confidence
from app.services.evidence_ladder import load_evidence_ladder_policy, rank_evidence_options
from app.services.explainability import build_explanations
from app.services.repayment_envelope import estimate_emi, generate_repayment_envelope, load_envelope_policy
from app.services.stress_simulator import load_stress_policy, simulate_borrower_stress


MODEL_PATH = Path(__file__).resolve().parents[3] / "models" / "repayment_risk_model.joblib"


def clean(value: Any) -> Any:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


def jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [jsonable(item) for item in value]
    if isinstance(value, Decimal):
        return float(value)
    if hasattr(value, "item"):
        return jsonable(value.item())
    if pd.isna(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def load_model_prediction(row: pd.Series) -> float | None:
    if not MODEL_PATH.exists():
        return None
    artifact = joblib.load(MODEL_PATH)
    model = artifact["model"]
    columns = artifact["feature_columns"]
    frame = pd.DataFrame([{column: row.get(column) for column in columns}])
    probability = model.predict_proba(frame)[:, 1][0]
    return float(probability)


def build_live_row(application: LoanApplication) -> pd.Series:
    if application.financial_data_source != "PKDD_DEMO" or application.source_loan_id is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="PKDD demo data is not connected")
    row = application_repository.get_application_row(application.source_loan_id).copy()
    envelope_policy = load_envelope_policy()
    requested_amount = float(application.requested_amount or 0)
    requested_tenure = int(application.requested_tenure or 1)
    scheduled_payment = estimate_emi(requested_amount, requested_tenure, envelope_policy.annual_interest_rate)
    row["requested_amount"] = requested_amount
    row["duration_months"] = requested_tenure
    row["scheduled_payment"] = scheduled_payment
    return row


def analyze_platform_application(session: Session, application: LoanApplication, actor: User | None = None) -> UnderwritingResult:
    application.status = ApplicationStatus.UNDER_ANALYSIS
    session.flush()

    row = build_live_row(application)
    risk_probability = load_model_prediction(row)
    if risk_probability is not None:
        row["risk_model_probability"] = risk_probability

    confidence = score_evidence_confidence(row, load_evidence_confidence_policy(), row.get("risk_model_probability"))
    row["confidence_score"] = confidence["confidence_score"]
    row["confidence_band"] = confidence["confidence_band"]
    row["confidence_reasons"] = json.dumps(confidence["reasons"])
    row["confidence_components"] = json.dumps(confidence["components"], sort_keys=True)

    stress = simulate_borrower_stress(row, load_stress_policy())
    row["stress_probability"] = stress["stress_probability"]
    row["stress_minimum_remaining_cash_buffer"] = stress["minimum_remaining_cash_buffer"]
    row["stress_worst_scenario"] = stress["worst_scenario"]
    row["stress_worst_projected_period"] = stress["worst_projected_period"]
    row["stress_scenario_results"] = json.dumps(stress["scenario_results"], sort_keys=True)
    row["stress_scenario_survival"] = json.dumps(stress["scenario_survival"], sort_keys=True)

    envelope = generate_repayment_envelope(row, load_envelope_policy())
    row["maximum_safe_exposure"] = envelope["maximum_safe_exposure"]
    row["recommended_amount"] = envelope["recommended_amount"]
    row["recommended_tenure"] = envelope["recommended_tenure"]
    row["recommended_emi"] = envelope["recommended_emi"]
    row["repayment_all_evaluated_combinations"] = json.dumps(envelope["all_evaluated_combinations"], sort_keys=True)
    row["repayment_safe_combinations"] = json.dumps(envelope["safe_combinations"], sort_keys=True)

    decision = make_decision(row, load_decision_policy())
    row["decision_state"] = decision["decision_state"]
    row["decision_recommended_amount"] = decision["decision_recommended_amount"]
    row["decision_recommended_tenure"] = decision["decision_recommended_tenure"]
    row["decision_recommended_emi"] = decision["decision_recommended_emi"]
    row["decision_reasons"] = json.dumps(decision["decision_reasons"])

    evidence = rank_evidence_options(row, load_evidence_ladder_policy())
    row["evidence_ladder_status"] = evidence["status"]
    row["recommended_evidence"] = evidence["recommended_evidence"]
    row["expected_confidence_improvement"] = evidence["expected_confidence_improvement"]
    row["evidence_reason"] = evidence["reason"]
    row["evidence_ladder_rankings"] = json.dumps(evidence["rankings"], sort_keys=True)

    starter = starter_recommendation(row, load_adaptive_credit_policy())
    row["starter_credit_eligible"] = starter["starter_credit_eligible"]
    row["starter_amount"] = starter["starter_amount"]
    row["starter_tenure"] = starter["starter_tenure"]
    row["starter_emi"] = starter["starter_emi"]
    row["starter_reason"] = starter["starter_reason"]

    explanations = build_explanations(row)
    result = UnderwritingResult(
        application=application,
        risk_probability=clean(row.get("risk_model_probability")),
        confidence_score=clean(row.get("confidence_score")),
        confidence_band=clean(row.get("confidence_band")),
        cash_flow_p10=clean(row.get("cash_flow_forecast_p10")),
        cash_flow_p50=clean(row.get("cash_flow_forecast_p50")),
        cash_flow_p90=clean(row.get("cash_flow_forecast_p90")),
        stress_probability=clean(row.get("stress_probability")),
        minimum_remaining_buffer=clean(row.get("stress_minimum_remaining_cash_buffer")),
        worst_stress_scenario=clean(row.get("stress_worst_scenario")),
        maximum_safe_exposure=clean(row.get("maximum_safe_exposure")),
        recommended_amount=clean(row.get("decision_recommended_amount")),
        recommended_tenure=clean(row.get("decision_recommended_tenure")),
        recommended_emi=clean(row.get("decision_recommended_emi")),
        nadi_decision_state=clean(row.get("decision_state")),
        decision_reasons_json=jsonable(decision["decision_reasons"]),
        loan_officer_explanation_json=jsonable(explanations["loan_officer"]),
        borrower_explanation_json=jsonable(explanations["borrower"]),
        repayment_envelope_json=jsonable(envelope),
    )
    application.status = ApplicationStatus.ADMIN_REVIEW
    application.submitted_at = application.submitted_at or utc_now()
    session.add(result)
    session.add(
        AuditLog(
            actor_user=actor,
            action="UNDERWRITING_COMPLETED",
            entity_type="LoanApplication",
            entity_id=application.id,
            metadata_json={
                "financial_data_source": application.financial_data_source,
                "nadi_decision_state": decision["decision_state"],
                "risk_probability_available": risk_probability is not None,
            },
        )
    )
    session.flush()
    return result
