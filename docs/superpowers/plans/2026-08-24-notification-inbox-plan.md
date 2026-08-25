# Notification inbox 10/10 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make BRIEFR’s in-app notifications a trustworthy GitHub-style inbox (read ≠ done, honest badge, four async states) with a Radix Popover UI that meets `docs/design/design-system.md` §4 / §18 / §23.

**Architecture:** Keep `user_notifications.read_at` / `dismissed_at`. Stop treating open-panel as mark-seen and stop labeling dismiss as “Mark read”. Extend `/api/me/notifications` with `view`, `scope=all`, `POST /read`, `POST /read-all`, `POST /{id}/restore`. Rebuild `NotificationBell` on a new `Popover` primitive. Mutes live in `display_prefs_json.notification_mutes` (no Alembic).

**Tech Stack:** FastAPI, existing SQLite/Postgres SQL helpers, React/Vite, `@radix-ui/react-popover`, Lucide, `AsyncState` / `EmptyState` / `ErrorState` / `Badge` / `Tabs` / `DropdownMenu`, Node `node:test`.

**Spec:** `docs/superpowers/specs/2026-08-24-notification-inbox-design.md`

## Global Constraints

- Semantic tokens only; dark-only; Lucide icons; no emoji; no `transform: scale` on the bell.
- Do not emit `kev_backlog` (PR #869). Do not add browser push, email, or a new analyst tab.
- `DropdownMenu` is not the inbox surface; `Popover` is.
- Opening the popover must not call `POST /api/me/notifications/seen`.
- “Mark as read” must not call dismiss. “Done” is dismiss.
- `unread_count` = undismissed AND `read_at IS NULL` (all severities).
- Merge gate: `./scripts/verify-local.sh`. Frontend: `cd frontend && npm run test:unit && npm run build`.
- Docs in the same PR: `PRODUCT_STATUS.md`, `API_REFERENCE.md`, design-system §18 Popover shipped.

## File map

| File | Responsibility |
|------|----------------|
| Modify: `backend/db/user_notifications.py` | `list_notifications(view=)`, `count_unread` all severities, `mark_one_read`, `mark_scope_read`, restore already exists |
| Modify: `backend/routers/notifications_me.py` | `scope=all`, `view=`, read/read-all/restore routes |
| Modify: `backend/notifications/emit.py` | Skip muted categories per user |
| Modify: `backend/preferences/display_validate.py` | `notification_mutes` defaults + validate |
| Modify: `backend/preferences/repo.py` | Patch/merge mutes |
| Modify: `backend/routers/me.py` | Pydantic field for mutes |
| Modify: `backend/tests/test_user_notifications.py` | Contract tests |
| Create: `frontend/src/utils/notificationInbox.js` | Destination, grouping, aria label, mute defaults (pure) |
| Create: `frontend/src/utils/notificationInbox.test.js` | Unit tests |
| Create: `frontend/src/utils/timeAgo.js` | Shared relative time (from CVECard logic) |
| Create: `frontend/src/utils/timeAgo.test.js` | Relative time tests |
| Create: `frontend/src/components/ui/Popover.jsx` | Radix Popover |
| Modify: `frontend/src/components/ui/index.js`, `ui.css` | Export + `.ui-popover-content` |
| Modify: `frontend/package.json` | `@radix-ui/react-popover` |
| Modify: `frontend/src/utils/notificationsApi.js` | New endpoints; `view` / `scope=all` |
| Rewrite: `frontend/src/components/NotificationBell.jsx` + `.css` | Inbox UI |
| Modify: `frontend/src/pages/admin/DisplayPage.jsx` | Mute switches |
| Modify: `frontend/src/utils/displayPrefsCore.js` | Parse mutes |
| Modify: `frontend/src/utils/forgeDeadControlsGate.test.js` or create `notificationInboxGate.test.js` | Source gates |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md`, `docs/design/design-system.md` | Shipped truth |

**Do not** add Alembic. **Do not** use `DropdownMenu` as the inbox panel.

---

### Task 1: Honest unread count + Inbox/Done list

**Files:**
- Modify: `backend/db/user_notifications.py`
- Modify: `backend/tests/test_user_notifications.py`

**Interfaces:**
- Consumes: existing `list_notifications`, `count_unread`
- Produces: `list_notifications(..., view: str = "inbox")`; `count_unread` with no severity filter

- [ ] **Step 1: Write the failing assertion** in `test_analyst_scope_lists_and_counts_unread`

Today the test inserts high + low and expects `unread_count == 1`. Change the expected count to `2` and add a Done-view test. Do not change production code yet.

```python
def test_analyst_scope_lists_and_counts_unread(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="a1")
    _insert(uid, "analyst", severity="low", dedupe="a2")

    _login(client, "analyst1")
    res = client.get("/api/me/notifications?scope=analyst")
    assert res.status_code == 200
    body = res.json()
    assert len(body["notifications"]) == 2
    assert body["unread_count"] == 2


def test_list_view_done_excludes_inbox(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="d1")
    _login(client, "analyst1")
    listed = client.get("/api/me/notifications?scope=analyst").json()
    nid = listed["notifications"][0]["id"]
    client.post(f"/api/me/notifications/{nid}/dismiss")
    inbox = client.get("/api/me/notifications?scope=analyst&view=inbox").json()
    done = client.get("/api/me/notifications?scope=analyst&view=done").json()
    assert inbox["notifications"] == []
    assert len(done["notifications"]) == 1
    assert done["unread_count"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py::test_analyst_scope_lists_and_counts_unread tests/test_user_notifications.py::test_list_view_done_excludes_inbox -q`

Expected: first FAIL (`2 != 1`); second FAIL (`view` ignored or 422).

- [ ] **Step 3: Implement**

In `count_unread`, delete `_BADGE_SEVERITIES` usage. Count:

```sql
SELECT COUNT(*) AS cnt FROM user_notifications
WHERE user_id = ?
  AND scope = ?
  AND dismissed_at IS NULL
  AND read_at IS NULL
```

Add `view: str = "inbox"` to `list_notifications`. If `view == "done"`, `dismissed_at IS NOT NULL` and `ORDER BY datetime(dismissed_at) DESC` (SQLite) / equivalent text timestamp order already used for `created_at`. If `view == "inbox"` (default), keep `dismissed_at IS NULL`. Invalid view: raise `ValueError` and map to 422 in the router in Task 2 if easier; for this task accept only `inbox|done`.

- [ ] **Step 4: Re-run tests**

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/db/user_notifications.py backend/tests/test_user_notifications.py
git commit -m "fix(notifications): count all unread severities and list Done view"
```

---

### Task 2: Read, read-all, restore, scope=all routes

**Files:**
- Modify: `backend/db/user_notifications.py`
- Modify: `backend/routers/notifications_me.py`
- Modify: `backend/tests/test_user_notifications.py`

**Interfaces:**
- Produces:
  - `async def mark_one_read(db, *, user_id: int, notification_id: int) -> bool`
  - `async def mark_scope_read(db, *, user_id: int, scope: str) -> int` — `scope` `analyst|operator|all`
  - `GET/POST` as spec
  - `ScopeBody.scope` pattern `^(analyst|operator|all)$`

- [ ] **Step 1: Failing tests**

```python
def test_read_does_not_remove_from_inbox(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="r1")
    _login(client, "analyst1")
    nid = client.get("/api/me/notifications").json()["notifications"][0]["id"]
    res = client.post(f"/api/me/notifications/{nid}/read")
    assert res.status_code == 200
    body = client.get("/api/me/notifications").json()
    assert len(body["notifications"]) == 1
    assert body["unread_count"] == 0
    assert body["notifications"][0]["read_at"]


def test_restore_returns_to_inbox(client):
    uid = _user_id("analyst1")
    _insert(uid, "analyst", dedupe="u1")
    _login(client, "analyst1")
    nid = client.get("/api/me/notifications").json()["notifications"][0]["id"]
    client.post(f"/api/me/notifications/{nid}/dismiss")
    assert client.post(f"/api/me/notifications/{nid}/restore").status_code == 200
    inbox = client.get("/api/me/notifications?view=inbox").json()
    assert len(inbox["notifications"]) == 1


def test_scope_all_admin_only(client):
    admin_id = _user_id("admin1")
    analyst_id = _user_id("analyst1")
    _insert(admin_id, "analyst", dedupe="aa")
    _insert(admin_id, "operator", dedupe="oo")
    _insert(analyst_id, "analyst", dedupe="xx")
    _login(client, "analyst1")
    assert client.get("/api/me/notifications?scope=all").status_code == 403
    _login(client, "admin1")
    body = client.get("/api/me/notifications?scope=all").json()
    scopes = {n["scope"] for n in body["notifications"]}
    assert scopes == {"analyst", "operator"}
    assert len(body["notifications"]) == 2
```

Use `dedupe_key` in the JSON if exposed; if not, assert `len == 2` and mixed `scope` values.

- [ ] **Step 2: Run tests — expect FAIL (404 on /read and /restore)**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py::test_read_does_not_remove_from_inbox tests/test_user_notifications.py::test_restore_returns_to_inbox tests/test_user_notifications.py::test_scope_all_admin_only -q`

- [ ] **Step 3: Implement db helpers**

`mark_one_read`: `UPDATE ... SET read_at = COALESCE(read_at, now) WHERE id=? AND user_id=? AND dismissed_at IS NULL`. Return rowcount > 0.

`mark_scope_read`: if scope `all`, omit scope predicate; else filter scope. Same dismissed/read nulls as mark seen.

`list_notifications` / `count_unread`: if scope `all`, drop `AND scope = ?`.

Router: `_require_scope` allows `all`; operator and all require admin. Query `view` default inbox. POST `/{id}/read`, `/{id}/restore`, `/read-all`.

Keep POST `/seen` as alias of read-all for the given scope (do not delete; UI will stop calling it).

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/db/user_notifications.py backend/routers/notifications_me.py backend/tests/test_user_notifications.py
git commit -m "feat(notifications): read, restore, and admin scope=all"
```

---

### Task 3: Mute categories on emit + preferences

**Files:**
- Modify: `backend/preferences/display_validate.py`
- Modify: `backend/preferences/repo.py`
- Modify: `backend/routers/me.py`
- Modify: `backend/notifications/emit.py`
- Modify: `backend/tests/test_user_notifications.py`
- Modify: `backend/tests/test_me_preferences.py` if GET shape is asserted

**Interfaces:**
- `NOTIFICATION_MUTE_CATEGORIES = ("watchlist", "ioc_watchlist", "job_error", "api_key_unhealthy", "webhook_failure")`
- `DEFAULT_DISPLAY_PREFS["notification_mutes"] = {k: False for k in ...}`
- `_emit_to_users` skips insert when that user’s mute for `category` is true

- [ ] **Step 1: Failing tests**

```python
def test_patch_notification_mutes(client):
    _login(client, "admin1")
    patch = client.patch(
        "/api/me/preferences",
        json={"notification_mutes": {"watchlist": True}},
    )
    assert patch.status_code == 200
    assert patch.json()["notification_mutes"]["watchlist"] is True
    assert patch.json()["notification_mutes"]["job_error"] is False


def test_muted_category_does_not_insert(client):
    from notifications.emit import emit_watchlist_notification
    uid = _user_id("analyst1")
    _login(client, "analyst1")
    client.patch("/api/me/preferences", json={"notification_mutes": {"watchlist": True}})

    async def _emit():
        db = await get_db()
        try:
            n = await emit_watchlist_notification(
                db,
                cve_id="CVE-2024-1",
                reason="Entered KEV",
                detail="x",
                dedupe_key="watch:CVE-2024-1:kev",
            )
            await db.commit()
            return n
        finally:
            await db.close()

    created = run_db_test(_emit())
    assert created == 0
    listed = client.get("/api/me/notifications?scope=analyst").json()
    assert listed["notifications"] == []
```

Unknown mute key → 422 (add if not covered).

- [ ] **Step 2: Run — FAIL (field ignored / 422)**

- [ ] **Step 3: Implement**

Validate mutes: dict, only known keys, bool values, merge with defaults.

`get_user_preferences` returns `notification_mutes`.

In `_emit_to_users`, for each `user_id` load prefs once per emit (or batch). If `notification_mutes.get(category)`: continue.

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/preferences backend/routers/me.py backend/notifications/emit.py backend/tests/test_user_notifications.py
git commit -m "feat(notifications): per-category inbox mutes"
```

---

### Task 4: Pure inbox helpers + timeAgo (frontend TDD)

**Files:**
- Create: `frontend/src/utils/notificationInbox.js`
- Create: `frontend/src/utils/notificationInbox.test.js`
- Create: `frontend/src/utils/timeAgo.js`
- Create: `frontend/src/utils/timeAgo.test.js`

**Interfaces:**
- `formatTimeAgo(isoString, nowMs = Date.now()) => string`
- `notificationDestination(item) => { search?: string, pathname: string, label: string } | null`
- `groupNotificationRows(items) => Array<{ key, latest, extras }>`
- `notificationTriggerLabel(unreadCount) => string`
- `DEFAULT_NOTIFICATION_MUTES` frozen object

- [ ] **Step 1: Write tests** (`node:test` like other frontend unit files)

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { formatTimeAgo } from './timeAgo.js'
import {
  notificationDestination,
  groupNotificationRows,
  notificationTriggerLabel,
} from './notificationInbox.js'

describe('formatTimeAgo', () => {
  it('formats minutes', () => {
    const now = Date.parse('2026-08-24T12:00:00Z')
    assert.equal(formatTimeAgo('2026-08-24T11:50:00Z', now), '10m ago')
  })
})

describe('notificationDestination', () => {
  it('opens CVE in feed', () => {
    const d = notificationDestination({ entity_type: 'cve', entity_id: 'CVE-1' })
    assert.equal(d.pathname, '/')
    assert.match(d.search, /tab=feed/)
    assert.match(d.search, /cve=CVE-1/)
    assert.equal(d.label, 'Open CVE')
  })
  it('returns null for unknown types', () => {
    assert.equal(notificationDestination({ entity_type: 'nope', entity_id: 'x' }), null)
  })
})

describe('groupNotificationRows', () => {
  it('collapses consecutive same entity', () => {
    const groups = groupNotificationRows([
      { id: 1, category: 'watchlist', entity_type: 'cve', entity_id: 'CVE-1', title: 'b' },
      { id: 2, category: 'watchlist', entity_type: 'cve', entity_id: 'CVE-1', title: 'a' },
      { id: 3, category: 'job_error', entity_type: 'job', entity_id: 'nvd', title: 'j' },
    ])
    assert.equal(groups.length, 2)
    assert.equal(groups[0].extras.length, 1)
  })
})

describe('notificationTriggerLabel', () => {
  it('includes unread count', () => {
    assert.equal(notificationTriggerLabel(3), 'Notifications, 3 unread')
    assert.equal(notificationTriggerLabel(0), 'Notifications, none unread')
  })
})
```

- [ ] **Step 2: Run**

Run: `cd frontend && node --test src/utils/notificationInbox.test.js src/utils/timeAgo.test.js`

Expected: FAIL module not found.

- [ ] **Step 3: Implement**

`formatTimeAgo`: port `CVECard` `timeAgo` (minutes/hours/days/months). `< 1m` → `just now`.

`notificationDestination`: copy the navigate map from current `NotificationBell.handleItemClick` (cve, ioc, kev_backlog, webhook, api_key, job).

`groupNotificationRows`: walk in list order; flush group when key changes. `key = category + '\\0' + entity_type + '\\0' + entity_id`. `latest` = first item (list is newest-first). `extras` = the rest.

- [ ] **Step 4: PASS**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/notificationInbox.js frontend/src/utils/notificationInbox.test.js frontend/src/utils/timeAgo.js frontend/src/utils/timeAgo.test.js
git commit -m "feat(notifications): pure inbox helpers and relative time"
```

---

### Task 5: Radix Popover primitive

**Files:**
- Modify: `frontend/package.json` (and lockfile via `npm install`)
- Create: `frontend/src/components/ui/Popover.jsx`
- Modify: `frontend/src/components/ui/index.js`
- Modify: `frontend/src/components/ui/ui.css`

**Interfaces:**
- `Popover`, `PopoverTrigger`, `PopoverContent` (Content always portaled)
- CSS class `ui-popover-content`

- [ ] **Step 1: Add dependency**

Run: `cd frontend && npm install @radix-ui/react-popover@^1.1.15`

Do not add Tailwind. Match other `@radix-ui/react-*` caret ranges.

- [ ] **Step 2: Implement Popover.jsx** (mirror `DropdownMenu.jsx`)

```javascript
import { forwardRef } from 'react'
import * as RadixPopover from '@radix-ui/react-popover'
import './ui.css'

export const Popover = RadixPopover.Root
export const PopoverTrigger = RadixPopover.Trigger
export const PopoverAnchor = RadixPopover.Anchor

export const PopoverContent = forwardRef(function PopoverContent(
  { className = '', sideOffset = 6, align = 'end', ...props },
  ref,
) {
  return (
    <RadixPopover.Portal>
      <RadixPopover.Content
        ref={ref}
        sideOffset={sideOffset}
        align={align}
        className={['ui-popover-content', className].filter(Boolean).join(' ')}
        {...props}
      />
    </RadixPopover.Portal>
  )
})

export default Popover
```

Export from `index.js` next to DropdownMenu.

CSS:

```css
.ui-popover-content {
  z-index: var(--z-dropdown);
  border: 1px solid var(--border2);
  border-radius: var(--radius-sm);
  background: var(--admin-surface-raised, var(--surface-raised));
  box-shadow: var(--shadow-overlay);
  color: var(--text);
  outline: none;
}
.ui-popover-content:focus-visible {
  box-shadow: var(--shadow-overlay), var(--focus-ring);
}
```

- [ ] **Step 3: Confirm import**

Run: `cd frontend && node -e "import('@radix-ui/react-popover').then(() => console.log('ok'))"`

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/components/ui/Popover.jsx frontend/src/components/ui/index.js frontend/src/components/ui/ui.css
git commit -m "feat(ui): add Radix Popover primitive"
```

---

### Task 6: NotificationBell inbox UI

**Files:**
- Modify: `frontend/src/utils/notificationsApi.js`
- Rewrite: `frontend/src/components/NotificationBell.jsx`
- Rewrite: `frontend/src/components/NotificationBell.css`
- Create: `frontend/src/utils/notificationInboxGate.test.js`

**Interfaces:**
- API helpers: `fetchNotifications(scope, { view, limit })`, `readNotification(id)`, `readAllNotifications(scope)`, `restoreNotification(id)` — keep dismiss helpers
- Bell uses `Popover` + `Tabs` + `AsyncState` + `Badge` + Lucide
- Admin: `scope='all'` when caller passes `scope="all"`; Header and StatusBar both pass `all` if role is admin (Task 7)

- [ ] **Step 1: Gate test (failing)**

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'url'

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), '..')
const src = fs.readFileSync(path.join(root, 'components/NotificationBell.jsx'), 'utf8')

