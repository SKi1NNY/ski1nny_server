from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID as UUIDValue, uuid4

from sqlalchemy import CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.product import ProductIngredient, ScanParsedIngredient
    from app.models.trouble_log import TroubleLogIngredient
    from app.models.user import AvoidIngredient


class ConflictSeverity(str, Enum):
    LOW = "LOW"
    MID = "MID"
    HIGH = "HIGH"


class Ingredient(Base):
    __tablename__ = "ingredients"

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    inci_name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    korean_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    aliases: Mapped[list["IngredientAlias"]] = relationship(
        back_populates="ingredient",
        cascade="all, delete-orphan",
    )
    conflicts_as_a: Mapped[list["IngredientConflict"]] = relationship(
        back_populates="ingredient_a",
        foreign_keys="IngredientConflict.ingredient_a_id",
        cascade="all, delete-orphan",
    )
    conflicts_as_b: Mapped[list["IngredientConflict"]] = relationship(
        back_populates="ingredient_b",
        foreign_keys="IngredientConflict.ingredient_b_id",
        cascade="all, delete-orphan",
    )
    product_ingredients: Mapped[list["ProductIngredient"]] = relationship(back_populates="ingredient")
    avoid_ingredients: Mapped[list["AvoidIngredient"]] = relationship(back_populates="ingredient")
    trouble_log_ingredients: Mapped[list["TroubleLogIngredient"]] = relationship(back_populates="ingredient")
    scan_parsed_ingredients: Mapped[list["ScanParsedIngredient"]] = relationship(back_populates="ingredient")


class IngredientAlias(Base):
    __tablename__ = "ingredient_aliases"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "alias_name", name="uq_ingredient_aliases_ingredient_id_alias_name"),
    )

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ingredient_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_name: Mapped[str] = mapped_column(String(255), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, server_default="ko", default="ko")

    ingredient: Mapped["Ingredient"] = relationship(back_populates="aliases")


class IngredientConflict(Base):
    __tablename__ = "ingredient_conflicts"
    __table_args__ = (
        UniqueConstraint("ingredient_a_id", "ingredient_b_id", name="uq_ingredient_conflicts_pair"),
        CheckConstraint("ingredient_a_id < ingredient_b_id", name="ck_ingredient_conflicts_ordering"),
    )

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    ingredient_a_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_b_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    )
    severity: Mapped[ConflictSeverity] = mapped_column(
        SqlEnum(ConflictSeverity, name="conflict_severity"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)

    ingredient_a: Mapped["Ingredient"] = relationship(
        back_populates="conflicts_as_a",
        foreign_keys=[ingredient_a_id],
    )
    ingredient_b: Mapped["Ingredient"] = relationship(
        back_populates="conflicts_as_b",
        foreign_keys=[ingredient_b_id],
    )


Index("ix_ingredient_aliases_alias_name_lower", func.lower(IngredientAlias.alias_name))
Index("ix_ingredient_conflicts_ingredient_a_id", IngredientConflict.ingredient_a_id)
Index("ix_ingredient_conflicts_ingredient_b_id", IngredientConflict.ingredient_b_id)
