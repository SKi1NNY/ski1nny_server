from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from app.models.user import SkinType


class RecommendationRequest(BaseModel):
    limit: int = Field(default=5, ge=1, le=20)
    skin_type: SkinType | None = None
    skin_concerns: list[str] = Field(default_factory=list)


class RecommendationWarningResponse(BaseModel):
    type: str
    message: str


class RecommendationItemResponse(BaseModel):
    product_id: UUID
    product_name: str
    brand: str
    category: str | None = None
    score: int
    reason: str | None = None
    warnings: list[RecommendationWarningResponse] = Field(default_factory=list)


class RecommendationFallbackResponse(BaseModel):
    message: str
    suggestion: str | None = None


class RecommendationResponse(BaseModel):
    recommendations: list[RecommendationItemResponse] = Field(default_factory=list)
    fallback: RecommendationFallbackResponse | None = None
