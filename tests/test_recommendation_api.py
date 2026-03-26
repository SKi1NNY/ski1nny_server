from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient
from app.models.trouble_log import TroubleReactionType
from app.models.user import SkinType
from app.repositories.user_repository import UserRepository
from app.services.trouble_log_service import TroubleLogService
from app.services.user_profile_service import UserProfileService


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_user(db_session, email: str = "recommend-api@example.com"):
    return UserRepository().create(db_session, email=email, password_hash="hashed")


def _create_ingredient(db_session, inci_name: str, *, category: str):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name, category=category)
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def _create_product(db_session, name: str, ingredient_ids):
    product = Product(name=name, brand="Skinny", category="Serum")
    db_session.add(product)
    db_session.flush()
    for order, ingredient_id in enumerate(ingredient_ids, start=1):
        db_session.add(
            ProductIngredient(
                product_id=product.id,
                ingredient_id=ingredient_id,
                ingredient_order=order,
            )
        )
    db_session.flush()
    return product


def _auth_headers(user_id) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


def test_recommendation_endpoint_returns_ranked_products(client: TestClient, db_session):
    user = _create_user(db_session)
    UserProfileService().upsert_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="api-profile",
    )

    centella = _create_ingredient(db_session, "Centella Asiatica Extract", category="Extract")
    glycerin = _create_ingredient(db_session, "Glycerin", category="Humectant")
    fragrance = _create_ingredient(db_session, "Fragrance", category="Additive")
    niacinamide = _create_ingredient(db_session, "Niacinamide", category="Brightening")

    soothing = _create_product(db_session, "Calm Ampoule", [centella.id, glycerin.id])
    _create_product(db_session, "Perfumed Mist", [centella.id, fragrance.id])
    trouble_source = _create_product(db_session, "Breakout Serum", [niacinamide.id])
    risky = _create_product(db_session, "Tone Repair Serum", [centella.id, niacinamide.id])

    trouble_service = TroubleLogService()
    trouble_service.create_trouble_log(
        db_session,
        user_id=user.id,
        product_id=trouble_source.id,
        reaction_type=TroubleReactionType.ACNE,
        severity=3,
        memo="first trouble",
    )
    trouble_service.create_trouble_log(
        db_session,
        user_id=user.id,
        product_id=trouble_source.id,
        reaction_type=TroubleReactionType.REDNESS,
        severity=4,
        memo="second trouble",
    )

    response = client.post(
        "/api/v1/recommendations",
        json={"limit": 5},
        headers=_auth_headers(user.id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["product_id"] for item in payload["recommendations"]] == [str(soothing.id), str(risky.id)]
    assert payload["fallback"] is None
    assert any(warning["type"] == "trouble_history" for warning in payload["recommendations"][1]["warnings"])


def test_recommendation_endpoint_returns_fallback_when_catalog_is_empty(client: TestClient, db_session):
    user = _create_user(db_session, email="recommend-empty@example.com")

    response = client.post(
        "/api/v1/recommendations",
        json={"limit": 3, "skin_type": "SENSITIVE", "skin_concerns": ["redness"]},
        headers=_auth_headers(user.id),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["recommendations"] == []
    assert payload["fallback"]["message"] == "등록된 제품이 아직 없습니다."
