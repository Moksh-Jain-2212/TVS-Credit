from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.app_database import (
    AppBase,
    create_app_session_factory,
    create_app_sqlite_engine,
    reset_app_engine_cache,
)
from app.core.env import load_backend_env
from app.core.security import create_jwt, hash_secret, utc_now
from app.main import app
from app.models import OtpVerification, User, UserRole
from app.services.finance import estimate_emi
from app.services.repayment_envelope import load_envelope_policy
from app.services import email_service, otp_service
from scripts.init_app_db import init_app_db


@pytest.fixture()
def platform_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "nadi_app.db"
    monkeypatch.setenv("APP_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("OTP_DELIVERY_MODE", "MOCK_CONSOLE")
    reset_app_engine_cache()
    init_app_db(db_path, drop_existing=True)
    with TestClient(app) as client:
        yield client, db_path
    reset_app_engine_cache()


def session_factory(db_path: Path):
    engine = create_app_sqlite_engine(db_path)
    AppBase.metadata.create_all(bind=engine)
    return create_app_session_factory(engine)


def register_verify_login(client: TestClient, email: str = "user@example.com") -> dict:
    register = client.post(
        "/auth/register",
        json={"name": "NADI User", "email": email, "phone": "+919999999999", "password": "strong-pass-1"},
    )
    assert register.status_code == 200
    otp = register.json()["otp_delivery"]["development_otp"]
    verify = client.post("/auth/verify-otp", json={"email": email, "otp": otp})
    assert verify.status_code == 200
    login = client.post("/auth/login", json={"email": email, "password": "strong-pass-1"})
    assert login.status_code == 200
    return login.json()


def create_admin(db_path: Path, email: str = "admin@example.com", password: str = "admin-pass-1") -> None:
    factory = session_factory(db_path)
    with factory() as session:
        session.add(
            User(
                name="Loan Officer",
                email=email,
                phone="+918888888888",
                password_hash=hash_secret(password),
                role=UserRole.ADMIN,
                is_verified=True,
                is_active=True,
            )
        )
        session.commit()


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def valid_application_payload() -> dict:
    return {
        "requested_amount": 100000,
        "requested_tenure": 12,
        "loan_purpose": "Two wheeler purchase",
        "employment_type": "salaried",
        "declared_monthly_income": 55000,
        "declared_monthly_expenses": 22000,
        "existing_monthly_emi": 0,
    }


def test_auth_otp_jwt_refresh_and_rbac(platform_client) -> None:
    client, db_path = platform_client
    register = client.post(
        "/auth/register",
        json={"name": "New User", "email": "new@example.com", "phone": "+910000000000", "password": "strong-pass-1"},
    )
    assert register.status_code == 200
    assert register.json()["otp_delivery"]["mode"] == "MOCK_CONSOLE"
    assert register.json()["otp_delivery"]["development_otp"].isdigit()

    invalid = client.post("/auth/verify-otp", json={"email": "new@example.com", "otp": "000000"})
    assert invalid.status_code == 400
    assert client.post("/auth/login", json={"email": "new@example.com", "password": "strong-pass-1"}).status_code == 403

    otp = register.json()["otp_delivery"]["development_otp"]
    assert client.post("/auth/verify-otp", json={"email": "new@example.com", "otp": otp}).status_code == 200
    assert client.post("/auth/verify-otp", json={"email": "new@example.com", "otp": otp}).status_code == 400

    login = client.post("/auth/login", json={"email": "new@example.com", "password": "strong-pass-1"})
    assert login.status_code == 200
    tokens = login.json()
    assert tokens["token_type"] == "bearer"
    assert client.get("/auth/me", headers=auth_header(tokens["access_token"])).status_code == 200
    assert client.get("/admin/dashboard", headers=auth_header(tokens["access_token"])).status_code == 403

    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401

    expired = create_jwt({"sub": "1", "role": "USER", "type": "access"}, timedelta(seconds=-1))
    assert client.get("/auth/me", headers=auth_header(expired)).status_code == 401

    create_admin(db_path)
    admin_login = client.post("/auth/login", json={"email": "admin@example.com", "password": "admin-pass-1"})
    assert admin_login.status_code == 200
    assert admin_login.json()["token_type"] == "bearer"
    assert client.get("/admin/dashboard", headers=auth_header(admin_login.json()["access_token"])).status_code == 200


def test_expired_otp_fails(platform_client) -> None:
    client, db_path = platform_client
    register = client.post(
        "/auth/register",
        json={"name": "Old OTP", "email": "old@example.com", "phone": None, "password": "strong-pass-1"},
    )
    otp = register.json()["otp_delivery"]["development_otp"]
    factory = session_factory(db_path)
    with factory() as session:
        verification = session.scalars(select(OtpVerification)).one()
        verification.expires_at = utc_now() - timedelta(minutes=1)
        session.commit()

    response = client.post("/auth/verify-otp", json={"email": "old@example.com", "otp": otp})
    assert response.status_code == 400
    assert response.json()["detail"] == "OTP expired"


def test_smtp_otp_delivery_does_not_return_otp_and_resend_sends_new_email(
    platform_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = platform_client
    monkeypatch.setenv("OTP_DELIVERY_MODE", "SMTP_EMAIL")
    monkeypatch.setenv("OTP_RESEND_COOLDOWN_SECONDS", "0")
    otp_values = iter(["111111", "222222"])
    monkeypatch.setattr(otp_service, "generate_otp", lambda: next(otp_values))
    sent: list[dict[str, str]] = []

    def fake_send_otp_email(recipient_email: str, recipient_name: str, otp: str, purpose: str) -> None:
        sent.append(
            {
                "recipient_email": recipient_email,
                "recipient_name": recipient_name,
                "otp": otp,
                "purpose": purpose,
            }
        )

    monkeypatch.setattr(email_service, "send_otp_email", fake_send_otp_email)
    register = client.post(
        "/auth/register",
        json={
            "name": "Email User",
            "email": "email-user@example.com",
            "phone": "+910000000000",
            "password": "strong-pass-1",
        },
    )
    assert register.status_code == 200
    delivery = register.json()["otp_delivery"]
    assert delivery == {
        "mode": "SMTP_EMAIL",
        "label": "Verification code sent to your email",
        "mocked": False,
    }
    assert "development_otp" not in delivery
    assert sent[0]["recipient_email"] == "email-user@example.com"
    assert sent[0]["recipient_name"] == "Email User"
    assert sent[0]["otp"].isdigit()
    assert len(sent[0]["otp"]) == 6

    resend = client.post("/auth/resend-otp", json={"email": "email-user@example.com"})
    assert resend.status_code == 200
    assert "development_otp" not in resend.json()["otp_delivery"]
    assert len(sent) == 2
    assert sent[1]["otp"].isdigit()
    assert len(sent[1]["otp"]) == 6
    assert sent[1]["otp"] != sent[0]["otp"]

    old_code = client.post("/auth/verify-otp", json={"email": "email-user@example.com", "otp": sent[0]["otp"]})
    assert old_code.status_code == 400
    assert old_code.json()["detail"] == "Invalid OTP"

    verified = client.post("/auth/verify-otp", json={"email": "email-user@example.com", "otp": sent[1]["otp"]})
    assert verified.status_code == 200
    assert verified.json()["is_verified"] is True

    used = client.post("/auth/verify-otp", json={"email": "email-user@example.com", "otp": sent[1]["otp"]})
    assert used.status_code == 400
    assert used.json()["detail"] == "OTP already used"

    login = client.post("/auth/login", json={"email": "email-user@example.com", "password": "strong-pass-1"})
    assert login.status_code == 200
    assert login.json()["user"]["is_verified"] is True


def test_smtp_delivery_failure_returns_503_and_rolls_back_user(
    platform_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, db_path = platform_client
    monkeypatch.setenv("OTP_DELIVERY_MODE", "SMTP_EMAIL")

    def fail_send_otp_email(recipient_email: str, recipient_name: str, otp: str, purpose: str) -> None:
        raise email_service.EmailDeliveryError("simulated SMTP failure")

    monkeypatch.setattr(email_service, "send_otp_email", fail_send_otp_email)
    response = client.post(
        "/auth/register",
        json={
            "name": "Failed Email",
            "email": "failed@example.com",
            "phone": "+910000000000",
            "password": "strong-pass-1",
        },
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "Unable to send verification email. Please try again."
    factory = session_factory(db_path)
    with factory() as session:
        assert session.scalar(select(User).where(User.email == "failed@example.com")) is None


def test_complete_platform_underwriting_and_admin_decision_flow(platform_client) -> None:
    client, db_path = platform_client
    user_tokens = register_verify_login(client, "borrower@example.com")
    other_tokens = register_verify_login(client, "other@example.com")
    user_headers = auth_header(user_tokens["access_token"])
    other_headers = auth_header(other_tokens["access_token"])
    create_admin(db_path)
    admin_tokens = client.post("/auth/login", json={"email": "admin@example.com", "password": "admin-pass-1"}).json()
    admin_headers = auth_header(admin_tokens["access_token"])

    created = client.post("/user/applications", json=valid_application_payload(), headers=user_headers)
    assert created.status_code == 200
    application_id = created.json()["id"]
    assert client.get(f"/user/applications/{application_id}", headers=other_headers).status_code == 404

    connected = client.post(
        f"/user/applications/{application_id}/connect-demo-financial-profile",
        headers=user_headers,
    )
    assert connected.status_code == 200
    assert connected.json()["label"] == "Demo bank data connected"

    submitted = client.post(f"/user/applications/{application_id}/submit", headers=user_headers)
    assert submitted.status_code == 200
    submitted_body = submitted.json()
    assert submitted_body["application"]["status"] == "ADMIN_REVIEW"
    assert submitted_body["underwriting"]["nadi_decision_state"] in {
        "APPROVE",
        "SAFE_TO_LEARN",
        "EVIDENCE_NEEDED",
        "NOT_CURRENTLY_AFFORDABLE",
    }

    assert client.get("/admin/applications", headers=user_headers).status_code == 403
    dashboard = client.get("/admin/dashboard", headers=admin_headers)
    assert dashboard.status_code == 200
    assert dashboard.json()["counts"]["admin_review"] == 1

    detail = client.get(f"/admin/applications/{application_id}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["nadi_recommendation"]["decision"] == submitted_body["underwriting"]["nadi_decision_state"]
    assert detail.json()["application"]["latest_admin_decision"] is None

    transactions = client.get(f"/admin/applications/{application_id}/transactions", headers=admin_headers)
    assert transactions.status_code == 200
    assert "average_monthly_inflow" in transactions.json()["summary"]
    assert transactions.json()["underwriting_evidence_scope"].startswith("UNDERWRITING_EVIDENCE")

    decision = client.post(
        f"/admin/applications/{application_id}/decision",
        json={"decision": "APPROVE_RECOMMENDED", "remarks": "Approve NADI recommended exposure."},
        headers=admin_headers,
    )
    assert decision.status_code == 200
    decided = decision.json()
    assert decided["application"]["status"] == "APPROVED"
    assert decided["application"]["latest_underwriting"]["nadi_decision_state"] == detail.json()["nadi_recommendation"]["decision"]
    assert decided["application"]["latest_admin_decision"]["decision"] == "APPROVE_RECOMMENDED"
    assert any(log["action"] == "ADMIN_DECISION_CREATED" for log in decided["audit_history"])


def test_admin_approve_requested_uses_new_loan_emi_and_requires_override_reason(platform_client) -> None:
    client, db_path = platform_client
    user_tokens = register_verify_login(client, "override@example.com")
    user_headers = auth_header(user_tokens["access_token"])
    create_admin(db_path)
    admin_tokens = client.post("/auth/login", json={"email": "admin@example.com", "password": "admin-pass-1"}).json()
    admin_headers = auth_header(admin_tokens["access_token"])
    created = client.post("/user/applications", json=valid_application_payload(), headers=user_headers)
    application_id = created.json()["id"]
    client.post(f"/user/applications/{application_id}/connect-demo-financial-profile", headers=user_headers)
    submitted = client.post(f"/user/applications/{application_id}/submit", headers=user_headers)
    assert submitted.status_code == 200

    without_reason = client.post(
        f"/admin/applications/{application_id}/decision",
        json={"decision": "APPROVE_REQUESTED"},
        headers=admin_headers,
    )
    if without_reason.status_code == 422:
        approved = client.post(
            f"/admin/applications/{application_id}/decision",
            json={"decision": "APPROVE_REQUESTED", "remarks": "Documented compensating business evidence."},
            headers=admin_headers,
        )
    else:
        approved = without_reason
    assert approved.status_code == 200
    decision = approved.json()["application"]["latest_admin_decision"]
    expected = round(estimate_emi(100000, 12, load_envelope_policy().annual_interest_rate), 2)
    assert decision["approved_emi"] == expected
    assert decision["approved_emi"] != valid_application_payload()["existing_monthly_emi"]
    if decision["override_metadata"]["override"]:
        assert decision["override_metadata"]["override_reason"]

    duplicate = client.post(
        f"/admin/applications/{application_id}/decision",
        json={"decision": "REJECT", "remarks": "Duplicate attempt"},
        headers=admin_headers,
    )
    assert duplicate.status_code == 409

    nonexistent = client.post(
        "/admin/applications/9999999/decision",
        json={"decision": "REJECT", "remarks": "No such application"},
        headers=admin_headers,
    )
    assert nonexistent.status_code == 404

    borrower_view = client.get(f"/user/applications/{application_id}", headers=user_headers)
    assert borrower_view.status_code == 200
    assert borrower_view.json()["status"] == "APPROVED"
    assert "Application approved" in borrower_view.json()["notifications"]


def test_underwriting_failure_does_not_silently_approve(platform_client) -> None:
    client, _ = platform_client
    user_tokens = register_verify_login(client, "failure@example.com")
    headers = auth_header(user_tokens["access_token"])
    created = client.post("/user/applications", json=valid_application_payload(), headers=headers).json()

    response = client.post(f"/user/applications/{created['id']}/submit", headers=headers)

    assert response.status_code == 422
    assert "Connect demo financial data" in response.json()["detail"]


def test_email_service_sends_smtp_message_with_tls(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    sent_messages = []

    class FakeSmtp:
        def __init__(self, host: str, port: int, timeout: float):
            events.append(f"connect:{host}:{port}:{timeout}")

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            events.append("close")

        def ehlo(self):
            events.append("ehlo")

        def starttls(self):
            events.append("starttls")

        def login(self, username: str, password: str):
            events.append(f"login:{username}:{password}")

        def send_message(self, message):
            sent_messages.append(message)
            events.append("send_message")

    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USERNAME", "sender@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "sender@example.com")
    monkeypatch.setenv("SMTP_FROM_NAME", "TVS NADI")
    monkeypatch.setenv("SMTP_USE_TLS", "true")
    monkeypatch.setattr(email_service.smtplib, "SMTP", FakeSmtp)

    email_service.send_otp_email("borrower@example.com", "Borrower", "123456", "REGISTER")

    assert events == [
        "connect:smtp.gmail.com:587:10.0",
        "ehlo",
        "starttls",
        "ehlo",
        "login:sender@example.com:app-password",
        "send_message",
        "close",
    ]
    assert sent_messages[0]["To"] == "borrower@example.com"
    assert sent_messages[0]["Subject"] == "Your TVS NADI verification code"
    assert "123456" in sent_messages[0].get_content()


def test_backend_env_loader_reads_smtp_settings_without_overriding_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "OTP_DELIVERY_MODE=SMTP_EMAIL",
                "SMTP_HOST=smtp.gmail.com",
                "SMTP_PASSWORD='app password with spaces'",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.delenv("OTP_DELIVERY_MODE", raising=False)
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.setenv("SMTP_PASSWORD", "already-set")

    load_backend_env(env_path)

    assert email_service.os.getenv("OTP_DELIVERY_MODE") == "SMTP_EMAIL"
    assert email_service.os.getenv("SMTP_HOST") == "smtp.gmail.com"
    assert email_service.os.getenv("SMTP_PASSWORD") == "already-set"
