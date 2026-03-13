from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.models.ingredient import Ingredient, IngredientAlias, IngredientConflict


@dataclass(slots=True)
class IngredientSearchHit:
    ingredient: Ingredient
    matched_alias: str | None = None


class IngredientRepository:
    def get_by_id(self, db: Session, ingredient_id: UUID) -> Ingredient | None:
        stmt = (
            select(Ingredient)
            .options(joinedload(Ingredient.aliases))
            .where(Ingredient.id == ingredient_id)
        )
        return db.scalar(stmt)

    def get_by_inci_name(self, db: Session, inci_name: str) -> Ingredient | None:
        normalized = inci_name.strip().lower()
        stmt = (
            select(Ingredient)
            .options(joinedload(Ingredient.aliases))
            .where(func.lower(Ingredient.inci_name) == normalized)
        )
        return db.scalar(stmt)

    def list_by_inci_names(self, db: Session, inci_names: list[str]) -> list[Ingredient]:
        normalized_names = [name.strip().lower() for name in inci_names if name.strip()]
        if not normalized_names:
            return []

        stmt = (
            select(Ingredient)
            .options(joinedload(Ingredient.aliases))
            .where(func.lower(Ingredient.inci_name).in_(normalized_names))
            .order_by(Ingredient.inci_name.asc())
        )
        return list(db.scalars(stmt).unique())

    def search(self, db: Session, query: str, limit: int = 20) -> list[IngredientSearchHit]:
        normalized = query.strip().lower()
        if not normalized:
            return []

        contains_pattern = f"%{normalized}%"
        prefix_pattern = f"{normalized}%"
        rank = case(
            (func.lower(Ingredient.inci_name) == normalized, 0),
            (func.lower(IngredientAlias.alias_name) == normalized, 1),
            (func.lower(Ingredient.inci_name).like(prefix_pattern), 2),
            (func.lower(IngredientAlias.alias_name).like(prefix_pattern), 3),
            else_=4,
        )

        stmt = (
            select(Ingredient, IngredientAlias.alias_name, rank.label("rank"))
            .outerjoin(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
            .where(
                or_(
                    func.lower(Ingredient.inci_name).like(contains_pattern),
                    func.lower(IngredientAlias.alias_name).like(contains_pattern),
                )
            )
            .order_by(rank.asc(), Ingredient.inci_name.asc(), IngredientAlias.alias_name.asc())
            .limit(limit * 3)
        )

        rows = db.execute(stmt).all()
        hits_by_id: dict[UUID, IngredientSearchHit] = {}
        for ingredient, matched_alias, _ in rows:
            if ingredient.id in hits_by_id:
                continue
            hits_by_id[ingredient.id] = IngredientSearchHit(
                ingredient=ingredient,
                matched_alias=matched_alias,
            )
            if len(hits_by_id) >= limit:
                break
        return list(hits_by_id.values())

    def map_aliases(self, db: Session, alias_names: list[str]) -> dict[str, Ingredient]:
        normalized_names = sorted({alias.strip().lower() for alias in alias_names if alias.strip()})
        if not normalized_names:
            return {}

        stmt = (
            select(IngredientAlias, Ingredient)
            .join(Ingredient, Ingredient.id == IngredientAlias.ingredient_id)
            .where(func.lower(IngredientAlias.alias_name).in_(normalized_names))
            .order_by(IngredientAlias.alias_name.asc())
        )

        mappings: dict[str, Ingredient] = {}
        for alias, ingredient in db.execute(stmt).all():
            mappings[alias.alias_name.strip().lower()] = ingredient
        return mappings

    def get_conflicts_for_ingredient_ids(
        self,
        db: Session,
        ingredient_ids: list[UUID],
    ) -> list[IngredientConflict]:
        unique_ids = list(dict.fromkeys(ingredient_ids))
        if len(unique_ids) < 2:
            return []

        stmt = (
            select(IngredientConflict)
            .options(
                joinedload(IngredientConflict.ingredient_a),
                joinedload(IngredientConflict.ingredient_b),
            )
            .where(
                IngredientConflict.ingredient_a_id.in_(unique_ids),
                IngredientConflict.ingredient_b_id.in_(unique_ids),
            )
            .order_by(
                IngredientConflict.severity.desc(),
                IngredientConflict.ingredient_a_id.asc(),
                IngredientConflict.ingredient_b_id.asc(),
            )
        )
        return list(db.scalars(stmt).unique())
