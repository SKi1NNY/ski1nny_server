"""add product and scan indexes

Revision ID: 20260315_0004
Revises: 20260315_0003
Create Date: 2026-03-15 15:30:00
"""
from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260315_0004"
down_revision = "20260315_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_products_name", "products", ["name"], unique=False)
    op.create_index("ix_products_brand", "products", ["brand"], unique=False)
    op.create_index("ix_product_ingredients_product_id", "product_ingredients", ["product_id"], unique=False)
    op.create_index("ix_scan_results_user_id", "scan_results", ["user_id"], unique=False)
    op.create_index("ix_scan_results_product_id", "scan_results", ["product_id"], unique=False)
    op.create_index("ix_scan_results_scanned_at", "scan_results", ["scanned_at"], unique=False)
    op.create_index("ix_scan_parsed_ingredients_scan_id", "scan_parsed_ingredients", ["scan_id"], unique=False)
    op.create_index(
        "ix_scan_parsed_ingredients_ingredient_id",
        "scan_parsed_ingredients",
        ["ingredient_id"],
        unique=False,
    )
    op.create_index(
        "ix_scan_parsed_ingredients_is_mapped",
        "scan_parsed_ingredients",
        ["is_mapped"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_scan_parsed_ingredients_is_mapped", table_name="scan_parsed_ingredients")
    op.drop_index("ix_scan_parsed_ingredients_ingredient_id", table_name="scan_parsed_ingredients")
    op.drop_index("ix_scan_parsed_ingredients_scan_id", table_name="scan_parsed_ingredients")
    op.drop_index("ix_scan_results_scanned_at", table_name="scan_results")
    op.drop_index("ix_scan_results_product_id", table_name="scan_results")
    op.drop_index("ix_scan_results_user_id", table_name="scan_results")
    op.drop_index("ix_product_ingredients_product_id", table_name="product_ingredients")
    op.drop_index("ix_products_brand", table_name="products")
    op.drop_index("ix_products_name", table_name="products")
