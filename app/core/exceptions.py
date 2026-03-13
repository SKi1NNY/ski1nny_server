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


class NotFoundError(SkinnyError):
    status_code = 404
    error_code = "not_found"
    message = "The requested resource does not exist."


class ConflictError(SkinnyError):
    status_code = 409
    error_code = "conflict"
    message = "The request conflicts with the current resource state."


class ExternalServiceError(SkinnyError):
    status_code = 502
    error_code = "external_service_error"
    message = "An external service request failed."
