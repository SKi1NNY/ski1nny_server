from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.user import AvoidIngredient, AvoidIngredientRegisteredType, User, UserProfile


class UserProfileRepository:
    def get_profile_by_user_id(self, db: Session, user_id: UUID) -> UserProfile | None:
        stmt = (
            select(UserProfile)
            .options(joinedload(UserProfile.user).joinedload(User.avoid_ingredients))
            .where(UserProfile.user_id == user_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    def create_profile(
        self,
        db: Session,
        *,
        user_id: UUID,
        skin_type,
        skin_concerns: list[str],
        notes: str | None,
    ) -> UserProfile:
        profile = UserProfile(
            user_id=user_id,
            skin_type=skin_type,
            skin_concerns=skin_concerns,
            notes=notes,
        )
        db.add(profile)
        db.flush()
        return profile

    def update_profile(
        self,
        db: Session,
        profile: UserProfile,
        *,
        skin_type,
        skin_concerns: list[str],
        notes: str | None,
    ) -> UserProfile:
        profile.skin_type = skin_type
        profile.skin_concerns = skin_concerns
        profile.notes = notes
        db.flush()
        return profile

    def list_avoid_ingredients(self, db: Session, user_id: UUID) -> list[AvoidIngredient]:
        stmt = (
            select(AvoidIngredient)
            .options(joinedload(AvoidIngredient.ingredient))
            .where(AvoidIngredient.user_id == user_id)
            .order_by(AvoidIngredient.created_at.asc(), AvoidIngredient.id.asc())
        )
        return list(db.scalars(stmt).unique())

    def get_avoid_ingredient(self, db: Session, avoid_ingredient_id: UUID, *, user_id: UUID) -> AvoidIngredient | None:
        stmt = (
            select(AvoidIngredient)
            .options(joinedload(AvoidIngredient.ingredient))
            .where(AvoidIngredient.id == avoid_ingredient_id, AvoidIngredient.user_id == user_id)
        )
        return db.scalar(stmt)

    def get_avoid_ingredient_by_user_and_ingredient(
        self,
        db: Session,
        *,
        user_id: UUID,
        ingredient_id: UUID,
    ) -> AvoidIngredient | None:
        stmt = (
            select(AvoidIngredient)
            .options(joinedload(AvoidIngredient.ingredient))
            .where(AvoidIngredient.user_id == user_id, AvoidIngredient.ingredient_id == ingredient_id)
        )
        return db.scalar(stmt)

    def add_avoid_ingredient(
        self,
        db: Session,
        *,
        user_id: UUID,
        ingredient_id: UUID,
        registered_type: AvoidIngredientRegisteredType = AvoidIngredientRegisteredType.MANUAL,
        is_confirmed: bool = True,
    ) -> AvoidIngredient:
        avoid_ingredient = AvoidIngredient(
            user_id=user_id,
            ingredient_id=ingredient_id,
            registered_type=registered_type,
            is_confirmed=is_confirmed,
        )
        db.add(avoid_ingredient)
        db.flush()
        db.refresh(avoid_ingredient)
        return self.get_avoid_ingredient(db, avoid_ingredient.id, user_id=user_id) or avoid_ingredient

    def delete_avoid_ingredient(self, db: Session, avoid_ingredient: AvoidIngredient) -> None:
        db.delete(avoid_ingredient)
        db.flush()
