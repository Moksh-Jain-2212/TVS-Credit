"""Bridge live platform applications into existing NADI underwriting services."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import utc_now
from app.models import AlternativeSourceType, ApplicationStatus, AuditLog, LoanApplication, UnderwritingResult, User
from app.services import application_repository
from app.services.adaptive_credit_path import load_adaptive_credit_policy, starter_recommendation
from app.services.behavioral_risk import assess_behavioral_risk, latest_active_snapshots
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


def numeric(values: list[Any]) -> list[float]:
    return [float(value) for value in values if value is not None and not pd.isna(value)]


def months_between(start: Any, end: Any) -> int:
    if start is None or end is None:
        return 0
    if isinstance(start, str):
        start = datetime.fromisoformat(start)
    if isinstance(end, str):
        end = datetime.fromisoformat(end)
    return max(1, ((end.year - start.year) * 12) + (end.month - start.month) + 1)


def build_declared_row(application: LoanApplication, session: Session) -> pd.Series:
    snapshots = latest_active_snapshots(session, application.id)
    envelope_policy = load_envelope_policy()
    requested_amount = float(application.requested_amount or 0)
    requested_tenure = int(application.requested_tenure or 1)
    scheduled_payment = estimate_emi(requested_amount, requested_tenure, envelope_policy.annual_interest_rate)
    declared_income = float(application.declared_monthly_income or 0)
    declared_expenses = float(application.declared_monthly_expenses or 0)
    existing_emi = float(application.existing_monthly_emi or 0)
    inflow_candidates = [declared_income]
    outflow_candidates = [declared_expenses + existing_emi]
    net_candidates = [declared_income - declared_expenses - existing_emi]
    stability_scores: list[float] = []
    transaction_density = 0.0
    history_months = 0
    anomaly_flags: list[str] = []
    source_labels: list[str] = []

    for snapshot in snapshots:
        features = snapshot.normalized_features_json
        source_labels.append(snapshot.source_type.value)
        history_months = max(history_months, months_between(snapshot.provenance_json.get("period_start"), snapshot.provenance_json.get("period_end")))
        history_months = max(
            history_months,
            int(features.get("active_filing_months") or features.get("observable_account_tenure_months") or features.get("observed_bills") or 0),
        )
        if snapshot.source_type == AlternativeSourceType.UPI:
            inflow_candidates.append(float(features.get("monthly_inflow") or 0))
            outflow_candidates.append(float(features.get("monthly_outflow") or 0))
            net_candidates.append(float(features.get("monthly_net_inflow") or 0))
            transaction_density = max(transaction_density, float(features.get("transactions_per_month") or 0))
            stability_scores.extend(numeric([features.get("inflow_stability"), features.get("transaction_frequency_stability")]))
        elif snapshot.source_type == AlternativeSourceType.GST:
            turnover = float(features.get("median_monthly_turnover") or 0)
            inflow_candidates.append(turnover)
            net_candidates.append(turnover * 0.28)
            stability_scores.append(float(features.get("business_inflow_consistency") or 0))
        elif snapshot.source_type == AlternativeSourceType.UTILITIES:
            outflow_candidates.append(float(features.get("observed_bills") or 0) * 500)
            stability_scores.extend(numeric([features.get("bill_amount_stability"), features.get("payment_continuity")]))
        elif snapshot.source_type == AlternativeSourceType.ECOMMERCE:
            settlement = float(features.get("median_monthly_settlement") or 0)
            inflow_candidates.append(settlement)
            net_candidates.append(settlement * 0.32)
            stability_scores.append(float(features.get("merchant_revenue_stability") or 0))
        elif snapshot.source_type == AlternativeSourceType.TELECOM:
            stability_scores.extend(numeric([features.get("interval_regularity"), features.get("recharge_spend_stability")]))
        elif snapshot.source_type == AlternativeSourceType.MOBILITY:
            stability_scores.extend(numeric([features.get("usage_consistency"), features.get("vehicle_active_month_ratio")]))

        quality = float(snapshot.data_quality_json.get("quality_score", 0.0))
        if quality < 0.65:
            anomaly_flags.append(f"{snapshot.source_type.value} data quality is low")

    mean_inflow = max(inflow_candidates) if inflow_candidates else declared_income
    mean_outflow = max(outflow_candidates) if outflow_candidates else declared_expenses + existing_emi
    mean_net = sum(net_candidates) / max(1, len(net_candidates))
    stability = max(0.05, min(1.0, sum(stability_scores) / len(stability_scores))) if stability_scores else 0.45
    if declared_income and mean_inflow > declared_income * 3:
        anomaly_flags.append("alternative inflow is materially higher than declared income")
    if mean_net <= 0:
        anomaly_flags.append("observed net cash flow is not positive")

    latest_buffer = max(0.0, mean_net * 1.5 + mean_inflow * 0.35)
    forecast_p50 = mean_net
    forecast_p10 = forecast_p50 - max(mean_outflow * 0.2, abs(forecast_p50) * (1.0 - stability))
    forecast_p90 = forecast_p50 + max(mean_inflow * 0.15, abs(forecast_p50) * stability * 0.5)
    row = pd.Series(
        {
            "loan_id": application.id,
            "account_id": application.user_id,
            "requested_amount": requested_amount,
            "duration_months": requested_tenure,
            "scheduled_payment": scheduled_payment,
            "pre_loan_latest_balance": latest_buffer,
            "months_of_history": history_months,
            "pre_loan_transaction_count": transaction_density * max(1, history_months),
            "transaction_density": transaction_density,
            "mean_monthly_inflow": mean_inflow,
            "mean_monthly_outflow": mean_outflow,
            "mean_monthly_net_cash_flow": mean_net,
            "positive_cash_flow_month_ratio": 1.0 if mean_net > 0 else 0.0,
            "income_volatility": 1.0 - stability,
            "balance_volatility": 1.0 - stability,
            "income_trend": 0.0,
            "average_balance": latest_buffer,
            "minimum_balance": latest_buffer - mean_outflow,
            "income_stability_score": stability,
            "cash_flow_stability_score": stability,
            "stability_history_status": "sufficient_history" if history_months >= 3 else "insufficient_history",
            "seasonality_status": "insufficient_history",
            "standing_order_count": 1 if existing_emi > 0 else 0,
            "cash_flow_forecast_status": "behavioral_forecast_available",
            "cash_flow_forecast_method": "declared_plus_alternative_data",
            "cash_flow_forecast_history_months": history_months,
            "cash_flow_forecast_p10": forecast_p10,
            "cash_flow_forecast_p50": forecast_p50,
            "cash_flow_forecast_p90": forecast_p90,
            "alternative_data_sources": source_labels,
            "alternative_data_anomaly_flags": anomaly_flags,
        }
    )
    return row


def build_live_row(application: LoanApplication, session: Session) -> pd.Series:
    if application.financial_data_source == "PKDD_DEMO" and application.source_loan_id is not None:
        row = application_repository.get_application_row(application.source_loan_id).copy()
        envelope_policy = load_envelope_policy()
        requested_amount = float(application.requested_amount or 0)
        requested_tenure = int(application.requested_tenure or 1)
        scheduled_payment = estimate_emi(requested_amount, requested_tenure, envelope_policy.annual_interest_rate)
        row["requested_amount"] = requested_amount
        row["duration_months"] = requested_tenure
        row["scheduled_payment"] = scheduled_payment
        row["live_evidence_mode"] = "PKDD_DEMO"
        return row
    row = build_declared_row(application, session)
    row["live_evidence_mode"] = "DECLARED_PLUS_ALTERNATIVE_DATA"
    return row


def analyze_platform_application(session: Session, application: LoanApplication, actor: User | None = None) -> UnderwritingResult:
    application.status = ApplicationStatus.UNDER_ANALYSIS
    session.flush()

    row = build_live_row(application, session)
    base_model_risk_probability = load_model_prediction(row) if row.get("live_evidence_mode") == "PKDD_DEMO" else None
    if base_model_risk_probability is not None:
        row["historical_model_risk_probability"] = base_model_risk_probability
    behavioral_assessment, behavioral_context = assess_behavioral_risk(
        session,
        application,
        base_model_risk_probability=base_model_risk_probability,
    )
    row["risk_model_probability"] = behavioral_context["combined_probability"]
    row["behavioral_risk_probability"] = behavioral_context["behavioral_probability"]
    row["behavioral_risk_score"] = behavioral_context["behavioral_score"]
    row["behavioral_data_coverage"] = behavioral_context["coverage"]
    row["behavioral_assessment_confidence"] = behavioral_context["confidence"]

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
    behavioral_assessment.underwriting_result = result
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
                "base_model_risk_probability": base_model_risk_probability,
                "behavioral_risk_probability": behavioral_context["behavioral_probability"],
                "combined_risk_probability": behavioral_context["combined_probability"],
                "risk_probability_available": row.get("risk_model_probability") is not None,
                "live_evidence_mode": row.get("live_evidence_mode"),
            },
        )
    )
    session.flush()
    return result
