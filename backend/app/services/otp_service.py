"""OTP lifecycle helpers."""

from __future__ import annotations

import secrets
from datetime import timedelta

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import (
    OTP_ITERATIONS,
    ensure_aware,
    hash_secret,
    otp_delivery_mode,
    otp_expire_minutes,
    utc_now,
    verify_secret,
)
from app.models import OtpVerification, User


MAX_OTP_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 30


def generate_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def create_otp(session: Session, user: User, purpose: str) -> tuple[OtpVerification, str]:
    otp = generate_otp()
    verification = OtpVerification(
        user=user,
        purpose=purpose,
        otp_hash=hash_secret(otp, iterations=OTP_ITERATIONS),
        expires_at=utc_now() + timedelta(minutes=otp_expire_minutes()),
    )
    session.add(verification)
    session.flush()
    return verification, otp


def latest_otp(session: Session, user: User, purpose: str) -> OtpVerification | None:
    return session.scalar(
        select(OtpVerification)
        .where(OtpVerification.user_id == user.id, OtpVerification.purpose == purpose)
        .order_by(desc(OtpVerification.created_at))
    )


def resend_otp(session: Session, user: User, purpose: str) -> tuple[OtpVerification, str]:
    existing = latest_otp(session, user, purpose)
    if existing and existing.consumed_at is None:
        elapsed = (utc_now() - ensure_aware(existing.created_at)).total_seconds()
        if elapsed < RESEND_COOLDOWN_SECONDS:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="OTP resend cooldown active")
    return create_otp(session, user, purpose)


def verify_otp(session: Session, user: User, purpose: str, otp: str) -> OtpVerification:
    verification = latest_otp(session, user, purpose)
    if verification is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP not found")
    if verification.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP already used")
    if ensure_aware(verification.expires_at) < utc_now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP expired")
    if verification.attempt_count >= MAX_OTP_ATTEMPTS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP attempts exceeded")
    if not verify_secret(otp, verification.otp_hash):
        verification.attempt_count += 1
        session.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    verification.consumed_at = utc_now()
    session.flush()
    return verification


def delivery_payload(otp: str) -> dict:
    mode = otp_delivery_mode()
    payload = {
        "mode": mode,
        "label": "OTP delivery: MOCK_CONSOLE" if mode == "MOCK_CONSOLE" else f"OTP delivery: {mode}",
        "mocked": mode == "MOCK_CONSOLE",
    }
    if mode == "MOCK_CONSOLE":
        payload["development_otp"] = otp
    return payload
