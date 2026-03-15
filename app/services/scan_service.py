from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.ocr_client import OCRClient, OCRResult
from app.repositories.ingredient_repository import IngredientRepository
from app.repositories.scan_repository import ScanRepository
from app.schemas.product import ScanFallbackResponse, ScanRecognizedIngredientResponse, ScanResponse

CONFIDENCE_THRESHOLD = 0.80
TOKEN_SPLIT_PATTERN = re.compile(r"[\n,;/]+")
PAREN_CONTENT_PATTERN = re.compile(r"\([^)]*\)")
NON_LETTER_PATTERN = re.compile(r"[^A-Za-z가-힣\s-]")
MULTISPACE_PATTERN = re.compile(r"\s+")


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
        raw_tokens = self._tokenize(ocr_result.text)
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
                    raw_name=token,
                    normalized_name=token,
                    ingredient_id=None,
                    is_mapped=False,
                )
                for token in raw_tokens
            ],
            unmapped_ingredients=raw_tokens,
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
