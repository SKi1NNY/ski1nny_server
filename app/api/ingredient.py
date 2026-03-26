from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.ingredient import (
    IngredientExplainResponse,
    IngredientResponse,
    IngredientSearchResponse,
    IngredientValidationRequest,
    IngredientValidationResponse,
)
from app.services.ingredient_service import IngredientService

router = APIRouter()


def get_ingredient_service() -> IngredientService:
    return IngredientService()


@router.get("/search", response_model=IngredientSearchResponse)
def search_ingredients(
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
    service: IngredientService = Depends(get_ingredient_service),
) -> IngredientSearchResponse:
    return service.search_ingredients(db, query=query, limit=limit)


@router.post("/validate", response_model=IngredientValidationResponse)
def validate_ingredients(
    payload: IngredientValidationRequest,
    db: Session = Depends(get_db),
    service: IngredientService = Depends(get_ingredient_service),
) -> IngredientValidationResponse:
    return service.validate_ingredients(
        db,
        ingredient_ids=payload.ingredient_ids,
        ingredient_names=payload.ingredient_names,
    )


@router.get("/{ingredient_id}", response_model=IngredientResponse)
def get_ingredient(
    ingredient_id: UUID,
    db: Session = Depends(get_db),
    service: IngredientService = Depends(get_ingredient_service),
) -> IngredientResponse:
    return service.get_ingredient(db, ingredient_id=ingredient_id)


@router.get("/{ingredient_id}/explain", response_model=IngredientExplainResponse)
def explain_ingredient(
    ingredient_id: UUID,
    db: Session = Depends(get_db),
    service: IngredientService = Depends(get_ingredient_service),
) -> IngredientExplainResponse:
    return service.explain_ingredient(db, ingredient_id=ingredient_id)
