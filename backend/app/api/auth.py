"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.app_database import get_app_session
from app.core.security import get_current_user
from app.models import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    OtpResendRequest,
    OtpVerifyRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services import auth_service


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register")
def register(request: RegisterRequest, session: Session = Depends(get_app_session)) -> dict:
    return auth_service.register_user(session, request)


@router.post("/verify-otp")
def verify_otp(request: OtpVerifyRequest, session: Session = Depends(get_app_session)) -> dict:
    return auth_service.verify_registration_otp(session, request.email, request.otp, request.purpose)


@router.post("/resend-otp")
def resend_otp(request: OtpResendRequest, session: Session = Depends(get_app_session)) -> dict:
    return auth_service.resend_registration_otp(session, request.email, request.purpose)


@router.post("/login")
def login(request: LoginRequest, session: Session = Depends(get_app_session)) -> dict:
    return auth_service.login(session, request.email, request.password)


@router.post("/refresh")
def refresh(request: RefreshRequest, session: Session = Depends(get_app_session)) -> dict:
    return auth_service.refresh(session, request.refresh_token)


@router.post("/logout")
def logout(
    request: LogoutRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_app_session),
) -> dict:
    return auth_service.logout(session, current_user, request.refresh_token)


@router.get("/me")
def me(current_user: User = Depends(get_current_user)) -> dict:
    return auth_service.serialize_user(current_user)
