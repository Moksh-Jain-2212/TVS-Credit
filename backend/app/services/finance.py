"""Shared finance calculations."""

from __future__ import annotations


def estimate_emi(amount: float, tenure_months: int, annual_interest_rate: float) -> float:
    """Calculate amortized EMI for a principal, tenure, and annual interest rate."""
    tenure = max(1, int(tenure_months))
    monthly_rate = annual_interest_rate / 12.0
    if monthly_rate <= 0:
        return float(amount / tenure)
    factor = (1.0 + monthly_rate) ** tenure
    return float(amount * monthly_rate * factor / (factor - 1.0))

