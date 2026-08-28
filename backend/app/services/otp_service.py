"""OTP lifecycle helpers."""

from __future__ import annotations

import secrets
from datetime import timedelta
import logging

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import (
    OTP_ITERATIONS,
    ensure_aware,
    hash_secret,
    otp_delivery_mode,
    otp_expire_minutes,
    otp_max_attempts,
    otp_resend_cooldown_seconds,
    utc_now,
    verify_secret,
)
from app.models import OtpVerification, User
from app.services import email_service


logger = logging.getLogger(__name__)


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
        if elapsed < otp_resend_cooldown_seconds():
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
    if verification.attempt_count >= otp_max_attempts():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP attempts exceeded")
    if not verify_secret(otp, verification.otp_hash):
        verification.attempt_count += 1
        session.flush()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP")

    verification.consumed_at = utc_now()
    session.flush()
    return verification


def deliver_otp(user: User, otp: str, purpose: str) -> dict:
    mode = otp_delivery_mode()
    if mode == "MOCK_CONSOLE":
        payload = {
            "mode": mode,
            "label": "OTP delivery: MOCK_CONSOLE",
            "mocked": True,
        }
        payload["development_otp"] = otp
        return payload
    if mode == "SMTP_EMAIL":
        try:
            email_service.send_otp_email(
                recipient_email=user.email,
                recipient_name=user.name,
                otp=otp,
                purpose=purpose,
            )
        except (email_service.EmailConfigurationError, email_service.EmailDeliveryError):
            logger.exception("OTP email delivery failed for user_id=%s purpose=%s", user.id, purpose)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to send verification email. Please try again.",
            )
        return {
            "mode": mode,
            "label": "Verification code sent to your email",
            "mocked": False,
        }
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Unsupported OTP delivery mode",
    )
