from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID as UUIDValue, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.product import ScanResult
    from app.models.trouble_log import TroubleLog


class SkinType(str, Enum):
    DRY = "DRY"
    OILY = "OILY"
    COMBINATION = "COMBINATION"
    SENSITIVE = "SENSITIVE"
    NORMAL = "NORMAL"


class AvoidIngredientRegisteredType(str, Enum):
    MANUAL = "MANUAL"
    AUTO = "AUTO"


class User(Base):
    __tablename__ = "users"

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    profile: Mapped["UserProfile"] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    avoid_ingredients: Mapped[list["AvoidIngredient"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    scan_results: Mapped[list["ScanResult"]] = relationship(back_populates="user")
    trouble_logs: Mapped[list["TroubleLog"]] = relationship(back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    skin_type: Mapped[SkinType] = mapped_column(
        SqlEnum(SkinType, name="skin_type"),
        nullable=False,
    )
    skin_concerns: Mapped[list[str]] = mapped_column(
        ARRAY(String(100)),
        nullable=False,
        default=list,
        server_default="{}",
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="profile")


class AvoidIngredient(Base):
    __tablename__ = "avoid_ingredients"
    __table_args__ = (
        UniqueConstraint("user_id", "ingredient_id", name="uq_avoid_ingredients_user_id_ingredient_id"),
    )

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    )
    registered_type: Mapped[AvoidIngredientRegisteredType] = mapped_column(
        SqlEnum(AvoidIngredientRegisteredType, name="avoid_ingredient_registered_type"),
        nullable=False,
    )
    is_confirmed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="avoid_ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="avoid_ingredients")


Index("ix_avoid_ingredients_user_id", AvoidIngredient.user_id)
