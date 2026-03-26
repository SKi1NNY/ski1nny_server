from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationService

router = APIRouter()


def get_recommendation_service() -> RecommendationService:
    return RecommendationService()


@router.post("", response_model=RecommendationResponse)
def recommend_products(
    payload: RecommendationRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: RecommendationService = Depends(get_recommendation_service),
) -> RecommendationResponse:
    return service.recommend_products(
        db,
        user_id=current_user.id,
        limit=payload.limit,
        skin_type=payload.skin_type,
        skin_concerns=payload.skin_concerns,
    )
