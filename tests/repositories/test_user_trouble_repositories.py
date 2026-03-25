from __future__ import annotations

from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient
from app.models.trouble_log import TroubleReactionType
from app.models.user import SkinType
from app.repositories.trouble_log_repository import TroubleLogRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.repositories.user_repository import UserRepository


def _create_ingredient(db_session, inci_name: str):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def _create_product(db_session, ingredient_ids):
    product = Product(name="Calming Cream", brand="Skinny", category="Cream")
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


def test_user_and_profile_repository_crud(db_session):
    user_repository = UserRepository()
    profile_repository = UserProfileRepository()
    ingredient = _create_ingredient(db_session, "Niacinamide")

    user = user_repository.create(
        db_session,
        email="profile@example.com",
        password_hash="hashed",
    )
    profile = profile_repository.create_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="baseline",
    )
    profile_repository.update_profile(
        db_session,
        profile,
        skin_type=SkinType.DRY,
        skin_concerns=["dryness"],
        notes="updated",
    )
    avoid = profile_repository.add_avoid_ingredient(
        db_session,
        user_id=user.id,
        ingredient_id=ingredient.id,
    )

    assert user_repository.get_by_email(db_session, "PROFILE@example.com") is not None
    loaded_profile = profile_repository.get_profile_by_user_id(db_session, user.id)
    assert loaded_profile is not None
    assert loaded_profile.skin_type == SkinType.DRY
    avoid_items = profile_repository.list_avoid_ingredients(db_session, user.id)
    assert len(avoid_items) == 1
    assert avoid_items[0].ingredient_id == ingredient.id

    profile_repository.delete_avoid_ingredient(db_session, avoid)
    assert profile_repository.list_avoid_ingredients(db_session, user.id) == []


def test_trouble_log_repository_supports_soft_delete_and_aggregation(db_session):
    user_repository = UserRepository()
    trouble_repository = TroubleLogRepository()
    ingredient_a = _create_ingredient(db_session, "Niacinamide")
    ingredient_b = _create_ingredient(db_session, "Retinol")
    product = _create_product(db_session, [ingredient_a.id, ingredient_b.id])
    user = user_repository.create(db_session, email="trouble@example.com", password_hash="hashed")

    first = trouble_repository.create(
        db_session,
        user_id=user.id,
        product_id=product.id,
        reaction_type=TroubleReactionType.ACNE,
        severity=3,
        memo="first",
    )
    trouble_repository.add_ingredients(db_session, trouble_log_id=first.id, ingredient_ids=[ingredient_a.id, ingredient_b.id])
    second = trouble_repository.create(
        db_session,
        user_id=user.id,
        product_id=product.id,
        reaction_type=TroubleReactionType.REDNESS,
        severity=4,
        memo="second",
    )
    trouble_repository.add_ingredients(db_session, trouble_log_id=second.id, ingredient_ids=[ingredient_a.id])

    stats = trouble_repository.aggregate_ingredient_occurrences(db_session, user.id)
    assert stats[0].ingredient_id == ingredient_a.id
    assert stats[0].occurrence_count == 2
    assert trouble_repository.list_active_product_ids_by_user(db_session, user.id) == [product.id]

    trouble_repository.soft_delete(db_session, first)
    remaining = trouble_repository.list_by_user_id(db_session, user.id)
    assert len(remaining) == 1
    assert remaining[0].id == second.id
