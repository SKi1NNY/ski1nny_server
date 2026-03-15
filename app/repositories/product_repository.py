from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.ingredient import Ingredient
from app.models.product import Product, ProductIngredient


class ProductRepository:
    def create(
        self,
        db: Session,
        *,
        name: str,
        brand: str,
        category: str | None = None,
        barcode: str | None = None,
        ingredient_items: list[tuple[UUID, int]] | None = None,
    ) -> Product:
        product = Product(
            name=name,
            brand=brand,
            category=category,
            barcode=barcode,
        )
        db.add(product)
        db.flush()

        for ingredient_id, ingredient_order in ingredient_items or []:
            db.add(
                ProductIngredient(
                    product_id=product.id,
                    ingredient_id=ingredient_id,
                    ingredient_order=ingredient_order,
                )
            )

        db.flush()
        return self.get_by_id(db, product.id) or product

    def get_by_barcode(self, db: Session, barcode: str) -> Product | None:
        normalized = barcode.strip()
        if not normalized:
            return None

        stmt = select(Product).where(Product.barcode == normalized)
        return db.scalar(stmt)

    def get_by_id(self, db: Session, product_id: UUID) -> Product | None:
        stmt = (
            select(Product)
            .options(
                joinedload(Product.product_ingredients).joinedload(ProductIngredient.ingredient),
            )
            .where(Product.id == product_id)
        )
        return db.execute(stmt).unique().scalar_one_or_none()

    def list_ingredient_ids(self, db: Session, product_id: UUID) -> list[UUID]:
        stmt = (
            select(ProductIngredient.ingredient_id)
            .where(ProductIngredient.product_id == product_id)
            .order_by(ProductIngredient.ingredient_order.asc(), ProductIngredient.id.asc())
        )
        return list(db.scalars(stmt))

    def count_matching_ingredients(self, db: Session, ingredient_ids: list[UUID]) -> int:
        if not ingredient_ids:
            return 0

        stmt = select(func.count(Ingredient.id)).where(Ingredient.id.in_(ingredient_ids))
        return int(db.scalar(stmt) or 0)