describe('NotificationBell inbox gate', () => {
  it('does not mark seen merely by opening', () => {
    assert.doesNotMatch(src, /markNotificationsSeen/)
    assert.doesNotMatch(src, /\/notifications\/seen/)
  })
  it('uses Popover, not a raw absolute panel as the only overlay', () => {
    assert.match(src, /PopoverContent/)
  })
  it('does not label dismiss as Mark read', () => {
    assert.doesNotMatch(src, /Mark read/)
    assert.doesNotMatch(src, /Mark all read/)
    assert.match(src, /Mark all as read/)
    assert.match(src, /Done/)
  })
})
```

Also keep the existing IOC navigate gate in `forgeDeadControlsGate.test.js` — update it if the navigate helper moves to `notificationInbox.js` (assert that file contains `tab=ioc`).

- [ ] **Step 2: Run gate — FAIL**

Run: `cd frontend && node --test src/utils/notificationInboxGate.test.js`

- [ ] **Step 3: Implement API + Bell**

`notificationsApi.js` add:

```javascript
export async function readNotification(id) {
  const res = await fetch(`/api/me/notifications/${id}/read`, {
    method: 'POST', credentials: 'include', headers: JSON_HEADERS,
  })
  return parseJson(res)
}
export async function readAllNotifications(scope) {
  const res = await fetch('/api/me/notifications/read-all', {
    method: 'POST', credentials: 'include', headers: JSON_HEADERS,
    body: JSON.stringify({ scope }),
  })
  return parseJson(res)
}
export async function restoreNotification(id) {
  const res = await fetch(`/api/me/notifications/${id}/restore`, {
    method: 'POST', credentials: 'include', headers: JSON_HEADERS,
  })
  return parseJson(res)
}
```

`fetchNotifications(scope, { view = 'inbox', limit = 50 } = {})` include `view` in query.

Bell behavior (must match spec):

- State: `open`, `view` inbox|done, `items`, `unreadCount`, `error`, `loading`, `undo`, `activeIndex`, `chip` all|intel|ops (ops = operator scope rows).
- Load on mount, interval from `localStorage` poll if easy else 30s, `document.visibilitychange` when visible, and when `open` becomes true.
- `error` is a real Error; `AsyncState` with `emptyTitle={view==='done' ? 'Nothing in Done yet.' : 'Inbox is clear.'}`.
- Trigger: `aria-label={notificationTriggerLabel(unreadCount)}`; visible badge if unreadCount > 0 (not aria-hidden without a name).
- Hidden `aria-live="polite"` text when unread increases and panel closed.
- Chime: same as now **and** `!open` **and** `!reduceMotion`. Add a unit test that reduced motion skips the chime.
- Row: `notificationDestination` + `navigate({ pathname, search })` then `readNotification`.
- Done button: `dismissNotification` then undo bar; Undo → `restoreNotification`.
- Mark all as read → `readAllNotifications(scope)`.
- Head `DropdownMenu`: Move all to Done → existing dismiss-all.
- Done view: Restore button per row.
- `j`/`k`/`Enter`/`e` when open (onContent). `Shift+E` restores in Done view only (focus in the list, not a text field).
- CSS: unread dot, no trigger scale, `--focus-ring`, `--type-*` tokens, `--hit-target-min` on icon buttons.
- Group via `groupNotificationRows`; show `+N more` in meta.

Chip filter: `intel` = `scope==='analyst'`; `ops` = `scope==='operator'`; only render chips when fetched `scope==='all'` or items have mixed scopes.

- [ ] **Step 4: Gate PASS + `npm run test:unit`**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/notificationsApi.js frontend/src/components/NotificationBell.jsx frontend/src/components/NotificationBell.css frontend/src/utils/notificationInboxGate.test.js frontend/src/utils/forgeDeadControlsGate.test.js
git commit -m "feat(notifications): Popover inbox with read vs Done"
```

