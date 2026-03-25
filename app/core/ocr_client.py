from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Protocol
from typing import Any

from app.core.config import settings
from app.core.exceptions import ExternalServiceError


@dataclass(slots=True)
class OCRResult:
    text: str
    confidence_score: float | None


class OCRClient(Protocol):
    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        ...


class LocalTextOCRClient:
    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        # Local development fallback: accept UTF-8 text payloads as OCR input.
        try:
            text = image_bytes.decode("utf-8").strip()
        except UnicodeDecodeError as exc:
            raise ExternalServiceError(
                "OCR provider is not configured for binary image processing in the current environment.",
                detail={"provider": "local-text", "filename": filename},
            ) from exc

        confidence_score = 0.99 if text else 0.0
        return OCRResult(text=text, confidence_score=confidence_score)


class GoogleCloudVisionOCRClient:
    def __init__(self, *, client: Any | None = None, timeout: float | None = None) -> None:
        self._client = client
        self._timeout = timeout or settings.ocr_timeout_seconds

    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        client = self._client or self._build_client()
        try:
            response = client.document_text_detection(
                image=self._build_image(image_bytes),
                timeout=self._timeout,
            )
        except ExternalServiceError:
            raise
        except Exception as exc:
            raise ExternalServiceError(
                "Google Cloud Vision OCR request failed.",
                detail={"provider": "google-cloud-vision", "filename": filename},
            ) from exc

        error_message = getattr(getattr(response, "error", None), "message", "")
        if error_message:
            raise ExternalServiceError(
                "Google Cloud Vision OCR request failed.",
                detail={
                    "provider": "google-cloud-vision",
                    "filename": filename,
                    "message": error_message,
                },
            )

        return OCRResult(
            text=self._extract_text_from_response(response),
            confidence_score=self._extract_confidence_score(response),
        )

    def _build_client(self) -> Any:
        vision = self._import_vision_module()
        credentials = self._load_credentials()
        if credentials is None:
            return vision.ImageAnnotatorClient(transport=settings.ocr_transport)
        return vision.ImageAnnotatorClient(
            credentials=credentials,
            transport=settings.ocr_transport,
        )

    def _build_image(self, image_bytes: bytes) -> Any:
        vision = self._import_vision_module()
        return vision.Image(content=image_bytes)

    def _extract_text_from_response(self, response: Any) -> str:
        full_text_annotation = getattr(response, "full_text_annotation", None)
        full_text = getattr(full_text_annotation, "text", None)
        if full_text:
            return full_text.strip()

        text_annotations = getattr(response, "text_annotations", None) or []
        if text_annotations:
            return getattr(text_annotations[0], "description", "").strip()
        return ""

    def _extract_confidence_score(self, response: Any) -> float | None:
        full_text_annotation = getattr(response, "full_text_annotation", None)
        if full_text_annotation is None:
            return None

        word_confidences: list[float] = []
        for page in getattr(full_text_annotation, "pages", []):
            for block in getattr(page, "blocks", []):
                for paragraph in getattr(block, "paragraphs", []):
                    for word in getattr(paragraph, "words", []):
                        confidence = getattr(word, "confidence", None)
                        if confidence is not None:
                            word_confidences.append(float(confidence))

        if word_confidences:
            return float(fmean(word_confidences))
        return None

    def _load_credentials(self) -> Any | None:
        credentials_path = settings.google_application_credentials
        if not credentials_path:
            return None

        try:
            from google.oauth2 import service_account
        except ImportError as exc:  # pragma: no cover - guarded by dependency installation
            raise ExternalServiceError(
                "Google Cloud Vision dependencies are not installed.",
                detail={"provider": "google-cloud-vision"},
            ) from exc

        try:
            return service_account.Credentials.from_service_account_file(credentials_path)
        except Exception as exc:
            raise ExternalServiceError(
                "Failed to load Google Cloud service account credentials.",
                detail={
                    "provider": "google-cloud-vision",
                    "credentials_path": credentials_path,
                },
            ) from exc

    def _import_vision_module(self) -> Any:
        try:
            from google.cloud import vision
        except ImportError as exc:  # pragma: no cover - guarded by dependency installation
            raise ExternalServiceError(
                "Google Cloud Vision dependencies are not installed.",
                detail={"provider": "google-cloud-vision"},
            ) from exc
        return vision


def get_ocr_client() -> OCRClient:
    if settings.ocr_provider == "google-cloud-vision":
        return GoogleCloudVisionOCRClient()
    return LocalTextOCRClient()
