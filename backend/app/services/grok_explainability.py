"""Optional xAI/Grok structured explanations for loan-officer review."""

from __future__ import annotations

import hashlib
import json
import os
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models import AIExplanation, LoanApplication
from app.services.alternative_data_service import application_sources
from app.services.application_service import decimal_or_none, latest_underwriting, serialize_underwriting


PROMPT_VERSION = "grok-underwriting-explanation-v1"


class GrokExplanationPayload(BaseModel):
    executive_summary: str
    approval_recommendation: str
    risk_drivers: list[str] = Field(default_factory=list)
    supportive_evidence: list[str] = Field(default_factory=list)
    evidence_gaps: list[str] = Field(default_factory=list)
    fair_lending_notes: list[str] = Field(default_factory=list)
    borrower_friendly_summary: str
    questions_for_officer: list[str] = Field(default_factory=list)


def truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def explanation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "executive_summary": {"type": "string"},
            "approval_recommendation": {"type": "string"},
            "risk_drivers": {"type": "array", "items": {"type": "string"}},
            "supportive_evidence": {"type": "array", "items": {"type": "string"}},
            "evidence_gaps": {"type": "array", "items": {"type": "string"}},
            "fair_lending_notes": {"type": "array", "items": {"type": "string"}},
            "borrower_friendly_summary": {"type": "string"},
            "questions_for_officer": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "executive_summary",
            "approval_recommendation",
            "risk_drivers",
            "supportive_evidence",
            "evidence_gaps",
            "fair_lending_notes",
            "borrower_friendly_summary",
            "questions_for_officer",
        ],
        "additionalProperties": False,
    }


def latest_explanation(session: Session, application_id: int) -> AIExplanation | None:
    return session.scalar(
        select(AIExplanation)
        .where(AIExplanation.application_id == application_id)
        .order_by(desc(AIExplanation.created_at))
    )


def serialize_ai_explanation(explanation: AIExplanation | None) -> dict | None:
    if explanation is None:
        return None
    return {
        "id": explanation.id,
        "provider": explanation.provider,
        "model": explanation.model,
        "prompt_version": explanation.prompt_version,
        "status": explanation.status,
        "structured_response": explanation.structured_response_json,
        "error_metadata": explanation.error_metadata_json,
        "created_at": explanation.created_at.isoformat(),
    }


def deidentified_input(session: Session, application: LoanApplication) -> dict[str, Any]:
    result = latest_underwriting(application)
    underwriting = serialize_underwriting(result) or {}
    sources = application_sources(session, application)
    behavioral = underwriting.get("behavioral_risk") or {}
    return {
        "application_id": application.id,
        "requested_amount": decimal_or_none(application.requested_amount),
        "requested_tenure": application.requested_tenure,
        "loan_purpose": application.loan_purpose,
        "employment_type": application.employment_type,
        "borrower_segment": application.borrower_segment.value if hasattr(application.borrower_segment, "value") else application.borrower_segment,
        "declared_monthly_income": decimal_or_none(application.declared_monthly_income),
        "declared_monthly_expenses": decimal_or_none(application.declared_monthly_expenses),
        "existing_monthly_emi": decimal_or_none(application.existing_monthly_emi),
        "status": application.status.value,
        "underwriting": {
            "risk_probability": underwriting.get("risk_probability"),
            "historical_model_risk_probability": behavioral.get("base_model_risk_probability"),
            "behavioral_risk_probability": behavioral.get("behavioral_risk_probability"),
            "behavioral_risk_score": behavioral.get("behavioral_risk_score"),
            "combined_risk_probability": behavioral.get("combined_risk_probability"),
            "confidence_score": underwriting.get("confidence_score"),
            "confidence_band": underwriting.get("confidence_band"),
            "maximum_safe_exposure": underwriting.get("maximum_safe_exposure"),
            "recommended_amount": underwriting.get("recommended_amount"),
            "recommended_tenure": underwriting.get("recommended_tenure"),
            "nadi_decision_state": underwriting.get("nadi_decision_state"),
            "decision_reasons": underwriting.get("decision_reasons") or [],
            "segment_analysis": underwriting.get("segment_analysis"),
        },
        "behavioral_sources": [
            {
                "source_type": source["source_type"],
                "active": source["active"],
                "quality_score": source["quality_score"],
                "connection_mode": source["connection_mode"],
                "segment_relevant": source.get("segment_relevant"),
            }
            for source in sources["sources"]
        ],
        "behavioral_breakdown": {
            "coverage": behavioral.get("behavioral_data_coverage"),
            "assessment_confidence": behavioral.get("behavioral_assessment_confidence"),
            "source_component_scores": behavioral.get("source_component_scores") or [],
            "factor_contributions": behavioral.get("factor_contributions") or [],
        },
    }


