"""Safe HTTP error helpers — log server-side detail, return bounded client text."""

from __future__ import annotations

import logging

from fastapi import HTTPException

logger = logging.getLogger(__name__)

_ADMIN_OPERATION_FAILED = "Operation failed. Check server logs or support pack for details."


def raise_admin_operation_failed(
    exc: BaseException,
    *,
    status_code: int = 500,
    client_message: str = _ADMIN_OPERATION_FAILED,
    log_message: str = "Admin operation failed",
) -> None:
    logger.exception("%s", log_message)
    raise HTTPException(status_code=status_code, detail=client_message) from exc


def admin_error_detail(exc: BaseException, *, fallback: str = _ADMIN_OPERATION_FAILED) -> str:
    """Return a bounded client-safe message for validation-style admin errors."""
    message = str(exc).strip()
    if not message or len(message) > 200:
        return fallback
    return message
