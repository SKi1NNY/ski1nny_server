from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DuplicateAvoidIngredientError,
    InvalidIngredientReferenceError,
    AvoidIngredientNotFoundError,
    UserNotFoundError,
    UserProfileNotFoundError,
)
from app.models.user import UserProfile
from app.repositories.ingredient_repository import IngredientRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import AvoidIngredientResponse, UserProfileResponse
from app.services.recommendation_cache import NoOpRecommendationCacheInvalidator, RecommendationCacheInvalidator


class UserProfileService:
    def __init__(
        self,
        user_repository: UserRepository | None = None,
        profile_repository: UserProfileRepository | None = None,
        ingredient_repository: IngredientRepository | None = None,
        cache_invalidator: RecommendationCacheInvalidator | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository()
        self.profile_repository = profile_repository or UserProfileRepository()
        self.ingredient_repository = ingredient_repository or IngredientRepository()
        self.cache_invalidator = cache_invalidator or NoOpRecommendationCacheInvalidator()

    def get_profile(self, db: Session, *, user_id: UUID) -> UserProfileResponse:
        self._ensure_user_exists(db, user_id)
        profile = self.profile_repository.get_profile_by_user_id(db, user_id)
        if profile is None:
            raise UserProfileNotFoundError()
        avoid_ingredients = self.profile_repository.list_avoid_ingredients(db, user_id)
        return self._build_profile_response(profile, avoid_ingredients)

    def upsert_profile(
        self,
        db: Session,
        *,
        user_id: UUID,
        skin_type,
        skin_concerns: list[str],
        notes: str | None,
    ) -> UserProfileResponse:
        self._ensure_user_exists(db, user_id)
        profile = self.profile_repository.get_profile_by_user_id(db, user_id)
        if profile is None:
            profile = self.profile_repository.create_profile(
                db,
                user_id=user_id,
                skin_type=skin_type,
                skin_concerns=skin_concerns,
                notes=notes,
            )
        else:
            profile = self.profile_repository.update_profile(
                db,
                profile,
                skin_type=skin_type,
                skin_concerns=skin_concerns,
                notes=notes,
            )

        db.commit()
        self.cache_invalidator.invalidate_recommendation_cache(user_id)
        avoid_ingredients = self.profile_repository.list_avoid_ingredients(db, user_id)
        return self._build_profile_response(profile, avoid_ingredients)

    def add_avoid_ingredient(self, db: Session, *, user_id: UUID, ingredient_id: UUID) -> AvoidIngredientResponse:
        self._ensure_user_exists(db, user_id)
        ingredient = self.ingredient_repository.get_by_id(db, ingredient_id)
        if ingredient is None:
            raise InvalidIngredientReferenceError("Ingredient does not exist.")

        existing = self.profile_repository.get_avoid_ingredient_by_user_and_ingredient(
            db,
            user_id=user_id,
            ingredient_id=ingredient_id,
        )
        if existing is not None:
            raise DuplicateAvoidIngredientError()

        avoid_ingredient = self.profile_repository.add_avoid_ingredient(
            db,
            user_id=user_id,
            ingredient_id=ingredient_id,
        )
        db.commit()
        self.cache_invalidator.invalidate_recommendation_cache(user_id)
        return self._build_avoid_ingredient_response(avoid_ingredient)

    def delete_avoid_ingredient(self, db: Session, *, user_id: UUID, avoid_ingredient_id: UUID) -> None:
        self._ensure_user_exists(db, user_id)
        avoid_ingredient = self.profile_repository.get_avoid_ingredient(
            db,
            avoid_ingredient_id,
            user_id=user_id,
        )
        if avoid_ingredient is None:
            raise AvoidIngredientNotFoundError()
        self.profile_repository.delete_avoid_ingredient(db, avoid_ingredient)
        db.commit()
        self.cache_invalidator.invalidate_recommendation_cache(user_id)

    def _ensure_user_exists(self, db: Session, user_id: UUID) -> None:
        user = self.user_repository.get_by_id(db, user_id)
        if user is None:
            raise UserNotFoundError()

    def _build_profile_response(self, profile: UserProfile, avoid_ingredients) -> UserProfileResponse:
        return UserProfileResponse(
            id=profile.id,
            user_id=profile.user_id,
            skin_type=profile.skin_type,
            skin_concerns=list(profile.skin_concerns),
            notes=profile.notes,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
            avoid_ingredients=[self._build_avoid_ingredient_response(item) for item in avoid_ingredients],
        )

    def _build_avoid_ingredient_response(self, avoid_ingredient) -> AvoidIngredientResponse:
        return AvoidIngredientResponse(
            id=avoid_ingredient.id,
            ingredient_id=avoid_ingredient.ingredient_id,
            inci_name=avoid_ingredient.ingredient.inci_name,
            registered_type=avoid_ingredient.registered_type,
            is_confirmed=avoid_ingredient.is_confirmed,
            created_at=avoid_ingredient.created_at,
        )
