from __future__ import annotations

from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient
from app.models.trouble_log import TroubleReactionType
from app.models.user import SkinType
from app.repositories.user_repository import UserRepository
from app.services.recommendation_service import RecommendationService
from app.services.trouble_log_service import TroubleLogService
from app.services.user_profile_service import UserProfileService


def _create_user(db_session, email: str = "recommend@example.com"):
    return UserRepository().create(db_session, email=email, password_hash="hashed")


def _create_ingredient(db_session, inci_name: str, *, category: str):
    ingredient = Ingredient(
        inci_name=inci_name,
        korean_name=inci_name,
        category=category,
    )
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def _create_product(db_session, name: str, ingredient_ids):
    product = Product(name=name, brand="Skinny", category="Serum")
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


def test_recommendation_service_filters_and_ranks_products(db_session):
    user = _create_user(db_session)
    UserProfileService().upsert_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="recommendation-profile",
    )

    centella = _create_ingredient(db_session, "Centella Asiatica Extract", category="Extract")
    glycerin = _create_ingredient(db_session, "Glycerin", category="Humectant")
    fragrance = _create_ingredient(db_session, "Fragrance", category="Additive")
    niacinamide = _create_ingredient(db_session, "Niacinamide", category="Brightening")

    soothing = _create_product(db_session, "Calm Ampoule", [centella.id, glycerin.id])
    fragranced = _create_product(db_session, "Perfumed Mist", [centella.id, fragrance.id])
    trouble_source = _create_product(db_session, "Breakout Serum", [niacinamide.id])
    risky = _create_product(db_session, "Tone Repair Serum", [centella.id, niacinamide.id])

    trouble_service = TroubleLogService()
    trouble_service.create_trouble_log(
        db_session,
        user_id=user.id,
        product_id=trouble_source.id,
        reaction_type=TroubleReactionType.ACNE,
        severity=3,
        memo="first trouble",
    )
    trouble_service.create_trouble_log(
        db_session,
        user_id=user.id,
        product_id=trouble_source.id,
        reaction_type=TroubleReactionType.REDNESS,
        severity=4,
        memo="second trouble",
    )

    response = RecommendationService().recommend_products(db_session, user_id=user.id, limit=5)

    assert [item.product_id for item in response.recommendations] == [soothing.id, risky.id]
    assert response.recommendations[0].score > response.recommendations[1].score
    assert response.recommendations[0].warnings == []
    assert any(warning.type == "trouble_history" for warning in response.recommendations[1].warnings)
    assert {item.product_id for item in response.recommendations}.isdisjoint({fragranced.id, trouble_source.id})
    assert response.fallback is None


def test_recommendation_service_returns_fallback_when_all_products_filtered(db_session):
    user = _create_user(db_session, email="fallback@example.com")
    UserProfileService().upsert_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="fallback-profile",
    )

    centella = _create_ingredient(db_session, "Centella Asiatica Extract", category="Extract")
    fragrance = _create_ingredient(db_session, "Fragrance", category="Additive")
    _create_product(db_session, "Blocked Mist", [centella.id, fragrance.id])

    response = RecommendationService().recommend_products(db_session, user_id=user.id, limit=3)

    assert response.recommendations == []
    assert response.fallback is not None
    assert "조건에 맞는 추천 제품이 없습니다." == response.fallback.message
