from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient

from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.repositories.user_repository import UserRepository


@pytest.fixture
def client(db_session) -> Generator[TestClient, None, None]:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_login_refresh_and_protected_profile_flow(client: TestClient):
    signup_response = client.post(
        "/api/v1/users/signup",
        json={"email": "auth@example.com", "password": "supersecret123"},
    )
    assert signup_response.status_code == 201

    login_response = client.post(
        "/api/v1/users/login",
        json={"email": "auth@example.com", "password": "supersecret123"},
    )
    assert login_response.status_code == 200
    tokens = login_response.json()
    assert tokens["token_type"] == "bearer"

    refresh_response = client.post(
        "/api/v1/users/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    assert refresh_response.json()["access_token"]

    access_token = tokens["access_token"]
    upsert_response = client.put(
        "/api/v1/users/me/profile",
        json={"skin_type": "SENSITIVE", "skin_concerns": ["redness"], "notes": "jwt-profile"},
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert upsert_response.status_code == 200

    profile_response = client.get(
        "/api/v1/users/me/profile",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert profile_response.status_code == 200
    assert profile_response.json()["skin_type"] == "SENSITIVE"

    invalid_refresh_response = client.post(
        "/api/v1/users/refresh",
        json={"refresh_token": access_token},
    )
    assert invalid_refresh_response.status_code == 401
    assert invalid_refresh_response.json()["error_code"] == "authentication_error"


def test_inactive_and_deleted_users_are_blocked(client: TestClient, db_session):
    repository = UserRepository()
    user = repository.create(db_session, email="inactive@example.com", password_hash="hashed")
    db_session.commit()

    repository.update_auth_state(db_session, user, is_active=False)
    db_session.commit()

    inactive_response = client.get(
        "/api/v1/users/me/profile",
        headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
    )
    assert inactive_response.status_code == 403
    assert inactive_response.json()["error_code"] == "permission_denied"

    repository.update_auth_state(db_session, user, is_active=True, is_deleted=True)
    db_session.commit()

    deleted_response = client.get(
        "/api/v1/users/me/profile",
        headers={"Authorization": f"Bearer {create_access_token(user.id)}"},
    )
    assert deleted_response.status_code == 403
    assert deleted_response.json()["error_code"] == "permission_denied"
