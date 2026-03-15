from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config import settings


ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class TokenDecodeError(Exception):
    pass


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"{base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        encoded_salt, encoded_digest = password_hash.split("$", maxsplit=1)
    except ValueError:
        return False

    salt = base64.b64decode(encoded_salt.encode())
    expected_digest = base64.b64decode(encoded_digest.encode())
    candidate_digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return hmac.compare_digest(candidate_digest, expected_digest)


def create_access_token(user_id: UUID) -> str:
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    return _encode_token(user_id=user_id, token_type=ACCESS_TOKEN_TYPE, expires_at=expires_at)


def create_refresh_token(user_id: UUID) -> str:
    expires_at = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    return _encode_token(
        user_id=user_id,
        token_type=REFRESH_TOKEN_TYPE,
        expires_at=expires_at,
        secret_key=settings.jwt_refresh_secret_key,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    return _decode_token(token, expected_type=ACCESS_TOKEN_TYPE)


def decode_refresh_token(token: str) -> dict[str, Any]:
    return _decode_token(
        token,
        expected_type=REFRESH_TOKEN_TYPE,
        secret_key=settings.jwt_refresh_secret_key,
    )


def _encode_token(
    *,
    user_id: UUID,
    token_type: str,
    expires_at: datetime,
    secret_key: str | None = None,
) -> str:
    payload = {
        "sub": str(user_id),
        "type": token_type,
        "exp": expires_at,
    }
    return jwt.encode(payload, secret_key or settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def _decode_token(
    token: str,
    *,
    expected_type: str,
    secret_key: str | None = None,
) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            secret_key or settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise TokenDecodeError("Token has expired.") from exc
    except InvalidTokenError as exc:
        raise TokenDecodeError("Token is invalid.") from exc

    if payload.get("type") != expected_type:
        raise TokenDecodeError("Token type is invalid for this endpoint.")

    subject = payload.get("sub")
    if not subject:
        raise TokenDecodeError("Token subject is missing.")

    try:
        UUID(str(subject))
    except ValueError as exc:
        raise TokenDecodeError("Token subject is invalid.") from exc

    return payload
