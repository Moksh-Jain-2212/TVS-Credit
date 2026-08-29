"""Alternative-data consent, provenance, behavioral risk, and AI explanation models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.app_database import AppBase
from app.models.auth import utc_now


class AlternativeSourceType(StrEnum):
    GST = "GST"
    UPI = "UPI"
    TELECOM = "TELECOM"
    UTILITIES = "UTILITIES"
    ECOMMERCE = "ECOMMERCE"
    MOBILITY = "MOBILITY"


class ConsentStatus(StrEnum):
    GRANTED = "GRANTED"
    REVOKED = "REVOKED"


class DataConnectionMode(StrEnum):
    MOCK = "MOCK"
    MANUAL = "MANUAL"
    UPLOAD = "UPLOAD"
    API = "API"


class DataConnectionStatus(StrEnum):
    CONNECTED = "CONNECTED"
    REVOKED = "REVOKED"
    FAILED = "FAILED"


source_type_enum = Enum(
    AlternativeSourceType,
    name="alternative_source_type",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
consent_status_enum = Enum(
    ConsentStatus,
    name="alternative_data_consent_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
connection_mode_enum = Enum(
    DataConnectionMode,
    name="alternative_data_connection_mode",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)
connection_status_enum = Enum(
    DataConnectionStatus,
    name="alternative_data_connection_status",
    native_enum=False,
    create_constraint=True,
    validate_strings=True,
)


class AlternativeDataConsent(AppBase):
    __tablename__ = "alternative_data_consents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), nullable=False, index=True)
    source_type: Mapped[AlternativeSourceType] = mapped_column(source_type_enum, nullable=False, index=True)
    consent_status: Mapped[ConsentStatus] = mapped_column(consent_status_enum, nullable=False)
    consented_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False, default="Alternative-data underwriting evidence")
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False, default="alt-consent-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    application: Mapped["LoanApplication"] = relationship(back_populates="alternative_data_consents")


class AlternativeDataConnection(AppBase):
    __tablename__ = "alternative_data_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), nullable=False, index=True)
    source_type: Mapped[AlternativeSourceType] = mapped_column(source_type_enum, nullable=False, index=True)
    mode: Mapped[DataConnectionMode] = mapped_column(connection_mode_enum, nullable=False)
    status: Mapped[DataConnectionStatus] = mapped_column(connection_status_enum, nullable=False)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False, default="alt-data-v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    application: Mapped["LoanApplication"] = relationship(back_populates="alternative_data_connections")


class AlternativeDataSnapshot(AppBase):
    __tablename__ = "alternative_data_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), nullable=False, index=True)
    source_type: Mapped[AlternativeSourceType] = mapped_column(source_type_enum, nullable=False, index=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    normalized_features_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    data_quality_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    provenance_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    application: Mapped["LoanApplication"] = relationship(back_populates="alternative_data_snapshots")


class BehavioralRiskAssessment(AppBase):
    __tablename__ = "behavioral_risk_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), nullable=False, index=True)
    underwriting_result_id: Mapped[int | None] = mapped_column(ForeignKey("underwriting_results.id"), nullable=True, index=True)
    base_model_risk_probability: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    behavioral_risk_score: Mapped[float | None] = mapped_column(Numeric(7, 3), nullable=True)
    behavioral_score_band: Mapped[str | None] = mapped_column(String(64), nullable=True)
    behavioral_risk_probability: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    behavioral_probability_calibration_status: Mapped[str] = mapped_column(String(64), nullable=False, default="POLICY_HEURISTIC")
    combined_risk_probability: Mapped[float | None] = mapped_column(Numeric(7, 6), nullable=True)
    behavioral_data_coverage: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False, default=0)
    behavioral_assessment_confidence: Mapped[float] = mapped_column(Numeric(7, 3), nullable=False, default=0)
    source_coverage_json: Mapped[list] = mapped_column(JSON, nullable=False)
    source_component_scores_json: Mapped[list] = mapped_column(JSON, nullable=False)
    factor_contributions_json: Mapped[list] = mapped_column(JSON, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    application: Mapped["LoanApplication"] = relationship(back_populates="behavioral_risk_assessments")
    underwriting_result: Mapped["UnderwritingResult | None"] = relationship(back_populates="behavioral_risk_assessment")


class AIExplanation(AppBase):
    __tablename__ = "ai_explanations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("loan_applications.id"), nullable=False, index=True)
    underwriting_result_id: Mapped[int | None] = mapped_column(ForeignKey("underwriting_results.id"), nullable=True, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    structured_response_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(64), nullable=False)
    error_metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    application: Mapped["LoanApplication"] = relationship(back_populates="ai_explanations")
    underwriting_result: Mapped["UnderwritingResult | None"] = relationship(back_populates="ai_explanations")
