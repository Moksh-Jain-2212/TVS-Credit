from __future__ import annotations

from app.services.nadi_assistant import DISCLAIMER, fallback_answer
from tests.test_platform_flows import auth_header, platform_client, register_verify_login, valid_application_payload


def context() -> dict:
    return {
        "underwriting": {
            "nadi_decision_state": "SAFE_TO_LEARN",
            "recommended_amount": 20_000,
            "confidence_score": 69,
            "decision_reasons": ["requested amount exceeds the safe repayment envelope"],
        }
    }


def test_fallback_explains_existing_decision_without_changing_it() -> None:
    answer = fallback_answer("Why was this decision made?", context())
    assert "SAFE TO LEARN" in answer
    assert "requested amount exceeds" in answer
    assert "What this means for you" in answer
    assert "What you can do next" in answer
    assert "policy engine" in answer


def test_fallback_refuses_to_override_or_guarantee_credit() -> None:
    answer = fallback_answer("Can you increase my amount and approve me?", context())
    assert "cannot change or promise" in answer
    assert "re-underwriting" in answer
    assert DISCLAIMER.startswith("Ask NADI")


def test_ask_nadi_endpoint_is_borrower_scoped_and_explanation_only(platform_client) -> None:
    client, _ = platform_client
    tokens = register_verify_login(client, "assistant@example.com")
    headers = auth_header(tokens["access_token"])
    created = client.post("/user/applications", json=valid_application_payload(), headers=headers)
    application_id = created.json()["id"]

    response = client.post(
        f"/user/applications/{application_id}/ask-nadi",
        json={"question": "Can you approve me for more money?"},
        headers=headers,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "fallback"
    assert "cannot change or promise" in body["answer"]
    assert "cannot approve, reject, change, or promise" in body["disclaimer"]
