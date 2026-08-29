"""Loan application and underwriting persistence models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.app_database import AppBase
from app.models.auth import utc_now


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_ANALYSIS = "UNDER_ANALYSIS"
    ADMIN_REVIEW = "ADMIN_REVIEW"
    MORE_INFORMATION_REQUIRED = "MORE_INFORMATION_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class NadiDecisionState(StrEnum):
    APPROVE = "APPROVE"
    SAFE_TO_LEARN = "SAFE_TO_LEARN"
    EVIDENCE_NEEDED = "EVIDENCE_NEEDED"
    NOT_CURRENTLY_AFFORDABLE = "NOT_CURRENTLY_AFFORDABLE"


class AdminDecisionState(StrEnum):
    APPROVE_REQUESTED = "APPROVE_REQUESTED"
    APPROVE_RECOMMENDED = "APPROVE_RECOMMENDED"
    REQUEST_MORE_INFORMATION = "REQUEST_MORE_INFORMATION"
    REJECT = "REJECT"


application_status_enum = Enum(
    ApplicationStatus,
    name="application_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
nadi_decision_enum = Enum(
    NadiDecisionState,
    name="nadi_decision_state",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
admin_decision_enum = Enum(
    AdminDecisionState,
    name="admin_decision_state",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class LoanApplication(AppBase):
    __tablename__ = "loan_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    requested_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    requested_tenure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    loan_purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    declared_monthly_income: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    declared_monthly_expenses: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    existing_monthly_emi: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[ApplicationStatus] = mapped_column(
        application_status_enum,
        nullable=False,
        default=ApplicationStatus.DRAFT,
    )
    financial_data_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_account_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_loan_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    user: Mapped["User"] = relationship(back_populates="applications")
    underwriting_results: Mapped[list["UnderwritingResult"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    admin_decisions: Mapped[list["AdminDecision"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    alternative_data_consents: Mapped[list["AlternativeDataConsent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    alternative_data_connections: Mapped[list["AlternativeDataConnection"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    alternative_data_snapshots: Mapped[list["AlternativeDataSnapshot"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    behavioral_risk_assessments: Mapped[list["BehavioralRiskAssessment"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    ai_explanations: Mapped[list["AIExplanation"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )


class UnderwritingResult(AppBase):
    __tablename__ = "underwriting_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )
    risk_probability: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    confidence_band: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cash_flow_p10: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cash_flow_p50: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    cash_flow_p90: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    stress_probability: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    minimum_remaining_buffer: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    worst_stress_scenario: Mapped[str | None] = mapped_column(String(128), nullable=True)
    maximum_safe_exposure: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    recommended_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    recommended_tenure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommended_emi: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    nadi_decision_state: Mapped[NadiDecisionState | None] = mapped_column(nadi_decision_enum, nullable=True)
    decision_reasons_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    loan_officer_explanation_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    borrower_explanation_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    repayment_envelope_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    application: Mapped[LoanApplication] = relationship(back_populates="underwriting_results")
    behavioral_risk_assessment: Mapped["BehavioralRiskAssessment | None"] = relationship(
        back_populates="underwriting_result",
        uselist=False,
    )
    ai_explanations: Mapped[list["AIExplanation"]] = relationship(back_populates="underwriting_result")


class AdminDecision(AppBase):
    __tablename__ = "admin_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("loan_applications.id"),
        nullable=False,
        index=True,
    )
    admin_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    decision: Mapped[AdminDecisionState] = mapped_column(admin_decision_enum, nullable=False)
    approved_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    approved_tenure: Mapped[int | None] = mapped_column(Integer, nullable=True)
    approved_emi: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    application: Mapped[LoanApplication] = relationship(back_populates="admin_decisions")
    admin_user: Mapped["User"] = relationship(back_populates="admin_decisions")
