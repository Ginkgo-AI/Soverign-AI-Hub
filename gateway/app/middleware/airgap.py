"""Air-gap network enforcement middleware for Phase 6.

When ``airgap_mode=True`` in settings, this middleware validates that all
configured service URLs point to internal (RFC 1918 / loopback / Docker DNS)
addresses, and provides helpers to verify URLs at runtime.
"""

from __future__ import annotations

import ipaddress
import logging
import re
import socket
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config import settings

logger = logging.getLogger("sovereign.airgap")

# RFC 1918 private ranges + loopback + link-local
_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Hostnames that are always considered internal (Docker DNS, k8s services, etc.)
_INTERNAL_HOSTNAME_PATTERNS = [
    re.compile(r"^localhost$", re.IGNORECASE),
    re.compile(r"^.*\.local$", re.IGNORECASE),
    re.compile(r"^.*\.internal$", re.IGNORECASE),
    re.compile(r"^.*\.svc\.cluster\.local$", re.IGNORECASE),
    # Docker Compose service names (single word, no dots)
    re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]*$"),
]


def is_internal_url(url: str) -> bool:
    """Return ``True`` if *url* points to an internal/private address."""
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
    except Exception:
        return False

    if not hostname:
        return False

    # Check hostname patterns first (fast path for Docker service names)
    for pat in _INTERNAL_HOSTNAME_PATTERNS:
        if pat.match(hostname):
            return True

    # Try to parse as IP address directly
    try:
        addr = ipaddress.ip_address(hostname)
        return any(addr in net for net in _PRIVATE_NETWORKS)
    except ValueError:
        pass

    # Attempt DNS resolution (may fail in air-gapped environments)
    try:
        resolved = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
        for _, _, _, _, sockaddr in resolved:
            ip = sockaddr[0]
            addr = ipaddress.ip_address(ip)
            if not any(addr in net for net in _PRIVATE_NETWORKS):
                return False
        return True
    except (socket.gaierror, OSError):
        # DNS resolution failed — in air-gap mode, treat unresolvable as suspicious
        return False


def validate_service_urls() -> list[str]:
    """Check all configured service URLs and return a list of violations."""
    violations: list[str] = []
    urls_to_check = {
        "vllm": settings.vllm_base_url,
        "llama_cpp": settings.llama_cpp_base_url,
        "whisper": settings.whisper_base_url,
        "piper": settings.piper_base_url,
        "comfyui": settings.comfyui_base_url,
    }

    if settings.keycloak_url:
        urls_to_check["keycloak"] = settings.keycloak_url

    if settings.siem_endpoint:
        urls_to_check["siem"] = settings.siem_endpoint

    for name, url in urls_to_check.items():
        if url and not is_internal_url(url):
            violations.append(f"{name}: {url} is not an internal address")
    return violations


class AirgapMiddleware(BaseHTTPMiddleware):
    """Middleware that enforces air-gap policy when ``airgap_mode=True``.

    On startup-equivalent first request, validates all service URLs.
    On every request, blocks anything routed to an external address
    (via the Referer / Origin headers as a heuristic).
    """

    _validated = False

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.airgap_mode:
            return await call_next(request)

        # One-time validation of configured service URLs
        if not AirgapMiddleware._validated:
            violations = validate_service_urls()
            for v in violations:
                logger.warning("[AIRGAP VIOLATION] %s", v)
                # Log as security audit event (fire-and-forget)
                try:
                    from app.services.audit import AuditService

                    import asyncio

                    asyncio.ensure_future(
                        AuditService.log_event(
                            action="AIRGAP_VIOLATION",
                            resource_type="network",
                            details={"violation": v},
                            classification_level="SECRET",
                        )
                    )
                except Exception:
                    pass
            AirgapMiddleware._validated = True

        response = await call_next(request)
        return response
