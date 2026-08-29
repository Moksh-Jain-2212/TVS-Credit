from __future__ import annotations

import json

from app.models import AlternativeSourceType
from app.services.alternative_data.registry import get_adapter

from tests.test_platform_flows import auth_header, create_admin, platform_client, register_verify_login, valid_application_payload


def test_all_mock_adapters_normalize_supported_sources() -> None:
    for source in AlternativeSourceType:
        adapter = get_adapter(source)
        normalized = adapter.normalize(adapter.mock_payload())
        assert normalized.source_type == source
        assert normalized.normalized_features["factor_scores"]
        assert 0 <= normalized.data_quality["quality_score"] <= 1
        assert normalized.period_start is not None
        assert normalized.period_end is not None


def test_alternative_data_submission_without_pkdd_and_grok_fallback(platform_client, monkeypatch) -> None:
    client, db_path = platform_client
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    monkeypatch.setenv("GROK_EXPLANATION_ENABLED", "false")
    user_tokens = register_verify_login(client, "alt-borrower@example.com")
    user_headers = auth_header(user_tokens["access_token"])
    create_admin(db_path)
    admin_tokens = client.post("/auth/login", json={"email": "admin@example.com", "password": "admin-pass-1"}).json()
    admin_headers = auth_header(admin_tokens["access_token"])

    created = client.post("/user/applications", json=valid_application_payload(), headers=user_headers)
    application_id = created.json()["id"]
    assert created.json()["financial_data_source"] is None

    sources = client.get(f"/user/applications/{application_id}/alternative-data/sources", headers=user_headers)
    assert sources.status_code == 200
    assert len(sources.json()["sources"]) == 6

    consent = client.post(
        f"/user/applications/{application_id}/alternative-data/UPI/consent",
        json={"granted": True},
        headers=user_headers,
    )
    assert consent.status_code == 200
    connected = client.post(
        f"/user/applications/{application_id}/alternative-data/UPI/connect-mock",
        headers=user_headers,
    )
    assert connected.status_code == 200
    assert connected.json()["active"] is True
    assert connected.json()["snapshot"]["provenance"]["raw_payload_persisted"] is False

    submitted = client.post(f"/user/applications/{application_id}/submit", headers=user_headers)
    assert submitted.status_code == 200
    underwriting = submitted.json()["underwriting"]
    assert underwriting["risk_probability"] is not None
    assert underwriting["behavioral_risk"]["base_model_risk_probability"] is None
    assert underwriting["behavioral_risk"]["behavioral_risk_score"] is not None
    assert underwriting["nadi_decision_state"] in {
        "APPROVE",
        "SAFE_TO_LEARN",
        "EVIDENCE_NEEDED",
        "NOT_CURRENTLY_AFFORDABLE",
    }

    detail = client.get(f"/admin/applications/{application_id}", headers=admin_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["application"]["source_loan_id"] is None
    assert body["alternative_data"]["readiness"]["connected_source_count"] == 1
    assert body["risk"]["historical_model_probability"] is None
    assert body["risk"]["combined_probability"] == underwriting["risk_probability"]

    grok = client.post(f"/admin/applications/{application_id}/grok-explanation", headers=admin_headers)
    assert grok.status_code == 200
    explanation = grok.json()
    assert explanation["status"] == "fallback"
    assert "executive_summary" in explanation["structured_response"]
    assert "alt-borrower@example.com" not in json.dumps(explanation)

    cached = client.get(f"/admin/applications/{application_id}/grok-explanation", headers=admin_headers)
    assert cached.status_code == 200
    assert cached.json()["id"] == explanation["id"]


def test_revoked_alternative_data_not_usable_for_submission(platform_client) -> None:
    client, _ = platform_client
    user_tokens = register_verify_login(client, "revoked@example.com")
    headers = auth_header(user_tokens["access_token"])
    created = client.post("/user/applications", json=valid_application_payload(), headers=headers)
    application_id = created.json()["id"]

    assert client.post(f"/user/applications/{application_id}/alternative-data/UPI/consent", json={"granted": True}, headers=headers).status_code == 200
    assert client.post(f"/user/applications/{application_id}/alternative-data/UPI/connect-mock", headers=headers).status_code == 200
    revoked = client.delete(f"/user/applications/{application_id}/alternative-data/UPI/consent", headers=headers)
    assert revoked.status_code == 200
    readiness = client.get(f"/user/applications/{application_id}/alternative-data/readiness", headers=headers)
    assert readiness.json()["ready"] is False
    submitted = client.post(f"/user/applications/{application_id}/submit", headers=headers)
    assert submitted.status_code == 422


def test_malformed_manual_alternative_data_returns_422(platform_client) -> None:
    client, _ = platform_client
    user_tokens = register_verify_login(client, "bad-upi@example.com")
    headers = auth_header(user_tokens["access_token"])
    created = client.post("/user/applications", json=valid_application_payload(), headers=headers)
    application_id = created.json()["id"]
    assert client.post(f"/user/applications/{application_id}/alternative-data/UPI/consent", json={"granted": True}, headers=headers).status_code == 200

    malformed = client.post(
        f"/user/applications/{application_id}/alternative-data/UPI/manual-input",
        json={"payload": {"records": [{"date": "2026-01-01", "type": "SIDEWAYS", "amount": 100, "status": "SUCCESS"}]}},
        headers=headers,
    )
    assert malformed.status_code == 422
    assert "INFLOW or OUTFLOW" in malformed.json()["detail"]
