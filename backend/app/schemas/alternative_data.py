"""Alternative-data request schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AlternativeDataConsentRequest(BaseModel):
    granted: bool = True
    purpose: str = Field(default="Alternative-data underwriting evidence", max_length=255)


class AlternativeDataManualInputRequest(BaseModel):
    payload: dict[str, Any]


class AlternativeDataSourceResponse(BaseModel):
    source_type: str
    label: str
    requested: str
    why: str
    excluded: str
    mock_available: bool

