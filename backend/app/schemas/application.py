"""Borrower application API schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class LoanApplicationCreateRequest(BaseModel):
    requested_amount: Decimal | None = Field(default=None, gt=0, le=5_000_000)
    requested_tenure: int | None = Field(default=None, ge=3, le=84)
    loan_purpose: str | None = Field(default=None, max_length=255)
    employment_type: str | None = Field(default=None, max_length=128)
    declared_monthly_income: Decimal | None = Field(default=None, ge=0, le=2_000_000)
    declared_monthly_expenses: Decimal | None = Field(default=None, ge=0, le=2_000_000)
    existing_monthly_emi: Decimal | None = Field(default=None, ge=0, le=2_000_000)


class LoanApplicationUpdateRequest(LoanApplicationCreateRequest):
    pass


class LoanApplicationResponse(BaseModel):
    id: int
    requested_amount: Decimal | None
    requested_tenure: int | None
    loan_purpose: str | None
    employment_type: str | None
    declared_monthly_income: Decimal | None
    declared_monthly_expenses: Decimal | None
    existing_monthly_emi: Decimal | None
    status: str
    financial_data_source: str | None
    demo_financial_profile_connected: bool
    submitted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    latest_underwriting: dict | None = None
    latest_admin_decision: dict | None = None


class SubmitApplicationResponse(BaseModel):
    application: LoanApplicationResponse
    underwriting: dict | None


class ConnectDemoFinancialProfileResponse(BaseModel):
    application_id: int
    financial_data_source: str
    label: str
    demo_profile_reference: str


class ApplicationDecisionStatus(BaseModel):
    message: str
    status: str


class RequiredApplicationFields(BaseModel):
    requested_amount: Decimal = Field(gt=0, le=5_000_000)
    requested_tenure: int = Field(ge=3, le=84)
    loan_purpose: str = Field(min_length=2, max_length=255)
    employment_type: str = Field(min_length=2, max_length=128)
    declared_monthly_income: Decimal = Field(ge=0, le=2_000_000)
    declared_monthly_expenses: Decimal = Field(ge=0, le=2_000_000)
    existing_monthly_emi: Decimal = Field(ge=0, le=2_000_000)

    @field_validator("declared_monthly_expenses", "existing_monthly_emi")
    @classmethod
    def normalize_money(cls, value: Decimal) -> Decimal:
        return value
