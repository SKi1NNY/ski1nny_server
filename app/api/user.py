from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.core.database import get_db
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, PermissionDeniedError, ValidationError
from app.core.security import create_access_token, create_refresh_token, decode_refresh_token, hash_password, verify_password
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import (
    AvoidIngredientCreateRequest,
    AvoidIngredientResponse,
    RefreshTokenRequest,
    TokenResponse,
    TroubleLogCreateRequest,
    TroubleLogCreateResponse,
    TroubleLogListResponse,
    UserLoginRequest,
    UserProfileResponse,
    UserProfileUpsertRequest,
    UserResponse,
    UserSignupRequest,
)
from app.services.trouble_log_service import TroubleLogService
from app.services.user_profile_service import UserProfileService

router = APIRouter()


def get_user_repository() -> UserRepository:
    return UserRepository()


def get_user_profile_service() -> UserProfileService:
    return UserProfileService()


def get_trouble_log_service() -> TroubleLogService:
    return TroubleLogService()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def signup(
    payload: UserSignupRequest,
    db: Session = Depends(get_db),
    repository: UserRepository = Depends(get_user_repository),
) -> UserResponse:
    if repository.get_by_email(db, payload.email) is not None:
        raise ConflictError("Email already exists.")

    user = repository.create(db, email=payload.email, password_hash=hash_password(payload.password))
    db.commit()
    db.refresh(user)
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLoginRequest,
    db: Session = Depends(get_db),
    repository: UserRepository = Depends(get_user_repository),
) -> TokenResponse:
    user = repository.get_by_email(db, payload.email)
    if user is None or not verify_password(payload.password, user.password_hash):
        raise AuthenticationError("Invalid email or password.")
    if not user.is_active:
        raise PermissionDeniedError("User account is inactive.")
    if user.is_deleted:
        raise PermissionDeniedError("User account is deleted.")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    payload: RefreshTokenRequest,
    db: Session = Depends(get_db),
    repository: UserRepository = Depends(get_user_repository),
) -> TokenResponse:
    try:
        token_payload = decode_refresh_token(payload.refresh_token)
    except Exception as exc:
        raise AuthenticationError("Refresh token is invalid.") from exc

    user = repository.get_by_id(db, UUID(str(token_payload["sub"])))
    if user is None:
        raise AuthenticationError("Authenticated user does not exist.")
    if not user.is_active:
        raise PermissionDeniedError("User account is inactive.")
    if user.is_deleted:
        raise PermissionDeniedError("User account is deleted.")
    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


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
    try:
        return service.upsert_profile(
            db,
            user_id=current_user.id,
            skin_type=payload.skin_type,
            skin_concerns=payload.skin_concerns,
            notes=payload.notes,
        )
    except NotFoundError:
        db.rollback()
        raise


@router.post("/me/avoid-ingredients", response_model=AvoidIngredientResponse, status_code=status.HTTP_201_CREATED)
def add_avoid_ingredient(
    payload: AvoidIngredientCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: UserProfileService = Depends(get_user_profile_service),
) -> AvoidIngredientResponse:
    try:
        return service.add_avoid_ingredient(db, user_id=current_user.id, ingredient_id=payload.ingredient_id)
    except (NotFoundError, ConflictError, ValidationError):
        db.rollback()
        raise


@router.delete("/me/avoid-ingredients/{avoid_ingredient_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_avoid_ingredient(
    avoid_ingredient_id: UUID,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: UserProfileService = Depends(get_user_profile_service),
) -> Response:
    try:
        service.delete_avoid_ingredient(db, user_id=current_user.id, avoid_ingredient_id=avoid_ingredient_id)
    except NotFoundError:
        db.rollback()
        raise
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/me/trouble-logs", response_model=TroubleLogCreateResponse, status_code=status.HTTP_201_CREATED)
def create_trouble_log(
    payload: TroubleLogCreateRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: TroubleLogService = Depends(get_trouble_log_service),
) -> TroubleLogCreateResponse:
    try:
        return service.create_trouble_log(
            db,
            user_id=current_user.id,
            product_id=payload.product_id,
            reaction_type=payload.reaction_type,
            severity=payload.severity,
            memo=payload.memo,
        )
    except NotFoundError:
        db.rollback()
        raise


@router.get("/me/trouble-logs", response_model=TroubleLogListResponse)
def list_trouble_logs(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    service: TroubleLogService = Depends(get_trouble_log_service),
) -> TroubleLogListResponse:
    return service.list_trouble_logs(db, user_id=current_user.id)
