"""Create or update an admin user for the NADI application platform."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.app_database import AppBase, app_database_path, create_app_session_factory, create_app_sqlite_engine
from app.core.security import hash_secret
from app.models import User, UserRole


def create_admin(name: str, email: str, phone: str | None, password: str) -> User:
    engine = create_app_sqlite_engine(app_database_path())
    AppBase.metadata.create_all(bind=engine)
    session_factory = create_app_session_factory(engine)
    with session_factory() as session:
        normalized_email = email.strip().lower()
        user = session.query(User).filter(User.email == normalized_email).one_or_none()
        if user is None:
            user = User(
                name=name,
                email=normalized_email,
                phone=phone,
                role=UserRole.ADMIN,
                password_hash=hash_secret(password),
                is_verified=True,
                is_active=True,
            )
            session.add(user)
        else:
            user.name = name
            user.phone = phone
            user.role = UserRole.ADMIN
            user.password_hash = hash_secret(password)
            user.is_verified = True
            user.is_active = True
        session.commit()
        session.refresh(user)
        return user


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--phone", default=None)
    parser.add_argument("--password", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    user = create_admin(args.name, args.email, args.phone, args.password)
    print(f"Admin user ready: {user.email}")


if __name__ == "__main__":
    main()
