from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import IngredientNotFoundError
from app.repositories.ingredient_repository import IngredientRepository
from app.schemas.ingredient import (
    IngredientExplainResponse,
    IngredientResponse,
    IngredientSearchItemResponse,
    IngredientSearchResponse,
    IngredientValidationResponse,
)
from app.services.rag_service import RAGService
from app.services.validation_service import ValidationService


class IngredientService:
    def __init__(
        self,
        *,
        repository: IngredientRepository | None = None,
        validation_service: ValidationService | None = None,
        rag_service: RAGService | None = None,
    ) -> None:
        self.repository = repository or IngredientRepository()
        self.validation_service = validation_service or ValidationService()
        self.rag_service = rag_service or RAGService()

    def get_ingredient(self, db: Session, *, ingredient_id: UUID) -> IngredientResponse:
        ingredient = self.repository.get_by_id(db, ingredient_id)
        if ingredient is None:
            raise IngredientNotFoundError()
        return IngredientResponse.model_validate(ingredient)

    def search_ingredients(
        self,
        db: Session,
        *,
        query: str,
        limit: int = 20,
    ) -> IngredientSearchResponse:
        hits = self.repository.search(db, query, limit=limit)
        return IngredientSearchResponse(
            items=[
                IngredientSearchItemResponse(
                    id=hit.ingredient.id,
                    inci_name=hit.ingredient.inci_name,
                    korean_name=hit.ingredient.korean_name,
                    category=hit.ingredient.category,
                    matched_alias=hit.matched_alias,
                )
                for hit in hits
            ]
        )

    def validate_ingredients(
        self,
        db: Session,
        *,
        ingredient_ids: list[UUID] | None = None,
        ingredient_names: list[str] | None = None,
    ) -> IngredientValidationResponse:
        return self.validation_service.validate_ingredients(
            db,
            ingredient_ids=ingredient_ids or [],
            ingredient_names=ingredient_names or [],
        )

    def explain_ingredient(self, db: Session, *, ingredient_id: UUID) -> IngredientExplainResponse:
        ingredient = self.repository.get_by_id(db, ingredient_id)
        if ingredient is None:
            raise IngredientNotFoundError()

        explanation = self.rag_service.explain_ingredient(ingredient)
        return IngredientExplainResponse(
            ingredient_id=ingredient.id,
            inci_name=ingredient.inci_name,
            korean_name=ingredient.korean_name,
            is_grounded=explanation.is_grounded,
            summary=explanation.summary,
            sources=self.rag_service.build_source_responses(
                ingredient_id=ingredient.id,
                sources=explanation.sources,
            ),
        )
