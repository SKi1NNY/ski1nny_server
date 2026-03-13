"""add ingredient indexes

Revision ID: 20260313_0002
Revises: 20260313_0001
Create Date: 2026-03-13 19:20:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260313_0002"
down_revision = "20260313_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_ingredient_aliases_alias_name_lower",
        "ingredient_aliases",
        [sa.text("LOWER(alias_name)")],
        unique=False,
    )
    op.create_index(
        "ix_ingredient_conflicts_ingredient_a_id",
        "ingredient_conflicts",
        ["ingredient_a_id"],
        unique=False,
    )
    op.create_index(
        "ix_ingredient_conflicts_ingredient_b_id",
        "ingredient_conflicts",
        ["ingredient_b_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_ingredient_conflicts_ingredient_b_id", table_name="ingredient_conflicts")
    op.drop_index("ix_ingredient_conflicts_ingredient_a_id", table_name="ingredient_conflicts")
    op.drop_index("ix_ingredient_aliases_alias_name_lower", table_name="ingredient_aliases")
