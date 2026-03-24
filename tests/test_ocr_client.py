from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.exceptions import ExternalServiceError
from app.core.ocr_client import GoogleCloudVisionOCRClient, LocalTextOCRClient, get_ocr_client


class FakeVisionClient:
    def __init__(self, response) -> None:
        self.response = response
        self.calls: list[dict] = []

    def document_text_detection(self, *, image, timeout):
        self.calls.append({"image": image, "timeout": timeout})
        return self.response


def _build_vision_response(*, text: str, confidences: list[float], error_message: str = ""):
    words = [SimpleNamespace(confidence=confidence) for confidence in confidences]
    paragraph = SimpleNamespace(words=words)
    block = SimpleNamespace(paragraphs=[paragraph])
    page = SimpleNamespace(blocks=[block])
    full_text_annotation = SimpleNamespace(text=text, pages=[page])
    return SimpleNamespace(
        full_text_annotation=full_text_annotation,
        text_annotations=[],
        error=SimpleNamespace(message=error_message),
    )


def test_get_ocr_client_returns_local_provider_by_default(monkeypatch):
    monkeypatch.setattr("app.core.ocr_client.settings.ocr_provider", "local-text")

    client = get_ocr_client()

    assert isinstance(client, LocalTextOCRClient)


def test_get_ocr_client_returns_google_provider(monkeypatch):
    monkeypatch.setattr("app.core.ocr_client.settings.ocr_provider", "google-cloud-vision")

    client = get_ocr_client()

    assert isinstance(client, GoogleCloudVisionOCRClient)


def test_local_text_ocr_client_decodes_utf8_payload():
    client = LocalTextOCRClient()

    result = client.extract_text("Niacinamide, Retinol".encode("utf-8"), filename="scan.txt")

    assert result.text == "Niacinamide, Retinol"
    assert result.confidence_score == 0.99


def test_local_text_ocr_client_rejects_binary_payload():
    client = LocalTextOCRClient()

    with pytest.raises(ExternalServiceError) as exc_info:
        client.extract_text(b"\xff\xd8\xff", filename="scan.jpg")

    assert exc_info.value.detail["provider"] == "local-text"
    assert exc_info.value.detail["filename"] == "scan.jpg"


def test_google_cloud_vision_client_extracts_text_and_confidence(monkeypatch):
    response = _build_vision_response(text="Niacinamide\nRetinol", confidences=[0.92, 0.78])
    fake_client = FakeVisionClient(response)
    client = GoogleCloudVisionOCRClient(client=fake_client, timeout=12.5)
    monkeypatch.setattr(client, "_build_image", lambda image_bytes: {"content": image_bytes})

    result = client.extract_text(b"binary-image", filename="scan.png")

    assert result.text == "Niacinamide\nRetinol"
    assert result.confidence_score == pytest.approx(0.85)
    assert fake_client.calls == [{"image": {"content": b"binary-image"}, "timeout": 12.5}]


def test_google_cloud_vision_client_raises_external_service_error_on_provider_error(monkeypatch):
    response = _build_vision_response(
        text="",
        confidences=[],
        error_message="quota exceeded",
    )
    fake_client = FakeVisionClient(response)
    client = GoogleCloudVisionOCRClient(client=fake_client)
    monkeypatch.setattr(client, "_build_image", lambda image_bytes: {"content": image_bytes})

    with pytest.raises(ExternalServiceError) as exc_info:
        client.extract_text(b"binary-image", filename="scan.png")

    assert exc_info.value.detail["provider"] == "google-cloud-vision"
    assert exc_info.value.detail["message"] == "quota exceeded"
