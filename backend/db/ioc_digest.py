"""Fixed-width IOC value digests for btree index lookups.

PostgreSQL btree index entries are capped at ~2704 bytes (~1/3 of an 8 KB page).
Full URLs from PhishTank, URLhaus, or OTX can exceed that when indexed on raw
``ioc_value``. Store a fixed-width digest of the **canonical stored value**
(32 hex chars) in indexed columns; keep the full value in ``ioc_value`` for
display and evidence. URL path case is preserved (same as ``normalize_ioc``).
"""

from __future__ import annotations

import hashlib


def ioc_value_digest(ioc_value: str) -> str:
    """Return a fixed-width digest for equality lookups on canonical ``ioc_value``."""
    material = (ioc_value or "").strip()
    return hashlib.md5(material.encode("utf-8"), usedforsecurity=False).hexdigest()