def input_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fallback_payload(payload: dict[str, Any]) -> GrokExplanationPayload:
    underwriting = payload["underwriting"]
    decision = underwriting.get("nadi_decision_state") or "PENDING"
    risk = underwriting.get("risk_probability")
    confidence = underwriting.get("confidence_band") or "unknown"
    active_sources = [
        source["source_type"]
        for source in payload["behavioral_sources"]
        if source.get("active")
    ]
    reasons = underwriting.get("decision_reasons") or ["No NADI decision reason is available yet."]
    return GrokExplanationPayload(
        executive_summary=f"NADI currently reads this application as {decision} with risk {risk if risk is not None else 'unavailable'} and {confidence} evidence confidence.",
        approval_recommendation=str(decision),
        risk_drivers=reasons[:5],
        supportive_evidence=[f"Connected behavioral sources: {', '.join(active_sources)}"] if active_sources else ["No behavioral source is currently connected."],
        evidence_gaps=["Additional alternative evidence may improve confidence."] if confidence != "high" else [],
        fair_lending_notes=[
            "This explanation excludes protected-class attributes and raw counterparties.",
            "Use policy thresholds and documented evidence, not demographic proxies, for the final decision.",
        ],
        borrower_friendly_summary="The decision is based on affordability, evidence confidence, observed repayment capacity, and connected behavioral financial signals.",
        questions_for_officer=["Is any material applicant-provided income evidence missing from the file?"],
    )


def call_xai(payload: dict[str, Any]) -> GrokExplanationPayload:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key or not truthy(os.getenv("GROK_EXPLANATION_ENABLED")):
        return fallback_payload(payload)
    base_url = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.getenv("XAI_MODEL", "grok-4.6").strip() or "grok-4.6"
    messages = [
        {
            "role": "system",
            "content": (
                "You are an underwriting explainability assistant. Return only valid JSON matching the schema. "
                "Do not infer protected characteristics. Distinguish historical model risk from behavioral risk."
            ),
        },
        {
            "role": "user",
            "content": json.dumps(payload, sort_keys=True, default=str),
        },
    ]
    response = httpx.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "nadi_underwriting_explanation",
                    "schema": explanation_schema(),
                    "strict": True,
                },
            },
        },
        timeout=20,
    )
    response.raise_for_status()
    body = response.json()
    content = body["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    return GrokExplanationPayload.model_validate(parsed)


def generate_explanation(session: Session, application: LoanApplication, *, force_refresh: bool = False) -> dict:
    payload = deidentified_input(session, application)
    digest = input_hash(payload)
    cached = latest_explanation(session, application.id)
    if cached is not None and cached.input_hash == digest and not force_refresh:
        return serialize_ai_explanation(cached) or {}
    result = latest_underwriting(application)
    model = os.getenv("XAI_MODEL", "grok-4.6").strip() or "grok-4.6"
    status = "success"
    error_metadata = None
    try:
        structured = call_xai(payload)
        if not os.getenv("XAI_API_KEY") or not truthy(os.getenv("GROK_EXPLANATION_ENABLED")):
            status = "fallback"
    except (httpx.HTTPError, KeyError, IndexError, json.JSONDecodeError, ValidationError) as exc:
        structured = fallback_payload(payload)
        status = "fallback"
        error_metadata = {"error": str(exc)[:500]}
    explanation = AIExplanation(
        application=application,
        underwriting_result=result,
        provider="xAI",
        model=model,
        prompt_version=PROMPT_VERSION,
        input_hash=digest,
        structured_response_json=structured.model_dump(),
        status=status,
        error_metadata_json=error_metadata,
    )
    session.add(explanation)
    session.commit()
    return serialize_ai_explanation(explanation) or {}
