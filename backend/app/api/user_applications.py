"""Borrower application routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.app_database import get_app_session
from app.core.security import require_user
from app.models import User
from app.schemas.alternative_data import AlternativeDataConsentRequest, AlternativeDataManualInputRequest
from app.schemas.application import LoanApplicationCreateRequest, LoanApplicationUpdateRequest
from app.services import alternative_data_service
from app.services import application_service


router = APIRouter(prefix="/user", tags=["user applications"])


@router.post("/applications")
def create_application(
    request: LoanApplicationCreateRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    return application_service.create_application(session, current_user, request)


@router.get("/applications")
def list_applications(
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> list[dict]:
    return application_service.list_applications(session, current_user)


@router.get("/applications/{application_id}")
def get_application(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    data = application_service.serialize_application(application)
    data["notifications"] = application_service.status_messages(application)
    return data


@router.put("/applications/{application_id}")
def update_application(
    application_id: int,
    request: LoanApplicationUpdateRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    return application_service.update_application(session, current_user, application_id, request)


@router.post("/applications/{application_id}/connect-demo-financial-profile")
def connect_demo_financial_profile(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    return application_service.connect_demo_financial_profile(session, current_user, application_id)


@router.get("/applications/{application_id}/alternative-data/sources")
def list_alternative_data_sources(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.application_sources(session, application)


@router.get("/applications/{application_id}/alternative-data")
def get_alternative_data_status(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.application_sources(session, application)


@router.get("/applications/{application_id}/alternative-data/readiness")
def get_alternative_data_readiness(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.alternative_data_readiness(session, application)


@router.post("/applications/{application_id}/alternative-data/{source_type}/consent")
def grant_alternative_data_consent(
    application_id: int,
    source_type: str,
    request: AlternativeDataConsentRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    if not request.granted:
        return alternative_data_service.revoke_consent(session, application, current_user, source_type)
    return alternative_data_service.grant_consent(session, application, current_user, source_type, request.purpose)


@router.delete("/applications/{application_id}/alternative-data/{source_type}/consent")
def revoke_alternative_data_consent(
    application_id: int,
    source_type: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.revoke_consent(session, application, current_user, source_type)


@router.post("/applications/{application_id}/alternative-data/{source_type}/connect-mock")
def connect_mock_alternative_data_source(
    application_id: int,
    source_type: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.connect_mock_source(session, application, current_user, source_type)


@router.post("/applications/{application_id}/alternative-data/{source_type}/manual-input")
def connect_manual_alternative_data_source(
    application_id: int,
    source_type: str,
    request: AlternativeDataManualInputRequest,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.connect_manual_source(session, application, current_user, source_type, request.payload)


@router.post("/applications/{application_id}/alternative-data/{source_type}/refresh")
def refresh_alternative_data_source(
    application_id: int,
    source_type: str,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    application = application_service.get_owned_application(session, current_user, application_id)
    return alternative_data_service.refresh_source(session, application, current_user, source_type)


@router.post("/applications/{application_id}/submit")
def submit_application(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    return application_service.submit_application(session, current_user, application_id)
