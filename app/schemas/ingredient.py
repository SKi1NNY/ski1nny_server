from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.ingredient import ConflictSeverity


class IngredientAliasResponse(BaseModel):
    alias_name: str
    language: str

    model_config = ConfigDict(from_attributes=True)


class IngredientResponse(BaseModel):
    id: UUID
    inci_name: str
    korean_name: str | None = None
    category: str | None = None
    description: str | None = None
    aliases: list[IngredientAliasResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class IngredientSearchItemResponse(BaseModel):
    id: UUID
    inci_name: str
    korean_name: str | None = None
    category: str | None = None
    matched_alias: str | None = None


class IngredientSearchResponse(BaseModel):
    items: list[IngredientSearchItemResponse] = Field(default_factory=list)


class IngredientValidationRequest(BaseModel):
    ingredient_ids: list[UUID] = Field(default_factory=list)
    ingredient_names: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_any_ingredient_input(self) -> "IngredientValidationRequest":
        if not self.ingredient_ids and not self.ingredient_names:
            raise ValueError("At least one ingredient identifier or name is required.")
        return self


class IngredientConflictResponse(BaseModel):
    ingredients: list[str]
    reason: str
    severity: ConflictSeverity
    layer: int = 1


class IngredientPersonalWarningResponse(BaseModel):
    ingredient: str
    reason: str
    layer: int = 2


class IngredientValidationResponse(BaseModel):
    is_safe: bool
    severity: ConflictSeverity | None = None
    conflicts: list[IngredientConflictResponse] = Field(default_factory=list)
    personal_warnings: list[IngredientPersonalWarningResponse] = Field(default_factory=list)


class IngredientExplainSourceResponse(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    source: str
    excerpt: str


class IngredientExplainResponse(BaseModel):
    ingredient_id: UUID
    inci_name: str
    korean_name: str | None = None
    is_grounded: bool
    summary: str
    sources: list[IngredientExplainSourceResponse] = Field(default_factory=list)
