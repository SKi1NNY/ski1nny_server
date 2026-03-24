from typing import Any


class SkinnyError(Exception):
    status_code = 500
    error_code = "internal_server_error"
    message = "An unexpected error occurred."

    def __init__(self, message: str | None = None, *, detail: dict[str, Any] | None = None) -> None:
        self.message = message or self.message
        self.detail = detail or {}
        super().__init__(self.message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": self.message,
            "detail": self.detail,
        }


class ValidationError(SkinnyError):
    status_code = 400
    error_code = "validation_error"
    message = "The request data is invalid."


class InvalidIngredientReferenceError(ValidationError):
    error_code = "invalid_ingredient_reference"
    message = "One or more ingredient references are invalid."


class InvalidAvoidIngredientSuggestionError(ValidationError):
    error_code = "invalid_avoid_ingredient_suggestion"
    message = "One or more suggested avoid ingredients are invalid."


class AuthenticationError(SkinnyError):
    status_code = 401
    error_code = "authentication_error"
    message = "Authentication failed."


class InvalidCredentialsError(AuthenticationError):
    error_code = "invalid_credentials"
    message = "Invalid email or password."


class InvalidRefreshTokenError(AuthenticationError):
    error_code = "invalid_refresh_token"
    message = "Refresh token is invalid."


class PermissionDeniedError(SkinnyError):
    status_code = 403
    error_code = "permission_denied"
    message = "You do not have permission to access this resource."


class InactiveUserError(PermissionDeniedError):
    error_code = "inactive_user"
    message = "User account is inactive."


class DeletedUserError(PermissionDeniedError):
    error_code = "deleted_user"
    message = "User account is deleted."


class NotFoundError(SkinnyError):
    status_code = 404
    error_code = "not_found"
    message = "The requested resource does not exist."


class UserNotFoundError(NotFoundError):
    error_code = "user_not_found"
    message = "User does not exist."


class UserProfileNotFoundError(NotFoundError):
    error_code = "user_profile_not_found"
    message = "User profile does not exist."


class ProductNotFoundError(NotFoundError):
    error_code = "product_not_found"
    message = "Product does not exist."


class TroubleLogNotFoundError(NotFoundError):
    error_code = "trouble_log_not_found"
    message = "Trouble log does not exist."


class AvoidIngredientNotFoundError(NotFoundError):
    error_code = "avoid_ingredient_not_found"
    message = "Avoid ingredient does not exist."


class ConflictError(SkinnyError):
    status_code = 409
    error_code = "conflict"
    message = "The request conflicts with the current resource state."


class DuplicateEmailError(ConflictError):
    error_code = "duplicate_email"
    message = "Email already exists."


class DuplicateBarcodeError(ConflictError):
    error_code = "duplicate_barcode"
    message = "Barcode already exists."


class DuplicateAvoidIngredientError(ConflictError):
    error_code = "duplicate_avoid_ingredient"
    message = "Avoid ingredient already exists."


class ExternalServiceError(SkinnyError):
    status_code = 502
    error_code = "external_service_error"
    message = "An external service request failed."


class InternalServerError(SkinnyError):
    status_code = 500
    error_code = "internal_server_error"
    message = "An unexpected error occurred."
