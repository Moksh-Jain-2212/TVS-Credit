"""Add borrower segment to loan applications.

Revision ID: 20260829_0002
Revises: 20260829_0001
Create Date: 2026-08-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260829_0002"
down_revision = "20260829_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("loan_applications", sa.Column("borrower_segment", sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column("loan_applications", "borrower_segment")