---

### Task 7: One inbox for admin + Display mutes

**Files:**
- Modify: `frontend/src/components/Header.jsx`
- Modify: `frontend/src/pages/admin/shared/NotificationCenter.jsx`
- Modify: `frontend/src/pages/admin/DisplayPage.jsx`
- Modify: `frontend/src/utils/displayPrefsCore.js`
- Modify: `frontend/src/utils/userPreferences.js` if patch mapping is needed

**Interfaces:**
- Header: if authed admin, `<NotificationBell scope="all" />`, else `analyst`
- NotificationCenter: `scope="all"` (admin-only page)
- `toDisplayPrefs` includes `notificationMutes` from `notification_mutes`

- [ ] **Step 1: Display prefs unit coverage**

If `test_me_preferences` / frontend display tests exist, extend. Otherwise add assertions in a small `displayPrefsCore` test if the file already has tests; if not, skip extra file and cover via DisplayPage copy.

Need Header to know admin role — use existing auth context (`authStatus`, user role). Read `Header.jsx` for the user object; pass `scope={role === 'admin' ? 'all' : 'analyst'}`.

- [ ] **Step 2: Display page**

Under Notifications card, five `ToggleSwitch` rows keyed by category. Labels:

- Watchlist (pinned CVE)
- IOC watchlist hit
- Scheduler job failure
- API key unhealthy
- Webhook delivery failure

