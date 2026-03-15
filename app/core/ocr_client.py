from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.core.config import settings
from app.core.exceptions import ExternalServiceError


@dataclass(slots=True)
class OCRResult:
    text: str
    confidence_score: float | None


class OCRClient(Protocol):
    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        ...


class GoogleMLKitOCRClient:
    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        # Local development fallback: accept UTF-8 text payloads as OCR input.
        try:
            text = image_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ExternalServiceError(
                "OCR provider is not configured for binary image processing in the current environment.",
                detail={"provider": settings.ocr_provider, "filename": filename},
            ) from exc

        confidence_score = 0.99 if text else 0.0
        return OCRResult(text=text, confidence_score=confidence_score)


def get_ocr_client() -> OCRClient:
    return GoogleMLKitOCRClient()
