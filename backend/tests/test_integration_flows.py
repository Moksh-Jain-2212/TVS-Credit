import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.services.decision_engine import load_decision_policy, make_decision
from app.services.repayment_envelope import generate_repayment_envelope, load_envelope_policy


client = TestClient(app)


def underwriting_result(row: pd.Series) -> dict:
    envelope = generate_repayment_envelope(row, load_envelope_policy())
    enriched = row.copy()
    enriched["maximum_safe_exposure"] = envelope["maximum_safe_exposure"]
    enriched["recommended_amount"] = envelope["recommended_amount"]
    enriched["recommended_tenure"] = envelope["recommended_tenure"]
    enriched["recommended_emi"] = envelope["recommended_emi"]
    enriched["stress_probability"] = row.get("stress_probability", 0.0)
    decision = make_decision(enriched, load_decision_policy())
    return {"envelope": envelope, "decision": decision}


def test_flow_a_good_evidence_and_affordable_request_can_approve() -> None:
    result = underwriting_result(
        pd.Series(
            {
                "requested_amount": 20000.0,
                "duration_months": 12,
                "scheduled_payment": 1800.0,
                "pre_loan_latest_balance": 100000.0,
                "mean_monthly_inflow": 60000.0,
                "cash_flow_forecast_p10": 25000.0,
                "cash_flow_forecast_p50": 32000.0,
                "cash_flow_forecast_p90": 42000.0,
                "risk_model_probability": 0.05,
                "confidence_score": 90.0,
                "stress_probability": 0.0,
            }
        )
    )

    assert result["envelope"]["maximum_safe_exposure"] >= 20000
    assert result["decision"]["decision_state"] == "APPROVE"


def test_flow_b_safe_to_learn_starter_then_reunderwriting() -> None:
    analysis = client.post("/applications/5161/analyze")
    simulation = client.post("/applications/5161/demo-simulation", json={"action": "on_time"})

    assert analysis.status_code == 200
    assert simulation.status_code == 200
    credit_path = analysis.json()["credit_path"]
    simulated = simulation.json()["result"]
    assert analysis.json()["decision"]["decision_state"] == "SAFE_TO_LEARN"
    assert credit_path["starter_credit_eligible"] is True
    assert credit_path["starter_amount"] > 0
    assert credit_path["simulated_observations"]
    assert simulated["decision_state"] in {"APPROVE", "SAFE_TO_LEARN", "NOT_CURRENTLY_AFFORDABLE", "EVIDENCE_NEEDED"}
    assert simulated["maximum_safe_exposure"] is not None


def test_flow_c_insufficient_evidence_can_request_more_evidence() -> None:
    result = underwriting_result(
        pd.Series(
            {
                "requested_amount": 50000.0,
                "duration_months": 12,
                "scheduled_payment": 4500.0,
                "pre_loan_latest_balance": 1000.0,
                "mean_monthly_inflow": 8000.0,
                "cash_flow_forecast_p10": -3000.0,
                "cash_flow_forecast_p50": 1200.0,
                "cash_flow_forecast_p90": 4000.0,
                "risk_model_probability": 0.2,
                "confidence_score": 35.0,
                "stress_probability": 0.9,
            }
        )
    )

    assert result["envelope"]["maximum_safe_exposure"] == 0
    assert result["decision"]["decision_state"] == "EVIDENCE_NEEDED"


def test_flow_d_sufficient_evidence_and_inadequate_capacity_is_not_affordable() -> None:
    response = client.post("/applications/6097/analyze")

    assert response.status_code == 200
    analysis = response.json()
    assert analysis["financial_profile"]["confidence_score"] >= 75
    assert analysis["repayment_envelope"]["maximum_safe_exposure"] == 0
    assert analysis["decision"]["decision_state"] == "NOT_CURRENTLY_AFFORDABLE"


def test_flow_e_stress_shock_changes_loan_recommendation() -> None:
    baseline = client.post("/applications/5161/analyze")
    shocked = client.post("/applications/5161/demo-simulation", json={"action": "income_shock_20"})

    assert baseline.status_code == 200
    assert shocked.status_code == 200
    baseline_amount = baseline.json()["repayment_envelope"]["maximum_safe_exposure"]
    shocked_amount = shocked.json()["result"]["maximum_safe_exposure"]
    assert shocked.json()["mock_simulation"] is True
    assert shocked_amount != baseline_amount
    assert shocked_amount < baseline_amount
