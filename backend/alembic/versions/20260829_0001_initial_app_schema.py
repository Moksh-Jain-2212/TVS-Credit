"""Initial application-platform schema.

Revision ID: 20260829_0001
Revises:
Create Date: 2026-08-29
"""

from __future__ import annotations

from alembic import op

from app import models  # noqa: F401
from app.core.app_database import AppBase


revision = "20260829_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    AppBase.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    AppBase.metadata.drop_all(bind=bind)

