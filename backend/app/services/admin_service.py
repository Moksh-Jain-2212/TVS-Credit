"""Admin and loan-officer services."""

from __future__ import annotations

from collections import Counter
from datetime import date
from decimal import Decimal
from statistics import mean
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.database import create_session_factory, create_sqlite_engine
from app.core.security import utc_now
from app.models import (
    AdminDecision,
    AdminDecisionState,
    ApplicationStatus,
    AuditLog,
    LoanApplication,
    StandingOrder,
    Transaction,
    User,
)
from app.schemas.admin import AdminDecisionRequest
from app.services import application_repository
from app.services.alternative_data_service import application_sources
from app.services.application_service import (
    decimal_or_none,
    latest_admin_decision,
    latest_underwriting,
    serialize_admin_decision,
    serialize_application,
    serialize_underwriting,
)
from app.services.behavioral_risk import latest_behavioral_assessment
from app.services.grok_explainability import generate_explanation, latest_explanation, serialize_ai_explanation
from app.services.live_underwriting import analyze_platform_application
from app.services.finance import estimate_emi
from app.services.repayment_envelope import load_envelope_policy


def enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": enum_value(user.role),
        "is_verified": user.is_verified,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat(),
    }


def serialize_audit(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "actor_user_id": log.actor_user_id,
        "action": log.action,
        "entity_type": log.entity_type,
        "entity_id": log.entity_id,
        "metadata": log.metadata_json,
        "created_at": log.created_at.isoformat(),
    }


def risk_band(risk_probability: float | None) -> str | None:
    if risk_probability is None:
        return None
    if risk_probability <= 0.2:
        return "low"
    if risk_probability <= 0.5:
        return "medium"
    return "high"


def is_admin_override(request: AdminDecisionRequest, application: LoanApplication, result: Any) -> bool:
    nadi_state = enum_value(result.nadi_decision_state)
    requested_approval = request.decision == AdminDecisionState.APPROVE_REQUESTED
    rejected_positive_recommendation = request.decision == AdminDecisionState.REJECT and nadi_state in {"APPROVE", "SAFE_TO_LEARN"}
    approved_amount = decimal_or_none(request.approved_amount) or decimal_or_none(application.requested_amount) or 0
    safe_exposure = decimal_or_none(result.maximum_safe_exposure) or 0
    return bool(
        (requested_approval and nadi_state != "APPROVE")
        or rejected_positive_recommendation
        or (request.decision in {AdminDecisionState.APPROVE_REQUESTED, AdminDecisionState.APPROVE_RECOMMENDED} and approved_amount > safe_exposure)
    )


def override_metadata(admin: User, request: AdminDecisionRequest, application: LoanApplication, result: Any, approved_amount: Decimal | None) -> dict[str, Any]:
    override = is_admin_override(request, application, result)
    return {
        "nadi_decision": enum_value(result.nadi_decision_state),
        "nadi_recommended_amount": decimal_or_none(result.recommended_amount),
        "maximum_safe_exposure": decimal_or_none(result.maximum_safe_exposure),
        "admin_decision": enum_value(request.decision),
        "admin_approved_amount": decimal_or_none(approved_amount),
        "override": override,
        "override_reason": request.remarks if override else None,
        "actor": {"id": admin.id, "email": admin.email},
        "timestamp": utc_now().isoformat(),
    }


def latest_result_query(session: Session, application_id: int):
    return session.scalar(
        select(AdminDecision)
        .where(AdminDecision.application_id == application_id)
        .order_by(desc(AdminDecision.created_at))
    )


def dashboard(session: Session) -> dict:
    applications = session.scalars(select(LoanApplication)).all()
    counts = Counter(enum_value(application.status) for application in applications)
    return {
        "counts": {
            "pending_applications": counts.get("SUBMITTED", 0),
            "under_analysis": counts.get("UNDER_ANALYSIS", 0),
            "admin_review": counts.get("ADMIN_REVIEW", 0),
            "approved": counts.get("APPROVED", 0),
            "rejected": counts.get("REJECTED", 0),
            "more_information_required": counts.get("MORE_INFORMATION_REQUIRED", 0),
        },
        "recent_applications": list_applications(session, limit=8),
    }


