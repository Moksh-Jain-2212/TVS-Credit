"""Authentication service for users, OTP verification, and JWT sessions."""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import (
    access_token_minutes,
    create_jwt,
    decode_jwt,
    ensure_aware,
    hash_secret,
    refresh_token_days,
    utc_now,
    verify_secret,
)
from app.models import AuditLog, RefreshSession, User, UserRole
from app.schemas.auth import RegisterRequest
from app.services.otp_service import create_otp, deliver_otp, resend_otp, verify_otp


def serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "phone": user.phone,
        "role": user.role.value if hasattr(user.role, "value") else str(user.role),
        "is_verified": user.is_verified,
        "is_active": user.is_active,
    }


def get_user_by_email(session: Session, email: str) -> User | None:
    return session.scalar(select(User).where(User.email == email.strip().lower()))


def register_user(session: Session, request: RegisterRequest) -> dict:
    user = User(
        name=request.name.strip(),
        email=request.email.strip().lower(),
        phone=request.phone,
        password_hash=hash_secret(request.password),
        role=UserRole.USER,
        is_verified=False,
        is_active=True,
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    _, otp = create_otp(session, user, "REGISTER")
    try:
        delivery = deliver_otp(user, otp, "REGISTER")
    except HTTPException:
        session.rollback()
        raise
    session.add(
        AuditLog(
            actor_user=user,
            action="USER_REGISTERED",
            entity_type="User",
            entity_id=user.id,
            metadata_json={"otp_delivery_mode": delivery["mode"]},
        )
    )
    session.commit()
    session.refresh(user)
    return {"user": serialize_user(user), "otp_delivery": delivery}


def verify_registration_otp(session: Session, email: str, otp: str, purpose: str = "REGISTER") -> dict:
    user = get_user_by_email(session, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    verify_otp(session, user, purpose, otp)
    if purpose == "REGISTER":
        user.is_verified = True
    session.add(
        AuditLog(
            actor_user=user,
            action="OTP_VERIFIED",
            entity_type="User",
            entity_id=user.id,
            metadata_json={"purpose": purpose},
        )
    )
    session.commit()
    session.refresh(user)
    return serialize_user(user)


def resend_registration_otp(session: Session, email: str, purpose: str = "REGISTER") -> dict:
    user = get_user_by_email(session, email)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    _, otp = resend_otp(session, user, purpose)
    try:
        delivery = deliver_otp(user, otp, purpose)
    except HTTPException:
        session.rollback()
        raise
    session.commit()
    return {"user": serialize_user(user), "otp_delivery": delivery}


def create_token_pair(session: Session, user: User) -> dict:
    refresh_jti = secrets.token_urlsafe(24)
    access_expires = timedelta(minutes=access_token_minutes())
    refresh_expires = timedelta(days=refresh_token_days())
    access_token = create_jwt(
        {"sub": str(user.id), "role": user.role.value, "type": "access"},
        access_expires,
    )
    refresh_token = create_jwt(
        {"sub": str(user.id), "role": user.role.value, "type": "refresh", "jti": refresh_jti},
        refresh_expires,
    )
    session.add(
        RefreshSession(
            user=user,
            token_identifier=refresh_jti,
            expires_at=utc_now() + refresh_expires,
        )
    )
    session.flush()
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": access_token_minutes() * 60,
        "user": serialize_user(user),
    }


def login(session: Session, email: str, password: str) -> dict:
    user = get_user_by_email(session, email)
    if user is None or not verify_secret(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is not verified")
    tokens = create_token_pair(session, user)
    session.add(
        AuditLog(
            actor_user=user,
            action="USER_LOGIN",
            entity_type="User",
            entity_id=user.id,
            metadata_json={},
        )
    )
    session.commit()
    return tokens


def refresh(session: Session, refresh_token: str) -> dict:
    payload = decode_jwt(refresh_token, expected_type="refresh")
    user = session.get(User, int(payload["sub"]))
    refresh_session = session.scalar(
        select(RefreshSession).where(RefreshSession.token_identifier == payload.get("jti"))
    )
    if user is None or not user.is_active or refresh_session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh session")
    if refresh_session.revoked_at is not None or ensure_aware(refresh_session.expires_at) < utc_now():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh session revoked or expired")
    refresh_session.revoked_at = utc_now()
    tokens = create_token_pair(session, user)
    session.commit()
    return tokens


def logout(session: Session, user: User, refresh_token: str | None = None) -> dict:
    if refresh_token:
        payload = decode_jwt(refresh_token, expected_type="refresh")
        refresh_session = session.scalar(
            select(RefreshSession).where(
                RefreshSession.token_identifier == payload.get("jti"),
                RefreshSession.user_id == user.id,
            )
        )
        if refresh_session is not None and refresh_session.revoked_at is None:
            refresh_session.revoked_at = utc_now()
    else:
        for item in session.scalars(
            select(RefreshSession).where(RefreshSession.user_id == user.id, RefreshSession.revoked_at.is_(None))
        ):
            item.revoked_at = utc_now()
    session.add(
        AuditLog(
            actor_user=user,
            action="USER_LOGOUT",
            entity_type="User",
            entity_id=user.id,
            metadata_json={},
        )
    )
    session.commit()
    return {"status": "ok"}
