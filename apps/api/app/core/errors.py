"""Stable error codes and the shared ErrorEnvelope handlers."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("navination")


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or []
        self.headers = headers


def not_found(message: str = "The requested resource was not found.") -> AppError:
    return AppError(404, "NOT_FOUND", message)


def unauthorized(message: str = "A valid guest session is required.") -> AppError:
    return AppError(401, "UNAUTHORIZED", message, headers={"WWW-Authenticate": "Bearer"})


def session_expired() -> AppError:
    return AppError(
        401,
        "SESSION_EXPIRED",
        "This guest session has expired. Start a new session to continue.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def context_stale(message: str, details: list[dict[str, Any]] | None = None) -> AppError:
    return AppError(409, "CONTEXT_STALE", message, details)


def validation_error(message: str, field: str | None = None) -> AppError:
    return AppError(422, "VALIDATION_ERROR", message, [{"field": field, "message": message}])


def request_id_of(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def envelope(
    request: Request, code: str, message: str, details: list[dict[str, Any]] | None = None
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": [
                {"field": d.get("field"), "message": str(d.get("message", ""))}
                for d in (details or [])
            ],
            "request_id": request_id_of(request),
        }
    }


_STATUS_CODES = {
    400: "VALIDATION_ERROR",
    401: "UNAUTHORIZED",
    404: "NOT_FOUND",
    405: "NOT_FOUND",
    409: "CONTEXT_STALE",
    413: "VALIDATION_ERROR",
    415: "VALIDATION_ERROR",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    503: "SERVICE_UNAVAILABLE",
}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            envelope(request, exc.code, exc.message, exc.details),
            status_code=exc.status_code,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = []
        for err in exc.errors():
            loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
            details.append({"field": ".".join(loc) or None, "message": err.get("msg", "Invalid")})
        return JSONResponse(
            envelope(request, "VALIDATION_ERROR", "The request was not valid.", details),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(exc.status_code, "INTERNAL_ERROR")
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        if exc.status_code == 404:
            message = "The requested resource was not found."
        return JSONResponse(
            envelope(request, code, message), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error request_id=%s", request_id_of(request))
        return JSONResponse(
            envelope(request, "INTERNAL_ERROR", "An unexpected error occurred."),
            status_code=500,
        )
