"""Typed underwriting domain objects used by the live platform path."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


EvidenceMode = Literal["PKDD_DEMO", "DECLARED_PLUS_ALTERNATIVE_DATA"]
ForecastMethod = Literal["HISTORICAL_BANK_FORECAST", "DECLARED_PLUS_ALTERNATIVE_ESTIMATE", "INSUFFICIENT_EVIDENCE"]


@dataclass(frozen=True)
class RiskInputs:
    base_model_probability: float | None
    behavioral_score: float | None
    behavioral_probability: float | None
    combined_probability: float
    calibration_status: str
    model_version: str | None


@dataclass(frozen=True)
class CapacityInputs:
    requested_amount: float
    tenure_months: int
    scheduled_payment: float
    monthly_inflow: float
    monthly_outflow: float
    monthly_net_cash_flow: float
    latest_balance: float


@dataclass(frozen=True)
class EvidenceInputs:
    mode: EvidenceMode
    source_types: list[str]
    coverage: float
    confidence: float
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CashFlowForecast:
    method: ForecastMethod
    p10: float | None
    p50: float | None
    p90: float | None
    confidence: float
    history_months: int
    limitations: list[str]


@dataclass(frozen=True)
class UnderwritingContext:
    application_id: int
    evidence: EvidenceInputs
    capacity: CapacityInputs
    forecast: CashFlowForecast
    risk: RiskInputs | None = None
    row: dict[str, Any] = field(default_factory=dict)

    def with_risk(self, risk: RiskInputs, row: dict[str, Any]) -> "UnderwritingContext":
        return UnderwritingContext(
            application_id=self.application_id,
            evidence=self.evidence,
            capacity=self.capacity,
            forecast=self.forecast,
            risk=risk,
            row=row,
        )


@dataclass(frozen=True)
class UnderwritingDecision:
    decision_state: str
    recommended_amount: float
    recommended_tenure: int | None
    recommended_emi: float | None
    reasons: list[str]

