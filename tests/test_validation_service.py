from __future__ import annotations

from app.models.ingredient import ConflictSeverity, Ingredient, IngredientAlias, IngredientConflict
from app.models.user import SkinType, User
from app.services.validation_service import ValidationService
from app.services.user_profile_service import UserProfileService


def _create_user(db_session, email: str = "validation@example.com"):
    user = User(email=email, password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    return user


def _create_ingredient(db_session, inci_name: str, alias_name: str | None = None):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()
    if alias_name:
        db_session.add(
            IngredientAlias(
                ingredient_id=ingredient.id,
                alias_name=alias_name,
                language="ko",
            )
        )
        db_session.flush()
    return ingredient


def _create_conflict(db_session, ingredient_a, ingredient_b, severity: ConflictSeverity, reason: str):
    ordered = sorted([ingredient_a, ingredient_b], key=lambda item: item.id.int)
    db_session.add(
        IngredientConflict(
            ingredient_a_id=ordered[0].id,
            ingredient_b_id=ordered[1].id,
            severity=severity,
            reason=reason,
        )
    )
    db_session.flush()


def test_validation_service_detects_conflicts_avoid_ingredients_and_skin_type_rules(db_session):
    user = _create_user(db_session)
    fragrance = _create_ingredient(db_session, "Fragrance", alias_name="향료")
    retinol = _create_ingredient(db_session, "Retinol")
    glycolic = _create_ingredient(db_session, "Glycolic Acid")
    _create_conflict(db_session, fragrance, retinol, ConflictSeverity.HIGH, "These ingredients can irritate together.")

    profile_service = UserProfileService()
    profile_service.upsert_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="validation-profile",
    )
    profile_service.add_avoid_ingredient(db_session, user_id=user.id, ingredient_id=glycolic.id)

    service = ValidationService()
    result = service.validate_ingredients(
        db_session,
        ingredient_ids=[fragrance.id, retinol.id, glycolic.id],
        user_id=user.id,
    )

    assert result.is_safe is False
    assert result.severity == ConflictSeverity.HIGH
    assert len(result.conflicts) == 1
    assert {item.ingredient for item in result.personal_warnings} == {
        "Glycolic Acid",
        "Fragrance",
        "Retinol",
    }


def test_validation_service_supports_name_and_alias_input(db_session):
    niacinamide = _create_ingredient(db_session, "Niacinamide", alias_name="나이아신아마이드")
    service = ValidationService()

    result = service.validate_ingredients(
        db_session,
        ingredient_names=["Niacinamide", "나이아신아마이드"],
    )

    assert result.is_safe is True
    assert result.severity is None
    assert result.conflicts == []
    assert result.personal_warnings == []
