# Notification alert tray — design spec

**Date:** 2026-08-25  
**Status:** Approved for planning (prior operator thread: Inbox/Done is the wrong metaphor for a bell/badge/chime).  
**Plan:** `docs/superpowers/plans/2026-08-25-notification-alert-tray-plan.md`  
**Supersedes:** `docs/superpowers/specs/2026-08-24-notification-inbox-design.md` §4.2 (Done as an unbounded second pile) and GitHub-inbox copy. Keep §4.3 honest verbs (read ≠ clear), Popover, mutes, no open-as-seen.

Related: `frontend/src/components/NotificationBell.jsx`, `backend/db/user_notifications.py`, `backend/routers/notifications_me.py`, `backend/db/cache_retention.py`.

---

## 1. Problem

The shipped bell is a **notification-alert component** (badge, chime, row, 5s undo). The UI still talks like mail: **Inbox** / **Done**, “Moved to Done”, restore from a second tab.

That is a filing cabinet. An alert that has been handled should leave the active tray. A **Cleared** buffer exists only so a mis-click can be undone for a short time. It is not a notification log, not a work queue, and not GitHub Inbox.

Facts in code today:

- `view=inbox|done` in `list_notifications`; Done = `dismissed_at` set.
- List cap 50 most recent Done; older dismissed rows stay in `user_notifications` forever.
- `cache_retention.py` does **not** purge `user_notifications`.
- 5s undo only covers the last clear; Restore on the Done tab can revive any listed row.

Watchlist **webhooks** (`watchlist_alert` Discord/Telegram) are a different channel. This spec does not change them.

## 2. Approaches considered

| Approach | Pros | Cons |
|----------|------|------|
| **A. Alerts + Cleared (24h then hard-delete)** | Matches alert semantics; undo + Restore still work; no new tab; no Alembic | Operators who wanted an archive lose it after 24h |
| B. Keep Inbox/Done, add Empty Done + TTL | Less copy churn | Still teaches “mail”; archive remains the product |
| C. Single list, 5s undo only, no second tab | Purest alert tray | Accidental clear after 5s is unrecoverable |

**Chosen: A.** Keep two tabs. Relabel. Bound Cleared. Purge dismissed rows after 24 hours. Do not add a third “Archive” view.

## 3. Product contract

### Actors

- Analyst: header bell, `scope=analyst`.
- Admin: header + StatusBar bells, `scope=all`, Intel/Ops chips unchanged.

### Verbs (unchanged meaning, new copy)

| User action | Copy | API / DB |
|-------------|------|----------|
| Open popover | — | Still does **not** mark read |
| Open row | — | `POST .../{id}/read` then navigate |
| Mark as read / Mark all as read | unchanged | `read_at` only; row stays in **Alerts** |
| Clear one / Clear all loaded | **Clear** / **Clear all** | existing dismiss endpoints (`dismissed_at`) |
| 5s undo | **Cleared** (not “Moved to Done”) | `POST .../{id}/restore` |
| Restore from Cleared | **Restore** | same restore; 404 if already purged |
| Mute type | unchanged | `notification_mutes`; does not disable Discord/Telegram |

### Views

| UI | Canonical `view` | Legacy alias | SQL |
|----|------------------|--------------|-----|
| Alerts | `active` | `inbox` | `dismissed_at IS NULL` |
| Cleared | `cleared` | `done` | `dismissed_at IS NOT NULL` ORDER BY `dismissed_at` DESC |

Default GET `view` stays `inbox` so existing clients keep working. Invalid view → 422.

`unread_count` always counts **active** unread (`dismissed_at IS NULL AND read_at IS NULL`), even when listing Cleared.

### Retention

- `NOTIFICATION_CLEARED_RETENTION_HOURS = 24` (module constant in `db/user_notifications.py`).
- Nightly `cache_retention_cleanup` deletes rows where `dismissed_at IS NOT NULL` and `dismissed_at` is older than 24h.
- Active (undismissed) rows are never deleted by this sweep (user delete-account already removes by `user_id`).
- No Empty Cleared button in v1 (TTL is the cancel). No admin “notification log”.

### Empty copy

- Alerts: `No alerts.`
- Cleared: `Nothing cleared in the last 24 hours.`

### Out of scope

- Browser / OS push, email, quiet hours, per-user webhooks, `tenant_id`.
- KEV Forge gaps → bell (`kev_backlog`).
- Changing emit allowlist or mute keys.
- Pagination beyond the existing 50-row cap.
- Configurable TTL in Admin → Config (constant is enough).

## 4. Acceptance examples

- Dismiss then GET `view=cleared` and `view=done` both return the row; GET `view=active` and `view=inbox` do not.
- Insert a dismissed row with `dismissed_at` = 48h ago; `purge_cleared_notifications` deletes it; a dismissed row from 1h ago remains; an undismissed row from 48h ago remains.
- `run_retention_cleanup` returns a `user_notifications` count key.
- NotificationBell source gate: tabs say Alerts / Cleared; no user-visible `Inbox` / `Done` strings except possible comments. `E` still clears/restores.
- Opening the popover still must not call `POST /seen`.

## 5. Risks

- Operators who treated Done as history lose rows after 24h. Document in PRODUCT_STATUS.
- ISO timestamp compare on SQLite vs Postgres: use the same cutoff helper style as `purge_old_resource_metrics` (`utcnow` minus timedelta, ISO string compare on stored UTC strings).
