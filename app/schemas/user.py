from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.trouble_log import TroubleReactionType
from app.models.user import AvoidIngredientRegisteredType, SkinType


class UserSignupRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)


class UserResponse(BaseModel):
    id: UUID
    email: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpsertRequest(BaseModel):
    skin_type: SkinType
    skin_concerns: list[str] = Field(default_factory=list)
    notes: str | None = None


class AvoidIngredientCreateRequest(BaseModel):
    ingredient_id: UUID


class AvoidIngredientResponse(BaseModel):
    id: UUID
    ingredient_id: UUID
    inci_name: str
    registered_type: AvoidIngredientRegisteredType
    is_confirmed: bool
    created_at: datetime


class UserProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    skin_type: SkinType
    skin_concerns: list[str] = Field(default_factory=list)
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
    avoid_ingredients: list[AvoidIngredientResponse] = Field(default_factory=list)


class SuggestedAvoidIngredientResponse(BaseModel):
    ingredient_id: UUID
    inci_name: str
    occurrence_count: int
    message: str


class TroubleLogCreateRequest(BaseModel):
    product_id: UUID
    reaction_type: TroubleReactionType
    severity: int = Field(ge=1, le=5)
    memo: str | None = None


class TroubleLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    product_id: UUID
    reaction_type: TroubleReactionType
    severity: int
    memo: str | None = None
    is_deleted: bool
    logged_at: datetime
    ingredient_ids: list[UUID] = Field(default_factory=list)


class TroubleLogCreateResponse(BaseModel):
    trouble_log: TroubleLogResponse
    suggested_avoid_ingredients: list[SuggestedAvoidIngredientResponse] = Field(default_factory=list)


class TroubleLogListResponse(BaseModel):
    items: list[TroubleLogResponse] = Field(default_factory=list)
