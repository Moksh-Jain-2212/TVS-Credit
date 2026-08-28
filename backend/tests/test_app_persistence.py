from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError, StatementError

from app.core.app_database import AppBase, create_app_session_factory, create_app_sqlite_engine
from app.core.database import create_session_factory, create_sqlite_engine
from app.models import (
    Account,
    AdminDecision,
    AdminDecisionState,
    ApplicationStatus,
    AuditLog,
    LoanApplication,
    OtpVerification,
    RefreshSession,
    UnderwritingResult,
    User,
    UserRole,
)
from scripts.init_app_db import init_app_db
from scripts.init_db import init_db


APP_TABLES = {
    "admin_decisions",
    "audit_logs",
    "loan_applications",
    "otp_verifications",
    "refresh_sessions",
    "underwriting_results",
    "users",
}


def app_session_factory(db_path: Path):
    engine = create_app_sqlite_engine(db_path)
    AppBase.metadata.create_all(bind=engine)
    return create_app_session_factory(engine)


def sample_user(email: str = "borrower@example.com", role: UserRole | str = UserRole.USER) -> User:
    return User(
        name="Borrower One",
        email=email,
        phone="+919999999999",
        password_hash="argon2id-placeholder-hash",
        role=role,
    )


def test_init_app_db_creates_application_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "nadi_app.db"

    init_app_db(db_path)

    inspector = inspect(create_app_sqlite_engine(db_path))
    assert APP_TABLES.issubset(set(inspector.get_table_names()))


def test_init_app_db_keeps_pkdd_database_untouched(tmp_path: Path) -> None:
    pkdd_db_path = tmp_path / "nadi.db"
    app_db_path = tmp_path / "nadi_app.db"
    init_db(pkdd_db_path)

    pkdd_engine = create_sqlite_engine(pkdd_db_path)
    pkdd_session_factory = create_session_factory(pkdd_engine)
    with pkdd_session_factory() as session:
        session.add(
            Account(
                account_id=1,
                district_id=10,
                frequency="POPLATEK MESICNE",
                account_open_date=datetime(1993, 1, 1).date(),
            )
        )
        session.commit()

    init_app_db(app_db_path)

    pkdd_inspector = inspect(create_sqlite_engine(pkdd_db_path))
    assert APP_TABLES.isdisjoint(set(pkdd_inspector.get_table_names()))
    with pkdd_session_factory() as session:
        assert session.get(Account, 1) is not None


def test_application_relationships_work(tmp_path: Path) -> None:
    session_factory = app_session_factory(tmp_path / "nadi_app.db")
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

    with session_factory() as session:
        user = sample_user()
        admin = sample_user("admin@example.com", UserRole.ADMIN)
        application = LoanApplication(
            user=user,
            requested_amount=100000,
            requested_tenure=12,
            loan_purpose="Two wheeler purchase",
        )
        result = UnderwritingResult(
            application=application,
            risk_probability=0.12,
            confidence_score=78.0,
            confidence_band="HIGH",
            nadi_decision_state="SAFE_TO_LEARN",
            decision_reasons_json=["starter exposure recommended"],
        )
        decision = AdminDecision(
            application=application,
            admin_user=admin,
            decision=AdminDecisionState.APPROVE_RECOMMENDED,
            approved_amount=50000,
            approved_tenure=12,
            approved_emi=4500,
            remarks="Proceed with recommended exposure.",
        )
        otp = OtpVerification(user=user, purpose="REGISTER", otp_hash="otp-hash", expires_at=expires_at)
        refresh_session = RefreshSession(
            user=user,
            token_identifier="refresh-token-id",
            expires_at=expires_at + timedelta(days=30),
        )
        audit_log = AuditLog(
            actor_user=admin,
            action="ADMIN_DECISION_CREATED",
            entity_type="LoanApplication",
            entity_id=1,
            metadata_json={"decision": decision.decision},
        )
        session.add_all([user, admin, application, result, decision, otp, refresh_session, audit_log])
        session.commit()

    with session_factory() as session:
        application = session.scalars(select(LoanApplication)).one()
        assert application.user.email == "borrower@example.com"
        assert application.status == ApplicationStatus.DRAFT
        assert application.underwriting_results[0].nadi_decision_state == "SAFE_TO_LEARN"
        assert application.admin_decisions[0].admin_user.role == UserRole.ADMIN
        assert application.user.otp_verifications[0].purpose == "REGISTER"
        assert application.user.refresh_sessions[0].token_identifier == "refresh-token-id"
        assert session.scalars(select(AuditLog)).one().actor_user.email == "admin@example.com"


def test_duplicate_emails_cannot_be_created(tmp_path: Path) -> None:
    session_factory = app_session_factory(tmp_path / "nadi_app.db")

    with session_factory() as session:
        session.add_all([sample_user(), sample_user()])

        with pytest.raises(IntegrityError):
            session.commit()


def test_invalid_user_role_fails(tmp_path: Path) -> None:
    session_factory = app_session_factory(tmp_path / "nadi_app.db")

    with session_factory() as session:
        session.add(sample_user(role="BORROWER"))

        with pytest.raises((IntegrityError, StatementError)):
            session.commit()


def test_application_to_user_relationship_works(tmp_path: Path) -> None:
    session_factory = app_session_factory(tmp_path / "nadi_app.db")

    with session_factory() as session:
        user = sample_user()
        user.applications.append(
            LoanApplication(
                requested_amount=75000,
                requested_tenure=18,
                loan_purpose="Inventory purchase",
            )
        )
        session.add(user)
        session.commit()

    with session_factory() as session:
        user = session.scalars(select(User).where(User.email == "borrower@example.com")).one()
        assert len(user.applications) == 1
        assert user.applications[0].user is user
        assert user.applications[0].loan_purpose == "Inventory purchase"
