# Operator honesty UX — design

**Status:** requirements (revised after screenshot RCA + pressure-test).  
**Not for SQLite PR #752.** Separate PRs.  
**Product authority:** `docs/PRODUCT_STATUS.md` after ship; until then this spec.

## Problem

Operators cannot tell **live health** from **history**, **My Stack** from **FEED keywords**, or **real disk** from **leftover `public` tables**. Copy in DETECT and Discord over-claims. Related type is below the token floor.

## Ideation survivors (rejected alternatives)

| Kept | Rejected | Why rejected |
|------|----------|--------------|
| Dismiss open `job_error` rows to **Cleared** when that job’s last run succeeds | Hard-delete on success | Destroys the 11h/2d flakiness trail |
| Efficiency = operator table; TABLE SIZES = DBA drill-down (`app`/`intel`) | Friendly-name every Postgres relation | Wrong altitude; Efficiency already named subsystems |
| Catalog title or `vendor product` for briefs | Invented brands (“Dell EMC …”) | Same honesty bug as DETECT DRL over-claim |
| One Discord embed; shorter morning | 2–3 embeds always | Mobile split; field titles already section |
| Stop FEED auto-fill from My Stack | Unify FEED = My Stack | User cleared FEED; reload restored server stack |
| Env stack: migrate-if-empty then stop matching | Delete env with no migrate | Empties wallboard for env-only hosts |
| ENV webhook Delete clears config URL + row | Hide-flag while env URL lives | `sync_env_destinations_to_db` resurrects the card |
| DETECT: no DRL paragraph when community = 0 | Keep policy paragraph always | Screenshot showed template fallback |
| Related chips ≥ `--type-micro` | Leave 9px | Violates `tokens.css` floor |

Generic UI-skill “cyberpunk / Fira / horizontal scroll” is **out of scope**. Use `docs/design/design-system.md` + `frontend/src/styles/tokens.css` (DM Sans / mono, `--accent-primary`, dark-only).

## Product contract

### 1. Headlines (Advisories & Intel)

- Exclude titles matching webinar / `[Virtual Event]` / registration CTAs (same mechanism as `EXCLUDED_NEWS_TITLE_PATTERNS`).
- `FeedCard` must not render a description that equals the title (empty RSS description today copies title).

### 2. Bell + briefs (one health rule)

- **Open Alerts / badge** = undismissed rows whose entity is **currently failing** (scheduler last run `had_error` for `entity_type=job`).
- On successful job run: **dismiss** (not delete) undismissed `job_error` for that `job_id`. They appear under **Cleared**. 24h cleared retention unchanged.
- Daily brief (EOD **and** standup) ops section: jobs whose **current** last run failed — not every `created_at` in the window. Dedupe by `job_id`. Omit section when none are open.
- Opening the popover still does not mark read.

### 3. Storage / Resources numbers

- `fetch_table_sizes` includes namespaces `app` and `intel` (`relkind` tables). Optional `include_system` for `public`/Procrastinate/Alembic (default off).
- Row counts join the same relations as sizes.
- **Efficiency** subsystems use those bytes (no 0 B + 112k rows).
- TABLE SIZES caption must not imply live DB growth from backup zips. Backup trend stays on backup copy only. 7-day DB forecast uses `resource_metrics.pg_db_size_bytes` (same series as Database page) on Efficiency / Storage disk, not the leftover-table grid.
- Connection pool bar: counts, not `fmtBytes`.

### 4. Layout (after honest numbers)

- Resources desktop: two-column chart cards (`admin-two-col` or equivalent). Host capacity + pool on one row. No new typefaces.

### 5. Stack

- FEED `STACK //` does **not** initialize from My Stack. Empty until the user types or uses “My stack only”.
- `BRIEFR_STACK_TERMS`: remove example keywords; if env set and admin My Stack empty, **one-time** copy into admin My Stack then stop using env for matching. Wallboard/backlog = My Stack only after that.

### 6. Discord / Telegram briefs

- Titles: **EOD report** / **Morning report** (author remains BRIEFR).
- Lede: 2–3 short sentences. Product labels: pass `software_catalog.title` as the `title` argument to `display_name_for`; if no catalog title, `display_name_for(vendor, product)` or the raw key. Never invent a vendor.
- Severity mix: **one** field `Critical n · High n · Medium n · Low n` (avoid Discord 3+1 wrap).
- Stay on **one** embed unless Discord 6000/25 limits force a second.
- Morning: glance + My Stack + KEV + open ops. Full product leaderboard is EOD-first (omit products on morning if over budget).

### 7. ENV webhook delete

- Delete allowed on `source=env` reserved ids.
- Effect: remove destination row, **clear** `DISCORD_WEBHOOK_URL` (and enabled flag) in the same config store Admin already writes, skip env bootstrap until the operator pastes a URL into **Add destination**.
- If process-level env still injects the URL after clear: HTTP 409 “unset `DISCORD_WEBHOOK_URL` in the process environment”. Persist the delete first (row + app_settings); do not no-op the write because process env is set.
- DB destinations (e.g. `discord-c5dd6db9`) unchanged.

### 8. DETECT

- If community Sigma + Elastic count is 0: do not show the DRL-1.1 policy paragraph. Show template-fallback copy. Keep DRL on actual SigmaHQ cards / Privacy.

### 9. RELATED

- `.drawer-related-*` body ≥ `--type-body`; chips ≥ `--type-micro`. Similarity chip must not depend on CVSS `margin-left: auto` for alignment (UNKNOWN without CVSS).

## Non-goals

- SQLite runtime, Docker, merging #752, light theme, new notification channels, rewriting `pg_adapt` / `_SQLITE` SQL twins.

## Success

- Screenshot cases: no `[Virtual Event]` duplicate lines; bell quiet when scheduler last run OK with history in Cleared; TABLE SIZES / Efficiency bytes match `app`/`intel`; FEED stack empty after hard reload if My Stack unused in the filter; ENV Discord card gone after Delete; DETECT honest on template-only CVEs; Related readable at 12px+.
