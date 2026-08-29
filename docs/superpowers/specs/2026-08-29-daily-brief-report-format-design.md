# Daily brief report format — design spec

**Date:** 2026-08-29  
**Status:** Ready for implementation (operator-approved mockups; no chat commands)  
**Parent:** `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`  
**MARKET:** `docs/superpowers/specs/2026-08-27-daily-brief-market-clusters-design.md`  
**Format (channel grammar):** `docs/design/daily-brief-format.md` (this work updates that file)  
**Plan:** `docs/superpowers/plans/2026-08-29-daily-brief-report-format.md`

This spec does **not** reopen email, per-user URLs, per-slot routing, inbound Discord/Telegram commands, NVD-age/backup/circuit health lines, or description-LIKE product guessing.

---

## 1. Problem

The daily brief already collects the right facts. Operators cannot read it:

- Admin preview is a green `<pre>` of Discord `content`.
- Channel copy uses PDF `// HEADLINE` and `C · H · M · L`.
- Unmapped (code: `unanalyzed`) looks like a product named “unanalyzed.”
- Reporting lives under Webhooks, not as a report.
- Watchlist **alert triggers** waste a full-width card for five toggles (unrelated product, same PR).

## 2. Chosen approach

**One grammar, three renderers:**

| Surface | Renderer |
|---------|----------|
| Discord | One classic **embed** (`embeds: […]`), orange bar `#e85533` (`color` 15230259). Prefer embed-only (no `content`) for `daily_brief`. |
| Telegram | Same sections as **HTML** (`parse_mode=HTML`). Escape `& < >` in titles. |
| Generic HTTPS | `text` = Telegram-shaped plain/HTML-stripped or the HTML string; structured `brief` remains the machine contract. |
| Admin | Structured cards (same section ids). Collapsed “Channel preview” shows Discord embed JSON or Telegram HTML. |

Morning and end of day use the **same sections and labels**. Only masthead title changes: **Morning briefing** vs **End of day**.

Fan-out stays: every destination subscribed to `daily_brief` gets the same brief.

## 3. Section order (fixed)

Always: masthead, summary, at a glance. Then:

| id | When |
|----|------|
| `coverage` | `published > 0` |
| `severity_mix` | `published > 0` (Critical/High/Medium/Low totals, spelled out) |
| `products` | `published > 0` (top 8; Unmapped may appear as coverage, not as “led volume”) |
| `headlines` | 1–3 RSS cards in the window |
| `advisories` | 1–2 CISA publications in the window |
| `kev` / `stack` / `watchlist` / `ioc` | rows exist |
| `ops` | rows exist (scheduler / API key / webhook delivery — existing categories) |
| `footer` | always |

Quiet window: summary `Quiet window.` + at a glance zeros. Still send.

Empty KEV/stack/watchlist/ioc: **omit** those fields on Discord (do not add a “none this window” wall). At a glance already shows zeros.

## 4. Copy (canonical)

| Old | New |
|-----|-----|
| `BRIEFR EOD` / `STANDUP` | `End of day` / `Morning briefing` (admin/Discord title). Masthead product word remains **BRIEFR**. |
| `// HEADLINE` | **Summary** |
| `// COUNTS` | **At a glance** |
| `KEV new` | New on CISA KEV |
| `Stack matches` | Matches My Stack |
| `Watchlist` | Pinned-CVE alerts |
| `IOC hits` | IOC watch hits |
| `Critical/High new` | New Critical or High |
| `Ops issues` | Instance problems (admin/ops field title). Job lines use human catalog names. |
| `C · H · M · L` | Critical / High / Medium / Low |
| `unanalyzed` (display) | **Unmapped** |
| `1 ops issue(s)` | `1 scheduler problem.` or `N instance problems.` when mixed categories; prefer specific (`1 scheduler problem`) when all ops rows are `job_error`. |

**Coverage (required when published > 0), Discord field value ≤ 1024 characters:**

```text
Named products {named} of {published} · Unmapped {unmapped}
Unmapped means NVD has not given these CVEs a product (CPE) yet. BRIEFR does not guess from the description. KEV and other prioritized CVEs are often named within about one business day. Most others can stay Unmapped for days, weeks, or never. This briefing is a snapshot; later CPE does not rewrite this message.
```

`named` = published − count of primary_product Unmapped (from clustered rows + header totals: unmapped count is the Unmapped product `total` if present, else 0). Header published stays untruncated.

**Summary** must not say Unmapped “led volume.” Keep skipping Unmapped as MARKET leader. If Unmapped ≥ 50% of published, Summary includes one sentence: `{unmapped} of {published} published CVEs have no product mapped yet (Unmapped).`

**Ops line example:**

```text
Scheduler job failed: KEV metadata sync
CISA KEV list may be stale until this job succeeds.
Detail: KEV request failed
```

Job display names come from `frontend/src/pages/admin/catalog.js` equivalents already on the backend catalog (`operatorName` / `label`). Do not show raw `kev_metadata_sync` as the only identifier; include it in `Detail` only if no catalog label exists.

