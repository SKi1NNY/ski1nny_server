from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.ocr_client import OCRClient
from app.repositories.ingredient_repository import IngredientRepository
from app.repositories.scan_repository import ScanRepository
from app.schemas.product import ScanResponse


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

        raise NotImplementedError("Scan OCR flow will be implemented in a follow-up commit.")
