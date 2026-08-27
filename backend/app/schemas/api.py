"""API request schemas for the NADI backend."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ApplicationCreateRequest(BaseModel):
    loan_id: int | None = Field(default=None, description="Existing PKDD loan/application id.")
    account_id: int | None = Field(default=None, description="Existing PKDD account id.")


class RepaymentEventRequest(BaseModel):
    event: Literal["on_time", "late", "missed"]


class DemoSimulationRequest(BaseModel):
    action: Literal[
        "on_time",
        "late",
        "missed",
        "income_shock_20",
        "emergency_expense",
        "additional_evidence",
    ]


class AdditionalEvidenceRequest(BaseModel):
    evidence_type: str | None = Field(
        default=None,
        description="Optional mocked evidence type to inspect.",
    )
