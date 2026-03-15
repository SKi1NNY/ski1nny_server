from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.ocr_client import OCRClient, OCRResult
from app.models.ingredient import Ingredient
from app.repositories.ingredient_repository import IngredientRepository
from app.repositories.scan_repository import ScanRepository
from app.schemas.product import ScanFallbackResponse, ScanRecognizedIngredientResponse, ScanResponse

CONFIDENCE_THRESHOLD = 0.80
TOKEN_SPLIT_PATTERN = re.compile(r"[\n,;/]+")
PAREN_CONTENT_PATTERN = re.compile(r"\([^)]*\)")
NON_LETTER_PATTERN = re.compile(r"[^A-Za-z가-힣\s-]")
MULTISPACE_PATTERN = re.compile(r"\s+")


@dataclass(slots=True)
class NormalizedToken:
    raw_name: str
    normalized_name: str
    ingredient: Ingredient | None

    @property
    def is_mapped(self) -> bool:
        return self.ingredient is not None


class ScanService:
    def __init__(
        self,
        ocr_client: OCRClient,
        ingredient_repository: IngredientRepository | None = None,
        scan_repository: ScanRepository | None = None,
    ) -> None:
        self.ocr_client = ocr_client
        self.ingredient_repository = ingredient_repository or IngredientRepository()
        self.scan_repository = scan_repository or ScanRepository()

    def scan_ingredients(
        self,
        db: Session,
        *,
        user_id: UUID,
        image_bytes: bytes,
        filename: str | None = None,
    ) -> ScanResponse:
        if not image_bytes:
            raise ValidationError("A non-empty file is required for OCR scanning.")

        ocr_result = self._extract_text(image_bytes=image_bytes, filename=filename)
        normalized_tokens = self._normalize_tokens(db, ocr_result.text)
        fallback = None
        if (ocr_result.confidence_score or 0.0) < CONFIDENCE_THRESHOLD:
            fallback = ScanFallbackResponse(
                requires_manual_input=True,
                reason="OCR confidence is below the automatic parsing threshold.",
            )

        return ScanResponse(
            scan_id=UUID(int=0),
            product_id=None,
            raw_ocr_text=ocr_result.text,
            confidence_score=ocr_result.confidence_score,
            recognized_ingredients=[
                ScanRecognizedIngredientResponse(
                    raw_name=token.raw_name,
                    normalized_name=token.normalized_name,
                    ingredient_id=token.ingredient.id if token.ingredient else None,
                    is_mapped=token.is_mapped,
                )
                for token in normalized_tokens
            ],
            unmapped_ingredients=[
                token.normalized_name
                for token in normalized_tokens
                if not token.is_mapped
            ],
            fallback=fallback,
        )

    def _extract_text(self, *, image_bytes: bytes, filename: str | None) -> OCRResult:
        try:
            return self.ocr_client.extract_text(image_bytes, filename)
        except ExternalServiceError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalServiceError("Failed to process OCR request.") from exc

    def _tokenize(self, raw_text: str) -> list[str]:
        cleaned = PAREN_CONTENT_PATTERN.sub(" ", raw_text)
        tokens: list[str] = []
        for chunk in TOKEN_SPLIT_PATTERN.split(cleaned):
            token = NON_LETTER_PATTERN.sub(" ", chunk)
            token = MULTISPACE_PATTERN.sub(" ", token).strip(" -")
            if token:
                tokens.append(token)
        return tokens

    def _normalize_tokens(self, db: Session, raw_text: str) -> list[NormalizedToken]:
        raw_tokens = self._tokenize(raw_text)
        if not raw_tokens:
            return []

        direct_ingredients = self.ingredient_repository.list_by_inci_names(db, raw_tokens)
        direct_map = {ingredient.inci_name.strip().lower(): ingredient for ingredient in direct_ingredients}
        alias_map = self.ingredient_repository.map_aliases(db, raw_tokens)

        normalized_tokens: list[NormalizedToken] = []
        seen_normalized_names: set[str] = set()
        for raw_token in raw_tokens:
            normalized_key = raw_token.strip().lower()
            ingredient = direct_map.get(normalized_key) or alias_map.get(normalized_key)
            normalized_name = ingredient.inci_name if ingredient else raw_token
            dedupe_key = normalized_name.strip().lower()
            if dedupe_key in seen_normalized_names:
                continue
            seen_normalized_names.add(dedupe_key)
            normalized_tokens.append(
                NormalizedToken(
                    raw_name=raw_token,
                    normalized_name=normalized_name,
                    ingredient=ingredient,
                )
            )
        return normalized_tokens
