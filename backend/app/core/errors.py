from __future__ import annotations

import contextvars
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm.exc import StaleDataError


_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)


class ErrorResponse(BaseModel):
    detail: Any
    code: str
    request_id: str


STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "AUTHENTICATION_REQUIRED",
    403: "PERMISSION_DENIED",
    404: "NOT_FOUND",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
    500: "INTERNAL_ERROR",
}


def current_request_id() -> str | None:
    return _request_id.get()


class RequestContextMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        request_id = headers.get(b"x-request-id", b"").decode().strip()
        if not request_id or len(request_id) > 128:
            request_id = str(uuid.uuid4())
        token = _request_id.set(request_id)

        async def send_with_request_id(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                message.setdefault("headers", []).append(
                    (b"x-request-id", request_id.encode())
                )
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            _request_id.reset(token)


def _payload(status_code: int, detail: Any) -> dict[str, Any]:
    request_id = current_request_id() or str(uuid.uuid4())
    embedded_code = detail.get("code") if isinstance(detail, dict) else None
    return {
        "detail": detail,
        "code": embedded_code or STATUS_CODES.get(status_code, "HTTP_ERROR"),
        "request_id": request_id,
    }


async def http_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, HTTPException):
        raise exc
    return JSONResponse(
        status_code=exc.status_code,
        content=_payload(exc.status_code, exc.detail),
        headers=exc.headers,
    )


async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder(_payload(422, exc.errors())),
    )


async def stale_data_error_handler(request: Request, exc: Exception) -> JSONResponse:
    if not isinstance(exc, StaleDataError):
        raise exc
    return JSONResponse(
        status_code=409,
        content=_payload(
            409,
            {
                "code": "CONCURRENT_MODIFICATION",
                "message": "The resource changed during this operation",
            },
        ),
    )


DEFAULT_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    status_code: {
        "model": ErrorResponse,
        "description": description,
    }
    for status_code, description in {
        400: "Bad request",
        401: "Authentication required",
        403: "Permission denied",
        404: "Resource not found",
        409: "Conflict",
        413: "Payload too large",
        422: "Validation error",
        429: "Rate limit exceeded",
        503: "Service temporarily unavailable",
        500: "Internal server error",
    }.items()
}
