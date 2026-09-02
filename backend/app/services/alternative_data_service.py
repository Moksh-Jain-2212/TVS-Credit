"""Application-level consent and source management for alternative data."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import utc_now
from app.models import (
    AlternativeDataConnection,
    AlternativeDataConsent,
    AlternativeDataSnapshot,
    AlternativeSourceType,
    ApplicationStatus,
    AuditLog,
    ConsentStatus,
    DataConnectionMode,
    DataConnectionStatus,
    LoanApplication,
    User,
)
from app.services.alternative_data.registry import get_adapter, supported_sources
from app.services.alternative_data.synthetic_evidence_generator import generated_mock_payload
from app.services.behavioral_risk import assess_behavioral_risk, latest_active_snapshot, latest_behavioral_assessment
from app.services.segment_analysis import SEGMENT_LABELS, SEGMENT_RELEVANT_SOURCES, normalize_borrower_segment


def enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def parse_source(source_type: str) -> AlternativeSourceType:
    try:
        return AlternativeSourceType(source_type.upper())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alternative-data source not supported") from exc


def latest_consent(session: Session, application_id: int, source: AlternativeSourceType) -> AlternativeDataConsent | None:
    return session.scalar(
        select(AlternativeDataConsent)
        .where(
            AlternativeDataConsent.application_id == application_id,
            AlternativeDataConsent.source_type == source,
        )
        .order_by(desc(AlternativeDataConsent.created_at))
    )


def latest_connection(session: Session, application_id: int, source: AlternativeSourceType) -> AlternativeDataConnection | None:
    return session.scalar(
        select(AlternativeDataConnection)
        .where(
            AlternativeDataConnection.application_id == application_id,
            AlternativeDataConnection.source_type == source,
        )
        .order_by(desc(AlternativeDataConnection.created_at))
    )


def latest_snapshot(session: Session, application_id: int, source: AlternativeSourceType) -> AlternativeDataSnapshot | None:
    return session.scalar(
        select(AlternativeDataSnapshot)
        .where(
            AlternativeDataSnapshot.application_id == application_id,
            AlternativeDataSnapshot.source_type == source,
        )
        .order_by(desc(AlternativeDataSnapshot.collected_at))
    )


def consent_is_granted(session: Session, application_id: int, source: AlternativeSourceType) -> bool:
    consent = latest_consent(session, application_id, source)
    return consent is not None and consent.consent_status == ConsentStatus.GRANTED


def assert_editable(application: LoanApplication) -> None:
    if application.status not in {ApplicationStatus.DRAFT, ApplicationStatus.MORE_INFORMATION_REQUIRED, ApplicationStatus.SUBMITTED, ApplicationStatus.ADMIN_REVIEW}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alternative data cannot be changed now")


def serialize_snapshot(snapshot: AlternativeDataSnapshot | None) -> dict | None:
    if snapshot is None:
        return None
    return {
        "id": snapshot.id,
        "source_type": enum_value(snapshot.source_type),
        "collected_at": snapshot.collected_at.isoformat(),
        "normalized_features": snapshot.normalized_features_json,
        "data_quality": snapshot.data_quality_json,
        "provenance": snapshot.provenance_json,
    }


def source_status(session: Session, application_id: int, source: AlternativeSourceType) -> dict[str, Any]:
    consent = latest_consent(session, application_id, source)
    connection = latest_connection(session, application_id, source)
    snapshot = latest_snapshot(session, application_id, source)
    active_snapshot = latest_active_snapshot(session, application_id, source)
    return {
        "source_type": source.value,
        "consent_status": enum_value(consent.consent_status) if consent else None,
        "connection_status": enum_value(connection.status) if connection else None,
        "connection_mode": enum_value(connection.mode) if connection else None,
        "connected_at": connection.connected_at.isoformat() if connection and connection.connected_at else None,
        "last_refreshed_at": connection.last_refreshed_at.isoformat() if connection and connection.last_refreshed_at else None,
        "quality_score": float(connection.quality_score) if connection and connection.quality_score is not None else None,
        "period_start": connection.period_start.isoformat() if connection and connection.period_start else None,
        "period_end": connection.period_end.isoformat() if connection and connection.period_end else None,
        "active": active_snapshot is not None,
        "snapshot": serialize_snapshot(snapshot),
    }


def list_source_definitions() -> list[dict[str, Any]]:
    return supported_sources()


def application_sources(session: Session, application: LoanApplication) -> dict[str, Any]:
    segment = normalize_borrower_segment(application)
    relevant_sources = SEGMENT_RELEVANT_SOURCES[segment]
    source_rows = []
    for definition in supported_sources():
        source_type = str(definition["source_type"])
        source = parse_source(source_type)
        priority = relevant_sources.index(source_type) if source_type in relevant_sources else len(relevant_sources) + 10
        source_rows.append(
            definition
            | source_status(session, application.id, source)
            | {
                "segment_relevant": source_type in relevant_sources,
                "segment_priority": priority,
            }
        )
    source_rows.sort(key=lambda row: (row["segment_priority"], row["source_type"]))
    return {
        "application_id": application.id,
        "borrower_segment": segment,
        "borrower_segment_label": SEGMENT_LABELS[segment],
        "sources": source_rows,
        "readiness": alternative_data_readiness(session, application),
    }


def alternative_data_readiness(session: Session, application: LoanApplication) -> dict[str, Any]:
    segment = normalize_borrower_segment(application)
    relevant_sources = set(SEGMENT_RELEVANT_SOURCES[segment])
    connected = [
        status_row
        for status_row in (source_status(session, application.id, source) for source in AlternativeSourceType)
        if status_row["active"]
    ]
    assessment = latest_behavioral_assessment(session, application.id) if connected else None
    return {
        "ready": bool(connected),
        "connected_source_count": len(connected),
        "connected_sources": [row["source_type"] for row in connected],
        "missing_sources": [source.value for source in AlternativeSourceType if source.value not in {row["source_type"] for row in connected}],
        "relevant_sources": sorted(relevant_sources),
        "connected_relevant_sources": [row["source_type"] for row in connected if row["source_type"] in relevant_sources],
        "missing_relevant_sources": [
            source for source in sorted(relevant_sources) if source not in {row["source_type"] for row in connected}
        ],
        "behavioral_data_coverage": float(assessment.behavioral_data_coverage) if assessment else 0,
        "behavioral_assessment_confidence": float(assessment.behavioral_assessment_confidence) if assessment else 0,
        "message": "Behavioral evidence connected" if connected else "Connect at least one behavioral evidence source",
    }


def grant_consent(
    session: Session,
    application: LoanApplication,
    user: User,
    source_type: str,
    purpose: str,
) -> dict[str, Any]:
    assert_editable(application)
    source = parse_source(source_type)
    now = utc_now()
    consent = AlternativeDataConsent(
        application=application,
        source_type=source,
        consent_status=ConsentStatus.GRANTED,
        consented_at=now,
        purpose=purpose,
    )
    session.add(consent)
    session.add(AuditLog(actor_user=user, action="ALTERNATIVE_DATA_CONSENT_GRANTED", entity_type="LoanApplication", entity_id=application.id, metadata_json={"source_type": source.value}))
    session.commit()
    return source_status(session, application.id, source)


def revoke_consent(session: Session, application: LoanApplication, user: User, source_type: str) -> dict[str, Any]:
    assert_editable(application)
    source = parse_source(source_type)
    now = utc_now()
    consent = AlternativeDataConsent(
        application=application,
        source_type=source,
        consent_status=ConsentStatus.REVOKED,
        revoked_at=now,
        purpose="Consent revoked by applicant",
    )
    connection = AlternativeDataConnection(
        application=application,
        source_type=source,
        mode=DataConnectionMode.MANUAL,
        status=DataConnectionStatus.REVOKED,
        last_refreshed_at=now,
    )
    session.add_all([consent, connection])
    session.add(AuditLog(actor_user=user, action="ALTERNATIVE_DATA_CONSENT_REVOKED", entity_type="LoanApplication", entity_id=application.id, metadata_json={"source_type": source.value}))
    session.commit()
    return source_status(session, application.id, source)


def persist_normalized_source(
    session: Session,
    application: LoanApplication,
    user: User,
    source: AlternativeSourceType,
    payload: dict[str, Any],
    mode: DataConnectionMode,
    provenance_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not consent_is_granted(session, application.id, source):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Grant consent before connecting this source")
    adapter = get_adapter(source)
    try:
        normalized = adapter.normalize(payload)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    now = utc_now()
    provenance = {
        "source_type": source.value,
        "mode": mode.value,
        "schema_version": normalized.schema_version,
        "period_start": normalized.period_start.isoformat() if normalized.period_start else None,
        "period_end": normalized.period_end.isoformat() if normalized.period_end else None,
        "collected_by": "applicant_mock_connector" if mode == DataConnectionMode.MOCK else "applicant_manual_input",
        "pii_excluded": True,
        "raw_payload_persisted": False,
    }
    if provenance_extra:
        provenance.update(provenance_extra)
    connection = AlternativeDataConnection(
        application=application,
        source_type=source,
        mode=mode,
        status=DataConnectionStatus.CONNECTED,
        connected_at=now,
        last_refreshed_at=now,
        period_start=normalized.period_start,
        period_end=normalized.period_end,
        quality_score=float(normalized.data_quality.get("quality_score", 0.0)),
        schema_version=normalized.schema_version,
    )
    snapshot = AlternativeDataSnapshot(
        application=application,
        source_type=source,
        collected_at=now,
        normalized_features_json=normalized.normalized_features,
        data_quality_json=normalized.data_quality,
        provenance_json=provenance,
    )
    session.add_all([connection, snapshot])
    session.add(AuditLog(actor_user=user, action="ALTERNATIVE_DATA_SOURCE_CONNECTED", entity_type="LoanApplication", entity_id=application.id, metadata_json={"source_type": source.value, "mode": mode.value}))
    underwriting = None
    if application.status in {ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_ANALYSIS, ApplicationStatus.ADMIN_REVIEW}:
        from app.services.application_service import serialize_underwriting
        from app.services.live_underwriting import analyze_platform_application

        underwriting_result = analyze_platform_application(session, application, actor=user)
        assessment = underwriting_result.behavioral_risk_assessment
        underwriting = serialize_underwriting(underwriting_result)
    else:
        assessment, _ = assess_behavioral_risk(session, application)
    session.commit()
    return source_status(session, application.id, source) | {
        "behavioral_risk": {
            "behavioral_risk_score": float(assessment.behavioral_risk_score) if assessment.behavioral_risk_score is not None else None,
            "behavioral_risk_probability": float(assessment.behavioral_risk_probability) if assessment.behavioral_risk_probability is not None else None,
            "combined_risk_probability": float(assessment.combined_risk_probability) if assessment.combined_risk_probability is not None else None,
            "behavioral_data_coverage": float(assessment.behavioral_data_coverage),
            "behavioral_assessment_confidence": float(assessment.behavioral_assessment_confidence),
        },
        "underwriting": underwriting,
    }


def connect_mock_source(session: Session, application: LoanApplication, user: User, source_type: str) -> dict[str, Any]:
    assert_editable(application)
    source = parse_source(source_type)
    generated = generated_mock_payload(application, source)
    payload, provenance = generated if generated is not None else (get_adapter(source).mock_payload(), None)
    return persist_normalized_source(session, application, user, source, payload, DataConnectionMode.MOCK, provenance)


def connect_manual_source(
    session: Session,
    application: LoanApplication,
    user: User,
    source_type: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    assert_editable(application)
    source = parse_source(source_type)
    return persist_normalized_source(session, application, user, source, payload, DataConnectionMode.MANUAL)


def refresh_source(session: Session, application: LoanApplication, user: User, source_type: str) -> dict[str, Any]:
    assert_editable(application)
    source = parse_source(source_type)
    connection = latest_connection(session, application.id, source)
    if connection is None or connection.status != DataConnectionStatus.CONNECTED:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source is not connected")
    generated = generated_mock_payload(application, source)
    payload, provenance = generated if generated is not None else (get_adapter(source).mock_payload(), None)
    return persist_normalized_source(session, application, user, source, payload, connection.mode or DataConnectionMode.MOCK, provenance)
