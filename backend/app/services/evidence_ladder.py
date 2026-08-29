"""Rank additional evidence options for insufficient-confidence cases."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "evidence_ladder_policy.json"


@dataclass(frozen=True)
class EvidenceOption:
    name: str
    base_confidence_gain: float
    friction_cost: float
    privacy_cost: float
    mocked_available: bool
    reason: str


@dataclass(frozen=True)
class EvidenceLadderPolicy:
    min_sufficient_confidence_score: float
    options: list[EvidenceOption]


def load_evidence_ladder_policy(path: Path = POLICY_PATH) -> EvidenceLadderPolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    options = [
        EvidenceOption(
            name=str(item["name"]),
            base_confidence_gain=float(item["base_confidence_gain"]),
            friction_cost=float(item["friction_cost"]),
            privacy_cost=float(item["privacy_cost"]),
            mocked_available=bool(item["mocked_available"]),
            reason=str(item["reason"]),
        )
        for item in data["default_options"]
    ]
    return EvidenceLadderPolicy(
        min_sufficient_confidence_score=float(data["min_sufficient_confidence_score"]),
        options=options,
    )


def safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    return float(value)


def friction_level(cost: float) -> str:
    if cost <= 2:
        return "low"
    if cost <= 3:
        return "medium"
    return "high"


def privacy_level(cost: float) -> str:
    if cost <= 2:
        return "low"
    if cost <= 3:
        return "medium"
    return "high"


def option_multiplier(row: pd.Series, option: EvidenceOption) -> float:
    months = safe_float(row.get("months_of_history"), 0.0)
    density = safe_float(row.get("transaction_density"), 0.0)
    confidence_score = safe_float(row.get("confidence_score"), 0.0)
    seasonality_insufficient = row.get("seasonality_status") == "insufficient_history"
    confidence_deficit = max(0.0, 75.0 - confidence_score) / 75.0

    if option.name == "additional_bank_history_months":
        return 0.7 + min(1.0, max(0.0, 12.0 - months) / 12.0) + confidence_deficit
    if option.name == "another_financial_account":
        return 0.7 + min(1.0, max(0.0, 5.0 - density) / 5.0) + confidence_deficit
    if option.name == "utility_history":
        return 0.6 + confidence_deficit
    if option.name == "gst_business_evidence":
        return 0.6 + (0.4 if seasonality_insufficient else 0.0) + confidence_deficit
    if option.name in {
        "upi_payment_trends",
        "telecom_recharge_history",
        "ecommerce_settlement_history",
        "mobility_activity_history",
    }:
        return 0.7 + min(1.0, max(0.0, 6.0 - months) / 6.0) + confidence_deficit
    return 1.0


def rank_evidence_options(row: pd.Series, policy: EvidenceLadderPolicy) -> dict[str, Any]:
    confidence_score = safe_float(row.get("confidence_score"), 0.0)
    if confidence_score >= policy.min_sufficient_confidence_score:
        return {
            "status": "sufficient_confidence",
            "recommended_evidence": "none",
            "expected_confidence_improvement": 0.0,
            "reason": "Evidence confidence is already sufficient.",
            "friction_level": "none",
            "privacy_cost_level": "none",
            "rankings": [],
        }

    rankings: list[dict[str, Any]] = []
    remaining_gain_cap = max(0.0, 100.0 - confidence_score)
    for option in policy.options:
        expected_gain = min(
            remaining_gain_cap,
            option.base_confidence_gain * option_multiplier(row, option),
        )
        cost_denominator = max(1.0, option.friction_cost + option.privacy_cost)
        score = expected_gain / cost_denominator
        rankings.append(
            {
                "evidence": option.name,
                "expected_confidence_improvement": round(float(expected_gain), 2),
                "ranking_score": round(float(score), 4),
                "reason": option.reason,
                "friction_level": friction_level(option.friction_cost),
                "privacy_cost_level": privacy_level(option.privacy_cost),
                "mocked_available": option.mocked_available,
            }
        )

    rankings.sort(
        key=lambda item: (
            item["ranking_score"],
            item["expected_confidence_improvement"],
        ),
        reverse=True,
    )
    top = rankings[0]
    return {
        "status": "additional_evidence_recommended",
        "recommended_evidence": top["evidence"],
        "expected_confidence_improvement": top["expected_confidence_improvement"],
        "reason": top["reason"],
        "friction_level": top["friction_level"],
        "privacy_cost_level": top["privacy_cost_level"],
        "rankings": rankings,
    }
