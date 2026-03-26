"""create ingredient domain tables

Revision ID: 20260313_0001
Revises:
Create Date: 2026-03-13 17:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260313_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inci_name", sa.String(length=255), nullable=False),
        sa.Column("korean_name", sa.String(length=255), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("inci_name"),
    )

    op.create_table(
        "ingredient_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("alias_name", sa.String(length=255), nullable=False),
        sa.Column("language", sa.String(length=10), server_default="ko", nullable=False),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingredient_id", "alias_name", name="uq_ingredient_aliases_ingredient_id_alias_name"),
    )

    op.create_table(
        "ingredient_conflicts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_a_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_b_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("LOW", "MID", "HIGH", name="conflict_severity", create_type=False),
            nullable=False,
        ),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.CheckConstraint("ingredient_a_id < ingredient_b_id", name="ck_ingredient_conflicts_ordering"),
        sa.ForeignKeyConstraint(["ingredient_a_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["ingredient_b_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ingredient_a_id", "ingredient_b_id", name="uq_ingredient_conflicts_pair"),
    )

def downgrade() -> None:
    op.drop_table("ingredient_conflicts")
    op.drop_table("ingredient_aliases")
    op.drop_table("ingredients")

    sa.Enum("LOW", "MID", "HIGH", name="conflict_severity").drop(op.get_bind(), checkfirst=True)
