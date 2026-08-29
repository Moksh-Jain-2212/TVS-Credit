"""Borrower-facing platform application service."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, object_session

from app.models import AdminDecision, ApplicationStatus, AuditLog, LoanApplication, UnderwritingResult, User
from app.schemas.application import LoanApplicationCreateRequest, LoanApplicationUpdateRequest, RequiredApplicationFields
from app.services import application_repository


EDITABLE_STATUSES = {ApplicationStatus.DRAFT, ApplicationStatus.MORE_INFORMATION_REQUIRED}


def decimal_or_none(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def latest_underwriting(application: LoanApplication) -> UnderwritingResult | None:
    if not application.underwriting_results:
        return None
    return max(application.underwriting_results, key=lambda item: item.created_at)


def latest_admin_decision(application: LoanApplication) -> AdminDecision | None:
    if not application.admin_decisions:
        return None
    return max(application.admin_decisions, key=lambda item: item.created_at)


def serialize_underwriting(result: UnderwritingResult | None) -> dict | None:
    if result is None:
        return None
    behavioral = result.behavioral_risk_assessment
    governance = result.governance_metadata_json or {}
    segment_analysis = governance.get("segment_analysis") if isinstance(governance, dict) else None
    return {
        "id": result.id,
        "risk_probability": decimal_or_none(result.risk_probability),
        "confidence_score": decimal_or_none(result.confidence_score),
        "confidence_band": result.confidence_band,
        "cash_flow_p10": decimal_or_none(result.cash_flow_p10),
        "cash_flow_p50": decimal_or_none(result.cash_flow_p50),
        "cash_flow_p90": decimal_or_none(result.cash_flow_p90),
        "stress_probability": decimal_or_none(result.stress_probability),
        "minimum_remaining_buffer": decimal_or_none(result.minimum_remaining_buffer),
        "worst_stress_scenario": result.worst_stress_scenario,
        "maximum_safe_exposure": decimal_or_none(result.maximum_safe_exposure),
        "recommended_amount": decimal_or_none(result.recommended_amount),
        "recommended_tenure": result.recommended_tenure,
        "recommended_emi": decimal_or_none(result.recommended_emi),
        "nadi_decision_state": result.nadi_decision_state,
        "decision_reasons": result.decision_reasons_json,
        "loan_officer_explanation": result.loan_officer_explanation_json,
        "borrower_explanation": result.borrower_explanation_json,
        "repayment_envelope": result.repayment_envelope_json,
        "segment_analysis": segment_analysis,
        "behavioral_risk": serialize_behavioral_assessment(behavioral),
        "model_version": result.model_version,
        "feature_schema_version": result.feature_schema_version,
        "underwriting_engine_version": result.underwriting_engine_version,
        "evidence_mode": result.evidence_mode,
        "governance_metadata": result.governance_metadata_json,
        "created_at": result.created_at.isoformat(),
    }


def serialize_behavioral_assessment(assessment: Any | None) -> dict | None:
    if assessment is None:
        return None
    return {
        "id": assessment.id,
        "base_model_risk_probability": decimal_or_none(assessment.base_model_risk_probability),
        "behavioral_risk_score": decimal_or_none(assessment.behavioral_risk_score),
        "behavioral_score_band": assessment.behavioral_score_band,
        "behavioral_risk_probability": decimal_or_none(assessment.behavioral_risk_probability),
        "behavioral_probability_calibration_status": assessment.behavioral_probability_calibration_status,
        "combined_risk_probability": decimal_or_none(assessment.combined_risk_probability),
        "behavioral_data_coverage": decimal_or_none(assessment.behavioral_data_coverage),
        "behavioral_assessment_confidence": decimal_or_none(assessment.behavioral_assessment_confidence),
        "source_coverage": assessment.source_coverage_json,
        "source_component_scores": assessment.source_component_scores_json,
        "factor_contributions": assessment.factor_contributions_json,
        "policy_version": assessment.policy_version,
        "created_at": assessment.created_at.isoformat(),
    }


def serialize_admin_decision(decision: AdminDecision | None) -> dict | None:
    if decision is None:
        return None
    return {
        "id": decision.id,
        "decision": decision.decision,
        "approved_amount": decimal_or_none(decision.approved_amount),
        "approved_tenure": decision.approved_tenure,
        "approved_emi": decimal_or_none(decision.approved_emi),
        "remarks": decision.remarks,
        "override_metadata": decision.override_metadata_json,
        "second_review_required": decision.second_review_required,
        "created_at": decision.created_at.isoformat(),
    }


def serialize_application(application: LoanApplication, *, borrower_safe: bool = True) -> dict:
    data = {
        "id": application.id,
        "requested_amount": application.requested_amount,
        "requested_tenure": application.requested_tenure,
        "loan_purpose": application.loan_purpose,
        "employment_type": application.employment_type,
        "borrower_segment": application.borrower_segment,
        "declared_monthly_income": application.declared_monthly_income,
        "declared_monthly_expenses": application.declared_monthly_expenses,
        "existing_monthly_emi": application.existing_monthly_emi,
        "status": application.status,
        "financial_data_source": application.financial_data_source,
        "demo_financial_profile_connected": application.financial_data_source == "PKDD_DEMO",
        "submitted_at": application.submitted_at,
        "created_at": application.created_at,
        "updated_at": application.updated_at,
        "latest_underwriting": serialize_underwriting(latest_underwriting(application)),
        "latest_admin_decision": serialize_admin_decision(latest_admin_decision(application)),
    }
    if not borrower_safe:
        data["source_account_id"] = application.source_account_id
        data["source_loan_id"] = application.source_loan_id
    return data


def get_owned_application(session: Session, user: User, application_id: int) -> LoanApplication:
    application = session.get(LoanApplication, application_id)
    if application is None or application.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def apply_fields(application: LoanApplication, request: LoanApplicationCreateRequest | LoanApplicationUpdateRequest) -> None:
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(application, field, value)


def create_application(session: Session, user: User, request: LoanApplicationCreateRequest) -> dict:
    application = LoanApplication(user=user)
    apply_fields(application, request)
    session.add(application)
    session.flush()
    session.add(AuditLog(actor_user=user, action="APPLICATION_CREATED", entity_type="LoanApplication", entity_id=application.id))
    session.commit()
    session.refresh(application)
    return serialize_application(application)


def list_applications(session: Session, user: User) -> list[dict]:
    applications = session.scalars(
        select(LoanApplication).where(LoanApplication.user_id == user.id).order_by(desc(LoanApplication.created_at))
    ).all()
    return [serialize_application(application) for application in applications]


def update_application(
    session: Session,
    user: User,
    application_id: int,
    request: LoanApplicationUpdateRequest,
) -> dict:
    application = get_owned_application(session, user, application_id)
    if application.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application cannot be edited in current status")
    if application.status == ApplicationStatus.MORE_INFORMATION_REQUIRED:
        application.status = ApplicationStatus.DRAFT
    apply_fields(application, request)
    session.add(AuditLog(actor_user=user, action="APPLICATION_UPDATED", entity_type="LoanApplication", entity_id=application.id))
    session.commit()
    session.refresh(application)
    return serialize_application(application)


def connect_demo_financial_profile(session: Session, user: User, application_id: int) -> dict:
    application = get_owned_application(session, user, application_id)
    if application.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Financial data cannot be changed now")
    frame = application_repository.load_features().sort_values(["loan_id", "account_id"]).reset_index(drop=True)
    if frame.empty:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="PKDD demo profiles unavailable")
    row = frame.iloc[(application.id - 1) % len(frame)]
    application.financial_data_source = "PKDD_DEMO"
    application.source_account_id = int(row["account_id"])
    application.source_loan_id = int(row["loan_id"])
    session.add(
        AuditLog(
            actor_user=user,
            action="DEMO_FINANCIAL_PROFILE_CONNECTED",
            entity_type="LoanApplication",
            entity_id=application.id,
            metadata_json={"financial_data_source": "PKDD_DEMO"},
        )
    )
    session.commit()
    return {
        "application_id": application.id,
        "financial_data_source": "PKDD_DEMO",
        "label": "Demo bank data connected",
        "demo_profile_reference": f"Demo profile {application.id}",
    }


def validate_ready_to_submit(application: LoanApplication) -> None:
    from app.services.alternative_data_service import alternative_data_readiness

    missing = []
    for field in RequiredApplicationFields.model_fields:
        if getattr(application, field) in {None, ""}:
            missing.append(field)
    if missing:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"missing_fields": missing})
    session = object_session(application)
    readiness = alternative_data_readiness(session, application) if session is not None else {"ready": False}
    if application.financial_data_source != "PKDD_DEMO" and not readiness["ready"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Connect demo financial data or at least one behavioral evidence source before submission",
        )


def submit_application(session: Session, user: User, application_id: int) -> dict:
    from app.services.live_underwriting import analyze_platform_application

    application = get_owned_application(session, user, application_id)
    if application.status not in EDITABLE_STATUSES:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application already submitted")
    validate_ready_to_submit(application)
    application.status = ApplicationStatus.SUBMITTED
    session.add(AuditLog(actor_user=user, action="APPLICATION_SUBMITTED", entity_type="LoanApplication", entity_id=application.id))
    session.flush()
    result = analyze_platform_application(session, application, actor=user)
    session.commit()
    session.refresh(application)
    return {"application": serialize_application(application), "underwriting": serialize_underwriting(result)}


def status_messages(application: LoanApplication) -> list[str]:
    messages = ["Application draft created"]
    if application.financial_data_source == "PKDD_DEMO":
        messages.append("Demo bank data connected")
    if application.submitted_at:
        messages.append("Application submitted")
    status_message = {
        ApplicationStatus.UNDER_ANALYSIS: "Application under analysis",
        ApplicationStatus.ADMIN_REVIEW: "Application awaiting admin review",
        ApplicationStatus.MORE_INFORMATION_REQUIRED: "More information requested",
        ApplicationStatus.APPROVED: "Application approved",
        ApplicationStatus.REJECTED: "Application rejected",
    }.get(application.status)
    if status_message:
        messages.append(status_message)
    return messages
