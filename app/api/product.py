from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.exceptions import ExternalServiceError, ValidationError
from app.core.ocr_client import get_ocr_client
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreateRequest, ProductIngredientResponse, ProductResponse, ScanResponse
from app.services.scan_service import ScanService

router = APIRouter()


def get_product_repository() -> ProductRepository:
    return ProductRepository()


def get_scan_service() -> ScanService:
    return ScanService(ocr_client=get_ocr_client())


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateRequest,
    db: Session = Depends(get_db),
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductResponse:
    if payload.barcode and repository.get_by_barcode(db, payload.barcode):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Barcode already exists.")

    ingredient_ids = [item.ingredient_id for item in payload.ingredients]
    if len(set(ingredient_ids)) != len(ingredient_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate ingredient IDs are not allowed.",
        )

    if repository.count_matching_ingredients(db, ingredient_ids) != len(set(ingredient_ids)):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="One or more ingredient IDs are invalid.")

    product = repository.create(
        db,
        name=payload.name,
        brand=payload.brand,
        category=payload.category,
        barcode=payload.barcode,
        ingredient_items=[(item.ingredient_id, item.ingredient_order) for item in payload.ingredients],
    )
    db.commit()
    reloaded_product = repository.get_by_id(db, product.id)
    if reloaded_product is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Product could not be reloaded.")
    return _build_product_response(reloaded_product)


@router.post("/scan", response_model=ScanResponse)
async def scan_product_ingredients(
    user_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    scan_service: ScanService = Depends(get_scan_service),
) -> ScanResponse:
    try:
        image_bytes = await file.read()
        return scan_service.scan_ingredients(
            db,
            user_id=user_id,
            image_bytes=image_bytes,
            filename=file.filename,
        )
    except ValidationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    except ExternalServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=exc.message) from exc


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductResponse:
    product = repository.get_by_id(db, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found.")
    return _build_product_response(product)


def _build_product_response(product) -> ProductResponse:
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
