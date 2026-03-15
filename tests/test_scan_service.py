from __future__ import annotations

from app.core.ocr_client import OCRResult
from app.models.ingredient import Ingredient, IngredientAlias
from app.models.user import User
from app.services.scan_service import ScanService


class FakeOCRClient:
    def __init__(self, text: str, confidence_score: float) -> None:
        self.text = text
        self.confidence_score = confidence_score

    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        return OCRResult(text=self.text, confidence_score=self.confidence_score)


def _create_user(db_session):
    user = User(email="scan-service@example.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    return user


def _create_ingredient(db_session, inci_name: str, alias_name: str | None = None):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()

    if alias_name:
        db_session.add(
            IngredientAlias(
                ingredient_id=ingredient.id,
                alias_name=alias_name,
                language="ko",
            )
        )
        db_session.flush()

    return ingredient


def test_scan_service_maps_aliases_and_preserves_raw_text(db_session):
    user = _create_user(db_session)
    niacinamide = _create_ingredient(db_session, "Niacinamide", alias_name="나이아신아마이드")
    _create_ingredient(db_session, "Retinol")

    service = ScanService(FakeOCRClient("나이아신아마이드, Unknown 123, Retinol (0.1%)", 0.95))

    result = service.scan_ingredients(
        db_session,
        user_id=user.id,
        image_bytes=b"fake-image-bytes",
        filename="scan.txt",
    )

    assert result.raw_ocr_text == "나이아신아마이드, Unknown 123, Retinol (0.1%)"
    assert result.fallback is None
    assert [item.normalized_name for item in result.recognized_ingredients] == [
        "Niacinamide",
        "Unknown",
        "Retinol",
    ]
    assert result.recognized_ingredients[0].ingredient_id == niacinamide.id
    assert result.unmapped_ingredients == ["Unknown"]


def test_scan_service_returns_fallback_for_low_confidence(db_session):
    user = _create_user(db_session)
    _create_ingredient(db_session, "Niacinamide")

    service = ScanService(FakeOCRClient("Niacinamide", 0.42))

    result = service.scan_ingredients(
        db_session,
        user_id=user.id,
        image_bytes=b"fake-image-bytes",
        filename="scan.txt",
    )

    assert result.fallback is not None
    assert result.fallback.requires_manual_input is True
    assert result.confidence_score == 0.42
    assert result.recognized_ingredients[0].normalized_name == "Niacinamide"
