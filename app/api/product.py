from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.ocr_client import get_ocr_client
from app.schemas.product import ProductCreateRequest, ProductResponse, ScanResponse
from app.services.product_service import ProductService
from app.services.scan_service import ScanService

router = APIRouter()


def get_product_service() -> ProductService:
    return ProductService()


def get_scan_service() -> ScanService:
    return ScanService(ocr_client=get_ocr_client())


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    payload: ProductCreateRequest,
    db: Session = Depends(get_db),
    service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    return service.create_product(db, payload=payload)


@router.post("/scan", response_model=ScanResponse)
async def scan_product_ingredients(
    user_id: UUID = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    scan_service: ScanService = Depends(get_scan_service),
) -> ScanResponse:
    image_bytes = await file.read()
    return scan_service.scan_ingredients(
        db,
        user_id=user_id,
        image_bytes=image_bytes,
        filename=file.filename,
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    service: ProductService = Depends(get_product_service),
) -> ProductResponse:
    return service.get_product(db, product_id=product_id)
