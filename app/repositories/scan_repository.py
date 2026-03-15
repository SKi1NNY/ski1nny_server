from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.product import ScanParsedIngredient, ScanResult


@dataclass(slots=True)
class ParsedIngredientCreateItem:
    raw_name: str
    ingredient_id: UUID | None
    is_mapped: bool


class ScanRepository:
    def create_scan_result(
        self,
        db: Session,
        *,
        user_id: UUID,
        raw_ocr_text: str,
        confidence_score: float | None,
        product_id: UUID | None = None,
    ) -> ScanResult:
        scan_result = ScanResult(
            user_id=user_id,
            product_id=product_id,
            raw_ocr_text=raw_ocr_text,
            confidence_score=confidence_score,
        )
        db.add(scan_result)
        db.flush()
        return scan_result

    def add_parsed_ingredients(
        self,
        db: Session,
        *,
        scan_id: UUID,
        items: list[ParsedIngredientCreateItem],
    ) -> list[ScanParsedIngredient]:
        parsed_rows: list[ScanParsedIngredient] = []
        for item in items:
            parsed_row = ScanParsedIngredient(
                scan_id=scan_id,
                ingredient_name_raw=item.raw_name,
                ingredient_id=item.ingredient_id,
                is_mapped=item.is_mapped,
            )
            db.add(parsed_row)
            parsed_rows.append(parsed_row)

        db.flush()
        return parsed_rows

    def get_by_id(self, db: Session, scan_id: UUID) -> ScanResult | None:
        stmt = (
            select(ScanResult)
            .options(joinedload(ScanResult.parsed_ingredients))
            .where(ScanResult.id == scan_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()