def list_applications(
    session: Session,
    status_filter: str | None = None,
    nadi_decision: str | None = None,
    date_filter: date | None = None,
    risk: str | None = None,
    confidence: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    applications = session.scalars(select(LoanApplication).order_by(desc(LoanApplication.created_at))).all()
    rows: list[dict] = []
    for application in applications:
        result = latest_underwriting(application)
        decision = latest_admin_decision(application)
        if status_filter and enum_value(application.status) != status_filter:
            continue
        if nadi_decision and (result is None or enum_value(result.nadi_decision_state) != nadi_decision):
            continue
        if date_filter and (application.submitted_at is None or application.submitted_at.date() != date_filter):
            continue
        current_risk_band = risk_band(decimal_or_none(result.risk_probability) if result else None)
        if risk and current_risk_band != risk:
            continue
        if confidence and (result is None or result.confidence_band != confidence):
            continue
        rows.append(
            {
                "id": application.id,
                "applicant": application.user.name,
                "applicant_email": application.user.email,
                "requested_amount": decimal_or_none(application.requested_amount),
                "requested_tenure": application.requested_tenure,
                "submitted_at": application.submitted_at.isoformat() if application.submitted_at else None,
                "risk": current_risk_band,
                "risk_probability": decimal_or_none(result.risk_probability) if result else None,
                "historical_model_risk_probability": (
                    decimal_or_none(result.behavioral_risk_assessment.base_model_risk_probability)
                    if result and result.behavioral_risk_assessment
                    else None
                ),
                "behavioral_risk_probability": (
                    decimal_or_none(result.behavioral_risk_assessment.behavioral_risk_probability)
                    if result and result.behavioral_risk_assessment
                    else None
                ),
                "behavioral_data_coverage": (
                    decimal_or_none(result.behavioral_risk_assessment.behavioral_data_coverage)
                    if result and result.behavioral_risk_assessment
                    else None
                ),
                "confidence_band": result.confidence_band if result else None,
                "confidence_score": decimal_or_none(result.confidence_score) if result else None,
                "nadi_recommendation": enum_value(result.nadi_decision_state) if result else None,
                "recommended_amount": decimal_or_none(result.recommended_amount) if result else None,
                "application_status": enum_value(application.status),
                "final_admin_decision": enum_value(decision.decision) if decision else None,
            }
        )
    return rows[offset : offset + limit]


def get_admin_application(session: Session, application_id: int) -> LoanApplication:
    application = session.get(LoanApplication, application_id)
    if application is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def transaction_session():
    engine = create_sqlite_engine()
    return create_session_factory(engine)()


def transaction_summary(transactions: list[Transaction], standing_orders: list[StandingOrder]) -> dict:
    if not transactions:
        return {
            "average_monthly_inflow": 0,
            "average_monthly_outflow": 0,
            "net_monthly_cash_flow": 0,
            "average_balance": 0,
            "minimum_balance": 0,
            "transaction_density": 0,
            "recurring_inflows": 0,
            "recurring_outflows": 0,
            "standing_order_burden": sum(float(order.amount) for order in standing_orders),
            "income_stability": None,
            "cash_flow_stability": None,
        }
    by_month: dict[str, dict[str, float]] = {}
    balances = []
    inflow_counter: Counter[float] = Counter()
    outflow_counter: Counter[float] = Counter()
    for transaction in transactions:
        month = transaction.transaction_date.strftime("%Y-%m")
        bucket = by_month.setdefault(month, {"inflow": 0.0, "outflow": 0.0, "count": 0})
        amount = float(transaction.amount)
        if transaction.type == "PRIJEM":
            bucket["inflow"] += amount
            inflow_counter[round(amount, 2)] += 1
        else:
            bucket["outflow"] += amount
            outflow_counter[round(amount, 2)] += 1
        bucket["count"] += 1
        balances.append(float(transaction.balance))
    months = max(1, len(by_month))
    inflows = [bucket["inflow"] for bucket in by_month.values()]
    outflows = [bucket["outflow"] for bucket in by_month.values()]
    return {
        "average_monthly_inflow": sum(inflows) / months,
        "average_monthly_outflow": sum(outflows) / months,
        "net_monthly_cash_flow": (sum(inflows) - sum(outflows)) / months,
        "average_balance": mean(balances),
        "minimum_balance": min(balances),
        "transaction_density": len(transactions) / months,
        "recurring_inflows": sum(1 for _, count in inflow_counter.items() if count >= 2),
        "recurring_outflows": sum(1 for _, count in outflow_counter.items() if count >= 2),
        "standing_order_burden": sum(float(order.amount) for order in standing_orders),
        "income_stability": None,
        "cash_flow_stability": None,
    }


def transactions_for_application(application: LoanApplication) -> dict:
    if application.financial_data_source != "PKDD_DEMO" or application.source_account_id is None:
        return {"summary": transaction_summary([], []), "transactions": [], "mocked": True}
    with transaction_session() as session:
        transactions = session.scalars(
            select(Transaction)
            .where(Transaction.account_id == application.source_account_id)
            .order_by(Transaction.transaction_date)
            .limit(500)
        ).all()
        orders = session.scalars(
            select(StandingOrder).where(StandingOrder.account_id == application.source_account_id)
        ).all()
    return {
        "summary": transaction_summary(transactions, orders),
        "transactions": [
            {
                "date": transaction.transaction_date.isoformat(),
                "type": transaction.type,
                "operation": transaction.operation,
                "amount": float(transaction.amount),
                "balance": float(transaction.balance),
                "category": transaction.k_symbol,
            }
            for transaction in transactions
        ],
        "mocked": True,
        "label": "PKDD demo transaction history",
        "underwriting_evidence_scope": "UNDERWRITING_EVIDENCE uses the original pre-loan feature snapshot only.",
    }


def application_detail(session: Session, application_id: int) -> dict:
    application = get_admin_application(session, application_id)
    result = latest_underwriting(application)
    row_analysis = None
    if application.source_loan_id is not None:
        try:
            row_analysis = application_repository.analyze_application(application.source_loan_id)
        except HTTPException:
            row_analysis = None
    audit = session.scalars(
        select(AuditLog)
        .where(AuditLog.entity_type == "LoanApplication", AuditLog.entity_id == application.id)
        .order_by(AuditLog.created_at)
    ).all()
    transactions = transactions_for_application(application)
    source_summary = application_sources(session, application)
    behavioral = latest_behavioral_assessment(session, application.id)
    return {
        "borrower": serialize_user(application.user),
        "application": serialize_application(application, borrower_safe=False),
        "linked_financial_evidence": {
            "source": application.financial_data_source,
            "label": "Demo bank data connected" if application.financial_data_source == "PKDD_DEMO" else None,
            "temporal_leakage_note": "UNDERWRITING_EVIDENCE is limited to the original pre-loan PKDD snapshot.",
        },
        "alternative_data": source_summary,
        "transaction_summary": transactions["summary"],
        "transactions": transactions["transactions"][:100],
        "financial_profile": row_analysis.get("financial_profile") if row_analysis else None,
        "forecast": row_analysis.get("forecast") if row_analysis else None,
        "stress_test": row_analysis.get("stress_test") if row_analysis else None,
        "repayment_envelope": (serialize_underwriting(result) or {}).get("repayment_envelope"),
        "risk": {
            "probability": decimal_or_none(result.risk_probability) if result else None,
            "band": risk_band(decimal_or_none(result.risk_probability) if result else None),
            "historical_model_probability": (
                decimal_or_none(behavioral.base_model_risk_probability) if behavioral else None
            ),
            "behavioral_probability": (
                decimal_or_none(behavioral.behavioral_risk_probability) if behavioral else None
            ),
            "combined_probability": (
                decimal_or_none(behavioral.combined_risk_probability) if behavioral else decimal_or_none(result.risk_probability) if result else None
            ),
        },
        "behavioral_risk": {
            "score": decimal_or_none(behavioral.behavioral_risk_score) if behavioral else None,
            "score_band": behavioral.behavioral_score_band if behavioral else None,
            "probability": decimal_or_none(behavioral.behavioral_risk_probability) if behavioral else None,
            "calibration_status": behavioral.behavioral_probability_calibration_status if behavioral else None,
            "coverage": decimal_or_none(behavioral.behavioral_data_coverage) if behavioral else None,
            "assessment_confidence": decimal_or_none(behavioral.behavioral_assessment_confidence) if behavioral else None,
            "source_coverage": behavioral.source_coverage_json if behavioral else [],
            "source_component_scores": behavioral.source_component_scores_json if behavioral else [],
            "factor_contributions": behavioral.factor_contributions_json if behavioral else [],
            "policy_version": behavioral.policy_version if behavioral else None,
        },
        "evidence_confidence": {
            "score": decimal_or_none(result.confidence_score) if result else None,
            "band": result.confidence_band if result else None,
        },
        "nadi_recommendation": {
            "decision": enum_value(result.nadi_decision_state) if result else None,
            "recommended_amount": decimal_or_none(result.recommended_amount) if result else None,
            "recommended_tenure": result.recommended_tenure if result else None,
            "recommended_emi": decimal_or_none(result.recommended_emi) if result else None,
            "maximum_safe_exposure": decimal_or_none(result.maximum_safe_exposure) if result else None,
            "reasons": result.decision_reasons_json if result else [],
        },
        "explanations": {
            "loan_officer": result.loan_officer_explanation_json if result else None,
            "borrower": result.borrower_explanation_json if result else None,
            "grok": serialize_ai_explanation(latest_explanation(session, application.id)),
        },
        "admin_decisions": [serialize_admin_decision(decision) for decision in application.admin_decisions],
        "audit_history": [serialize_audit(log) for log in audit],
    }


def get_grok_explanation(session: Session, application_id: int) -> dict:
    application = get_admin_application(session, application_id)
    return serialize_ai_explanation(latest_explanation(session, application.id)) or generate_explanation(session, application)


def generate_grok_explanation(session: Session, application_id: int) -> dict:
    application = get_admin_application(session, application_id)
    return generate_explanation(session, application, force_refresh=True)


def analyze_application(session: Session, admin: User, application_id: int) -> dict:
    application = get_admin_application(session, application_id)
    if application.status in {ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application already finalized")
    result = analyze_platform_application(session, application, actor=admin)
    session.commit()
    session.refresh(application)
    return application_detail(session, application.id) | {"underwriting_result": serialize_underwriting(result)}


def create_admin_decision(
    session: Session,
    admin: User,
    application_id: int,
    request: AdminDecisionRequest,
) -> dict:
    application = get_admin_application(session, application_id)
    if application.status in {ApplicationStatus.APPROVED, ApplicationStatus.REJECTED}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Application already finalized")
    result = latest_underwriting(application)
    if result is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Run NADI analysis before admin decision")

    approved_amount = request.approved_amount
    approved_tenure = request.approved_tenure
    approved_emi = request.approved_emi
    if request.decision == AdminDecisionState.APPROVE_RECOMMENDED:
        approved_amount = Decimal(str(result.recommended_amount or 0))
        approved_tenure = result.recommended_tenure
    if request.decision == AdminDecisionState.APPROVE_REQUESTED:
        approved_amount = approved_amount or application.requested_amount
        approved_tenure = approved_tenure or application.requested_tenure
    if request.decision == AdminDecisionState.APPROVE_REQUESTED and (approved_amount is None or approved_tenure is None):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Approved amount and tenure are required")
    if (
        request.decision in {AdminDecisionState.APPROVE_REQUESTED, AdminDecisionState.APPROVE_RECOMMENDED}
        and approved_amount is not None
        and approved_tenure is not None
        and float(approved_amount) > 0
    ):
        approved_emi = Decimal(
            str(
                round(
                    estimate_emi(float(approved_amount), int(approved_tenure), load_envelope_policy().annual_interest_rate),
                    2,
                )
            )
        )
    is_override = is_admin_override(request, application, result)
    if is_override and not (request.remarks or "").strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Override reason is required when final decision materially differs from NADI.",
        )
    metadata = override_metadata(admin, request, application, result, approved_amount)

    decision = AdminDecision(
        application=application,
        admin_user=admin,
        decision=request.decision,
        approved_amount=approved_amount,
        approved_tenure=approved_tenure,
        approved_emi=approved_emi,
        remarks=request.remarks,
        override_metadata_json=metadata,
        second_review_required=bool(is_override and (decimal_or_none(result.risk_probability) or 0) > 0.55),
    )
    status_map = {
        AdminDecisionState.APPROVE_REQUESTED: ApplicationStatus.APPROVED,
        AdminDecisionState.APPROVE_RECOMMENDED: ApplicationStatus.APPROVED,
        AdminDecisionState.REQUEST_MORE_INFORMATION: ApplicationStatus.MORE_INFORMATION_REQUIRED,
        AdminDecisionState.REJECT: ApplicationStatus.REJECTED,
    }
    application.status = status_map[request.decision]
    session.add(decision)
    session.add(
        AuditLog(
            actor_user=admin,
            action="ADMIN_DECISION_CREATED",
            entity_type="LoanApplication",
            entity_id=application.id,
            metadata_json={
                "nadi_decision": enum_value(result.nadi_decision_state),
                "admin_decision": enum_value(request.decision),
                "override": is_override,
                "override_reason": request.remarks if is_override else None,
            },
        )
    )
    session.commit()
    session.refresh(application)
    return application_detail(session, application.id)


def get_user_detail(session: Session, user_id: int) -> dict:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {
        "user": serialize_user(user),
        "applications": [serialize_application(application, borrower_safe=False) for application in user.applications],
    }
