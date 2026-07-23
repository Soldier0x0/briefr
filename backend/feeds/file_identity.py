"""Whole-file feed identity helpers (Q5).

Reusable for EPSS CSV today and CTID/other bulk files later:
store ``{score_date, sha256}`` in sync_state after a successful apply;
matching sha256 skips decompress/parse/apply on the next run.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from db.sync_state import get_sync_state_value, set_sync_state_value
from db.types import DbConnection

logger = logging.getLogger(__name__)

EPSS_FILE_IDENTITY_KEY = "epss_csv_file_identity"
SIGMAHQ_ARCHIVE_IDENTITY_KEY = "sigmahq_archive_identity"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_epss_score_date(csv_text: str) -> str | None:
    """Extract ``#score_date:YYYY-MM-DD`` from EPSS CSV comment header."""
    for line in csv_text.split("\n", 20)[:20]:
        if not line.startswith("#"):
            continue
        lower = line.lower()
        if "score_date" in lower:
            # formats: #score_date:2024-01-01 or # score_date: 2024-01-01
            for part in line.replace("#", "").split(","):
                if "score_date" in part.lower():
                    _, _, rest = part.partition(":")
                    date = rest.strip().split()[0] if rest.strip() else ""
                    if len(date) >= 10 and date[4] == "-" and date[7] == "-":
                        return date[:10]
    return None


async def get_file_identity(db: DbConnection, key: str) -> dict[str, Any] | None:
    raw = await get_sync_state_value(db, key)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        logger.warning(
            "Corrupt file identity JSON for key=%s; treating as missing",
            key,
            exc_info=True,
        )
        return None
    if not isinstance(data, dict):
        return None
    return data


async def set_file_identity(
    db: DbConnection,
    key: str,
    *,
    sha256: str,
    score_date: str | None = None,
    commit_sha: str | None = None,
    synced_at: str | None = None,
) -> None:
    """Persist feed identity JSON.

    EPSS uses ``sha256`` + ``score_date``. SigmaHQ uses ``sha256`` +
    ``commit_sha`` + ``synced_at``. Extra keys are omitted when ``None``.
    """
    payload: dict[str, Any] = {"sha256": sha256}
    if score_date is not None or (commit_sha is None and synced_at is None):
        # Preserve EPSS shape when callers only pass sha256/score_date.
        payload["score_date"] = score_date or ""
    if commit_sha is not None:
        payload["commit_sha"] = commit_sha
    if synced_at is not None:
        payload["synced_at"] = synced_at
    await set_sync_state_value(db, key, json.dumps(payload))


async def clear_file_identity(db: DbConnection, key: str) -> None:
    await set_sync_state_value(db, key, "")
    logger.info("Cleared file identity key=%s", key)


def identity_matches(stored: dict | None, *, sha256: str) -> bool:
    if not stored:
        return False
    return (stored.get("sha256") or "") == sha256


def commit_identity_matches(stored: dict | None, *, commit_sha: str) -> bool:
    if not stored:
        return False
    return (stored.get("commit_sha") or "") == commit_sha
