from __future__ import annotations

from collections.abc import Generator

from fastapi.testclient import TestClient
import pytest

from app.core.database import get_db
from app.main import app


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_authentication_error_uses_global_error_format(client: TestClient):
    response = client.get("/api/v1/users/me/profile")

    assert response.status_code == 401
    assert response.json() == {
        "error_code": "authentication_error",
        "message": "Authentication credentials were not provided.",
        "detail": {},
    }


def test_conflict_error_uses_global_error_format(client: TestClient):
    first_response = client.post(
        "/api/v1/users/signup",
        json={"email": "duplicate@example.com", "password": "supersecret123"},
    )
    assert first_response.status_code == 201

    duplicate_response = client.post(
        "/api/v1/users/signup",
        json={"email": "duplicate@example.com", "password": "supersecret123"},
    )

    assert duplicate_response.status_code == 409
    assert duplicate_response.json() == {
        "error_code": "conflict",
        "message": "Email already exists.",
        "detail": {},
    }


def test_request_validation_error_uses_global_error_format(client: TestClient):
    response = client.post(
        "/api/v1/users/signup",
        json={"email": "broken@example.com", "password": "123"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["error_code"] == "request_validation_error"
    assert payload["message"] == "The request payload is invalid."
    assert "errors" in payload["detail"]
