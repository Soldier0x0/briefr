"""Fixed-width IOC value digests for btree index lookups.

PostgreSQL btree index entries are capped at ~2704 bytes (~1/3 of an 8 KB page).
Full URLs from PhishTank, URLhaus, or OTX can exceed that when indexed on raw
``ioc_value``. Store ``md5(lower(ioc_value))`` (32 hex chars) in indexed columns
instead; keep the full value in ``ioc_value`` for display and evidence.
"""

from __future__ import annotations

import hashlib


def ioc_value_digest(ioc_value: str) -> str:
    """Return a fixed-width digest for case-insensitive IOC equality lookups."""
    normalized = (ioc_value or "").strip().lower()
    return hashlib.md5(normalized.encode("utf-8"), usedforsecurity=False).hexdigest()
