"""add user and trouble log indexes

Revision ID: 20260315_0006
Revises: 20260315_0005
Create Date: 2026-03-15 19:20:00
"""
from __future__ import annotations

from alembic import op


revision = "20260315_0006"
down_revision = "20260315_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_avoid_ingredients_user_id", "avoid_ingredients", ["user_id"], unique=False)
    op.create_index("ix_trouble_logs_user_id", "trouble_logs", ["user_id"], unique=False)
    op.create_index("ix_trouble_logs_product_id", "trouble_logs", ["product_id"], unique=False)
    op.create_index(
        "ix_trouble_log_ingredients_trouble_log_id",
        "trouble_log_ingredients",
        ["trouble_log_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_trouble_log_ingredients_trouble_log_id", table_name="trouble_log_ingredients")
    op.drop_index("ix_trouble_logs_product_id", table_name="trouble_logs")
    op.drop_index("ix_trouble_logs_user_id", table_name="trouble_logs")
    op.drop_index("ix_avoid_ingredients_user_id", table_name="avoid_ingredients")
