"""Full audit middleware for Phase 6.

Captures structured audit records for every request and writes them to
PostgreSQL via the batched AuditService buffer.  Replaces the Phase-1
stdout-only stub.
"""

import json
import time
import uuid

from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings
from app.services.audit import _redact, _summarise_body, buffer_audit_record

_ALGORITHM = "HS256"


def _extract_user_id(request: Request) -> uuid.UUID | None:
    """Best-effort extraction of user_id from the Authorization header JWT."""
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[7:]
    try:
        payload = jwt.decode(token, settings.gateway_secret_key, algorithms=[_ALGORITHM])
        sub = payload.get("sub")
        return uuid.UUID(sub) if sub else None
    except (JWTError, ValueError):
        return None


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs every request to the audit trail via batched DB writes."""

    SKIP_PATHS = {"/health", "/healthz", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        # Capture request body for POST/PUT (read and reassign)
        body_summary: str | None = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                raw = await request.body()
                body_summary = _summarise_body(raw)
            except Exception:
                body_summary = None

        response = await call_next(request)

        duration_ms = int((time.monotonic() - start) * 1000)
        user_id = _extract_user_id(request)
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")[:200]

        # Map method+path to action/resource_type
        method = request.method
        path = request.url.path
        action = f"{method} {path}"
        resource_type = path.split("/")[2] if len(path.split("/")) > 2 else "system"

        record = {
            "user_id": user_id,
            "action": action[:100],
            "resource_type": resource_type[:100],
            "resource_id": request_id,
            "request_summary": body_summary,
            "response_summary": f"status={response.status_code} duration={duration_ms}ms",
            "ip_address": ip_address,
            "classification_level": "UNCLASSIFIED",
            "metadata_": {
                "method": method,
                "path": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "user_agent": user_agent,
            },
        }

        # Non-blocking write to buffer
        await buffer_audit_record(record)

        response.headers["X-Request-ID"] = request_id
        return response
