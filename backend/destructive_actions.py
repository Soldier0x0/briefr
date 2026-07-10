"""Single source of truth for confirm-gated destructive admin actions.

Generalizes the confirm-text pattern that previously lived only in
routers/admin.py's storage-purge map (_PURGE_CONFIRM_MAP), so every
destructive action — not just storage purges — is gated the same way and
the frontend can render confirm dialogs generically via
GET /api/admin/destructive-actions instead of hardcoding confirm words
per page.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DestructiveAction:
    id: str
    confirm_word: str | None
    description: str


DESTRUCTIVE_ACTIONS: tuple[DestructiveAction, ...] = (
    DestructiveAction(
        "storage.purge.ioc_cache", "clear",
        "Deletes all rows from ioc_cache. Next lookups will re-query external APIs.",
    ),
    DestructiveAction(
        "storage.purge.feed_cache", "clear",
        "Deletes all rows from feed_cache. Next incident feed load will be slower.",
    ),
    DestructiveAction(
        "storage.purge.epss_history_old", "prune",
        "Deletes epss_history rows older than 90 days.",
    ),
    DestructiveAction(
        "storage.purge.change_history_old", "prune",
        "Deletes cve_change_history rows older than 90 days.",
    ),
    DestructiveAction(
        "storage.purge.rejected_cves", "purge",
        "Removes CVEs with 'Rejected reason:' in description.",
    ),
    DestructiveAction(
        "storage.purge.nvd_watermark", "backfill",
        "Clears the NVD sync watermark. Next NVD sync re-fetches from NVD_DAYS_BACK days ago.",
    ),
    DestructiveAction(
        "storage.purge.epss_backfill_reset", None,
        "Clears the epss_backfill_done marker. Next startup re-runs full backfill.",
    ),
    DestructiveAction(
        "scheduler.pause_all", "pause",
        "Pauses every active scheduler job. No scheduled syncs will run until resumed.",
    ),
    DestructiveAction(
        "scheduler.resume_all", "resume",
        "Resumes every paused scheduler job.",
    ),
    DestructiveAction(
        "watchlist.clear_snoozes", "clear",
        "Removes every legacy snooze entry from the watchlist table.",
    ),
    DestructiveAction(
        "system.restart", "restart",
        "Immediately restarts the backend. Any in-progress jobs will be interrupted.",
    ),
    DestructiveAction(
        "system.restart.drain", None,
        "Waits for running jobs to finish, then restarts the backend gracefully.",
    ),
    DestructiveAction(
        "database.migrate", "migrate",
        "Copies every row from the current SQLite database into the target "
        "PostgreSQL database, replacing any existing data there.",
    ),
    DestructiveAction(
        "webhook.destination.delete", "delete",
        "Permanently removes a database-backed webhook destination.",
    ),
)

_BY_ID: dict[str, DestructiveAction] = {a.id: a for a in DESTRUCTIVE_ACTIONS}


def get_action(action_id: str) -> DestructiveAction | None:
    return _BY_ID.get(action_id)


def require_confirm(action_id: str, confirm_text: str) -> None:
    """Raise ValueError if confirm_text doesn't match the action's required word.

    Unknown action_ids are treated as requiring no specific word (callers
    that pass an id not in the registry get no protection from this
    function — the registry is additive, not the sole gate).
    """
    action = get_action(action_id)
    required = action.confirm_word if action else None
    if required is not None and confirm_text != required:
        raise ValueError(f"Type '{required}' to confirm")


def list_actions() -> list[dict]:
    return [
        {"id": a.id, "confirm_word": a.confirm_word, "description": a.description}
        for a in DESTRUCTIVE_ACTIONS
    ]
