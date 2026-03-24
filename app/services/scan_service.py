from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.ocr_client import OCRClient, OCRResult
from app.models.ingredient import Ingredient
from app.repositories.ingredient_repository import IngredientRepository
from app.repositories.scan_repository import ParsedIngredientCreateItem, ScanRepository
from app.schemas.product import ScanFallbackResponse, ScanRecognizedIngredientResponse, ScanResponse
from app.services.validation_service import ValidationService

CONFIDENCE_THRESHOLD = 0.80
TOKEN_SPLIT_PATTERN = re.compile(r"[,;]+")
PAREN_CONTENT_PATTERN = re.compile(r"\([^)]*\)")
LEADING_HEADER_PATTERN = re.compile(r"^\s*\[?\s*전성분\s*\]?\s*[:：]?\s*", re.IGNORECASE)
NUMERIC_COMMA_PATTERN = re.compile(r"(?<=\d),(?=\d)")
NON_INGREDIENT_PATTERN = re.compile(r"[^0-9A-Za-z가-힣\s\-/]")
STANDALONE_NUMBER_PATTERN = re.compile(r"(?<![/-])\b\d+(?:,\d+)?\b(?![/-])")
MULTISPACE_PATTERN = re.compile(r"\s+")
SEPARATOR_SPACE_PATTERN = re.compile(r"\s*([/,-])\s*")
NUMERIC_COMMA_PLACEHOLDER = "NUMERICCOMMA"


@dataclass(slots=True)
class NormalizedToken:
    raw_name: str
    normalized_name: str
    ingredient: Ingredient | None

    @property
    def is_mapped(self) -> bool:
        return self.ingredient is not None


