from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient
from app.repositories.user_profile_repository import UserProfileRepository
from app.repositories.user_repository import UserRepository


def _create_user(db_session, email: str = "trouble-api@example.com"):
    return UserRepository().create(db_session, email=email, password_hash="hashed")


def _create_ingredient(db_session, inci_name: str):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def _create_product(db_session, ingredient_ids):
    product = Product(name="Recovery Cream", brand="Skinny", category="Cream")
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


def _create_trouble_log(client: TestClient, *, access_token_headers: dict[str, str], product_id, reaction_type: str, severity: int):
    return client.post(
        "/api/v1/users/me/trouble-logs",
        json={
            "product_id": str(product_id),
            "reaction_type": reaction_type,
            "severity": severity,
            "memo": "api-test",
        },
        headers=access_token_headers,
    )


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_confirm_trouble_log_suggestions_persists_auto_avoid_ingredients(client: TestClient, db_session):
    user = _create_user(db_session)
    ingredient_a = _create_ingredient(db_session, "Niacinamide")
    ingredient_b = _create_ingredient(db_session, "Retinol")
    product = _create_product(db_session, [ingredient_a.id, ingredient_b.id])
    headers = _auth_headers(user.id)

    first = _create_trouble_log(
        client,
        access_token_headers=headers,
        product_id=product.id,
        reaction_type="ACNE",
        severity=3,
    )
    second = _create_trouble_log(
        client,
        access_token_headers=headers,
        product_id=product.id,
        reaction_type="REDNESS",
        severity=4,
    )

    assert first.status_code == 201
    assert second.status_code == 201

    second_payload = second.json()
    trouble_log_id = second_payload["trouble_log"]["id"]
    suggested_ingredient_id = second_payload["suggested_avoid_ingredients"][0]["ingredient_id"]

    confirm_response = client.post(
        f"/api/v1/users/me/trouble-logs/{trouble_log_id}/confirm-avoid-ingredients",
        json={"ingredient_ids": [suggested_ingredient_id]},
        headers=headers,
    )

    assert confirm_response.status_code == 200
    payload = confirm_response.json()
    assert payload["trouble_log_id"] == trouble_log_id
    assert payload["confirmed_avoid_ingredients"][0]["ingredient_id"] == suggested_ingredient_id
    assert payload["confirmed_avoid_ingredients"][0]["registered_type"] == "AUTO"
    assert payload["confirmed_avoid_ingredients"][0]["is_confirmed"] is True

    avoid_items = UserProfileRepository().list_avoid_ingredients(db_session, user.id)
    assert len(avoid_items) == 1
    assert str(avoid_items[0].ingredient_id) == suggested_ingredient_id


def test_delete_trouble_log_endpoint_soft_deletes_and_hides_item(client: TestClient, db_session):
    user = _create_user(db_session, email="delete-api@example.com")
    ingredient = _create_ingredient(db_session, "Niacinamide")
    product = _create_product(db_session, [ingredient.id])
    headers = _auth_headers(user.id)

    created = _create_trouble_log(
        client,
        access_token_headers=headers,
        product_id=product.id,
        reaction_type="ACNE",
        severity=2,
    )
    trouble_log_id = created.json()["trouble_log"]["id"]

    delete_response = client.delete(
        f"/api/v1/users/me/trouble-logs/{trouble_log_id}",
        headers=headers,
    )
    assert delete_response.status_code == 204

    list_response = client.get("/api/v1/users/me/trouble-logs", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["items"] == []

    second_delete_response = client.delete(
        f"/api/v1/users/me/trouble-logs/{trouble_log_id}",
        headers=headers,
    )
    assert second_delete_response.status_code == 404
    assert second_delete_response.json()["error_code"] == "trouble_log_not_found"


def test_confirm_trouble_log_suggestions_rejects_invalid_ingredient(client: TestClient, db_session):
    user = _create_user(db_session, email="invalid-confirm-api@example.com")
    ingredient_a = _create_ingredient(db_session, "Niacinamide")
    ingredient_b = _create_ingredient(db_session, "Retinol")
    ingredient_c = _create_ingredient(db_session, "Glycerin")
    product = _create_product(db_session, [ingredient_a.id, ingredient_b.id])
    headers = _auth_headers(user.id)

    _create_trouble_log(
        client,
        access_token_headers=headers,
        product_id=product.id,
        reaction_type="ACNE",
        severity=3,
    )
    created = _create_trouble_log(
        client,
        access_token_headers=headers,
        product_id=product.id,
        reaction_type="REDNESS",
        severity=4,
    )
    trouble_log_id = created.json()["trouble_log"]["id"]

    confirm_response = client.post(
        f"/api/v1/users/me/trouble-logs/{trouble_log_id}/confirm-avoid-ingredients",
        json={"ingredient_ids": [str(ingredient_c.id)]},
        headers=headers,
    )

    assert confirm_response.status_code == 400
    assert confirm_response.json()["error_code"] == "invalid_avoid_ingredient_suggestion"