## 5. Headlines and Advisories

**Headlines (max 3)** from `feed_cache` key `incident_feed:snapshot` (existing Incidents & News snapshot). Include `kind != atlas`. Filter `publishedAt` into the brief UTC window. Sort newest first. Line: `{source} — {title}` (title truncated 120 chars). If snapshot missing or no rows: **omit** the field.

Dedup: if an advisory `canonical_url` equals a headline `url`, drop that headline (advisory wins).

**Advisories (max 2)** from `publications` whose `published_at` falls in the window (ISO/text compare consistent with other collectors). Prefer `source_key = 'cisa-news'` when rows exist; otherwise any publication in window. Line: `CISA — {title}` (or source label) truncated 120 chars. If none: **omit** the field (do not mention `PUBLICATION_SYNC_ENABLED` in Discord).

Do not fetch live RSS on the brief request path. Snapshot + DB only.

## 6. Discord embed map

Single embed:

- `author.name`: `BRIEFR`
- `title`: `End of day` or `Morning briefing`
- `color`: `0xE85533` (15230259)
- `description`: window line + Summary paragraphs
- `fields` (skip empty):
  - Severity mix — inline 2×2: Critical, High, Medium, Low (values = market header totals)
  - Coverage — full width
  - At a glance — full width, six labeled counts
  - Published by product — full width, top 8 with spelled-out severities; Unmapped first if present
  - Headlines / Advisories — full width
  - CISA KEV / My Stack / Pinned CVEs / IOC watch — full width, existing list grammar, max 8/5
  - Instance problems — full width, human ops
- `footer.text`: `Generated {local} {tz} · local facts · {template|groq|…}`
- `timestamp`: window end UTC ISO-8601

**Limits:** Discord embed 6000 combined characters, 25 fields, 1024 per field value, 4096 description. If over: drop fields in order `ioc` → `watchlist` → `stack` → `kev` → `advisories` → `headlines` → trim product lines to 5. Never drop coverage, severity mix, at a glance, or footer. Do **not** apply the old 2000-character `content` budget to Discord `daily_brief` embeds.

Telegram HTML budget remains 4096 (engine truncate). Assembly target 3500 then engine safety truncate.

Generic `text` uses the Telegram HTML body (or stripped text if we must avoid HTML in generic). Prefer the same HTML string; generic consumers already have `brief`.

## 7. Engine

`dispatch_event` / `deliver_to_destination` gain optional `discord_embeds: list[dict] | None` and `telegram_parse_mode: str | None`.

- Other events: unchanged (`content` only / Telegram plain).
- `daily_brief`: Discord sends `{"embeds": [...]}`; Telegram sends `text` + `parse_mode=HTML` + `disable_web_page_preview: true`.

Fallback: if embed JSON is rejected (400), log and retry once with `content` = current plain formatter truncated to 2000 (never-raise delivery). Tests may mock 400.

## 8. Admin

**Nav:** new section **REPORTS** (operator only): item **Daily brief** (`p=dailybrief`).

**Page:** slot select, Preview, Send test (existing APIs). Delivery line: destinations subscribed to `daily_brief` (read-only; link to Webhooks → Events). Structured preview of sections. Collapsed channel preview.

**Webhooks page:** remove the large Daily brief `<pre>` block; one-line link “Configure schedule & preview → Daily brief.” Event checkbox label stays `Daily brief (EOD / standup)`. Grouping “Scheduled reports” vs “Real-time alerts” in the Events editor is allowed if cheap.

**Watchlist & cache:** alert triggers as a compact column of label+switch (max-width ~24rem), not five full-width `admin-filter-bar` rows. HelpTip: “Real-time pinned-CVE alerts — not the daily brief.”

**Analyst nav:** no Daily brief page (operator report).

## 9. APIs

Extend `brief_to_payload` with `headlines: [{source, title, url}]` and `advisories: [{source, title, url}]`. Preview/test responses may include `discord_embeds` for admin channel preview.

No new public analyst routes. No inbound bot routes.

## 10. Out of scope

Inbound commands; Discord Components V2; instance health (NVD age, backup, circuits); MARKET enrichment; per-destination pickers; email; light theme.

## 11. Tests (intent)

- Template/summary copy: Unmapped not leader; coverage sentence when unmapped ≥ 50%.
- Embed field names use new labels; color 15230259; no `// HEADLINE`.
- Telegram HTML escapes `<` in a title.
- Headlines filtered by window; atlas excluded; max 3.
- Advisories omitted when table empty.
- Discord dispatch payload has `embeds` and no requirement for `content`.
- Watchlist trigger container class exists (unit/css or RTL if already used).
- Admin nav includes `dailybrief`.

## 12. Docs

Update `docs/design/daily-brief-format.md`, `docs/PRODUCT_STATUS.md` Daily brief row, `docs/API_REFERENCE.md` preview payload. Do not claim inbound chat.
