"""Authentication API schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class EmailRequestMixin(BaseModel):
    email: str = Field(min_length=3, max_length=320)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
            raise ValueError("valid email address is required")
        return normalized


class RegisterRequest(EmailRequestMixin):
    name: str = Field(min_length=2, max_length=255)
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        has_letter = any(character.isalpha() for character in value)
        has_digit = any(character.isdigit() for character in value)
        if not has_letter or not has_digit:
            raise ValueError("password must include at least one letter and one number")
        return value


class OtpVerifyRequest(EmailRequestMixin):
    otp: str = Field(pattern=r"^\d{6}$")
    purpose: str = Field(default="REGISTER", max_length=64)


class OtpResendRequest(EmailRequestMixin):
    purpose: str = Field(default="REGISTER", max_length=64)


class LoginRequest(EmailRequestMixin):
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str
    phone: str | None
    role: str
    is_verified: bool
    is_active: bool


class RegisterResponse(BaseModel):
    user: UserResponse
    otp_delivery: dict


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse
