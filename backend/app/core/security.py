"""Security helpers for password hashing and JWT authentication."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.app_database import get_app_session
from app.core.env import load_backend_env
from app.models import User, UserRole


load_backend_env()

PASSWORD_ITERATIONS = 210_000
OTP_ITERATIONS = 120_000
JWT_ALGORITHM = "HS256"

bearer_scheme = HTTPBearer()


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value not in {None, ""} else default


def jwt_secret() -> str:
    secret = os.getenv("JWT_SECRET")
    environment = os.getenv("ENVIRONMENT", os.getenv("APP_ENV", "development")).lower()
    if secret:
        return secret
    if environment in {"production", "prod"}:
        raise RuntimeError("JWT_SECRET must be configured in production.")
    return "dev-only-nadi-jwt-secret-change-me"


def access_token_minutes() -> int:
    return env_int("ACCESS_TOKEN_EXPIRE_MINUTES", 15)


def refresh_token_days() -> int:
    return env_int("REFRESH_TOKEN_EXPIRE_DAYS", 14)


def otp_expire_minutes() -> int:
    return env_int("OTP_EXPIRE_MINUTES", 5)


def otp_max_attempts() -> int:
    return env_int("OTP_MAX_ATTEMPTS", 5)


def otp_resend_cooldown_seconds() -> int:
    return env_int("OTP_RESEND_COOLDOWN_SECONDS", 30)


def otp_delivery_mode() -> str:
    return os.getenv("OTP_DELIVERY_MODE", "MOCK_CONSOLE")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_secret(secret_value: str, *, iterations: int = PASSWORD_ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", secret_value.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${b64url_encode(salt)}${b64url_encode(digest)}"


def verify_secret(secret_value: str, hashed_value: str) -> bool:
    try:
        algorithm, iterations_text, salt_text, digest_text = hashed_value.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_text)
        salt = b64url_decode(salt_text)
        expected = b64url_decode(digest_text)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", secret_value.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)


def create_jwt(payload: dict[str, Any], expires_delta: timedelta) -> str:
    now = utc_now()
    claims = {
        **payload,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    signing_input = ".".join(
        [
            b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            b64url_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8")),
        ]
    )
    signature = hmac.new(jwt_secret().encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{b64url_encode(signature)}"


def decode_jwt(token: str, expected_type: str | None = None) -> dict[str, Any]:
    try:
        header_text, payload_text, signature_text = token.split(".", 2)
        signing_input = f"{header_text}.{payload_text}"
        expected_signature = hmac.new(
            jwt_secret().encode("utf-8"),
            signing_input.encode("ascii"),
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected_signature, b64url_decode(signature_text)):
            raise ValueError("invalid signature")
        payload = json.loads(b64url_decode(payload_text))
    except (ValueError, json.JSONDecodeError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if int(payload.get("exp", 0)) < int(utc_now().timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Expired token")
    if expected_type is not None and payload.get("type") != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_app_session),
) -> User:
    payload = decode_jwt(credentials.credentials, expected_type="access")
    user_id = payload.get("sub")
    user = session.get(User, int(user_id)) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")
    return user


def require_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.USER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Borrower access required")
    return current_user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user
