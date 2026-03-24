from __future__ import annotations

from uuid import uuid4

from app.services.recommendation_cache import build_recommendation_cache_key, build_recommendation_cache_pattern


def test_recommendation_cache_key_rule_is_stable_for_user_scope():
    user_id = uuid4()

    key = build_recommendation_cache_key(
        user_id=user_id,
        request_payload={
            "limit": 10,
            "filters": {"skin_type": "SENSITIVE", "concerns": ["redness", "dryness"]},
        },
    )
    reordered_key = build_recommendation_cache_key(
        user_id=user_id,
        request_payload={
            "filters": {"concerns": ["redness", "dryness"], "skin_type": "SENSITIVE"},
            "limit": 10,
        },
    )

    assert key == reordered_key
    assert key.startswith(f"recommendations:v1:user:{user_id}:query:")
    assert build_recommendation_cache_pattern(user_id=user_id) == f"recommendations:v1:user:{user_id}:*"
