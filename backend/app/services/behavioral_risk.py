"""Policy-driven behavioral risk assessment from normalized alternative data."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import ensure_aware, utc_now
from app.models import (
    AlternativeDataConnection,
    AlternativeDataConsent,
    AlternativeDataSnapshot,
    AlternativeSourceType,
    BehavioralRiskAssessment,
    ConsentStatus,
    DataConnectionStatus,
    LoanApplication,
)


POLICY_PATH = Path(__file__).resolve().parents[1] / "core" / "behavioral_risk_policy.json"


@dataclass(frozen=True)
class BehavioralRiskPolicy:
    policy_version: str
    score_direction: str
    supported_sources: list[str]
    source_weights: dict[str, float]
    factor_weights: dict[str, dict[str, float]]
    minimum_calibrated_coverage: float
    probability_min: float
    probability_max: float
    declared_only_probability: float
    max_behavioral_overlay_weight: float
    stale_after_days: int


def load_behavioral_policy(path: Path = POLICY_PATH) -> BehavioralRiskPolicy:
    data = json.loads(path.read_text(encoding="utf-8"))
    probability = data["behavioral_probability_scale"]
    combination = data["combination_policy"]
    confidence = data["confidence_policy"]
    return BehavioralRiskPolicy(
        policy_version=str(data["policy_version"]),
        score_direction=str(data["score_direction"]),
        supported_sources=list(data["supported_sources"]),
        source_weights={str(key): float(value) for key, value in data["source_weights"].items()},
        factor_weights={
            str(source): {str(key): float(value) for key, value in weights.items()}
            for source, weights in data["factor_weights"].items()
        },
        minimum_calibrated_coverage=float(data["minimum_calibrated_coverage"]),
        probability_min=float(probability["min_probability"]),
        probability_max=float(probability["max_probability"]),
        declared_only_probability=float(combination["declared_only_probability"]),
        max_behavioral_overlay_weight=float(combination["max_behavioral_overlay_weight"]),
        stale_after_days=int(confidence["stale_after_days"]),
    )


def latest_active_snapshot(session: Session, application_id: int, source: AlternativeSourceType) -> AlternativeDataSnapshot | None:
    consent = session.scalar(
        select(AlternativeDataConsent)
        .where(
            AlternativeDataConsent.application_id == application_id,
            AlternativeDataConsent.source_type == source,
        )
        .order_by(desc(AlternativeDataConsent.created_at))
    )
    if consent is None or consent.consent_status != ConsentStatus.GRANTED:
        return None
    connection = session.scalar(
        select(AlternativeDataConnection)
        .where(
            AlternativeDataConnection.application_id == application_id,
            AlternativeDataConnection.source_type == source,
        )
        .order_by(desc(AlternativeDataConnection.last_refreshed_at))
    )
    if connection is None or connection.status != DataConnectionStatus.CONNECTED:
        return None
    return session.scalar(
        select(AlternativeDataSnapshot)
        .where(
            AlternativeDataSnapshot.application_id == application_id,
            AlternativeDataSnapshot.source_type == source,
        )
        .order_by(desc(AlternativeDataSnapshot.collected_at))
    )


def latest_active_snapshots(session: Session, application_id: int) -> list[AlternativeDataSnapshot]:
    snapshots = []
    for source in AlternativeSourceType:
        snapshot = latest_active_snapshot(session, application_id, source)
        if snapshot is not None:
            snapshots.append(snapshot)
    return snapshots


def latest_behavioral_assessment(session: Session, application_id: int) -> BehavioralRiskAssessment | None:
    return session.scalar(
        select(BehavioralRiskAssessment)
        .where(BehavioralRiskAssessment.application_id == application_id)
        .order_by(desc(BehavioralRiskAssessment.created_at))
    )


def factor_direction(score: float) -> str:
    if score >= 60:
        return "adverse"
    if score <= 40:
        return "supportive"
    return "neutral"


def score_band(score: float | None) -> str | None:
    if score is None:
        return None
    if score < 34:
        return "low"
    if score < 67:
        return "medium"
    return "high"


def source_score(source: AlternativeSourceType, features: dict[str, Any], policy: BehavioralRiskPolicy) -> tuple[float, list[dict[str, Any]]]:
    factor_scores = features.get("factor_scores") or {}
    weights = policy.factor_weights[source.value]
    total_weight = sum(weights.values()) or 1.0
    factors = []
    weighted_score = 0.0
    for factor, weight in weights.items():
        score = float(factor_scores.get(factor, 50.0))
        weighted_score += score * (weight / total_weight)
        factors.append(
            {
                "name": factor,
                "observed_value": features.get(factor),
                "risk_score": round(score, 3),
                "direction": factor_direction(score),
                "weight": weight,
            }
        )
    return round(weighted_score, 3), factors


def recency_multiplier(snapshot: AlternativeDataSnapshot, policy: BehavioralRiskPolicy) -> float:
    age_days = (utc_now() - ensure_aware(snapshot.collected_at)).days
    if age_days <= policy.stale_after_days:
        return 1.0
    return max(0.35, 1.0 - ((age_days - policy.stale_after_days) / 365.0))


def behavioral_probability(score: float, coverage: float, policy: BehavioralRiskPolicy) -> float | None:
    if coverage < policy.minimum_calibrated_coverage:
        return None
    span = policy.probability_max - policy.probability_min
    return round(policy.probability_min + (score / 100.0) * span, 6)


def combine_probability(base_probability: float | None, behavioral_probability_value: float | None, coverage: float, policy: BehavioralRiskPolicy) -> float:
    if behavioral_probability_value is None:
        return round(float(base_probability if base_probability is not None else policy.declared_only_probability), 6)
    if base_probability is None:
        return round(behavioral_probability_value, 6)
    overlay_weight = min(policy.max_behavioral_overlay_weight, policy.max_behavioral_overlay_weight * coverage)
    return round((base_probability * (1.0 - overlay_weight)) + (behavioral_probability_value * overlay_weight), 6)


def assess_behavioral_risk(
    session: Session,
    application: LoanApplication,
    base_model_risk_probability: float | None = None,
) -> tuple[BehavioralRiskAssessment, dict[str, Any]]:
    policy = load_behavioral_policy()
    snapshots = latest_active_snapshots(session, application.id)
    weight_denominator = sum(policy.source_weights[source.value] for source in AlternativeSourceType)
    present_weight = sum(policy.source_weights[snapshot.source_type.value] for snapshot in snapshots)
    coverage = round(present_weight / weight_denominator, 3) if weight_denominator else 0.0
    source_rows = []
    raw_contributions = []
    quality_scores = []
    recency_scores = []
    for snapshot in snapshots:
        quality_score = float(snapshot.data_quality_json.get("quality_score", 0.0))
        recency = recency_multiplier(snapshot, policy)
        adjusted_source_weight = policy.source_weights[snapshot.source_type.value] * quality_score * recency
        score, factors = source_score(snapshot.source_type, snapshot.normalized_features_json, policy)
        source_rows.append(
            {
                "source": snapshot.source_type.value,
                "source_score": score,
                "weight": policy.source_weights[snapshot.source_type.value],
                "quality_score": quality_score,
                "recency_multiplier": round(recency, 3),
                "factors": factors,
            }
        )
        raw_contributions.append((snapshot.source_type.value, score, adjusted_source_weight, factors))
        quality_scores.append(quality_score)
        recency_scores.append(recency)
    score_denominator = sum(weight for _, _, weight, _ in raw_contributions)
    behavioral_score = None
    if score_denominator > 0:
        behavioral_score = round(sum(score * weight for _, score, weight, _ in raw_contributions) / score_denominator, 3)
    behavioral_probability_value = (
        behavioral_probability(behavioral_score, coverage, policy) if behavioral_score is not None else None
    )
    combined_probability = combine_probability(base_model_risk_probability, behavioral_probability_value, coverage, policy)
    contribution_denominator = sum(abs((score - 50.0) * weight) for _, score, weight, _ in raw_contributions)
    factor_contributions = []
    for source, score, weight, factors in raw_contributions:
        source_contribution = abs((score - 50.0) * weight)
        contribution_pct = round((source_contribution / contribution_denominator) * 100, 2) if contribution_denominator else 0.0
        for factor in factors:
            factor_contributions.append(
                {
                    "name": factor["name"],
                    "source": source,
                    "direction": factor["direction"],
                    "contribution_pct": contribution_pct,
                    "risk_score": factor["risk_score"],
                    "observed_value": factor["observed_value"],
                }
            )
    confidence = round(
        (
            (coverage * 0.35)
            + ((sum(quality_scores) / max(1, len(quality_scores))) * 0.35)
            + ((sum(recency_scores) / max(1, len(recency_scores))) * 0.2)
            + (0.8 * 0.1)
        )
        * 100,
        3,
    )
    source_coverage = [
        {
            "source": source.value,
            "connected": any(snapshot.source_type == source for snapshot in snapshots),
            "missing_is_adverse": False,
        }
        for source in AlternativeSourceType
    ]
    assessment = BehavioralRiskAssessment(
        application=application,
        base_model_risk_probability=base_model_risk_probability,
        behavioral_risk_score=behavioral_score,
        behavioral_score_band=score_band(behavioral_score),
        behavioral_risk_probability=behavioral_probability_value,
        behavioral_probability_calibration_status="POLICY_HEURISTIC",
        combined_risk_probability=combined_probability,
        behavioral_data_coverage=coverage,
        behavioral_assessment_confidence=confidence,
        source_coverage_json=source_coverage,
        source_component_scores_json=source_rows,
        factor_contributions_json=factor_contributions,
        policy_version=policy.policy_version,
    )
    session.add(assessment)
    session.flush()
    return assessment, {
        "policy": policy,
        "snapshots": snapshots,
        "coverage": coverage,
        "behavioral_score": behavioral_score,
        "behavioral_probability": behavioral_probability_value,
        "combined_probability": combined_probability,
        "confidence": confidence,
    }
