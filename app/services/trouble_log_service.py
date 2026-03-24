from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    InvalidAvoidIngredientSuggestionError,
    ProductNotFoundError,
    TroubleLogNotFoundError,
    UserNotFoundError,
)
from app.models.trouble_log import TroubleLog
from app.models.user import AvoidIngredientRegisteredType
from app.repositories.product_repository import ProductRepository
from app.repositories.trouble_log_repository import TroubleIngredientStat, TroubleLogRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    AvoidIngredientResponse,
    SuggestedAvoidIngredientResponse,
    TroubleLogConfirmAvoidIngredientsResponse,
    TroubleLogCreateResponse,
    TroubleLogListResponse,
    TroubleLogResponse,
)
from app.services.recommendation_cache import NoOpRecommendationCacheInvalidator, RecommendationCacheInvalidator

TROUBLE_SUGGESTION_THRESHOLD = 2


class TroubleLogService:
    def __init__(
        self,
        user_repository: UserRepository | None = None,
        product_repository: ProductRepository | None = None,
        trouble_log_repository: TroubleLogRepository | None = None,
        profile_repository: UserProfileRepository | None = None,
        cache_invalidator: RecommendationCacheInvalidator | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository()
        self.product_repository = product_repository or ProductRepository()
        self.trouble_log_repository = trouble_log_repository or TroubleLogRepository()
        self.profile_repository = profile_repository or UserProfileRepository()
        self.cache_invalidator = cache_invalidator or NoOpRecommendationCacheInvalidator()

    def create_trouble_log(
        self,
        db: Session,
        *,
        user_id: UUID,
        product_id: UUID,
        reaction_type,
        severity: int,
        memo: str | None,
    ) -> TroubleLogCreateResponse:
        self._ensure_user_exists(db, user_id)
        product = self.product_repository.get_by_id(db, product_id)
        if product is None:
            raise ProductNotFoundError()

        trouble_log = self.trouble_log_repository.create(
            db,
            user_id=user_id,
            product_id=product_id,
            reaction_type=reaction_type,
            severity=severity,
            memo=memo,
        )
        ingredient_ids = self.product_repository.list_ingredient_ids(db, product_id)
        self.trouble_log_repository.add_ingredients(
            db,
            trouble_log_id=trouble_log.id,
            ingredient_ids=ingredient_ids,
        )
        db.commit()

        reloaded = self.trouble_log_repository.get_by_id(db, trouble_log.id, user_id=user_id)
        if reloaded is None:
            raise TroubleLogNotFoundError("Trouble log could not be loaded.")

        suggestions = self._build_suggestions(
            self.trouble_log_repository.aggregate_ingredient_occurrences(db, user_id),
        )
        self.cache_invalidator.invalidate_recommendation_cache(user_id)
        return TroubleLogCreateResponse(
            trouble_log=self._build_trouble_log_response(reloaded),
            suggested_avoid_ingredients=suggestions,
        )

    def list_trouble_logs(self, db: Session, *, user_id: UUID) -> TroubleLogListResponse:
        self._ensure_user_exists(db, user_id)
        items = self.trouble_log_repository.list_by_user_id(db, user_id)
        return TroubleLogListResponse(items=[self._build_trouble_log_response(item) for item in items])

    def confirm_suggested_avoid_ingredients(
        self,
        db: Session,
        *,
        user_id: UUID,
        trouble_log_id: UUID,
        ingredient_ids: list[UUID],
    ) -> TroubleLogConfirmAvoidIngredientsResponse:
        self._ensure_user_exists(db, user_id)
        trouble_log = self.trouble_log_repository.get_by_id(db, trouble_log_id, user_id=user_id)
        if trouble_log is None or trouble_log.is_deleted:
            raise TroubleLogNotFoundError()

        unique_ingredient_ids = list(dict.fromkeys(ingredient_ids))
        suggested_ids = {
            item.ingredient_id
            for item in self._build_suggestions(
                self.trouble_log_repository.aggregate_ingredient_occurrences(db, user_id),
            )
        }
        invalid_ingredient_ids = [
            ingredient_id
            for ingredient_id in unique_ingredient_ids
            if ingredient_id not in suggested_ids
        ]
        if invalid_ingredient_ids:
            raise InvalidAvoidIngredientSuggestionError(
                detail={
                    "ingredient_ids": [str(ingredient_id) for ingredient_id in invalid_ingredient_ids],
                    "trouble_log_id": str(trouble_log_id),
                }
            )

        confirmed_items: list[AvoidIngredientResponse] = []
        for ingredient_id in unique_ingredient_ids:
            existing = self.profile_repository.get_avoid_ingredient_by_user_and_ingredient(
                db,
                user_id=user_id,
                ingredient_id=ingredient_id,
            )
            if existing is None:
                avoid_ingredient = self.profile_repository.add_avoid_ingredient(
                    db,
                    user_id=user_id,
                    ingredient_id=ingredient_id,
                    registered_type=AvoidIngredientRegisteredType.AUTO,
                    is_confirmed=True,
                )
            else:
                if not existing.is_confirmed:
                    existing.is_confirmed = True
                    existing.registered_type = AvoidIngredientRegisteredType.AUTO
                    db.flush()
                avoid_ingredient = existing

            confirmed_items.append(self._build_avoid_ingredient_response(avoid_ingredient))

        db.commit()
        self.cache_invalidator.invalidate_recommendation_cache(user_id)
        return TroubleLogConfirmAvoidIngredientsResponse(
            trouble_log_id=trouble_log_id,
            confirmed_avoid_ingredients=confirmed_items,
        )

    def soft_delete_trouble_log(self, db: Session, *, user_id: UUID, trouble_log_id: UUID) -> TroubleLogResponse:
        self._ensure_user_exists(db, user_id)
        trouble_log = self.trouble_log_repository.get_by_id(db, trouble_log_id, user_id=user_id)
        if trouble_log is None or trouble_log.is_deleted:
            raise TroubleLogNotFoundError()
        deleted = self.trouble_log_repository.soft_delete(db, trouble_log)
        db.commit()
        self.cache_invalidator.invalidate_recommendation_cache(user_id)
        return self._build_trouble_log_response(deleted)

    def _ensure_user_exists(self, db: Session, user_id: UUID) -> None:
        if self.user_repository.get_by_id(db, user_id) is None:
            raise UserNotFoundError()

    def _build_suggestions(self, stats: list[TroubleIngredientStat]) -> list[SuggestedAvoidIngredientResponse]:
        return [
            SuggestedAvoidIngredientResponse(
                ingredient_id=stat.ingredient_id,
                inci_name=stat.inci_name,
                occurrence_count=stat.occurrence_count,
                message=f"{stat.inci_name} has appeared in trouble logs multiple times.",
            )
            for stat in stats
            if stat.occurrence_count >= TROUBLE_SUGGESTION_THRESHOLD
        ]

    def _build_trouble_log_response(self, trouble_log: TroubleLog) -> TroubleLogResponse:
        return TroubleLogResponse(
            id=trouble_log.id,
            user_id=trouble_log.user_id,
            product_id=trouble_log.product_id,
            reaction_type=trouble_log.reaction_type,
            severity=trouble_log.severity,
            memo=trouble_log.memo,
            is_deleted=trouble_log.is_deleted,
            logged_at=trouble_log.logged_at,
            ingredient_ids=[item.ingredient_id for item in trouble_log.trouble_log_ingredients],
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
