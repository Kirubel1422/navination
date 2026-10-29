"""Request IDs, sanitized access logs, and request size limits."""

import logging
import secrets
import time

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import get_settings

logger = logging.getLogger("navination.access")


class RequestContextMiddleware:
    """Assigns a request ID, enforces the body size limit and logs method/path/status only.

    Query strings, headers (including Authorization) and bodies are never logged.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = "req_" + secrets.token_hex(8)
        scope.setdefault("state", {})["request_id"] = request_id
        limit = get_settings().max_request_bytes
        started = time.perf_counter()
        status_holder = {"status": 500}

        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _send_too_large(scope, send, request_id)
            logger.info("%s %s 413 request_id=%s", scope["method"], scope["path"], request_id)
            return

        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _BodyTooLarge()
            return message

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
                message.setdefault("headers", [])
                message["headers"].append((b"x-request-id", request_id.encode()))
            await send(message)

        try:
            await self.app(scope, limited_receive, send_wrapper)
        except _BodyTooLarge:
            await _send_too_large(scope, send, request_id)
            status_holder["status"] = 413
        finally:
            elapsed = (time.perf_counter() - started) * 1000
            logger.info(
                "%s %s %s %.1fms request_id=%s",
                scope["method"],
                scope["path"],
                status_holder["status"],
                elapsed,
                request_id,
            )


class _BodyTooLarge(Exception):
    pass


async def _send_too_large(scope: Scope, send: Send, request_id: str) -> None:
    import json

    body = json.dumps(
        {
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request body is too large.",
                "details": [],
                "request_id": request_id,
            }
        }
    ).encode()
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"x-request-id", request_id.encode()),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})
