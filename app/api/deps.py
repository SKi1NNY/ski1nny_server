from __future__ import annotations

from uuid import UUID

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import AuthenticationError, DeletedUserError, InactiveUserError, UserNotFoundError
from app.core.security import TokenDecodeError, decode_access_token
from app.repositories.user_repository import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
    repository: UserRepository = Depends(get_user_repository),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Authentication credentials were not provided.")

    try:
        payload = decode_access_token(credentials.credentials)
    except TokenDecodeError as exc:
        raise AuthenticationError(str(exc)) from exc

    user_id = UUID(str(payload["sub"]))
    user = repository.get_by_id(db, user_id)
    if user is None:
        raise UserNotFoundError("Authenticated user does not exist.")
    return user


def get_current_active_user(current_user=Depends(get_current_user)):
    if not current_user.is_active:
        raise InactiveUserError()
    if current_user.is_deleted:
        raise DeletedUserError()
    return current_user
