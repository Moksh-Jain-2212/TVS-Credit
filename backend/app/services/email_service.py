"""SMTP email delivery for TVS NADI verification messages."""

from __future__ import annotations

import logging
import os
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.security import otp_expire_minutes


logger = logging.getLogger(__name__)


class EmailConfigurationError(RuntimeError):
    """Raised when required SMTP settings are missing or invalid."""


class EmailDeliveryError(RuntimeError):
    """Raised when SMTP delivery fails."""


@dataclass(frozen=True)
class SmtpSettings:
    host: str
    port: int
    username: str
    password: str
    from_email: str
    from_name: str
    use_tls: bool
    timeout_seconds: float = 10.0


def env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def smtp_settings_from_env() -> SmtpSettings:
    required = {
        "SMTP_HOST": os.getenv("SMTP_HOST"),
        "SMTP_PORT": os.getenv("SMTP_PORT"),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME"),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD"),
        "SMTP_FROM_EMAIL": os.getenv("SMTP_FROM_EMAIL"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise EmailConfigurationError(f"Missing SMTP configuration: {', '.join(missing)}")
    try:
        port = int(required["SMTP_PORT"] or "0")
    except ValueError as exc:
        raise EmailConfigurationError("SMTP_PORT must be an integer") from exc
    return SmtpSettings(
        host=str(required["SMTP_HOST"]).strip(),
        port=port,
        username=str(required["SMTP_USERNAME"]).strip(),
        password=str(required["SMTP_PASSWORD"]).strip(),
        from_email=str(required["SMTP_FROM_EMAIL"]).strip(),
        from_name=os.getenv("SMTP_FROM_NAME", "TVS NADI").strip(),
        use_tls=env_bool("SMTP_USE_TLS", True),
    )


def build_otp_email(
    recipient_email: str,
    recipient_name: str,
    otp: str,
    purpose: str,
    settings: SmtpSettings,
) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = "Your TVS NADI verification code"
    message["From"] = f"{settings.from_name} <{settings.from_email}>"
    message["To"] = recipient_email
    message.set_content(
        "\n".join(
            [
                f"Hello {recipient_name},",
                "",
                "Your TVS NADI verification code is:",
                "",
                otp,
                "",
                f"This code expires in {otp_expire_minutes()} minutes.",
                "",
                "Do not share this code with anyone.",
                "",
                "If you did not request this verification, you can ignore this email.",
                "",
                "TVS NADI",
            ]
        )
    )
    message["X-TVS-NADI-Purpose"] = purpose
    return message


def send_otp_email(
    recipient_email: str,
    recipient_name: str,
    otp: str,
    purpose: str,
) -> None:
    settings = smtp_settings_from_env()
    message = build_otp_email(recipient_email, recipient_name, otp, purpose, settings)
    try:
        with smtplib.SMTP(settings.host, settings.port, timeout=settings.timeout_seconds) as smtp:
            smtp.ehlo()
            if settings.use_tls:
                smtp.starttls()
                smtp.ehlo()
            smtp.login(settings.username, settings.password)
            smtp.send_message(message)
    except smtplib.SMTPException as exc:
        logger.exception("SMTP OTP email delivery failed for recipient %s", recipient_email)
        raise EmailDeliveryError("Unable to send verification email") from exc
    except OSError as exc:
        logger.exception("SMTP connection failed for recipient %s", recipient_email)
        raise EmailDeliveryError("Unable to send verification email") from exc