Helper text: “Muted types are not added to the inbox. Discord and Telegram still follow Admin → Webhooks.”

Patch `notification_mutes` as a full merged object (defaults + toggled key) so the API merge stays dumb.

- [ ] **Step 3: Manual check list (implementer)**

Analyst role: Header bell, no Ops chip. Admin on `/` and `/admin`: both bells show mixed intel+ops.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Header.jsx frontend/src/pages/admin/shared/NotificationCenter.jsx frontend/src/pages/admin/DisplayPage.jsx frontend/src/utils/displayPrefsCore.js frontend/src/utils/userPreferences.js
git commit -m "feat(notifications): admin unified inbox and mute toggles"
```

---

### Task 8: Docs + design-system inventory

**Files:**
- Modify: `docs/PRODUCT_STATUS.md` Notification center sentence + last updated
- Modify: `docs/API_REFERENCE.md` `/api/me/notifications*`
- Modify: `docs/design/design-system.md` §18: Popover shipped (move out of “not yet exported”)
- Modify: `docs/SYSTEM_DESIGN.md` only if it still says open-clears-badge / kev_backlog notify

- [ ] **Step 1: Edit PRODUCT_STATUS**

Replace the Notification center clause with: analyst/admin share `NotificationBell` Popover inbox; unread badge = all severities; open does not mark read; Done vs Mark as read; mutes in Display; KEV gaps stay in Forge.

- [ ] **Step 2: API_REFERENCE**

Document `view`, `scope=all`, `unread_count` definition, `POST /read`, `/read-all`, `/restore`. State `POST /seen` is legacy alias of read-all.

- [ ] **Step 3: design-system §18**

Move Popover from “Target / not yet exported” to primitives list: “Popover (Radix, portaled, `--shadow-overlay`)”.

- [ ] **Step 4: Commit**

```bash
git add docs/PRODUCT_STATUS.md docs/API_REFERENCE.md docs/design/design-system.md docs/SYSTEM_DESIGN.md
git commit -m "docs: notification inbox contract and Popover primitive"
```

---

### Task 9: Verify

- [ ] **Step 1: Frontend**

Run: `cd frontend && npm run test:unit && npm run build`

Expected: exit 0.

- [ ] **Step 2: Backend notifications tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_user_notifications.py tests/test_detection_backlog.py tests/test_api_key_health.py -q`

