"""Session auth gate for analyst API routes (matches React RequireAuth).

Embeddings E5: scoped search API tokens may authenticate a small allowlist
of read-only retrieval routes via ``Authorization: Bearer briefr_search_…``.
"""

from __future__ import annotations

import re

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

_CVE_ID_PATH = re.compile(r"^/api/cves/CVE-\d{4}-\d+$", re.IGNORECASE)
_CVE_RELATED_OR_DRAWER = re.compile(
    r"^/api/cves/CVE-\d{4}-\d+/(related|drawer)$", re.IGNORECASE
)
_SEARCH_TOKEN_PREFIX = "briefr_search_"


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


def search_token_path_allowed(path: str, method: str) -> bool:
    """Routes a search service token may call (design §8 scopes)."""
    if method.upper() != "GET":
        return False
    if path == "/api/search/semantic":
        return True
    if _CVE_ID_PATH.fullmatch(path):
        return True
    if _CVE_RELATED_OR_DRAWER.fullmatch(path):
        return True
    return False


def _bearer_token(request: Request) -> str | None:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    return auth[7:].strip() or None


async def session_auth_middleware(request: Request, call_next) -> Response:
    """Require a valid briefr_at session for analyst /api/* routes.

    Search tokens: when ``Authorization: Bearer briefr_search_…`` is present
    and the path is allowlisted, verify the token and skip session cookies.
    """
    if request.method == "OPTIONS" or _skip_session_gate(request.url.path):
        return await call_next(request)

    bearer = _bearer_token(request)
    if bearer and bearer.startswith(_SEARCH_TOKEN_PREFIX):
        if not search_token_path_allowed(request.url.path, request.method):
            return JSONResponse(
                status_code=403,
                content={"detail": "Search token cannot access this route"},
            )
        from database import get_db
        from db.search_tokens import verify_search_token
        from rate_limit import rate_limit_search_token

        try:
            rate_limit_search_token(request)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
                headers=dict(exc.headers or {}),
            )

        db = await get_db()
        try:
            meta = await verify_search_token(db, bearer)
        finally:
            await db.close()
        if not meta:
            return JSONResponse(
                status_code=401, content={"detail": "Invalid search token"}
            )
        request.state.search_token = meta
        request.state.user_username = f"search_token:{meta.get('id')}"
        request.state.user_role = "search_token"
        return await call_next(request)

    from dependencies import require_user

    try:
        await require_user(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    return await call_next(request)
