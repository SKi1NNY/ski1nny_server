from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.ingredient import IngredientValidationResponse


class ProductIngredientCreateItem(BaseModel):
    ingredient_id: UUID
    ingredient_order: int = Field(ge=1)


class ProductCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    brand: str = Field(min_length=1, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, max_length=50)
    ingredients: list[ProductIngredientCreateItem] = Field(default_factory=list)


class ProductIngredientResponse(BaseModel):
    ingredient_id: UUID
    inci_name: str
    korean_name: str | None = None
    category: str | None = None
    ingredient_order: int


class ProductResponse(BaseModel):
    id: UUID
    name: str
    brand: str
    category: str | None = None
    barcode: str | None = None
    ingredients: list[ProductIngredientResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ScanRequest(BaseModel):
    user_id: UUID


class ScanRecognizedIngredientResponse(BaseModel):
    raw_name: str
    normalized_name: str
    ingredient_id: UUID | None = None
    is_mapped: bool


class ScanFallbackResponse(BaseModel):
    requires_manual_input: bool
    reason: str


class ScanResponse(BaseModel):
    scan_id: UUID
    product_id: UUID | None = None
    raw_ocr_text: str
    confidence_score: float | None = None
    recognized_ingredients: list[ScanRecognizedIngredientResponse] = Field(default_factory=list)
    unmapped_ingredients: list[str] = Field(default_factory=list)
    fallback: ScanFallbackResponse | None = None
    validation: IngredientValidationResponse | None = None
