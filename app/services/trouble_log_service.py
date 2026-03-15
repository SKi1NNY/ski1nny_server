from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.trouble_log import TroubleLog
from app.repositories.product_repository import ProductRepository
from app.repositories.trouble_log_repository import TroubleIngredientStat, TroubleLogRepository
from app.repositories.user_repository import UserRepository
from app.schemas.user import SuggestedAvoidIngredientResponse, TroubleLogCreateResponse, TroubleLogListResponse, TroubleLogResponse

TROUBLE_SUGGESTION_THRESHOLD = 2


class TroubleLogService:
    def __init__(
        self,
        user_repository: UserRepository | None = None,
        product_repository: ProductRepository | None = None,
        trouble_log_repository: TroubleLogRepository | None = None,
    ) -> None:
        self.user_repository = user_repository or UserRepository()
        self.product_repository = product_repository or ProductRepository()
        self.trouble_log_repository = trouble_log_repository or TroubleLogRepository()

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
            raise NotFoundError("Product does not exist.")

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
            raise NotFoundError("Trouble log could not be loaded.")

        suggestions = self._build_suggestions(
            self.trouble_log_repository.aggregate_ingredient_occurrences(db, user_id),
        )
        return TroubleLogCreateResponse(
            trouble_log=self._build_trouble_log_response(reloaded),
            suggested_avoid_ingredients=suggestions,
        )

    def list_trouble_logs(self, db: Session, *, user_id: UUID) -> TroubleLogListResponse:
        self._ensure_user_exists(db, user_id)
        items = self.trouble_log_repository.list_by_user_id(db, user_id)
        return TroubleLogListResponse(items=[self._build_trouble_log_response(item) for item in items])

    def soft_delete_trouble_log(self, db: Session, *, user_id: UUID, trouble_log_id: UUID) -> TroubleLogResponse:
        self._ensure_user_exists(db, user_id)
        trouble_log = self.trouble_log_repository.get_by_id(db, trouble_log_id, user_id=user_id)
        if trouble_log is None or trouble_log.is_deleted:
            raise NotFoundError("Trouble log does not exist.")
        deleted = self.trouble_log_repository.soft_delete(db, trouble_log)
        db.commit()
        return self._build_trouble_log_response(deleted)

    def _ensure_user_exists(self, db: Session, user_id: UUID) -> None:
        if self.user_repository.get_by_id(db, user_id) is None:
            raise NotFoundError("User does not exist.")

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
