from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
import pytest

from app.core.database import get_db
from app.main import app
from app.models.ingredient import ConflictSeverity, Ingredient, IngredientAlias, IngredientConflict


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _create_ingredient(db_session, inci_name: str, *, korean_name: str | None = None, alias_name: str | None = None) -> Ingredient:
    ingredient = Ingredient(
        inci_name=inci_name,
        korean_name=korean_name or inci_name,
        category="Active",
    )
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


def _create_conflict(
    db_session,
    ingredient_a: Ingredient,
    ingredient_b: Ingredient,
    *,
    severity: ConflictSeverity = ConflictSeverity.HIGH,
    reason: str = "같이 쓰면 자극 위험이 있습니다.",
) -> None:
    ordered = sorted([ingredient_a, ingredient_b], key=lambda item: item.id.int)
    db_session.add(
        IngredientConflict(
            ingredient_a_id=ordered[0].id,
            ingredient_b_id=ordered[1].id,
            severity=severity,
            reason=reason,
        )
    )
    db_session.flush()


def test_get_ingredient_endpoint_returns_detail(client: TestClient, db_session) -> None:
    ingredient = _create_ingredient(
        db_session,
        "Niacinamide",
        korean_name="나이아신아마이드",
        alias_name="비타민B3",
    )

    response = client.get(f"/api/v1/ingredients/{ingredient.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["inci_name"] == "Niacinamide"
    assert payload["korean_name"] == "나이아신아마이드"
    assert payload["aliases"][0]["alias_name"] == "비타민B3"


def test_search_ingredients_endpoint_returns_alias_match(client: TestClient, db_session) -> None:
    _create_ingredient(
        db_session,
        "Niacinamide",
        korean_name="나이아신아마이드",
        alias_name="나이아신아마이드",
    )

    response = client.get("/api/v1/ingredients/search", params={"query": "나이아신"})

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["inci_name"] == "Niacinamide"
    assert payload["items"][0]["matched_alias"] == "나이아신아마이드"


def test_validate_ingredients_endpoint_returns_conflicts(client: TestClient, db_session) -> None:
    niacinamide = _create_ingredient(db_session, "Niacinamide")
    retinol = _create_ingredient(db_session, "Retinol")
    _create_conflict(db_session, niacinamide, retinol)

    response = client.post(
        "/api/v1/ingredients/validate",
        json={"ingredient_names": ["Niacinamide", "Retinol"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_safe"] is False
    assert payload["severity"] == "HIGH"
    assert len(payload["conflicts"]) == 1


def test_explain_ingredient_endpoint_returns_grounded_summary(client: TestClient, db_session) -> None:
    ingredient = _create_ingredient(
        db_session,
        "Niacinamide",
        korean_name="나이아신아마이드",
    )

    response = client.get(f"/api/v1/ingredients/{ingredient.id}/explain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_grounded"] is True
    assert payload["inci_name"] == "Niacinamide"
    assert "피부 장벽" in payload["summary"]
    assert payload["sources"][0]["source"].startswith("knowledge_base/ingredients/niacinamide.md#")


def test_explain_ingredient_endpoint_returns_ungrounded_response_when_kb_is_missing(
    client: TestClient,
    db_session,
) -> None:
    ingredient = _create_ingredient(
        db_session,
        "Imaginary Ingredient",
        korean_name="가상성분",
    )

    response = client.get(f"/api/v1/ingredients/{ingredient.id}/explain")

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_grounded"] is False
    assert payload["summary"] == "해당 성분에 대한 정보가 없습니다."
    assert payload["sources"] == []
