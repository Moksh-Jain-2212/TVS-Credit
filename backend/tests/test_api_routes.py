from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def first_application_id() -> int:
    response = client.get("/borrowers", params={"limit": 1})
    assert response.status_code == 200
    borrowers = response.json()
    assert borrowers
    return int(borrowers[0]["latest_loan_id"])


def test_openapi_schema_exposes_phase17_routes() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    assert "/borrowers" in paths
    assert "/applications/{application_id}/decision" in paths


def test_borrower_and_application_analysis_routes() -> None:
    application_id = first_application_id()

    create_response = client.post("/applications", json={"loan_id": application_id})
    analyze_response = client.post(f"/applications/{application_id}/analyze")

    assert create_response.status_code == 200
    assert create_response.json()["application_id"] == application_id
    assert analyze_response.status_code == 200
    analysis = analyze_response.json()
    assert analysis["financial_profile"]["bureau_available"] is False
    assert "income_stability_score" in analysis["financial_profile"]
    assert analysis["repayment_envelope"]["all_evaluated_combinations"][0]["classification_reasons"]
    assert analysis["decision"]["decision_state"] in {
        "APPROVE",
        "SAFE_TO_LEARN",
        "EVIDENCE_NEEDED",
        "NOT_CURRENTLY_AFFORDABLE",
    }
    assert "p50_expected" in analysis["forecast"]
    assert "scenario_survival" in analysis["stress_test"]


def test_individual_application_routes_and_mocked_posts() -> None:
    application_id = first_application_id()

    assert client.get(f"/applications/{application_id}/financial-profile").status_code == 200
    assert client.get(f"/applications/{application_id}/forecast").status_code == 200
    assert client.post(f"/applications/{application_id}/stress-test").status_code == 200
    assert client.get(f"/applications/{application_id}/repayment-envelope").status_code == 200
    assert client.get(f"/applications/{application_id}/decision").status_code == 200
    assert client.get(f"/applications/{application_id}/credit-path").status_code == 200

    repayment = client.post(f"/applications/{application_id}/repayments", json={"event": "on_time"})
    evidence = client.post(f"/applications/{application_id}/additional-evidence", json={})

    assert repayment.status_code == 200
    assert repayment.json()["mock_simulation"] is True
    assert evidence.status_code == 200
    assert evidence.json()["mock_external_retrieval"] is True


def test_demo_simulation_runs_backend_recalculations() -> None:
    application_id = first_application_id()

    responses = {
        action: client.post(
            f"/applications/{application_id}/demo-simulation",
            json={"action": action},
        )
        for action in (
            "on_time",
            "late",
            "missed",
            "income_shock_20",
            "emergency_expense",
            "additional_evidence",
        )
    }
    invalid = client.post(
        f"/applications/{application_id}/demo-simulation",
        json={"action": "not_supported"},
    )

    for response in responses.values():
        assert response.status_code == 200
        assert response.json()["mock_simulation"] is True
        assert "decision_state" in response.json()["result"]
    assert responses["income_shock_20"].json()["applied_adjustments"]["income_multiplier"] == 0.8
    assert responses["income_shock_20"].json()["result"]["stress_survival"] is not None
    assert responses["emergency_expense"].json()["applied_adjustments"]["one_off_expense"] > 0
    assert "recommended_evidence" in responses["additional_evidence"].json()["applied_adjustments"]
    assert invalid.status_code == 422


def test_missing_application_returns_404() -> None:
    response = client.get("/applications/999999999/decision")

    assert response.status_code == 404
