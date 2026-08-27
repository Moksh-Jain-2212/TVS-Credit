"""FastAPI routes for the NADI backend."""

from __future__ import annotations

from fastapi import APIRouter

from app.schemas.api import (
    AdditionalEvidenceRequest,
    ApplicationCreateRequest,
    DemoSimulationRequest,
    RepaymentEventRequest,
)
from app.services import application_repository as repository


router = APIRouter()


@router.get("/borrowers")
def list_borrowers(limit: int = 100) -> list[dict]:
    return repository.list_borrowers(limit=limit)


@router.get("/borrowers/{account_id}")
def get_borrower(account_id: int) -> dict:
    return repository.get_borrower(account_id)


@router.post("/applications")
def create_application(request: ApplicationCreateRequest) -> dict:
    return repository.create_application_reference(request.loan_id, request.account_id)


@router.post("/applications/{application_id}/analyze")
def analyze_application(application_id: int) -> dict:
    return repository.analyze_application(application_id)


@router.get("/applications/{application_id}/financial-profile")
def get_financial_profile(application_id: int) -> dict:
    return repository.financial_profile(application_id)


@router.get("/applications/{application_id}/forecast")
def get_forecast(application_id: int) -> dict:
    return repository.forecast(application_id)


@router.post("/applications/{application_id}/stress-test")
def run_stress_test(application_id: int) -> dict:
    return repository.stress_test(application_id)


@router.get("/applications/{application_id}/repayment-envelope")
def get_repayment_envelope(application_id: int) -> dict:
    return repository.repayment_envelope(application_id)


@router.get("/applications/{application_id}/decision")
def get_decision(application_id: int) -> dict:
    return repository.decision(application_id)


@router.get("/applications/{application_id}/credit-path")
def get_credit_path(application_id: int) -> dict:
    return repository.credit_path(application_id)


@router.post("/applications/{application_id}/repayments")
def add_repayment(application_id: int, request: RepaymentEventRequest) -> dict:
    return repository.simulate_repayment_event(application_id, request.event)


@router.post("/applications/{application_id}/demo-simulation")
def run_demo_simulation(application_id: int, request: DemoSimulationRequest) -> dict:
    return repository.run_demo_simulation(application_id, request.action)


@router.post("/applications/{application_id}/additional-evidence")
def add_additional_evidence(application_id: int, request: AdditionalEvidenceRequest) -> dict:
    return repository.additional_evidence(application_id, request.evidence_type)