class ScanService:
    def __init__(
        self,
        ocr_client: OCRClient,
        ingredient_repository: IngredientRepository | None = None,
        scan_repository: ScanRepository | None = None,
        validation_service: ValidationService | None = None,
    ) -> None:
        self.ocr_client = ocr_client
        self.ingredient_repository = ingredient_repository or IngredientRepository()
        self.scan_repository = scan_repository or ScanRepository()
        self.validation_service = validation_service or ValidationService()

    def scan_ingredients(
        self,
        db: Session,
        *,
        user_id: UUID,
        image_bytes: bytes,
        filename: str | None = None,
    ) -> ScanResponse:
        if not image_bytes:
            raise ValidationError("A non-empty file is required for OCR scanning.")

        ocr_result = self._extract_text(image_bytes=image_bytes, filename=filename)
        normalized_tokens = self._normalize_tokens(db, ocr_result.text)
        scan_result = self.scan_repository.create_scan_result(
            db,
            user_id=user_id,
            raw_ocr_text=ocr_result.text,
            confidence_score=ocr_result.confidence_score,
        )
        self.scan_repository.add_parsed_ingredients(
            db,
            scan_id=scan_result.id,
            items=[
                ParsedIngredientCreateItem(
                    raw_name=token.raw_name,
                    ingredient_id=token.ingredient.id if token.ingredient else None,
                    is_mapped=token.is_mapped,
                )
                for token in normalized_tokens
            ],
        )
        db.commit()

        fallback = None
        if (ocr_result.confidence_score or 0.0) < CONFIDENCE_THRESHOLD:
            fallback = ScanFallbackResponse(
                requires_manual_input=True,
                reason="OCR confidence is below the automatic parsing threshold.",
            )

        validation = self.validation_service.validate_ingredients(
            db,
            ingredient_ids=[
                token.ingredient.id
                for token in normalized_tokens
                if token.ingredient is not None
            ],
            user_id=user_id,
        )

        return ScanResponse(
            scan_id=scan_result.id,
            product_id=scan_result.product_id,
            raw_ocr_text=scan_result.raw_ocr_text,
            confidence_score=scan_result.confidence_score,
            recognized_ingredients=[
                ScanRecognizedIngredientResponse(
                    raw_name=token.raw_name,
                    normalized_name=token.normalized_name,
                    ingredient_id=token.ingredient.id if token.ingredient else None,
                    is_mapped=token.is_mapped,
                )
                for token in normalized_tokens
            ],
            unmapped_ingredients=[
                token.normalized_name
                for token in normalized_tokens
                if not token.is_mapped
            ],
            fallback=fallback,
            validation=validation,
        )

    def _extract_text(self, *, image_bytes: bytes, filename: str | None) -> OCRResult:
        try:
            return self.ocr_client.extract_text(image_bytes, filename)
        except ExternalServiceError:
            raise
        except Exception as exc:  # pragma: no cover
            raise ExternalServiceError("Failed to process OCR request.") from exc

    def _tokenize(self, raw_text: str) -> list[str]:
        cleaned = self._normalize_raw_text(raw_text)
        if not cleaned:
            return []

        protected = NUMERIC_COMMA_PATTERN.sub(NUMERIC_COMMA_PLACEHOLDER, cleaned)
        tokens: list[str] = []
        for chunk in TOKEN_SPLIT_PATTERN.split(protected):
            token = NON_INGREDIENT_PATTERN.sub(" ", chunk)
            token = STANDALONE_NUMBER_PATTERN.sub(" ", token)
            token = MULTISPACE_PATTERN.sub(" ", token).strip(" -")
            token = token.replace(NUMERIC_COMMA_PLACEHOLDER, ",")
            token = SEPARATOR_SPACE_PATTERN.sub(r"\1", token)
            if token:
                tokens.append(token)
        return tokens

    def _normalize_raw_text(self, raw_text: str) -> str:
        cleaned = raw_text.replace("\r", "")
        cleaned = LEADING_HEADER_PATTERN.sub("", cleaned)
        cleaned = PAREN_CONTENT_PATTERN.sub(" ", cleaned)
        lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
        if not lines:
            return ""

        merged = lines[0]
        for line in lines[1:]:
            if merged.rstrip().endswith((",", ";")):
                merged = f"{merged.rstrip()} {line.lstrip()}"
            else:
                merged = f"{merged.rstrip()}{line.lstrip()}"
        return merged.strip()

    def _normalize_tokens(self, db: Session, raw_text: str) -> list[NormalizedToken]:
        raw_tokens = self._tokenize(raw_text)
        if not raw_tokens:
            return []

        candidate_tokens = self._build_candidate_tokens(raw_tokens)
        direct_ingredients = self.ingredient_repository.list_by_inci_names(db, candidate_tokens)
        direct_map = {ingredient.inci_name.strip().lower(): ingredient for ingredient in direct_ingredients}
        alias_map = self.ingredient_repository.map_aliases(db, candidate_tokens)
        raw_tokens = self._expand_compound_tokens(raw_tokens, direct_map=direct_map, alias_map=alias_map)

        normalized_tokens: list[NormalizedToken] = []
        seen_normalized_names: set[str] = set()
        for raw_token in raw_tokens:
            normalized_key = raw_token.strip().lower()
            ingredient = direct_map.get(normalized_key) or alias_map.get(normalized_key)
            normalized_name = ingredient.inci_name if ingredient else raw_token
            dedupe_key = normalized_name.strip().lower()
            if dedupe_key in seen_normalized_names:
                continue
            seen_normalized_names.add(dedupe_key)
            normalized_tokens.append(
                NormalizedToken(
                    raw_name=raw_token,
                    normalized_name=normalized_name,
                    ingredient=ingredient,
                )
            )
        return normalized_tokens

    def _build_candidate_tokens(self, raw_tokens: list[str]) -> list[str]:
        candidates = {token for token in raw_tokens if token}
        for token in raw_tokens:
            if len(token) < 4:
                continue
            for index in range(1, len(token)):
                left = token[:index].strip(" -")
                right = token[index:].strip(" -")
                if left:
                    candidates.add(left)
                if right:
                    candidates.add(right)
        return sorted(candidates)

    def _expand_compound_tokens(
        self,
        raw_tokens: list[str],
        *,
        direct_map: dict[str, Ingredient],
        alias_map: dict[str, Ingredient],
    ) -> list[str]:
        exact_matches = set(direct_map) | set(alias_map)

        @lru_cache(maxsize=None)
        def split_token(token: str) -> tuple[str, ...] | None:
            normalized = token.strip().lower()
            if not normalized:
                return None
            if normalized in exact_matches:
                return (token,)

            for index in range(1, len(token)):
                left = token[:index].strip(" -")
                right = token[index:].strip(" -")
                if not left or not right:
                    continue
                if left.strip().lower() not in exact_matches:
                    continue
                right_parts = split_token(right)
                if right_parts is not None:
                    return (left, *right_parts)

            return None

        expanded: list[str] = []
        for token in raw_tokens:
            parts = split_token(token)
            if parts is None:
                expanded.append(token)
            else:
                expanded.extend(parts)
        return expanded
