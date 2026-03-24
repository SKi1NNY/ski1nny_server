from __future__ import annotations

import json
from hashlib import sha256
from typing import Any, Protocol
from uuid import UUID

RECOMMENDATION_CACHE_NAMESPACE = "recommendations"
RECOMMENDATION_CACHE_VERSION = "v1"


def build_recommendation_cache_prefix(*, user_id: UUID) -> str:
    return f"{RECOMMENDATION_CACHE_NAMESPACE}:{RECOMMENDATION_CACHE_VERSION}:user:{user_id}"


def build_recommendation_cache_key(
    *,
    user_id: UUID,
    request_payload: dict[str, Any] | None = None,
) -> str:
    normalized_payload = _normalize_payload(request_payload or {})
    serialized = json.dumps(
        normalized_payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    payload_hash = sha256(serialized.encode("utf-8")).hexdigest()[:16]
    return f"{build_recommendation_cache_prefix(user_id=user_id)}:query:{payload_hash}"


def build_recommendation_cache_pattern(*, user_id: UUID) -> str:
    return f"{build_recommendation_cache_prefix(user_id=user_id)}:*"


def _normalize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_payload(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, tuple):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, list):
        return [_normalize_payload(item) for item in value]
    if isinstance(value, set):
        return [_normalize_payload(item) for item in sorted(value, key=str)]
    if isinstance(value, UUID):
        return str(value)
    return value


class RecommendationCacheInvalidator(Protocol):
    def invalidate_recommendation_cache(self, user_id: UUID) -> None:
        ...


class NoOpRecommendationCacheInvalidator:
    def invalidate_recommendation_cache(self, user_id: UUID) -> None:
        return None
