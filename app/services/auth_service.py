from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import (
    DeletedUserError,
    DuplicateEmailError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidRefreshTokenError,
    UserNotFoundError,
)
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token, hash_password, verify_password
from app.repositories.user_repository import UserRepository
from app.schemas.user import TokenResponse, UserResponse


class AuthService:
    def __init__(self, user_repository: UserRepository | None = None) -> None:
        self.user_repository = user_repository or UserRepository()

    def signup(self, db: Session, *, email: str, password: str) -> UserResponse:
        if self.user_repository.get_by_email(db, email) is not None:
            raise DuplicateEmailError()

        user = self.user_repository.create(
            db,
            email=email,
            password_hash=hash_password(password),
        )
        db.commit()
        db.refresh(user)
        return UserResponse.model_validate(user)

    def login(self, db: Session, *, email: str, password: str) -> TokenResponse:
        user = self.user_repository.get_by_email(db, email)
        if user is None or not verify_password(password, user.password_hash):
            raise InvalidCredentialsError()
        self._ensure_user_is_available(user.is_active, user.is_deleted)
        return self._build_token_response(user.id)

    def refresh(self, db: Session, *, refresh_token: str) -> TokenResponse:
        try:
            token_payload = decode_refresh_token(refresh_token)
        except Exception as exc:
            raise InvalidRefreshTokenError() from exc

        user = self.user_repository.get_by_id(db, UUID(str(token_payload["sub"])))
        if user is None:
            raise UserNotFoundError("Authenticated user does not exist.")
        self._ensure_user_is_available(user.is_active, user.is_deleted)
        return self._build_token_response(user.id)

    def _ensure_user_is_available(self, is_active: bool, is_deleted: bool) -> None:
        if not is_active:
            raise InactiveUserError()
        if is_deleted:
            raise DeletedUserError()

    def _build_token_response(self, user_id: UUID) -> TokenResponse:
        return TokenResponse(
            access_token=create_access_token(user_id),
            refresh_token=create_refresh_token(user_id),
        )
