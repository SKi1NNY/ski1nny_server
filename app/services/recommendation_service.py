from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.ingredient import ConflictSeverity
from app.models.product import Product
from app.models.user import SkinType
from app.repositories.product_repository import ProductRepository
from app.repositories.trouble_log_repository import TroubleIngredientStat, TroubleLogRepository
from app.repositories.user_profile_repository import UserProfileRepository
from app.schemas.ingredient import IngredientValidationResponse
from app.schemas.recommendation import (
    RecommendationFallbackResponse,
    RecommendationItemResponse,
    RecommendationResponse,
    RecommendationWarningResponse,
)
from app.services.validation_service import SKIN_TYPE_RULES, ValidationService

BASE_RECOMMENDATION_SCORE = 50

SKIN_TYPE_CATEGORY_WEIGHTS: dict[SkinType, dict[str, int]] = {
    SkinType.DRY: {
        "Humectant": 18,
        "Emollient": 16,
        "Extract": 6,
    },
    SkinType.OILY: {
        "Humectant": 10,
        "Brightening": 8,
        "Antioxidant": 6,
    },
    SkinType.COMBINATION: {
        "Humectant": 12,
        "Emollient": 6,
        "Extract": 6,
    },
    SkinType.SENSITIVE: {
        "Extract": 16,
        "Humectant": 12,
        "Emollient": 10,
        "Antioxidant": 6,
    },
    SkinType.NORMAL: {
        "Humectant": 8,
        "Emollient": 8,
        "Extract": 6,
    },
}

SKIN_CONCERN_CATEGORY_WEIGHTS: dict[str, dict[str, int]] = {
    "redness": {
        "Extract": 18,
        "Antioxidant": 10,
        "Humectant": 6,
    },
    "dryness": {
        "Humectant": 18,
        "Emollient": 16,
        "Extract": 4,
    },
    "acne": {
        "Brightening": 12,
        "Exfoliant": 10,
        "Humectant": 4,
    },
    "wrinkle": {
        "Anti-aging": 18,
        "Antioxidant": 10,
        "Humectant": 4,
    },
    "aging": {
        "Anti-aging": 18,
        "Antioxidant": 10,
    },
    "pigmentation": {
        "Brightening": 18,
        "Antioxidant": 8,
    },
    "sensitivity": {
        "Extract": 16,
        "Humectant": 10,
        "Emollient": 8,
    },
}

TROUBLE_OCCURRENCE_PENALTY = 7
MAX_TROUBLE_INGREDIENT_PENALTY = 18


@dataclass(slots=True)
class RecommendationCandidate:
    product: Product
    validation: IngredientValidationResponse


