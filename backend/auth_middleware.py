"""Session auth gate for analyst API routes (matches React RequireAuth)."""

from __future__ import annotations

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

# Public without app login — wallboard uses its own token on /api/wallboard data routes.
_PUBLIC_PREFIXES = (
    "/api/auth/",
    "/api/wallboard/",
)

_PUBLIC_EXACT = frozenset(
    {
        "/api/health",
        "/api/health/live",
        "/api/docs",
        "/api/redoc",
        "/api/openapi.json",
    }
)

# Already gated by require_admin on the router / inline.
_ADMIN_PREFIXES = (
    "/api/admin/",
    "/api/refresh",
)


def _is_public_api_path(path: str) -> bool:
    if path in _PUBLIC_EXACT:
        return True
    return any(path.startswith(prefix) for prefix in _PUBLIC_PREFIXES)


def _skip_session_gate(path: str) -> bool:
    if not path.startswith("/api/"):
        return True
    if _is_public_api_path(path):
        return True
    return any(path.startswith(prefix) for prefix in _ADMIN_PREFIXES)


async def session_auth_middleware(request: Request, call_next) -> Response:
    """Require a valid briefr_at session for analyst /api/* routes."""
    if request.method == "OPTIONS" or _skip_session_gate(request.url.path):
        return await call_next(request)

    from dependencies import require_user

    try:
        await require_user(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return await call_next(request)
