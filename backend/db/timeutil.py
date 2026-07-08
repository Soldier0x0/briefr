"""Shared UTC timestamp helpers for DB writes."""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow_str() -> str:
    """Current UTC time as 'YYYY-MM-DD HH:MM:SS' — bound param, not SQL ``datetime('now')``."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