class RecommendationService:
    def __init__(
        self,
        product_repository: ProductRepository | None = None,
        trouble_log_repository: TroubleLogRepository | None = None,
        profile_repository: UserProfileRepository | None = None,
        validation_service: ValidationService | None = None,
    ) -> None:
        self.product_repository = product_repository or ProductRepository()
        self.trouble_log_repository = trouble_log_repository or TroubleLogRepository()
        self.profile_repository = profile_repository or UserProfileRepository()
        self.validation_service = validation_service or ValidationService()

    def recommend_products(
        self,
        db: Session,
        *,
        user_id: UUID,
        limit: int = 5,
        skin_type: SkinType | None = None,
        skin_concerns: list[str] | None = None,
    ) -> RecommendationResponse:
        products = self.product_repository.list_all(db)
        if not products:
            return RecommendationResponse(
                recommendations=[],
                fallback=RecommendationFallbackResponse(
                    message="등록된 제품이 아직 없습니다.",
                    suggestion="제품 데이터를 먼저 등록한 뒤 다시 추천을 요청해 주세요.",
                ),
            )

        profile = self.profile_repository.get_profile_by_user_id(db, user_id)
        effective_skin_type = skin_type or (profile.skin_type if profile is not None else None)
        effective_concerns = self._resolve_skin_concerns(
            requested=skin_concerns or [],
            profile_concerns=profile.skin_concerns if profile is not None else [],
        )
        trouble_product_ids = set(self.trouble_log_repository.list_active_product_ids_by_user(db, user_id))
        trouble_stats = self.trouble_log_repository.aggregate_ingredient_occurrences(db, user_id)
        trouble_occurrence_map = {stat.ingredient_id: stat for stat in trouble_stats}

        candidates = self._apply_validation_stage(
            db,
            products=products,
            user_id=user_id,
            effective_skin_type=effective_skin_type,
        )
        candidates = self._apply_personal_filter_stage(
            candidates=candidates,
            trouble_product_ids=trouble_product_ids,
        )

        ranked_items = [
            self._build_recommendation_item(
                candidate=candidate,
                effective_skin_type=effective_skin_type,
                effective_concerns=effective_concerns,
                trouble_occurrence_map=trouble_occurrence_map,
            )
            for candidate in candidates
        ]
        ranked_items.sort(
            key=lambda item: (
                -item.score,
                len(item.warnings),
                item.product_name.lower(),
                item.brand.lower(),
            )
        )

        if not ranked_items:
            return RecommendationResponse(
                recommendations=[],
                fallback=RecommendationFallbackResponse(
                    message="조건에 맞는 추천 제품이 없습니다.",
                    suggestion="기피 성분 조건을 줄이거나 피부 고민을 단순화해서 다시 시도해 주세요.",
                ),
            )

        return RecommendationResponse(recommendations=ranked_items[:limit], fallback=None)

    def _apply_validation_stage(
        self,
        db: Session,
        *,
        products: list[Product],
        user_id: UUID,
        effective_skin_type: SkinType | None,
    ) -> list[RecommendationCandidate]:
        candidates: list[RecommendationCandidate] = []
        for product in products:
            ingredient_ids = [item.ingredient_id for item in product.product_ingredients]
            validation = self.validation_service.validate_ingredients(
                db,
                ingredient_ids=ingredient_ids,
                user_id=user_id,
            )

            has_high_conflict = any(conflict.severity == ConflictSeverity.HIGH for conflict in validation.conflicts)
            has_skin_type_blocker = bool(
                effective_skin_type
                and self._has_skin_type_blocker(product, effective_skin_type)
            )
            if has_high_conflict or has_skin_type_blocker:
                continue

            candidates.append(RecommendationCandidate(product=product, validation=validation))

        return candidates

    def _apply_personal_filter_stage(
        self,
        *,
        candidates: list[RecommendationCandidate],
        trouble_product_ids: set[UUID],
    ) -> list[RecommendationCandidate]:
        filtered: list[RecommendationCandidate] = []
        for candidate in candidates:
            has_avoid_warning = any(warning.layer == 2 for warning in candidate.validation.personal_warnings)
            if has_avoid_warning:
                continue
            if candidate.product.id in trouble_product_ids:
                continue
            filtered.append(candidate)
        return filtered

    def _build_recommendation_item(
        self,
        *,
        candidate: RecommendationCandidate,
        effective_skin_type: SkinType | None,
        effective_concerns: list[str],
        trouble_occurrence_map: dict[UUID, TroubleIngredientStat],
    ) -> RecommendationItemResponse:
        skin_type_bonus = self._score_skin_type(candidate.product, effective_skin_type)
        concern_bonus = self._score_skin_concerns(candidate.product, effective_concerns)
        trouble_penalty, trouble_warnings = self._score_trouble_history(candidate.product, trouble_occurrence_map)
        validation_warnings = self._build_validation_warnings(candidate.validation)
        score = max(0, min(100, BASE_RECOMMENDATION_SCORE + skin_type_bonus + concern_bonus - trouble_penalty))

        return RecommendationItemResponse(
            product_id=candidate.product.id,
            product_name=candidate.product.name,
            brand=candidate.product.brand,
            category=candidate.product.category,
            score=score,
            reason=None,
            warnings=validation_warnings + trouble_warnings,
        )

    def _score_skin_type(self, product: Product, skin_type: SkinType | None) -> int:
        if skin_type is None:
            return 0

        weights = SKIN_TYPE_CATEGORY_WEIGHTS.get(skin_type, {})
        matched_categories = {
            item.ingredient.category
            for item in product.product_ingredients
            if item.ingredient.category
        }
        return sum(weights.get(category, 0) for category in matched_categories)

    def _score_skin_concerns(self, product: Product, concerns: list[str]) -> int:
        if not concerns:
            return 0

        matched_categories = {
            item.ingredient.category
            for item in product.product_ingredients
            if item.ingredient.category
        }
        score = 0
        for concern in concerns:
            weights = SKIN_CONCERN_CATEGORY_WEIGHTS.get(concern, {})
            score += sum(weights.get(category, 0) for category in matched_categories)
        return score

    def _score_trouble_history(
        self,
        product: Product,
        trouble_occurrence_map: dict[UUID, TroubleIngredientStat],
    ) -> tuple[int, list[RecommendationWarningResponse]]:
        penalty = 0
        warnings: list[RecommendationWarningResponse] = []
        for item in product.product_ingredients:
            stat = trouble_occurrence_map.get(item.ingredient_id)
            if stat is None:
                continue

            penalty += min(stat.occurrence_count * TROUBLE_OCCURRENCE_PENALTY, MAX_TROUBLE_INGREDIENT_PENALTY)
            warnings.append(
                RecommendationWarningResponse(
                    type="trouble_history",
                    message=(
                        f"{item.ingredient.inci_name} 성분이 이전 트러블 로그에 "
                        f"{stat.occurrence_count}회 기록되었습니다."
                    ),
                )
            )

        unique_messages: dict[str, RecommendationWarningResponse] = {}
        for warning in warnings:
            unique_messages[warning.message] = warning
        return penalty, list(unique_messages.values())

    def _build_validation_warnings(
        self,
        validation: IngredientValidationResponse,
    ) -> list[RecommendationWarningResponse]:
        warnings: list[RecommendationWarningResponse] = []
        for conflict in validation.conflicts:
            if conflict.severity == ConflictSeverity.HIGH:
                continue
            warnings.append(
                RecommendationWarningResponse(
                    type="validation_conflict",
                    message=conflict.reason,
                )
            )
        return warnings

    def _has_skin_type_blocker(
        self,
        product: Product,
        skin_type: SkinType,
    ) -> bool:
        rules = SKIN_TYPE_RULES.get(skin_type, {})
        if not rules:
            return False

        for item in product.product_ingredients:
            ingredient_name = item.ingredient.inci_name.strip().lower()
            rule = rules.get(ingredient_name)
            if rule is None:
                continue
            severity, _ = rule
            if severity in {ConflictSeverity.MID, ConflictSeverity.HIGH}:
                return True
        return False

    def _resolve_skin_concerns(self, *, requested: list[str], profile_concerns: list[str]) -> list[str]:
        source = requested or profile_concerns
        normalized = [concern.strip().lower() for concern in source if concern and concern.strip()]
        return list(dict.fromkeys(normalized))
