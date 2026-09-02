"""Evidence confidence scoring independent of repayment risk."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "evidence_confidence_policy.json"

SENSITIVE_OR_TARGET_COLUMNS = {
    "primary_client_birth_number",
    "primary_client_district_id",
    "account_district_id",
    "loan_status_target",
    "loan_status_from_source",
    "loan_status_meaning",
    "repayment_outcome_known",
    "repayment_default_target",
    "target_exclusion_reason",
}

COMPLETENESS_COLUMNS = [
    "months_of_history",
    "pre_loan_transaction_count",
    "transaction_density",
    "mean_monthly_inflow",
    "mean_monthly_outflow",
    "average_balance",
    "minimum_balance",
    "income_stability_score",
    "cash_flow_stability_score",
    "stability_history_status",
    "seasonality_status",
]


@dataclass(frozen=True)
class EvidenceConfidencePolicy:
    weights: dict[str, float]
    history_months_full_credit: float
    transactions_per_month_full_credit: float
    medium_band_min_score: int
    high_band_min_score: int


def load_policy(path: Path = POLICY_PATH) -> EvidenceConfidencePolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    weights = {str(key): float(value) for key, value in data["weights"].items()}
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Evidence confidence weights must sum to a positive value")
    normalized = {key: value / total for key, value in weights.items()}
    return EvidenceConfidencePolicy(
        weights=normalized,
        history_months_full_credit=float(data["history_months_full_credit"]),
        transactions_per_month_full_credit=float(data["transactions_per_month_full_credit"]),
        medium_band_min_score=int(data["medium_band_min_score"]),
        high_band_min_score=int(data["high_band_min_score"]),
    )


def clamp01(value: float) -> float:
    if np.isnan(value):
        return 0.0
    return float(max(0.0, min(1.0, value)))


def value_present(value: Any) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str) and value.strip() in {"", "insufficient_history"}:
        return False
    return True


def safe_float(value: Any, default: float = 0.0) -> float:
    if not value_present(value):
        return default
    return float(value)


def score_history_length(row: pd.Series, policy: EvidenceConfidencePolicy) -> float:
    return clamp01(safe_float(row.get("months_of_history"), 0.0) / policy.history_months_full_credit)


def score_transaction_density(row: pd.Series, policy: EvidenceConfidencePolicy) -> float:
    return clamp01(
        safe_float(row.get("transaction_density"), 0.0) / policy.transactions_per_month_full_credit
    )


def score_missingness(row: pd.Series) -> float:
    relevant_values = [
        row[column]
        for column in COMPLETENESS_COLUMNS
        if column in row.index and column not in SENSITIVE_OR_TARGET_COLUMNS
    ]
    if not relevant_values:
        return 0.0
    present_count = sum(1 for value in relevant_values if value_present(value))
    return float(present_count / len(relevant_values))


def score_data_completeness(row: pd.Series) -> float:
    checks = [
        safe_float(row.get("pre_loan_transaction_count"), 0.0) > 0,
        value_present(row.get("mean_monthly_inflow")),
        value_present(row.get("mean_monthly_outflow")),
        value_present(row.get("average_balance")),
        row.get("stability_history_status") == "sufficient_history",
    ]
    return float(sum(checks) / len(checks))


def score_evidence_consistency(row: pd.Series) -> float:
    income_stability = row.get("income_stability_score")
    cash_flow_stability = row.get("cash_flow_stability_score")
    if value_present(income_stability) or value_present(cash_flow_stability):
        scores = [
            float(value)
            for value in (income_stability, cash_flow_stability)
            if value_present(value)
        ]
        return clamp01(float(np.mean(scores)))

    income_volatility = safe_float(row.get("income_volatility"), 0.0)
    balance_volatility = safe_float(row.get("balance_volatility"), 0.0)
    return clamp01(1.0 / (1.0 + max(0.0, np.mean([income_volatility, balance_volatility]))))


def score_usable_evidence_types(row: pd.Series) -> float:
    if row.get("live_evidence_mode") == "PKDD_DEMO":
        # PKDD demo evidence is complete bank-transaction evidence, not an
        # alternative-data source. Do not penalise it for lacking a UPI consent.
        checks = [
            safe_float(row.get("months_of_history"), 0.0) > 0,
            safe_float(row.get("pre_loan_transaction_count"), 0.0) > 0,
            safe_float(row.get("mean_monthly_inflow"), 0.0) > 0,
            value_present(row.get("average_balance")),
        ]
        return float(sum(checks) / len(checks))
    relevant = row.get("segment_relevant_sources")
    if isinstance(relevant, list) and relevant:
        connected = row.get("alternative_data_sources")
        connected_set = set(connected if isinstance(connected, list) else [])
        relevant_score = len(connected_set.intersection(set(relevant))) / len(relevant)
        common_checks = [
            safe_float(row.get("months_of_history"), 0.0) > 0,
            safe_float(row.get("mean_monthly_inflow"), 0.0) > 0,
            value_present(row.get("average_balance")),
        ]
        return float((relevant_score + (sum(common_checks) / len(common_checks))) / 2.0)
    checks = [
        safe_float(row.get("months_of_history"), 0.0) > 0,
        safe_float(row.get("mean_monthly_inflow"), 0.0) > 0,
        safe_float(row.get("mean_monthly_outflow"), 0.0) > 0,
        value_present(row.get("average_balance")),
        safe_float(row.get("standing_order_count"), 0.0) > 0,
        row.get("seasonality_status") == "sufficient_history",
    ]
    return float(sum(checks) / len(checks))


def score_model_certainty(risk_probability: float | None) -> float:
    if risk_probability is None or pd.isna(risk_probability):
        return 0.5
    return clamp01(abs(float(risk_probability) - 0.5) * 2.0)


def confidence_band(score: int, policy: EvidenceConfidencePolicy) -> str:
    if score >= policy.high_band_min_score:
        return "high"
    if score >= policy.medium_band_min_score:
        return "medium"
    return "low"


def reason_messages(component_scores: dict[str, float], band: str) -> list[str]:
    reasons: list[str] = [f"overall evidence confidence is {band}"]
    weak = [name for name, score in component_scores.items() if score < 0.5]
    strong = [name for name, score in component_scores.items() if score >= 0.8]
    if strong:
        reasons.append("strong evidence from " + ", ".join(strong[:3]))
    if weak:
        reasons.append("weaker evidence from " + ", ".join(weak[:3]))
    return reasons


def score_evidence_confidence(
    row: pd.Series,
    policy: EvidenceConfidencePolicy,
    risk_probability: float | None = None,
) -> dict[str, Any]:
    component_scores = {
        "history_length": score_history_length(row, policy),
        "transaction_density": score_transaction_density(row, policy),
        "missingness": score_missingness(row),
        "data_completeness": score_data_completeness(row),
        "evidence_consistency": score_evidence_consistency(row),
        "usable_evidence_types": score_usable_evidence_types(row),
        "model_certainty": score_model_certainty(risk_probability),
    }
    weighted_score = sum(
        component_scores[name] * policy.weights.get(name, 0.0)
        for name in component_scores
    )
    score = int(round(clamp01(weighted_score) * 100))
    band = confidence_band(score, policy)
    return {
        "confidence_score": score,
        "confidence_band": band,
        "reasons": reason_messages(component_scores, band),
        "components": component_scores,
    }
