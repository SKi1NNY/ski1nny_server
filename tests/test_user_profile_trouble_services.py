from __future__ import annotations

from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient
from app.models.trouble_log import TroubleReactionType
from app.models.user import SkinType
from app.repositories.user_repository import UserRepository
from app.services.trouble_log_service import TroubleLogService
from app.services.user_profile_service import UserProfileService


class FakeCacheInvalidator:
    def __init__(self) -> None:
        self.invalidated_user_ids: list = []

    def invalidate_recommendation_cache(self, user_id) -> None:
        self.invalidated_user_ids.append(user_id)


def _create_user(db_session, email: str = "service@example.com"):
    repository = UserRepository()
    return repository.create(db_session, email=email, password_hash="hashed")


def _create_ingredient(db_session, inci_name: str):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def _create_product(db_session, ingredient_ids):
    product = Product(name="Barrier Cream", brand="Skinny", category="Cream")
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


def test_user_profile_service_upserts_profile_and_invalidates_cache(db_session):
    user = _create_user(db_session)
    ingredient = _create_ingredient(db_session, "Niacinamide")
    cache_invalidator = FakeCacheInvalidator()
    service = UserProfileService(cache_invalidator=cache_invalidator)

    profile = service.upsert_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="initial",
    )
    avoid = service.add_avoid_ingredient(db_session, user_id=user.id, ingredient_id=ingredient.id)

    assert profile.skin_type == SkinType.SENSITIVE
    assert avoid.inci_name == "Niacinamide"
    assert cache_invalidator.invalidated_user_ids == [user.id, user.id]


def test_trouble_log_service_returns_repeated_ingredient_suggestions(db_session):
    user = _create_user(db_session, email="repeat@example.com")
    ingredient_a = _create_ingredient(db_session, "Niacinamide")
    ingredient_b = _create_ingredient(db_session, "Retinol")
    product = _create_product(db_session, [ingredient_a.id, ingredient_b.id])
    service = TroubleLogService()

    first = service.create_trouble_log(
        db_session,
        user_id=user.id,
        product_id=product.id,
        reaction_type=TroubleReactionType.ACNE,
        severity=3,
        memo="first",
    )
    second = service.create_trouble_log(
        db_session,
        user_id=user.id,
        product_id=product.id,
        reaction_type=TroubleReactionType.REDNESS,
        severity=4,
        memo="second",
    )

    assert first.suggested_avoid_ingredients == []
    assert len(second.trouble_log.ingredient_ids) == 2
    assert second.suggested_avoid_ingredients[0].ingredient_id == ingredient_a.id
    assert second.suggested_avoid_ingredients[0].occurrence_count == 2
