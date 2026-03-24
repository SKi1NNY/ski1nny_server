from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.user import (
    AvoidIngredientCreateRequest,
    AvoidIngredientResponse,
    RefreshTokenRequest,
    TokenResponse,
    TroubleLogConfirmAvoidIngredientsRequest,
    TroubleLogConfirmAvoidIngredientsResponse,
    TroubleLogCreateRequest,
    TroubleLogCreateResponse,
    TroubleLogListResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserProfileUpsertRequest,
    UserResponse,
    UserSignupRequest,
)
from app.services.auth_service import AuthService
from app.services.trouble_log_service import TroubleLogService
from app.services.user_profile_service import UserProfileService

router = APIRouter()


def get_auth_service() -> AuthService:
    return AuthService()


def get_user_profile_service() -> UserProfileService:
    return UserProfileService()


def get_trouble_log_service() -> TroubleLogService:
    return TroubleLogService()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: UserSignupRequest,
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
) -> UserResponse:
    return service.signup(db, email=payload.email, password=payload.password)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return service.login(db, email=payload.email, password=payload.password)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    return service.refresh(db, refresh_token=payload.refresh_token)


@router.get("/me/profile", response_model=UserProfileResponse)
def get_my_profile(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    return service.get_profile(db, user_id=current_user.id)


@router.put("/me/profile", response_model=UserProfileResponse)
def upsert_my_profile(
    payload: UserProfileUpsertRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: UserProfileService = Depends(get_user_profile_service),
) -> UserProfileResponse:
    return service.upsert_profile(
        db,
        user_id=current_user.id,
        skin_type=payload.skin_type,
        skin_concerns=payload.skin_concerns,
        notes=payload.notes,
    )


@router.post("/me/avoid-ingredients", response_model=AvoidIngredientResponse, status_code=status.HTTP_201_CREATED)
def add_avoid_ingredient(
    payload: AvoidIngredientCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: UserProfileService = Depends(get_user_profile_service),
) -> AvoidIngredientResponse:
    return service.add_avoid_ingredient(db, user_id=current_user.id, ingredient_id=payload.ingredient_id)


@router.delete("/me/avoid-ingredients/{avoid_ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_avoid_ingredient(
    avoid_ingredient_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: UserProfileService = Depends(get_user_profile_service),
) -> Response:
    service.delete_avoid_ingredient(db, user_id=current_user.id, avoid_ingredient_id=avoid_ingredient_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/trouble-logs", response_model=TroubleLogCreateResponse, status_code=status.HTTP_201_CREATED)
def create_trouble_log(
    payload: TroubleLogCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: TroubleLogService = Depends(get_trouble_log_service),
) -> TroubleLogCreateResponse:
    return service.create_trouble_log(
        db,
        user_id=current_user.id,
        product_id=payload.product_id,
        reaction_type=payload.reaction_type,
        severity=payload.severity,
        memo=payload.memo,
    )


@router.get("/me/trouble-logs", response_model=TroubleLogListResponse)
def list_trouble_logs(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: TroubleLogService = Depends(get_trouble_log_service),
) -> TroubleLogListResponse:
    return service.list_trouble_logs(db, user_id=current_user.id)


@router.post(
    "/me/trouble-logs/{trouble_log_id}/confirm-avoid-ingredients",
    response_model=TroubleLogConfirmAvoidIngredientsResponse,
)
def confirm_trouble_log_avoid_ingredients(
    trouble_log_id: UUID,
    payload: TroubleLogConfirmAvoidIngredientsRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: TroubleLogService = Depends(get_trouble_log_service),
) -> TroubleLogConfirmAvoidIngredientsResponse:
    return service.confirm_suggested_avoid_ingredients(
        db,
        user_id=current_user.id,
        trouble_log_id=trouble_log_id,
        ingredient_ids=payload.ingredient_ids,
    )


@router.delete("/me/trouble-logs/{trouble_log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trouble_log(
    trouble_log_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: TroubleLogService = Depends(get_trouble_log_service),
) -> Response:
    service.soft_delete_trouble_log(db, user_id=current_user.id, trouble_log_id=trouble_log_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
