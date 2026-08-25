# Notification alert tray Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treat the bell as an alert tray: Alerts / Cleared, 24h purge of dismissed rows, keep read ≠ clear and the 5s undo.

**Architecture:** Alias `view=active|cleared` onto the existing `dismissed_at` split; hard-delete dismissed rows from the nightly retention job. Relabel `NotificationBell` copy. No Alembic. Watchlist webhooks unchanged.

**Tech Stack:** FastAPI, existing SQLite/Postgres helpers in `db/user_notifications.py`, `db/cache_retention.py`, React `NotificationBell.jsx`, Node `node:test` source gates.

**Spec:** `docs/superpowers/specs/2026-08-25-notification-alert-tray-design.md`

## Global Constraints

- Do not emit `kev_backlog`. Do not add OS push, email, or a notifications tab.
- Opening the popover must still not call `POST /api/me/notifications/seen`.
- Mark as read must not dismiss. Clear is dismiss.
- `unread_count` = undismissed AND `read_at IS NULL` (all severities).
- Merge gate: `./scripts/verify-local.sh`. Frontend: `cd frontend && npm run test:unit && npm run build`.
- Same-PR docs: `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md`.

## File map

| File | Responsibility |
|------|----------------|
| Modify: `backend/db/user_notifications.py` | `normalize_notification_view`, accept aliases, `purge_cleared_notifications` |
| Modify: `backend/routers/notifications_me.py` | Pass through new view names (422 still from ValueError) |
| Modify: `backend/db/cache_retention.py` | Call purge; add `user_notifications` to cleanup stats |
| Modify: `backend/tests/test_user_notifications.py` | Alias + purge API tests |
| Modify: `backend/tests/test_db_cache_retention.py` | Expected key set includes `user_notifications` |
| Modify: `frontend/src/components/NotificationBell.jsx` | Alerts/Cleared copy; `view` state `active`/`cleared` |
| Modify: `frontend/src/utils/notificationsApi.js` | Default `view: 'active'` |
| Modify: `frontend/src/utils/notificationInboxGate.test.js` | Assert Alerts/Cleared, not Inbox/Done |
| Modify: `frontend/src/pages/admin/DisplayPage.jsx` | Mute help text: alert tray, not inbox |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md` | Shipped truth |

**Do not** add Alembic. **Do not** change webhook emit.

---

### Task 1: View aliases `active` / `cleared`

**Files:**
- Modify: `backend/db/user_notifications.py`
- Modify: `backend/tests/test_user_notifications.py`

**Interfaces:**
- Consumes: existing `list_notifications(..., view: str = "inbox")`
- Produces: `normalize_notification_view(view: str) -> str` returning `"active"` or `"cleared"`; `list_notifications` treats `inbox`/`active` as undismissed and `done`/`cleared` as dismissed

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_user_notifications.py` after `test_list_view_done_excludes_inbox`:

```python
def test_list_view_aliases_active_cleared(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="alias1")
    _login(client, "analyst1")
    nid = client.get("/api/me/notifications?scope=analyst").json()["notifications"][0]["id"]
    client.post(f"/api/me/notifications/{nid}/dismiss")

    active = client.get("/api/me/notifications?scope=analyst&view=active").json()
    inbox = client.get("/api/me/notifications?scope=analyst&view=inbox").json()
    cleared = client.get("/api/me/notifications?scope=analyst&view=cleared").json()
    done = client.get("/api/me/notifications?scope=analyst&view=done").json()

    assert active["notifications"] == []
    assert inbox["notifications"] == []
    assert len(cleared["notifications"]) == 1
    assert len(done["notifications"]) == 1
    assert cleared["unread_count"] == 0


def test_list_view_rejects_unknown(client):
    _login(client, "analyst1")
    res = client.get("/api/me/notifications?scope=analyst&view=archive")
    assert res.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py::test_list_view_aliases_active_cleared tests/test_user_notifications.py::test_list_view_rejects_unknown -q`

Expected: FAIL (`view must be inbox or done` or 422 on `active`).

- [ ] **Step 3: Implement**

At the top of `list_notifications` in `backend/db/user_notifications.py`, replace the `if view not in ("inbox", "done")` check with:

```python
_VIEW_ALIASES = {
    "inbox": "active",
    "active": "active",
    "done": "cleared",
    "cleared": "cleared",
}


def normalize_notification_view(view: str) -> str:
    key = (view or "inbox").strip().lower()
    mapped = _VIEW_ALIASES.get(key)
    if mapped is None:
        raise ValueError("view must be active, cleared, inbox, or done")
    return mapped
```

In `list_notifications`, first line of view handling:

```python
    canonical = normalize_notification_view(view)
    if canonical == "cleared":
        dismissed_clause = "dismissed_at IS NOT NULL"
        order_by = "dismissed_at DESC"
    else:
        dismissed_clause = "dismissed_at IS NULL"
        order_by = "created_at DESC"
```

