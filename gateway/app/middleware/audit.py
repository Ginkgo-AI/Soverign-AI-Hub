import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.config import settings


class AuditMiddleware(BaseHTTPMiddleware):
    """Logs every request to the audit trail. Append-only."""

    SKIP_PATHS = {"/health", "/healthz", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.SKIP_PATHS:
            return await call_next(request)

        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.monotonic()

        response = await call_next(request)

        duration_ms = int((time.monotonic() - start) * 1000)

        if settings.environment == "development":
            method = request.method
            path = request.url.path
            status = response.status_code
            print(f"[AUDIT] {request_id} {method} {path} -> {status} ({duration_ms}ms)")

        # TODO: Write structured audit record to PostgreSQL audit_log table
        # This will be implemented in Phase 6 with full structured logging.
        # For now, stdout logging provides basic observability.

        response.headers["X-Request-ID"] = request_id
        return response
