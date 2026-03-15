from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import SkinnyError

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(SkinnyError, skinny_error_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_error_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)


async def skinny_error_handler(_: Request, exc: SkinnyError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content=exc.to_dict())


async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    message, detail = _normalize_http_detail(exc.detail)
    error_code = _status_to_error_code(exc.status_code)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": error_code,
            "message": message,
            "detail": detail,
        },
    )


async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "request_validation_error",
            "message": "The request payload is invalid.",
            "detail": {"errors": exc.errors()},
        },
    )


async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled application error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "internal_server_error",
            "message": "An unexpected error occurred.",
            "detail": {},
        },
    )


def _normalize_http_detail(detail: Any) -> tuple[str, dict[str, Any]]:
    if isinstance(detail, str):
        return detail, {}
    if isinstance(detail, dict):
        message = detail.get("message", HTTPStatus.BAD_REQUEST.phrase)
        extra_detail = {key: value for key, value in detail.items() if key != "message"}
        return message, extra_detail
    return HTTPStatus.BAD_REQUEST.phrase, {}


def _status_to_error_code(status_code: int) -> str:
    if status_code == 400:
        return "bad_request"
    if status_code == 401:
        return "authentication_error"
    if status_code == 403:
        return "permission_denied"
    if status_code == 404:
        return "not_found"
    if status_code == 409:
        return "conflict"
    if status_code == 422:
        return "request_validation_error"
    if 500 <= status_code < 600:
        return "internal_server_error"
    try:
        return HTTPStatus(status_code).name.lower()
    except ValueError:
        return "http_error"
