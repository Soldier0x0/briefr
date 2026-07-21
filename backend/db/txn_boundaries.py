"""Transaction boundaries between SQL work and outbound source I/O.

Postgres ``command_timeout`` (``DATABASE_POOL_COMMAND_TIMEOUT_SECONDS``) is a
**single shared budget for SQL statements** on pooled connections. Feed/source
HTTP timeouts are independent and intentionally different per API (CIRCL ~25s,
Sploitus ~30s, ThreatFox ~120s, Nuclei/ExploitDB ~180s, …).

Never nest source HTTP/DNS latency inside an open write transaction: concurrent
jobs waiting on ``cves`` / ``feed_cache`` locks will burn the shared SQL timeout
and fail with ``Database command timeout``. Commit (or close the connection)
before outbound calls; keep source timeouts in the feed modules, not by raising
the global DB command timeout.
"""

from __future__ import annotations


async def commit_before_source_io(db) -> None:
    """Flush pending writes so source HTTP cannot hold row locks.

    Safe when there is nothing to commit. Call immediately before any outbound
    feed/API request that may take longer than a typical SQL statement.
    """
    await db.commit()
