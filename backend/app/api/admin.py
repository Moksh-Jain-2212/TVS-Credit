"""Admin and loan-officer routes."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.app_database import get_app_session
from app.core.security import require_admin
from app.models import User
from app.schemas.admin import AdminDecisionRequest
from app.services import admin_service


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/dashboard")
def dashboard(
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.dashboard(session)


@router.get("/applications")
def list_applications(
    status: str | None = None,
    nadi_decision: str | None = None,
    submitted_date: date | None = None,
    risk_band: str | None = None,
    confidence_band: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> list[dict]:
    return admin_service.list_applications(
        session,
        status_filter=status,
        nadi_decision=nadi_decision,
        date_filter=submitted_date,
        risk=risk_band,
        confidence=confidence_band,
        limit=limit,
    )


@router.get("/applications/{application_id}")
def get_application(
    application_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.application_detail(session, application_id)


@router.get("/applications/{application_id}/grok-explanation")
def get_grok_explanation(
    application_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.get_grok_explanation(session, application_id)


@router.post("/applications/{application_id}/grok-explanation")
def generate_grok_explanation(
    application_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.generate_grok_explanation(session, application_id)


@router.get("/applications/{application_id}/transactions")
def get_transactions(
    application_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    application = admin_service.get_admin_application(session, application_id)
    return admin_service.transactions_for_application(application)


@router.get("/users/{user_id}")
def get_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.get_user_detail(session, user_id)


@router.post("/applications/{application_id}/analyze")
def analyze_application(
    application_id: int,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.analyze_application(session, current_user, application_id)


@router.post("/applications/{application_id}/decision")
def decide_application(
    application_id: int,
    request: AdminDecisionRequest,
    current_user: User = Depends(require_admin),
    session: Session = Depends(get_app_session),
) -> dict:
    return admin_service.create_admin_decision(session, current_user, application_id, request)
