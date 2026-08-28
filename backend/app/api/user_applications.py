"""Borrower application routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.app_database import get_app_session
from app.core.security import require_user
from app.models import User
from app.schemas.application import LoanApplicationCreateRequest, LoanApplicationUpdateRequest
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


@router.post("/applications/{application_id}/submit")
def submit_application(
    application_id: int,
    current_user: User = Depends(require_user),
    session: Session = Depends(get_app_session),
) -> dict:
    return application_service.submit_application(session, current_user, application_id)
