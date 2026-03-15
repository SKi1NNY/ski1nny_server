from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.security import (
    TokenDecodeError,
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)


def test_password_hash_and_verify():
    password_hash = hash_password("supersecret123")

    assert password_hash != "supersecret123"
    assert verify_password("supersecret123", password_hash) is True
    assert verify_password("wrong-password", password_hash) is False


def test_access_and_refresh_tokens_are_type_safe():
    user_id = uuid4()
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    assert decode_access_token(access_token)["sub"] == str(user_id)
    assert decode_refresh_token(refresh_token)["sub"] == str(user_id)

    with pytest.raises(TokenDecodeError):
        decode_refresh_token(access_token)

    with pytest.raises(TokenDecodeError):
        decode_access_token(refresh_token)
