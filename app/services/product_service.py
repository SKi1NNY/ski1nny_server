from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import DuplicateBarcodeError, InternalServerError, InvalidIngredientReferenceError, ProductNotFoundError, ValidationError
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreateRequest, ProductIngredientResponse, ProductResponse


class ProductService:
    def __init__(self, repository: ProductRepository | None = None) -> None:
        self.repository = repository or ProductRepository()

    def create_product(self, db: Session, *, payload: ProductCreateRequest) -> ProductResponse:
        if payload.barcode and self.repository.get_by_barcode(db, payload.barcode):
            raise DuplicateBarcodeError()

        ingredient_ids = [item.ingredient_id for item in payload.ingredients]
        if len(set(ingredient_ids)) != len(ingredient_ids):
            raise ValidationError("Duplicate ingredient IDs are not allowed.")

        if self.repository.count_matching_ingredients(db, ingredient_ids) != len(set(ingredient_ids)):
            raise InvalidIngredientReferenceError()

        product = self.repository.create(
            db,
            name=payload.name,
            brand=payload.brand,
            category=payload.category,
            barcode=payload.barcode,
            ingredient_items=[(item.ingredient_id, item.ingredient_order) for item in payload.ingredients],
        )
        db.commit()

        reloaded_product = self.repository.get_by_id(db, product.id)
        if reloaded_product is None:
            raise InternalServerError("Product could not be reloaded.")
        return self._build_product_response(reloaded_product)

    def get_product(self, db: Session, *, product_id) -> ProductResponse:
        product = self.repository.get_by_id(db, product_id)
        if product is None:
            raise ProductNotFoundError()
        return self._build_product_response(product)

    def _build_product_response(self, product) -> ProductResponse:
        return ProductResponse(
            id=product.id,
            name=product.name,
            brand=product.brand,
            category=product.category,
            barcode=product.barcode,
            ingredients=[
                ProductIngredientResponse(
                    ingredient_id=item.ingredient_id,
                    inci_name=item.ingredient.inci_name,
                    korean_name=item.ingredient.korean_name,
                    category=item.ingredient.category,
                    ingredient_order=item.ingredient_order,
                )
                for item in product.product_ingredients
            ],
        )
