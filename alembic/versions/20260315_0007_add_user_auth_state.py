"""add user auth state fields

Revision ID: 20260315_0007
Revises: 20260315_0006
Create Date: 2026-03-15 21:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260315_0007"
down_revision = "20260315_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("users", "is_deleted")
    op.drop_column("users", "is_active")