Expected: pass (`test_repeated_identical_failure_notifies_once` still valid — mute default false).

- [ ] **Step 3: Merge gate**

Run: `./scripts/verify-local.sh`

Expected: green, or only documented unrelated SQLite schema failures. Do not ship if notification tests fail.

- [ ] **Step 3b: Graphify**

Run: `graphify update .` from the repository root after implementation edits and before the merge gate. Keep `graphify-out/` uncommitted.

- [ ] **Step 4: Browser (required for UI)**

Analyst: unread low-severity row still badges; open panel does not clear badge; Mark all as read clears badge and keeps rows; Done moves to Done; Undo restores; Esc closes; keyboard j/k; failed fetch shows Retry not “Inbox is clear.”

Admin: job failure appears on FEED header bell.

Mute watchlist, trigger monitor in tests or seed, confirm no row.

- [ ] **Step 5: Final commit only if verify caused extra fixes**

---

## Self-review

**Spec coverage:** verbs, badge, empty vs error, Popover, grouping, a11y, mutes, scope=all, no kev_backlog, no push — each has a task. Toast/Needs attention unchanged (spec §2).

**Placeholders:** none.

**Types:** `view=inbox|done`, `scope=analyst|operator|all`, mute keys match emit categories.

**Prerequisite:** merge or rebase onto PR #869 so Forge gaps stay out of the inbox.