Keep `Query("inbox")` default on `GET /api/me/notifications`.

- [ ] **Step 4: Re-run tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py -q`

Expected: PASS (including existing `view=inbox` / `view=done` tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/user_notifications.py backend/tests/test_user_notifications.py
git commit -m "feat(notifications): accept active/cleared view aliases"
```

---

### Task 2: Purge dismissed rows after 24 hours

**Files:**
- Modify: `backend/db/user_notifications.py`
- Modify: `backend/db/cache_retention.py`
- Modify: `backend/tests/test_user_notifications.py`
- Modify: `backend/tests/test_db_cache_retention.py`

**Interfaces:**
- Consumes: `utcnow_str` / ISO timestamps already stored on `dismissed_at`
- Produces: `NOTIFICATION_CLEARED_RETENTION_HOURS = 24`; `async def purge_cleared_notifications(db: DbConnection, *, retention_hours: int | None = None) -> int`; `run_retention_cleanup` key `"user_notifications"`

- [ ] **Step 1: Write the failing tests**

Add to `backend/tests/test_user_notifications.py`:

```python
def test_purge_cleared_keeps_active_and_recent(client):
    from db.timeutil import utcnow_str
    from db.user_notifications import purge_cleared_notifications
    from datetime import datetime, timedelta, timezone

    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="keep-active")
    _insert(uid, "analyst", dedupe="old-cleared")
    _insert(uid, "analyst", dedupe="new-cleared")

    old_ts = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat()
    recent_ts = utcnow_str()

    async def _stamp_and_purge():
        db = await get_db()
        try:
            rows = await db.execute_fetchall(
                "SELECT id, dedupe_key FROM user_notifications WHERE user_id = ?",
                (uid,),
            )
            by_key = {r["dedupe_key"]: r["id"] for r in rows}
            await db.execute(
                "UPDATE user_notifications SET dismissed_at = ? WHERE id = ?",
                (old_ts, by_key["old-cleared"]),
            )
            await db.execute(
                "UPDATE user_notifications SET dismissed_at = ? WHERE id = ?",
                (recent_ts, by_key["new-cleared"]),
            )
            await db.commit()
            deleted = await purge_cleared_notifications(db)
            await db.commit()
            left = await db.execute_fetchall(
                "SELECT dedupe_key FROM user_notifications WHERE user_id = ? ORDER BY dedupe_key",
                (uid,),
            )
            return deleted, [r["dedupe_key"] for r in left]
        finally:
            await db.close()

    deleted, keys = run_db_test(_stamp_and_purge())
    assert deleted == 1
    assert keys == ["keep-active", "new-cleared"]
```

In `backend/tests/test_db_cache_retention.py`, add `"user_notifications"` to the `assert set(counts.keys()) == {` frozenset in `test_run_retention_cleanup_returns_counts`.

If `tests/test_cache_retention.py` also asserts the key set, add `"user_notifications"` there too.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py::test_purge_cleared_keeps_active_and_recent tests/test_db_cache_retention.py::test_run_retention_cleanup_returns_counts -q`

Expected: FAIL (`purge_cleared_notifications` missing and/or key set mismatch).

- [ ] **Step 3: Implement purge**

In `backend/db/user_notifications.py`:

```python
from datetime import datetime, timedelta, timezone

NOTIFICATION_CLEARED_RETENTION_HOURS = 24


async def purge_cleared_notifications(
    db: DbConnection,
    *,
    retention_hours: int | None = None,
) -> int:
    hours = (
        NOTIFICATION_CLEARED_RETENTION_HOURS
        if retention_hours is None
        else max(1, int(retention_hours))
    )
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    pg = _is_postgres_connection(db)
    sql = (
        "DELETE FROM user_notifications WHERE dismissed_at IS NOT NULL AND dismissed_at < $1"
        if pg
        else "DELETE FROM user_notifications WHERE dismissed_at IS NOT NULL AND dismissed_at < ?"
    )
    cursor = await db.execute(sql, (cutoff,))
    return int(getattr(cursor, "rowcount", 0) or 0)
```

In `backend/db/cache_retention.py` `run_retention_cleanup` stats dict, add:

```python
        "user_notifications": await purge_cleared_notifications(db),
```

Import `purge_cleared_notifications` from `db.user_notifications` at the call site (top of file is fine).

- [ ] **Step 4: Re-run tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py tests/test_db_cache_retention.py tests/test_cache_retention.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/user_notifications.py backend/db/cache_retention.py backend/tests/test_user_notifications.py backend/tests/test_db_cache_retention.py backend/tests/test_cache_retention.py
git commit -m "feat(notifications): purge cleared alerts after 24h"
```

---

### Task 3: Bell copy — Alerts / Cleared

