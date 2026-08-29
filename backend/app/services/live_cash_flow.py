"""Live cash-flow estimation for platform underwriting."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.underwriting_domain import CashFlowForecast, ForecastMethod


@dataclass(frozen=True)
class LiveCashFlowInputs:
    monthly_inflow: float
    monthly_outflow: float
    monthly_net_cash_flow: float
    stability: float
    history_months: int
    evidence_mode: str


def estimate_live_cash_flow(inputs: LiveCashFlowInputs) -> CashFlowForecast:
    if inputs.evidence_mode == "PKDD_DEMO":
        return CashFlowForecast(
            method="HISTORICAL_BANK_FORECAST",
            p10=None,
            p50=None,
            p90=None,
            confidence=1.0,
            history_months=inputs.history_months,
            limitations=[],
        )
    if inputs.history_months <= 0 or inputs.monthly_inflow <= 0:
        return CashFlowForecast(
            method="INSUFFICIENT_EVIDENCE",
            p10=None,
            p50=None,
            p90=None,
            confidence=0.0,
            history_months=inputs.history_months,
            limitations=["No sufficient time-series evidence is available."],
        )
    stability = max(0.05, min(1.0, inputs.stability))
    p50 = inputs.monthly_net_cash_flow
    p10 = p50 - max(inputs.monthly_outflow * 0.2, abs(p50) * (1.0 - stability))
    p90 = p50 + max(inputs.monthly_inflow * 0.15, abs(p50) * stability * 0.5)
    limitations = [
        "Declared-plus-alternative estimates are policy heuristics, not statistically calibrated bank forecasts."
    ]
    if inputs.history_months < 6:
        limitations.append("Less than six months of evidence limits seasonality analysis.")
    return CashFlowForecast(
        method="DECLARED_PLUS_ALTERNATIVE_ESTIMATE",
        p10=float(p10),
        p50=float(p50),
        p90=float(p90),
        confidence=round(min(1.0, 0.35 + stability * 0.45 + min(inputs.history_months, 12) / 60), 3),
        history_months=inputs.history_months,
        limitations=limitations,
    )

