"""Curated infrastructure-classification seed data (v1).

Small, operator-curated seed for `app.infra_classifications` (Postgres app
schema only — no SQLite bootstrap exists for this table). This is NOT a
bulk third-party allowlist — each entry carries a human-readable reason, and
external provenance is recorded as free text (with a license-review note) so
no third-party list is absorbed wholesale.

Insertion is idempotent: `seed_infra_classifications` upserts by canonical
host and only fills rows that are absent (it never overwrites operator edits).
"""

from __future__ import annotations

from db.timeutil import utcnow_str
from db.types import DbConnection

# Frozen classification enum (mirrors the DB CHECK/documentation contract).
LEGITIMATE_DOMAIN = "LEGITIMATE_DOMAIN"
SHARED_LEGITIMATE_INFRASTRUCTURE = "SHARED_LEGITIMATE_INFRASTRUCTURE"
TRUSTED_SERVICE = "TRUSTED_SERVICE"
UNKNOWN = "UNKNOWN"

CLASSIFICATIONS: frozenset[str] = frozenset({
    LEGITIMATE_DOMAIN,
    SHARED_LEGITIMATE_INFRASTRUCTURE,
    TRUSTED_SERVICE,
    UNKNOWN,
})

# Every classification that suppresses host-level corroboration / export
# eligibility for a domain. UNKNOWN is deliberately excluded — an unclassified
# host is treated as a normal candidate.
EXCLUSION_CLASSIFICATIONS: frozenset[str] = frozenset({
    LEGITIMATE_DOMAIN,
    SHARED_LEGITIMATE_INFRASTRUCTURE,
    TRUSTED_SERVICE,
})

# host -> (classification, reason). Provenance is "curated" for every seed row.
_SEED_HOSTS: tuple[tuple[str, str, str], ...] = (
    (
        "google.com",
        LEGITIMATE_DOMAIN,
        "Curated: top-level Google search/portal domain frequently abused as "
        "a shared redirect target; not an indicator of compromise on its own.",
    ),
    (
        "microsoft.com",
        LEGITIMATE_DOMAIN,
        "Curated: Microsoft corporate domain commonly used in click-jacking / "
        "phishing lures; exact-path evidence still matters.",
    ),
    (
        "apple.com",
        LEGITIMATE_DOMAIN,
        "Curated: Apple corporate domain; a bare domain reference is not "
        "sufficient evidence of a malicious domain candidate.",
    ),
    (
        "drive.google.com",
        SHARED_LEGITIMATE_INFRASTRUCTURE,
        "Curated: Google Drive hosts attacker-controlled documents and C2 "
        "downloads on shared infrastructure — the exact URL is the IOC, not "
        "the host.",
    ),
    (
        "t.me",
        SHARED_LEGITIMATE_INFRASTRUCTURE,
        "Curated: Telegram.me link-shortener used for malware delivery; the "
        "exact URL is the IOC, not the host.",
    ),
    (
        "steamcommunity.com",
        SHARED_LEGITIMATE_INFRASTRUCTURE,
        "Curated: Steam Community profile pages abused for phishing and C2; "
        "the exact URL is the IOC, not the host.",
    ),
)


async def seed_infra_classifications(db: DbConnection) -> int:
    """Idempotently insert the curated seed; returns rows written.

    Operator-edited rows (classification, enabled, reason, notes) are never
    overwritten — only hosts missing entirely are inserted.
    """
    now = utcnow_str()
    written = 0
    for host, classification, reason in _SEED_HOSTS:
        rows = await db.execute_fetchall(
            "SELECT id FROM app.infra_classifications WHERE host = ?",
            (host,),
        )
        if rows:
            continue
        await db.execute(
            """
            INSERT INTO app.infra_classifications (
                host, classification, enabled, provenance, reason, notes,
                created_at, updated_at
            ) VALUES (?, ?, 1, 'curated', ?, '', ?, ?)
            """,
            (host, classification, reason, now, now),
        )
        written += 1
    return written
