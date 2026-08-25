# In-app notification inbox — design spec

**Date:** 2026-08-24  
**Status:** Shipped on `main` (Popover, read ≠ dismiss, honest badge). **Done-as-archive is superseded** by `docs/superpowers/specs/2026-08-25-notification-alert-tray-design.md` (Alerts / Cleared + 24h purge).  
**Bar:** GitHub Inbox verbs + Linear popover quality + PagerDuty honesty, on BRIEFR’s dense dark console. Not Instagram, not Slack chat unread, not OS push.

Related: `frontend/src/components/NotificationBell.jsx`, `backend/db/user_notifications.py`, `backend/routers/notifications_me.py`, `backend/notifications/emit.py`, `docs/design/design-system.md` §4 / §18 / §23, `docs/PRODUCT_STATUS.md` Notification center.

---

## 1. What “10/10” means here

A CVE console is not a social app. 10/10 is:

1. **Honest verbs** — seen, read, done, mute are different.
2. **Only actionable events** — if the analyst cannot do anything, do not notify (KEV Forge gaps: PR #869).
3. **Trustworthy badge** — count matches unread rows still in Inbox.
4. **Four async states** — loading, empty, error, data (`AsyncState`).
5. **Overlay quality** — portaled Popover, Esc, focus restore, `--focus-ring`, collision-aware.
6. **Scannable rows** — relative time, severity icon+label (not color alone), whole-row open, destination copy.
7. **Operator can quiet types** without code changes.

Out of scope (would fake a 10 without helping this product): browser `Notification` / service-worker push, email, quiet hours, a new analyst tab competing with FEED, virtualized lists (cap 100), multi-tenant inboxes.

---

## 2. Root causes (code, not taste)

Traced 2026-08-24:

| Symptom | Root |
|---------|------|
| “Mark read” deletes the row | `dismissOne` → `POST .../dismiss`; copy lies. Open panel → `POST .../seen` (sets `read_at`) while the same button dismisses. |
| Badge does not match the list | `count_unread` only counts `severity IN (critical, high)`. Low/medium never badge. |
| Empty looks like success | `load()` `catch` sets `items=[]` → “No notifications.” |
| Overlay fails DS §4 / §18 | Absolute `div`, click-outside only, no Esc, no portal. Design system already lists **Popover as a missing primitive**. `@radix-ui/react-popover` is not in `package.json`. `DropdownMenu` is the wrong primitive (command list, closes on select, typeahead). |
| Two bells, split streams | Header `scope=analyst`; Admin StatusBar `scope=operator`. Admin on FEED never sees job failures in the header bell. |
| Timestamp scan cost | `fmtIso` in the list; `fmtAge` / CVECard `timeAgo` already exist elsewhere. |
| Severity by color only | Left border `--red`/`--amber`; no icon or word. Violates DS §4 color independence. |
| Undo is fake after 5s | UI delays dismiss; `undo_dismiss_notification` exists in `db/user_notifications.py` and has **no router**. |
| Settings | Display page: chime on/off only. |
| ui-ux-pro-max `--design-system` | Suggested cyberpunk neon / horizontal-scroll landing. **Rejected.** BRIEFR DS wins: tokens, Lucide, no decorative motion, dark-only. Keep its *usable* rules: Popover not absolute div; `role=alert` on errors; `aria-live` for badge; no scale-on-hover layout shift. |

Toasts (`Toast.jsx`) and Admin **Needs attention** stay separate. Toast = interrupt. Needs attention = live ops checklist. Bell = durable inbox.

---

## 3. Approaches considered

| Approach | Pros | Cons |
|----------|------|------|
| **A. Fix verbs + Popover inbox (chosen)** | Matches GitHub; no new tab; no migration; uses existing `read_at` / `dismissed_at` | Still a popover, not a full GitHub page |
| B. New `?tab=inbox` analyst page | Linear-class destination | Competes with FEED; too much chrome for one operator |
| C. Browser push + inbox | True 10/10 interrupt when AFK | Permission UX, HTTPS quirks, self-host pain; YAGNI |

**Chosen: A.** Inbox lives in a Radix Popover. Done pile is a second view inside the same panel (`view=done`), like GitHub Inbox / Done.

---

## 4. Information architecture

### 4.1 One inbox, two placements

Same `NotificationBell` component:

- Analyst shell header (always).
- Admin StatusBar (always).

For **admin** role, both fetch `scope=all` (analyst + operator rows in one list). For **analyst** role, `scope=analyst` only.

Filter chips in the panel (admin only): **All | Intel | Ops** (`scope` client filter on already-fetched `all` payload, or pass `scope=`). Prefer one request `scope=all` + client chips to avoid double poll.

### 4.2 Views

| View | SQL | UI label |
|------|-----|----------|
| Inbox | `dismissed_at IS NULL` | Inbox |
| Done | `dismissed_at IS NOT NULL` ORDER BY dismissed_at DESC | Done |

Limit 50 (raise from 30). No pagination in v1.

### 4.3 Verbs (locked)

| User action | API | DB |
|-------------|-----|-----|
| Open popover | none required for read state | Do **not** mark all seen on open. Badge stays until rows are read or done. |
| Click row / Open | `POST /api/me/notifications/{id}/read` then navigate | `read_at = now` if null |
| Mark as read (row or “Mark all as read”) | `POST .../read` or `POST .../read-all` | `read_at` only; row **stays in Inbox** |
| Done (row or “Move all to Done”) | existing dismiss endpoints | `dismissed_at` (+ `read_at` coalesce) |
| Undo Done (5s toast in panel + Done view Restore) | `POST .../{id}/restore` | `dismissed_at = NULL` (existing helper) |
| Mute type | `PATCH /api/me/preferences` | `display_prefs_json.notification_mutes.{category}=true` |

**Breaking change (intentional):** opening the bell no longer calls `POST /seen`. `POST /seen` remains for compatibility but the UI must not use it as “I glanced at the panel.”

**Breaking change (intentional):** `unread_count` counts **all** undismissed rows with `read_at IS NULL`, any severity. Update `test_analyst_scope_lists_and_counts_unread` (today expects low severity not to count).

### 4.4 What may be emitted

Allowlist (already the emit.py set after #869):

| category | scope | When |
|----------|-------|------|
| `watchlist` | analyst | Pinned CVE: KEV / EPSS jump / PoC (existing monitor) |
| `ioc_watchlist` | analyst | Retro-match hit |
| `job_error` | operator | Scheduler job error |
| `api_key_unhealthy` | operator | Key health fail (still deduped) |
| `webhook_failure` | operator | Delivery fail (still deduped) |

Do not add `kev_backlog`. Do not emit muted categories (`insert` skipped per user).

Webhooks (Discord) are a **different** channel. Inbox mute does not disable webhooks in v1 (document that). Per-destination event_types already exist on Webhooks page.

---

## 5. API contract

Keep prefix `/api/me/notifications`.

**GET `?scope=analyst|operator|all&view=inbox|done&limit=`**

- `all` → 403 unless `role=admin`.
- Response adds `read_at`, `dismissed_at`, `category`, `scope` (already mostly selected).
- `unread_count` always refers to **Inbox** unread, even when `view=done`.

**POST `/{id}/read`** — 404 if not owner / already dismissed? Allow read on inbox rows only; 404 if missing.

**POST `/read-all`** body `{scope}` including `all`.

**POST `/{id}/restore`** — calls `undo_dismiss_notification`.

**POST `/seen`** — keep; unused by new UI.

**Preferences:** `notification_mutes` object, keys = allowlisted categories, values bool, default all `false`. Stored inside `display_prefs_json` (no Alembic). Validate unknown keys → 422. Bump `MAX_DISPLAY_PREFS_JSON_LEN` only if needed (4096 is enough).

**Emit path:** before insert, load that user’s mutes; skip if muted.

---

## 6. UI / UX (10/10 on this console)

### 6.1 Primitive

Add `frontend/src/components/ui/Popover.jsx` wrapping `@radix-ui/react-popover` (new dependency, pin caret like other Radix packages). Export from `index.js`. Styles in `ui.css`: `.ui-popover-content` uses `--shadow-overlay`, `--border-subtle` / `--border2`, `--surface-raised`, `z-index: var(--z-dropdown)`, `border-radius: var(--radius-sm)`. `align="end"` `side="bottom"` `sideOffset={6}`.

Bell trigger: no `transform: scale` on `:active`. Hover = background/border only. `min` hit 24px (`--hit-target-min`). `:focus-visible { box-shadow: var(--focus-ring) }`.

### 6.2 Panel chrome (dense, not marketing)

Width `min(420px, calc(100vw - 24px))`. Max height `min(480px, 70vh)`. Flex column: head, filters, scroll list, footer.

**Head:** title “Inbox” / “Done” (Tabs primitive already in `components/ui/Tabs.jsx`). Actions: Mark all as read (Inbox only). No “Refresh” button — refetch on open, on `visibilitychange`, interval = user `poll_interval_seconds` (already in prefs, default 30).

**Row:**

```text
[unread dot] [severity icon]  Title (semibold if unread)
                              Body one line, ellipsis
                              {category label} · {relative time} · {Open {destination}}
                                                    [Done]
```

- Unread: 6px `--accent-primary` dot **and** semibold title (not color alone).
- Severity: Lucide `OctagonAlert` / `TriangleAlert` / `Info` + `Badge` with `explain` tooltip (required by Badge primitive).
- Time: relative (`fmtAge` or shared `formatTimeAgo`) + `title`/`Tooltip` with absolute `fmtIso`.
- Row is a non-button container; a sibling row-activation button opens the destination, and a sibling Done button marks Done (`stopPropagation` not required if they are not nested).
- Destination helper (pure): CVE → “Open CVE”; IOC → “Open IOC”; job → “Open scheduler”; api_key → “Open API keys”; webhook → “Open webhooks”; kev_backlog leftover → “Open Forge backlog”; unknown → no navigation, no fake control.

**Empty Inbox:** `EmptyState` title “Inbox is clear.” No action required.

**Empty Done:** “Nothing in Done yet.”

**Error:** `ErrorState` compact + Retry (`role=alert`). Never reuse empty copy.

**Loading:** existing `NotificationListSkeleton` via `AsyncState`.

**Footer:** optional one-line “Move all to Done” (Inbox, only if rows exist) — quieter than Mark all as read; place in head overflow (`DropdownMenu` of actions) to avoid two equal text links. Primary: Mark all as read. Secondary menu: Move all to Done.

**Undo:** after Done, panel footer bar 5s + `POST restore` on Undo (optimistic restore). If the request already committed, restore API still works.

### 6.3 Grouping (no schema)

Pure function `groupNotificationRows(items)`: consecutive rows with same `(category, entity_type, entity_id)` collapse to one row showing latest title + meta “+N more”. Expanding is YAGNI; click opens the latest entity. Count unread in the group for the dot.

Skip virtualization (n ≤ 50).

### 6.4 Accessibility

- Trigger `aria-label={unread ? `Notifications, ${n} unread` : 'Notifications, none unread'}`.
- Badge visible but also in the accessible name; do not `aria-hidden` the only count.
- `aria-live="polite"` on a visually hidden node that updates when unread increases (not on every 30s identical count).
- Popover: Radix focus + Esc. `aria-labelledby` panel title.
- Keyboard inside list: `j`/`k` move, `Enter` open, `e` Done, `Shift+E` restore on Done view (Linear-ish). Ignore when focus is in a text field (none expected). `prefers-reduced-motion`: no chime (already), no extra animation.

### 6.5 Sound

Chime only if: prefs on, not reduced motion, unread **increased**, popover **closed**. Never chime because the user opened the panel.

### 6.6 Display settings

Card **Notifications**:

- Play chime (existing).
- Mute per category (Switch list, five rows). Copy: “Muted types are not added to the inbox. Discord/Telegram still follow Webhooks.”

### 6.7 Tokens / copy

Semantic tokens only. Dark-only. Lucide only. No emoji. Cursor pointer on clickable rows. Transition colors 150–200ms (`--transition-fast`).

---

## 7. Testing

Backend: extend `backend/tests/test_user_notifications.py` for unread-all-severities, view=done, read vs dismiss, restore, scope=all 403, mutes skip emit.

Frontend unit: `frontend/src/utils/notificationInbox.js` + `.test.js` (destination, grouping, aria label, mute defaults). Gate: NotificationBell does not call `/seen` on open; uses Popover; Mark as read ≠ dismiss — extend `forgeDeadControlsGate.test.js` or a dedicated `notificationInboxGate.test.js`.

Merge gate: `./scripts/verify-local.sh`.

---

## 8. Docs

Same PR as code: `PRODUCT_STATUS.md` Notification center sentence, `API_REFERENCE.md` `/api/me/notifications`, `SYSTEM_DESIGN.md` if it still says open-clears-badge, design-system §18: Popover **shipped**.

---

## 9. Non-goals recap

No Alembic. No push. No email. No full-page inbox. No mute→webhook coupling. No digest into BRIEF in this spec (BRIEF remains its own surface).
