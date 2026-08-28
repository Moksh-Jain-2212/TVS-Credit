"""Admin API schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, Field

from app.models import AdminDecisionState


class AdminDecisionRequest(BaseModel):
    decision: AdminDecisionState
    approved_amount: Decimal | None = Field(default=None, gt=0, le=5_000_000)
    approved_tenure: int | None = Field(default=None, ge=3, le=84)
    approved_emi: Decimal | None = Field(default=None, gt=0, le=2_000_000)
    remarks: str | None = Field(default=None, max_length=2000)
