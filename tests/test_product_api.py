from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
import pytest

from app.api.product import get_scan_service
from app.core.database import get_db
from app.core.ocr_client import OCRResult
from app.main import app
from app.models.ingredient import ConflictSeverity, Ingredient, IngredientConflict
from app.models.user import User
from app.services.scan_service import ScanService


class FakeOCRClient:
    def __init__(self, text: str, confidence_score: float) -> None:
        self.text = text
        self.confidence_score = confidence_score

    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        return OCRResult(text=self.text, confidence_score=self.confidence_score)


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    def override_get_scan_service() -> ScanService:
        return ScanService(ocr_client=FakeOCRClient("Niacinamide, Retinol", 0.97))

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_scan_service] = override_get_scan_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(db_session) -> User:
    user = User(email="product-api@example.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    return user


def _create_ingredient(db_session, inci_name: str) -> Ingredient:
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def _create_conflict(db_session, ingredient_a: Ingredient, ingredient_b: Ingredient) -> None:
    ordered = sorted([ingredient_a, ingredient_b], key=lambda item: item.id.int)
    db_session.add(
        IngredientConflict(
            ingredient_a_id=ordered[0].id,
            ingredient_b_id=ordered[1].id,
            severity=ConflictSeverity.HIGH,
            reason="These ingredients should not be combined.",
        )
    )
    db_session.flush()


def test_scan_product_endpoint_returns_recognized_ingredients_and_validation(client: TestClient, db_session) -> None:
    user = _create_user(db_session)
    niacinamide = _create_ingredient(db_session, "Niacinamide")
    retinol = _create_ingredient(db_session, "Retinol")
    _create_conflict(db_session, niacinamide, retinol)

    response = client.post(
        "/api/v1/products/scan",
        data={"user_id": str(user.id)},
        files={"file": ("scan.txt", b"fake-image", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["raw_ocr_text"] == "Niacinamide, Retinol"
    assert [item["normalized_name"] for item in payload["recognized_ingredients"]] == [
        "Niacinamide",
        "Retinol",
    ]
    assert payload["validation"]["is_safe"] is False
    assert len(payload["validation"]["conflicts"]) == 1
