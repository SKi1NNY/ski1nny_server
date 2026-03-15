from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ingredient import ConflictSeverity, Ingredient
from app.models.user import SkinType
from app.repositories.ingredient_repository import IngredientRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.schemas.ingredient import (
    IngredientConflictResponse,
    IngredientPersonalWarningResponse,
    IngredientValidationResponse,
)

SKIN_TYPE_RULES: dict[SkinType, dict[str, tuple[ConflictSeverity, str]]] = {
    SkinType.SENSITIVE: {
        "fragrance": (ConflictSeverity.MID, "Sensitive skin may react to fragrance ingredients."),
        "retinol": (ConflictSeverity.MID, "Sensitive skin should use retinol cautiously."),
    },
    SkinType.DRY: {
        "glycolic acid": (ConflictSeverity.LOW, "Dry skin may experience extra dryness with glycolic acid."),
    },
}

SEVERITY_RANK = {
    ConflictSeverity.LOW: 1,
    ConflictSeverity.MID: 2,
    ConflictSeverity.HIGH: 3,
}


@dataclass(slots=True)
class ResolvedValidationInput:
    ingredients: list[Ingredient]


class ValidationService:
    def __init__(
        self,
        ingredient_repository: IngredientRepository | None = None,
        user_profile_repository: UserProfileRepository | None = None,
    ) -> None:
        self.ingredient_repository = ingredient_repository or IngredientRepository()
        self.user_profile_repository = user_profile_repository or UserProfileRepository()

    def validate_ingredients(
        self,
        db: Session,
        *,
        ingredient_ids: list[UUID] | None = None,
        ingredient_names: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> IngredientValidationResponse:
        resolved = self._resolve_input(
            db,
            ingredient_ids=ingredient_ids or [],
            ingredient_names=ingredient_names or [],
        )
        if not resolved.ingredients:
            return IngredientValidationResponse(is_safe=True, severity=None, conflicts=[], personal_warnings=[])

        conflicts = self._build_conflict_responses(
            db,
            [ingredient.id for ingredient in resolved.ingredients],
        )
        personal_warnings = self._build_personal_warnings(
            db,
            user_id=user_id,
            ingredients=resolved.ingredients,
        )
        skin_type_warnings = self._build_skin_type_warnings(
            db,
            user_id=user_id,
            ingredients=resolved.ingredients,
        )

        all_warnings = personal_warnings + skin_type_warnings
        severity = self._calculate_max_severity(conflicts, all_warnings)
        is_safe = not any(conflict.severity == ConflictSeverity.HIGH for conflict in conflicts) and not any(
            warning.layer == 2 for warning in all_warnings
        )

        return IngredientValidationResponse(
            is_safe=is_safe,
            severity=severity,
            conflicts=conflicts,
            personal_warnings=all_warnings,
        )

    def _resolve_input(
        self,
        db: Session,
        *,
        ingredient_ids: list[UUID],
        ingredient_names: list[str],
    ) -> ResolvedValidationInput:
        ingredients: list[Ingredient] = []

        for ingredient_id in dict.fromkeys(ingredient_ids):
            ingredient = self.ingredient_repository.get_by_id(db, ingredient_id)
            if ingredient is not None:
                ingredients.append(ingredient)

        by_name = self.ingredient_repository.list_by_inci_names(db, ingredient_names)
        alias_map = self.ingredient_repository.map_aliases(db, ingredient_names)
        by_name_lookup = {ingredient.id: ingredient for ingredient in by_name}
        alias_lookup = {ingredient.id: ingredient for ingredient in alias_map.values()}

        combined = {ingredient.id: ingredient for ingredient in ingredients}
        combined.update(by_name_lookup)
        combined.update(alias_lookup)
        return ResolvedValidationInput(ingredients=list(combined.values()))

    def _build_conflict_responses(self, db: Session, ingredient_ids: list[UUID]) -> list[IngredientConflictResponse]:
        conflicts = self.ingredient_repository.get_conflicts_for_ingredient_ids(db, ingredient_ids)
        return [
            IngredientConflictResponse(
                ingredients=[conflict.ingredient_a.inci_name, conflict.ingredient_b.inci_name],
                reason=conflict.reason,
                severity=conflict.severity,
                layer=1,
            )
            for conflict in conflicts
        ]

    def _build_personal_warnings(
        self,
        db: Session,
        *,
        user_id: UUID | None,
        ingredients: list[Ingredient],
    ) -> list[IngredientPersonalWarningResponse]:
        if user_id is None:
            return []

        avoid_ingredients = self.user_profile_repository.list_avoid_ingredients(db, user_id)
        avoid_by_ingredient_id = {item.ingredient_id: item for item in avoid_ingredients}
        warnings: list[IngredientPersonalWarningResponse] = []
        for ingredient in ingredients:
            avoid = avoid_by_ingredient_id.get(ingredient.id)
            if avoid is None:
                continue
            warnings.append(
                IngredientPersonalWarningResponse(
                    ingredient=ingredient.inci_name,
                    reason="This ingredient is marked as avoided in the user profile.",
                    layer=2,
                )
            )
        return warnings

    def _build_skin_type_warnings(
        self,
        db: Session,
        *,
        user_id: UUID | None,
        ingredients: list[Ingredient],
    ) -> list[IngredientPersonalWarningResponse]:
        if user_id is None:
            return []

        profile = self.user_profile_repository.get_profile_by_user_id(db, user_id)
        if profile is None:
            return []

        rules = SKIN_TYPE_RULES.get(profile.skin_type, {})
        warnings: list[IngredientPersonalWarningResponse] = []
        for ingredient in ingredients:
            rule = rules.get(ingredient.inci_name.strip().lower())
            if rule is None:
                continue
            _, reason = rule
            warnings.append(
                IngredientPersonalWarningResponse(
                    ingredient=ingredient.inci_name,
                    reason=reason,
                    layer=3,
                )
            )
        return warnings

    def _calculate_max_severity(
        self,
        conflicts: list[IngredientConflictResponse],
        warnings: list[IngredientPersonalWarningResponse],
    ) -> ConflictSeverity | None:
        severities = [conflict.severity for conflict in conflicts]
        if any(warning.layer == 2 for warning in warnings):
            severities.append(ConflictSeverity.HIGH)
        if any(warning.layer == 3 for warning in warnings):
            severities.append(ConflictSeverity.MID)
        if not severities:
            return None
        return max(severities, key=lambda severity: SEVERITY_RANK[severity])
