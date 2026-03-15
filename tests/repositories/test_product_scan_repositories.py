from __future__ import annotations

from app.models.ingredient import Ingredient
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.repositories.scan_repository import ParsedIngredientCreateItem, ScanRepository


def _create_user(db_session):
    user = User(email="product-scan@example.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    return user


def _create_ingredient(db_session, inci_name: str, korean_name: str):
    ingredient = Ingredient(inci_name=inci_name, korean_name=korean_name)
    db_session.add(ingredient)
    db_session.flush()
    return ingredient


def test_product_repository_creates_product_with_ordered_ingredients(db_session):
    ingredient_a = _create_ingredient(db_session, "Niacinamide", "나이아신아마이드")
    ingredient_b = _create_ingredient(db_session, "Retinol", "레티놀")

    repository = ProductRepository()
    product = repository.create(
        db_session,
        name="Daily Serum",
        brand="Skinny",
        category="Serum",
        barcode="880100000001",
        ingredient_items=[
            (ingredient_b.id, 2),
            (ingredient_a.id, 1),
        ],
    )

    reloaded = repository.get_by_id(db_session, product.id)

    assert reloaded is not None
    assert reloaded.barcode == "880100000001"
    assert [item.ingredient.inci_name for item in reloaded.product_ingredients] == [
        "Niacinamide",
        "Retinol",
    ]
    assert repository.get_by_barcode(db_session, "880100000001") is not None


def test_scan_repository_persists_raw_text_and_parsed_rows(db_session):
    user = _create_user(db_session)
    ingredient = _create_ingredient(db_session, "Niacinamide", "나이아신아마이드")

    repository = ScanRepository()
    scan_result = repository.create_scan_result(
        db_session,
        user_id=user.id,
        raw_ocr_text="Niacinamide, Unknown Extract",
        confidence_score=0.97,
    )
    repository.add_parsed_ingredients(
        db_session,
        scan_id=scan_result.id,
        items=[
            ParsedIngredientCreateItem(
                raw_name="Niacinamide",
                ingredient_id=ingredient.id,
                is_mapped=True,
            ),
            ParsedIngredientCreateItem(
                raw_name="Unknown Extract",
                ingredient_id=None,
                is_mapped=False,
            ),
        ],
    )

    reloaded = repository.get_by_id(db_session, scan_result.id)

    assert reloaded is not None
    assert reloaded.raw_ocr_text == "Niacinamide, Unknown Extract"
    assert reloaded.confidence_score == 0.97
    assert len(reloaded.parsed_ingredients) == 2
    assert {item.ingredient_name_raw for item in reloaded.parsed_ingredients} == {
        "Niacinamide",
        "Unknown Extract",
    }
