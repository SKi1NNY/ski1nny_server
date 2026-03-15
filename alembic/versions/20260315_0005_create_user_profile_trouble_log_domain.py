"""create user profile and trouble log domain tables

Revision ID: 20260315_0005
Revises: 20260315_0004
Create Date: 2026-03-15 19:10:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260315_0005"
down_revision = "20260315_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("skin_type", sa.Enum("DRY", "OILY", "COMBINATION", "SENSITIVE", "NORMAL", name="skin_type"), nullable=False),
        sa.Column("skin_concerns", postgresql.ARRAY(sa.String(length=100)), server_default="{}", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "avoid_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "registered_type",
            sa.Enum("MANUAL", "AUTO", name="avoid_ingredient_registered_type"),
            nullable=False,
        ),
        sa.Column("is_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "ingredient_id", name="uq_avoid_ingredients_user_id_ingredient_id"),
    )

    op.create_table(
        "trouble_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "reaction_type",
            sa.Enum("ACNE", "DRYNESS", "REDNESS", "ITCH", "OTHER", name="trouble_reaction_type"),
            nullable=False,
        ),
        sa.Column("severity", sa.SmallInteger(), nullable=False),
        sa.Column("memo", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("logged_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("severity >= 1 AND severity <= 5", name="ck_trouble_logs_severity_range"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "trouble_log_ingredients",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trouble_log_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["trouble_log_id"], ["trouble_logs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "trouble_log_id",
            "ingredient_id",
            name="uq_trouble_log_ingredients_log_id_ingredient_id",
        ),
    )


def downgrade() -> None:
    op.drop_table("trouble_log_ingredients")
    op.drop_table("trouble_logs")
    op.drop_table("avoid_ingredients")
    op.drop_table("user_profiles")

    sa.Enum("ACNE", "DRYNESS", "REDNESS", "ITCH", "OTHER", name="trouble_reaction_type").drop(
        op.get_bind(),
        checkfirst=True,
    )
    sa.Enum("MANUAL", "AUTO", name="avoid_ingredient_registered_type").drop(op.get_bind(), checkfirst=True)
    sa.Enum("DRY", "OILY", "COMBINATION", "SENSITIVE", "NORMAL", name="skin_type").drop(
        op.get_bind(),
        checkfirst=True,
    )
