from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID as UUIDValue, uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.trouble_log import TroubleLog
    from app.models.user import User


class Product(Base):
    __tablename__ = "products"

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(50), unique=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    product_ingredients: Mapped[list["ProductIngredient"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductIngredient.ingredient_order",
    )
    scan_results: Mapped[list["ScanResult"]] = relationship(back_populates="product")
    trouble_logs: Mapped[list["TroubleLog"]] = relationship(back_populates="product")


class ProductIngredient(Base):
    __tablename__ = "product_ingredients"
    __table_args__ = (
        UniqueConstraint("product_id", "ingredient_id", name="uq_product_ingredients_product_id_ingredient_id"),
    )

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_order: Mapped[int] = mapped_column(Integer, nullable=False)

    product: Mapped["Product"] = relationship(back_populates="product_ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="product_ingredients")


class ScanResult(Base):
    __tablename__ = "scan_results"

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id: Mapped[UUIDValue | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    raw_ocr_text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    scanned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    product: Mapped["Product"] = relationship(back_populates="scan_results")
    user: Mapped["User"] = relationship(back_populates="scan_results")
    parsed_ingredients: Mapped[list["ScanParsedIngredient"]] = relationship(
        back_populates="scan_result",
        cascade="all, delete-orphan",
    )


class ScanParsedIngredient(Base):
    __tablename__ = "scan_parsed_ingredients"

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    scan_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scan_results.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_name_raw: Mapped[str] = mapped_column(String(255), nullable=False)
    ingredient_id: Mapped[UUIDValue | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_mapped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    scan_result: Mapped["ScanResult"] = relationship(back_populates="parsed_ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="scan_parsed_ingredients")


Index("ix_products_name", Product.name)
Index("ix_products_brand", Product.brand)
Index("ix_product_ingredients_product_id", ProductIngredient.product_id)
Index("ix_scan_results_user_id", ScanResult.user_id)
Index("ix_scan_results_product_id", ScanResult.product_id)
Index("ix_scan_results_scanned_at", ScanResult.scanned_at)
Index("ix_scan_parsed_ingredients_scan_id", ScanParsedIngredient.scan_id)
Index("ix_scan_parsed_ingredients_ingredient_id", ScanParsedIngredient.ingredient_id)
Index("ix_scan_parsed_ingredients_is_mapped", ScanParsedIngredient.is_mapped)
