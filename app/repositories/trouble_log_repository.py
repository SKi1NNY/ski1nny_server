from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.trouble_log import TroubleLog, TroubleLogIngredient


@dataclass(slots=True)
class TroubleIngredientStat:
    ingredient_id: UUID
    inci_name: str
    occurrence_count: int


class TroubleLogRepository:
    def create(
        self,
        db: Session,
        *,
        user_id: UUID,
        product_id: UUID,
        reaction_type,
        severity: int,
        memo: str | None,
    ) -> TroubleLog:
        trouble_log = TroubleLog(
            user_id=user_id,
            product_id=product_id,
            reaction_type=reaction_type,
            severity=severity,
            memo=memo,
        )
        db.add(trouble_log)
        db.flush()
        return trouble_log

    def add_ingredients(self, db: Session, *, trouble_log_id: UUID, ingredient_ids: list[UUID]) -> list[TroubleLogIngredient]:
        rows: list[TroubleLogIngredient] = []
        for ingredient_id in dict.fromkeys(ingredient_ids):
            row = TroubleLogIngredient(trouble_log_id=trouble_log_id, ingredient_id=ingredient_id)
            db.add(row)
            rows.append(row)
        db.flush()
        return rows

    def get_by_id(self, db: Session, trouble_log_id: UUID, *, user_id: UUID) -> TroubleLog | None:
        stmt = (
            select(TroubleLog)
            .options(joinedload(TroubleLog.trouble_log_ingredients))
            .where(TroubleLog.id == trouble_log_id, TroubleLog.user_id == user_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    def list_by_user_id(self, db: Session, user_id: UUID) -> list[TroubleLog]:
        stmt = (
            select(TroubleLog)
            .options(joinedload(TroubleLog.trouble_log_ingredients))
            .where(TroubleLog.user_id == user_id, TroubleLog.is_deleted.is_(False))
            .order_by(TroubleLog.logged_at.desc(), TroubleLog.id.desc())
        )
        return list(db.scalars(stmt).unique())

    def soft_delete(self, db: Session, trouble_log: TroubleLog) -> TroubleLog:
        trouble_log.is_deleted = True
        db.flush()
        return trouble_log

    def aggregate_ingredient_occurrences(self, db: Session, user_id: UUID) -> list[TroubleIngredientStat]:
        from app.models.ingredient import Ingredient

        stmt = (
            select(
                TroubleLogIngredient.ingredient_id,
                Ingredient.inci_name,
                func.count(TroubleLogIngredient.id).label("occurrence_count"),
            )
            .join(TroubleLog, TroubleLog.id == TroubleLogIngredient.trouble_log_id)
            .join(Ingredient, Ingredient.id == TroubleLogIngredient.ingredient_id)
            .where(TroubleLog.user_id == user_id, TroubleLog.is_deleted.is_(False))
            .group_by(TroubleLogIngredient.ingredient_id, Ingredient.inci_name)
            .order_by(func.count(TroubleLogIngredient.id).desc(), Ingredient.inci_name.asc())
        )
        return [
            TroubleIngredientStat(
                ingredient_id=ingredient_id,
                inci_name=inci_name,
                occurrence_count=int(occurrence_count),
            )
            for ingredient_id, inci_name, occurrence_count in db.execute(stmt).all()
        ]