**Files:**
- Modify: `frontend/src/components/NotificationBell.jsx`
- Modify: `frontend/src/utils/notificationsApi.js`
- Modify: `frontend/src/utils/notificationInboxGate.test.js`
- Modify: `frontend/src/pages/admin/DisplayPage.jsx`

**Interfaces:**
- Consumes: GET `view=active|cleared` from Task 1
- Produces: UI labels Alerts / Cleared; default fetch `view: 'active'`

- [ ] **Step 1: Write the failing gate assertions**

Replace the Done-specific cases in `frontend/src/utils/notificationInboxGate.test.js` so they match the new copy:

```javascript
  it('does not label dismiss as Mark read', () => {
    assert.doesNotMatch(src, /Mark read/)
    assert.doesNotMatch(src, /Mark all read/)
    assert.match(src, /Mark all as read/)
    assert.match(src, /Clear all/)
  })

  it('labels the tray Alerts and Cleared, not Inbox or Done', () => {
    assert.match(src, /Alerts/)
    assert.match(src, /Cleared/)
    assert.doesNotMatch(src, /<TabsTrigger value="inbox">Inbox<\/TabsTrigger>/)
    assert.doesNotMatch(src, /<TabsTrigger value="done">Done<\/TabsTrigger>/)
    assert.doesNotMatch(src, /Moved to Done/)
  })

  it('clears only the loaded notification ids', () => {
    assert.doesNotMatch(src, /dismissAllNotifications/)
    assert.match(src, /const ids = filteredItems\.map\(item => item\.id\)/)
    assert.match(
      src,
      /Promise\.allSettled\(ids\.map\(id => dismissNotification\(id\)\)\)/,
    )
  })
```

Rename the old `moves only the loaded notification ids to Done` test to the Clear wording above (do not leave two copies).

- [ ] **Step 2: Run the gate to verify it fails**

Run: `cd frontend && npm run test:unit -- src/utils/notificationInboxGate.test.js`

Expected: FAIL (still contains Inbox/Done tabs).

- [ ] **Step 3: Implement UI**

In `frontend/src/utils/notificationsApi.js`:

```javascript
export async function fetchNotifications(
  scope = 'analyst',
  { view = 'active', limit = 50 } = {},
) {
```

In `NotificationBell.jsx`:

- `useState('active')` instead of `'inbox'`.
- `actionLabel = view === 'cleared' ? 'Restore' : 'Clear'`
- Undo labels: `'Cleared'` and `` `${n} notification(s) cleared` ``
- Errors: `could not be cleared` (not moved to Done)
- `panelTitle = view === 'cleared' ? 'Cleared' : 'Alerts'`
- Dropdown: `Clear all`
- Tabs: `value="active"` / `value="cleared"` with labels Alerts / Cleared
- `handleContentKeyDown`: `view === 'cleared'` for restore
- Empty titles: `'No alerts.'` and `'Nothing cleared in the last 24 hours.'`

Keep `handleDone` / `handleMoveAllDone` function names or rename to `handleClear` / `handleClearLoaded` — if renamed, update all call sites in the same file.

DisplayPage mute lede: change “Muted types are not added to the inbox” to “Muted types are not added to the alert tray.”

- [ ] **Step 4: Re-run frontend tests**

Run: `cd frontend && npm run test:unit && npm run build`

Expected: PASS / build OK.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/NotificationBell.jsx frontend/src/utils/notificationsApi.js frontend/src/utils/notificationInboxGate.test.js frontend/src/pages/admin/DisplayPage.jsx
git commit -m "feat(notifications): relabel bell as Alerts/Cleared"
```

---

### Task 4: Docs

**Files:**
- Modify: `docs/API_REFERENCE.md` (`GET /api/me/notifications` and restore/dismiss bullets)
- Modify: `docs/PRODUCT_STATUS.md` Notification center sentence (Admin table)

**Interfaces:**
- Consumes: Tasks 1–3 behavior
- Produces: shipped copy matches the tray, not GitHub Inbox

- [ ] **Step 1: Update API_REFERENCE**

Change the notifications section so it states:

- `view` = `inbox` \| `done` \| `active` \| `cleared` (`inbox`=`active`, `done`=`cleared`)
- Opening the tray does not mark read
- Dismiss moves a row to **Cleared**; rows with `dismissed_at` older than 24 hours are deleted by `cache_retention_cleanup`
- Restore returns a row to **Alerts** or 404 if already purged

- [ ] **Step 2: Update PRODUCT_STATUS**

Replace Inbox/Done wording in the Notification center bullet with Alerts/Cleared and 24h purge. Bump **Last updated** date if that line exists.

- [ ] **Step 3: Run verify-local**

Run: `./scripts/verify-local.sh`

Expected: green (or documented SQLite-only skips).

- [ ] **Step 4: Commit**

```bash
git add docs/API_REFERENCE.md docs/PRODUCT_STATUS.md
git commit -m "docs: notification alert tray Alerts/Cleared + 24h purge"
```
