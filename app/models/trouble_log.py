from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING
from uuid import UUID as UUIDValue, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum as SqlEnum, ForeignKey, Index, SmallInteger, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.ingredient import Ingredient
    from app.models.product import Product
    from app.models.user import User


class TroubleReactionType(str, Enum):
    ACNE = "ACNE"
    DRYNESS = "DRYNESS"
    REDNESS = "REDNESS"
    ITCH = "ITCH"
    OTHER = "OTHER"


class TroubleLog(Base):
    __tablename__ = "trouble_logs"
    __table_args__ = (
        CheckConstraint("severity >= 1 AND severity <= 5", name="ck_trouble_logs_severity_range"),
    )

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )
    reaction_type: Mapped[TroubleReactionType] = mapped_column(
        SqlEnum(TroubleReactionType, name="trouble_reaction_type"),
        nullable=False,
    )
    severity: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    user: Mapped["User"] = relationship(back_populates="trouble_logs")
    product: Mapped["Product"] = relationship(back_populates="trouble_logs")
    trouble_log_ingredients: Mapped[list["TroubleLogIngredient"]] = relationship(
        back_populates="trouble_log",
        cascade="all, delete-orphan",
    )


class TroubleLogIngredient(Base):
    __tablename__ = "trouble_log_ingredients"
    __table_args__ = (
        UniqueConstraint("trouble_log_id", "ingredient_id", name="uq_trouble_log_ingredients_log_id_ingredient_id"),
    )

    id: Mapped[UUIDValue] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    trouble_log_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("trouble_logs.id", ondelete="CASCADE"),
        nullable=False,
    )
    ingredient_id: Mapped[UUIDValue] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ingredients.id", ondelete="CASCADE"),
        nullable=False,
    )

    trouble_log: Mapped["TroubleLog"] = relationship(back_populates="trouble_log_ingredients")
    ingredient: Mapped["Ingredient"] = relationship(back_populates="trouble_log_ingredients")


Index("ix_trouble_logs_user_id", TroubleLog.user_id)
Index("ix_trouble_logs_product_id", TroubleLog.product_id)
Index("ix_trouble_log_ingredients_trouble_log_id", TroubleLogIngredient.trouble_log_id)
