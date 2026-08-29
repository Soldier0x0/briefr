# Daily brief report format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the existing daily brief as a readable Discord embed + Telegram HTML + admin report page, with Unmapped coverage copy, RSS headlines, CISA advisories, and compact watchlist trigger toggles.

**Architecture:** Keep `collect_daily_brief` SQL facts. Add headlines/advisories onto `DailyBrief`. Build `format_daily_brief_embed` / `format_daily_brief_html` from one section grammar. Discord `daily_brief` delivery sends `embeds`; Telegram sends `parse_mode=HTML`. Admin `p=dailybrief` uses existing preview/test APIs. Watchlist CSS-only density fix.

**Tech Stack:** FastAPI, existing webhook engine (`safe_webhook_request`), React admin (`constants.js`, `WebhooksPage.jsx`, `WatchlistPage.jsx`), pytest + frontend unit if present.

**Spec:** `docs/superpowers/specs/2026-08-29-daily-brief-report-format-design.md`

## Global Constraints

- No inbound Discord/Telegram commands, no email, no per-slot routing, no description-LIKE products.
- No NVD-age / backup / circuit lines on the brief.
- Fan-out unchanged: destinations subscribed to `daily_brief`.
- Display label **Unmapped**; code key may stay `unanalyzed` / `UNANALYZED_LABEL`.
- Discord embed color `0xE85533` (15230259). Embed limits: 25 fields, 1024/field, 6000 total. Do not apply 2000 `content` cap to Discord embeds.
- Telegram HTML must escape `&`, `<`, `>` in interpolated titles.
- Headlines from `incident_feed:snapshot` only (no live RSS on the request path). Advisories from `publications` table only.
- Dark UI, semantic tokens, no new light theme.
- Merge gate: `./scripts/verify-local.sh`. No inline imports in new Python.
- TDD: failing test → implement → pass → commit per task.

---

### File map

| File | Responsibility |
|------|----------------|
| Modify: `backend/reports/market_clusters.py` | Display label Unmapped; keep `UNANALYZED_LABEL` key |
| Modify: `backend/reports/daily_brief.py` | Copy, headlines/advisories collect, embed + HTML formatters, ops display names |
| Modify: `backend/webhooks/engine.py` | Optional embeds + Telegram parse_mode on deliver/dispatch |
| Modify: `backend/tests/test_daily_brief.py` | Grammar, headlines, embed, HTML escape |
| Modify: `backend/tests/test_webhooks_engine.py` | Discord embed payload for daily_brief |
| Modify: `backend/tests/test_market_clusters.py` | Unmapped display |
| Modify: `frontend/src/pages/admin/constants.js` | REPORTS nav |
| Modify: `frontend/src/pages/admin/AdminPage.jsx` | Route `dailybrief` |
| Create: `frontend/src/pages/admin/DailyBriefPage.jsx` | Structured preview + delivery line |
| Create: `frontend/src/pages/admin/DailyBriefPage.css` | Section cards |
| Modify: `frontend/src/pages/admin/WebhooksPage.jsx` | Remove large preview; link to Daily brief |
| Modify: `frontend/src/pages/admin/WatchlistPage.jsx` + `AdminPage.css` | Compact triggers |
| Modify: `docs/design/daily-brief-format.md`, `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md` | Contract |

---

### Task 1: Unmapped display + human summary copy

**Files:**
- Modify: `backend/reports/market_clusters.py`
- Modify: `backend/reports/daily_brief.py` (`template_headline`, `format_daily_brief_text`, ops mapping)
- Test: `backend/tests/test_daily_brief.py`
- Test: `backend/tests/test_market_clusters.py`

**Interfaces:**
- Consumes: `cluster_published`, `UNANALYZED_LABEL` (internal key still `unanalyzed`)
- Produces: product `label` **Unmapped** for that key; `template_headline` uses “Morning briefing” facts without `led volume` for Unmapped; coverage helper `unmapped_coverage(market) -> dict` with `published`, `unmapped`, `named`

- [ ] **Step 1: Write failing tests**

```python
def test_unmapped_display_label_not_unanalyzed():
    from reports.market_clusters import cluster_published
    market = cluster_published([{"severity": "LOW", "cpe_matches": "", "affected_products": ""}])
    assert market["products"][0]["label"] == "Unmapped"
    assert "unanalyzed" not in market["products"][0]["label"]


def test_template_headline_mentions_unmapped_share():
    from reports.daily_brief import DailyBrief, COUNT_KEYS, template_headline
    from reports.market_clusters import cluster_published
    rows = [{"severity": "MEDIUM", "cpe_matches": "", "affected_products": ""}] * 6
    rows.append({"severity": "CRITICAL", "cpe_matches": '[{"product":"gitea"}]', "affected_products": ""})
    market = cluster_published(rows)
    brief = DailyBrief(
        slot="eod", tz_name="UTC",
        window_start_local="2026-08-26 18:00", window_end_local="2026-08-27 18:00",
        generated_local="2026-08-27 18:00", headline="", lede_source="template",
        counts={k: 0 for k in COUNT_KEYS},
        kev=[], stack=[], watchlist=[], ioc=[], ops=[], market=market,
    )
    text = template_headline(brief)
    assert "gitea led volume" in text.lower() or "Gitea ranked" in text or "gitea" in text.lower()
    assert "unanalyzed led volume" not in text.lower()
    assert "Unmapped" in text or "no product mapped" in text.lower()
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_market_clusters.py tests/test_daily_brief.py::test_template_headline_mentions_unmapped_share tests/test_daily_brief.py::test_unmapped_display_label_not_unanalyzed -q`

Expected: FAIL (label still `unanalyzed` or tests missing).

- [ ] **Step 3: Implement**

In `primary_product` keep returning `UNANALYZED_LABEL` (`unanalyzed`). In `cluster_published`, set display `label` to `"Unmapped"` when `key == UNANALYZED_LABEL`.

Update `template_headline`: skip Unmapped as leader (already skips `UNANALYZED_LABEL` — compare key or label). Add unmapped-share sentence when `unmapped / published >= 0.5`.

Add `_JOB_DISPLAY = {"kev_metadata_sync": "KEV metadata sync"}` and format ops as `Scheduler job failed: {display}` when `error_class == "job_error"`.

Replace `format_daily_brief_text` section titles with human names (Summary, At a glance, …) so Telegram/generic stay aligned. Drop `// HEADLINE`.

- [ ] **Step 4: Run tests — expect PASS**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_market_clusters.py tests/test_daily_brief.py -q`

Expected: PASS (plus any updated assertions on `// MARKET` strings in existing tests — update those tests to the new titles in this task).

- [ ] **Step 5: Commit**

```bash
git add backend/reports/market_clusters.py backend/reports/daily_brief.py backend/tests/test_daily_brief.py backend/tests/test_market_clusters.py
git commit -m "feat(reports): Unmapped label and human daily-brief copy"
```

---

### Task 2: Headlines and advisories on DailyBrief

**Files:**
- Modify: `backend/reports/daily_brief.py` (`DailyBrief` fields, `collect_daily_brief`, `brief_to_payload`)
- Test: `backend/tests/test_daily_brief.py`

**Interfaces:**
- Consumes: `get_feed_cache` / `feed_cache` row `incident_feed:snapshot`; `publications` table
- Produces: `brief.headlines: list[dict]` keys `source`, `title`, `url`; `brief.advisories` same; max 3 / 2; atlas excluded; URL dedup (advisory wins)

- [ ] **Step 1: Write failing tests**

```python
def test_headlines_from_snapshot_in_window(db_env):
    from database import get_db, set_feed_cache
    from reports.daily_brief import collect_daily_brief
    from datetime import datetime, timedelta, timezone

    end = datetime(2026, 8, 27, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)
    snapshot = {
        "cards": [
            {"kind": "news", "source": "Krebs on Security", "sourceId": "krebs",
             "title": "CISA adds VPN flaws to KEV", "url": "https://kreb.example/a",
             "publishedAt": "2026-08-27T10:00:00+00:00"},
            {"kind": "atlas", "source": "MITRE ATLAS", "title": "Ignore me",
             "url": "https://atlas.example", "publishedAt": "2026-08-27T11:00:00+00:00"},
            {"kind": "news", "source": "The Hacker News", "sourceId": "hackernews",
             "title": "Old", "url": "https://thn.example/old",
             "publishedAt": "2026-08-20T10:00:00+00:00"},
        ]
    }

    async def _go():
        db = await get_db()
        try:
            await set_feed_cache(db, "incident_feed:snapshot", snapshot, ttl_hours=24)
            await db.commit()
            return await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
        finally:
            await db.close()

    brief = run_db_test(_go())
    assert len(brief.headlines) == 1
    assert brief.headlines[0]["source"] == "Krebs on Security"
    assert brief_to_payload(brief)["headlines"][0]["title"].startswith("CISA adds")
```

Also assert empty advisories `[]` when `publications` has no in-window rows.

- [ ] **Step 2: Run test — expect FAIL**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_daily_brief.py::test_headlines_from_snapshot_in_window -q`

Expected: FAIL (`DailyBrief` has no `headlines`).

- [ ] **Step 3: Implement**

Add `headlines: list` and `advisories: list` on `DailyBrief` (default `field(default_factory=list)`).

`_fetch_headlines(db, start, end)`: parse snapshot JSON; skip `kind == "atlas"`; parse `publishedAt` to UTC; keep half-open `[start, end)`; sort desc; cap 3; title slice 120.

`_fetch_advisories(db, start_bound, end_bound)`: `SELECT title, canonical_url, source_key, published_at FROM publications WHERE published_at >= ? AND published_at < ? ORDER BY published_at DESC LIMIT 2` with dual placeholders. Cap 2.

Dedup: drop headline whose `url` is in advisory urls.

Wire into `collect_daily_brief` and `brief_to_payload`.

- [ ] **Step 4: pytest those tests PASS**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_daily_brief.py -q`

- [ ] **Step 5: Commit**

```bash
git add backend/reports/daily_brief.py backend/tests/test_daily_brief.py
git commit -m "feat(reports): daily brief headlines and advisories"
```

---

### Task 3: Discord embed + Telegram HTML formatters

**Files:**
- Modify: `backend/reports/daily_brief.py`
- Test: `backend/tests/test_daily_brief.py`

**Interfaces:**
- Consumes: `DailyBrief` including market, headlines, advisories, ops
- Produces: `format_daily_brief_embed(brief) -> list[dict]` (one embed); `format_daily_brief_html(brief) -> str`; `DISCORD_EMBED_COLOR = 0xE85533`

- [ ] **Step 1: Write failing tests**

```python
def test_embed_uses_orange_and_human_fields():
    from reports.daily_brief import (
        COUNT_KEYS, DailyBrief, format_daily_brief_embed, DISCORD_EMBED_COLOR,
    )
    from reports.market_clusters import cluster_published
    market = cluster_published([
        {"severity": "CRITICAL", "cpe_matches": '[{"product":"gitea"}]', "affected_products": ""},
        {"severity": "LOW", "cpe_matches": "", "affected_products": ""},
    ])
    brief = DailyBrief(
        slot="eod", tz_name="Asia/Kolkata",
        window_start_local="2026-08-26 21:15", window_end_local="2026-08-27 21:15",
        generated_local="2026-08-27 21:15", headline="2 published. gitea ranked first.",
        lede_source="template",
        counts={k: 0 for k in COUNT_KEYS} | {"critical_high_new": 1, "ops_issues": 1},
        kev=[], stack=[], watchlist=[], ioc=[],
        ops=[{"id": "kev_metadata_sync", "reason": "KEV request failed", "error_class": "job_error"}],
        market=market,
        headlines=[{"source": "Krebs on Security", "title": "VPN KEV", "url": "https://kreb.example/a"}],
        advisories=[],
    )
    embeds = format_daily_brief_embed(brief)
    assert len(embeds) == 1
    emb = embeds[0]
    assert emb["color"] == DISCORD_EMBED_COLOR == 0xE85533
    assert emb["title"] == "End of day"
    names = [f["name"] for f in emb["fields"]]
    assert "At a glance" in names
    assert "Coverage" in names
    assert "Headlines" in names
    blob = json.dumps(emb)
    assert "// HEADLINE" not in blob
    assert "Unmapped" in blob


def test_html_escapes_headline_title():
    from reports.daily_brief import COUNT_KEYS, DailyBrief, format_daily_brief_html
    brief = DailyBrief(
        slot="standup", tz_name="UTC",
        window_start_local="a", window_end_local="b", generated_local="c",
        headline="Quiet window.", lede_source="template",
        counts={k: 0 for k in COUNT_KEYS},
        kev=[], stack=[], watchlist=[], ioc=[], ops=[],
        headlines=[{"source": "THN", "title": "Foo <script> x", "url": "https://x.example"}],
        advisories=[],
    )
    html = format_daily_brief_html(brief)
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<b>Morning briefing</b>" in html or "Morning briefing" in html
```

- [ ] **Step 2: Run — expect FAIL**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 .venv/bin/python -m pytest tests/test_daily_brief.py::test_embed_uses_orange_and_human_fields tests/test_daily_brief.py::test_html_escapes_headline_title -q`

- [ ] **Step 3: Implement formatters**

`html.escape` for Telegram. Coverage field text exactly as spec (≤1024). Severity mix as four inline fields. Skip empty headlines/advisories/list sections. Ops humanized. Footer + ISO timestamp from `window_end_local` converted with `tz_name` if possible, else omit timestamp.

Overflow: if `_embed_char_count(emb) > 6000` or `len(fields) > 25`, drop fields in spec order.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/reports/daily_brief.py backend/tests/test_daily_brief.py
git commit -m "feat(reports): Discord embed and Telegram HTML daily brief"
```

---

### Task 4: Webhook engine channel payloads

**Files:**
- Modify: `backend/webhooks/engine.py` (`_deliver_discord`, `_deliver_telegram`, `deliver_to_destination`, `dispatch_event`)
- Modify: `backend/reports/daily_brief.py` (`run_daily_brief_slot` / admin test path)
- Modify: `backend/routers/admin/webhooks.py` (preview returns embeds)
- Test: `backend/tests/test_webhooks_engine.py`

**Interfaces:**
- Consumes: `format_daily_brief_embed`, `format_daily_brief_html`
- Produces: `dispatch_event(..., discord_embeds=None, telegram_parse_mode=None)`; Discord JSON `{"embeds": [...]}` when embeds non-empty

- [ ] **Step 1: Write failing test** (extend existing daily-brief generic extra test pattern)

```python
def test_discord_daily_brief_sends_embeds(monkeypatch, tmp_path):
    captured = {}

    async def fake_request(source, method, url, json=None, **_k):
        captured["json"] = json
        class R:
            def raise_for_status(self):
                return None
        return R()

    # wire one enabled discord dest subscribed to daily_brief, call dispatch_event
    # with discord_embeds=[{"title": "End of day", "color": 15230259}]
    # assert "embeds" in captured["json"]
    # assert "content" not in captured["json"] or not captured["json"].get("content")
```

Use the existing `test_webhooks_engine.py` dest fixtures. If the file uses env Discord URL, follow that pattern.

- [ ] **Step 2: FAIL then implement**

`_deliver_discord(dest, message, *, embeds=None)`: if `embeds`: `payload = {"embeds": embeds}` else `payload = {"content": _truncate(message, DISCORD_MAX_CONTENT)}`.

`_deliver_telegram(..., parse_mode=None)`: add `parse_mode` when set.

Thread kwargs through `deliver_to_destination` and `dispatch_event`.

`run_daily_brief_slot` and admin test send: `dispatch_event(..., message=html_or_plain, discord_embeds=format_daily_brief_embed(brief), telegram_parse_mode="HTML")`. Preview JSON adds `discord_embeds`.

- [ ] **Step 3: pytest `test_webhooks_engine.py` + `test_daily_brief.py` PASS**

- [ ] **Step 4: Commit**

```bash
git add backend/webhooks/engine.py backend/reports/daily_brief.py backend/routers/admin/webhooks.py backend/tests/test_webhooks_engine.py
git commit -m "feat(webhooks): send daily brief as Discord embeds"
```

---

### Task 5: Admin Daily brief page + Webhooks pointer + watchlist density

**Files:**
- Modify: `frontend/src/pages/admin/constants.js`
- Modify: `frontend/src/pages/admin/AdminPage.jsx`
- Create: `frontend/src/pages/admin/DailyBriefPage.jsx`
- Create: `frontend/src/pages/admin/DailyBriefPage.css`
- Modify: `frontend/src/pages/admin/WebhooksPage.jsx`
- Modify: `frontend/src/pages/admin/WatchlistPage.jsx`
- Modify: `frontend/src/pages/AdminPage.css`
- Test: `frontend/src/pages/admin/adminFormFieldGate.test.js` or a small `DailyBriefPage` unit if the repo uses vitest on admin pages — follow existing `toastCopy.test.js` pattern: assert nav id `dailybrief` exported / Watchlist class `admin-watchlist-triggers`.

**Interfaces:**
- Consumes: `GET /api/admin/webhooks/daily-brief/preview`, `POST .../test`, `GET /api/admin/webhooks/destinations`
- Produces: operator nav REPORTS → Daily brief; structured sections from `brief`; delivery “Sends to {labels} (Daily brief subscribed)”

- [ ] **Step 1: Failing frontend unit**

```javascript
import { NAV } from './constants.js'
it('includes Daily brief under REPORTS', () => {
  const reports = NAV.find(s => s.section === 'REPORTS')
  expect(reports.items.some(i => i.id === 'dailybrief')).toBe(true)
})
```

Put in `frontend/src/pages/admin/constants.test.js` if that pattern exists; else add next to `adminFormFieldGate.test.js`.

- [ ] **Step 2: FAIL, then implement nav + page**

`NAV` insert after DATA or before CONFIGURATION:

```javascript
{ section: 'REPORTS', items: [{ id: 'dailybrief', label: 'Daily brief', icon: 'Newspaper' }] },
```

Use an icon already imported in `Sidebar.jsx` (if `Newspaper` missing, use `ScrollText` or `FileText` already in the icon map).

`VALID_ADMIN_PAGES` add `dailybrief`. Render `<DailyBriefPage toast={toast} />`.

Page: reuse Webhooks daily-brief fetch logic (move helpers if needed, do not duplicate event-type bugs). Render Summary / At a glance / Coverage / products / headlines / advisories / ops as bordered cards (`var(--border-subtle)`, `var(--surface-raised)`). Slot EOD/standup, Preview, Send test.

WebhooksPage: delete the `<pre className="webhook-daily-brief-preview">` card; add `<Link to="/admin?p=dailybrief">Daily brief preview and schedule</Link>`.

WatchlistPage: wrap triggers in `div.admin-watchlist-triggers` (column, `max-width: 24rem`, `gap: var(--space-2)`). HelpTip text includes “not the daily brief.”

- [ ] **Step 3: `cd frontend && npm run test:unit`** (or the file’s vitest command)

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/admin frontend/src/pages/AdminPage.css
git commit -m "feat(admin): Daily brief report page and compact watchlist triggers"
```

---

### Task 6: Docs

**Files:**
- Modify: `docs/design/daily-brief-format.md`
- Modify: `docs/PRODUCT_STATUS.md`
- Modify: `docs/API_REFERENCE.md`

**Interfaces:** Format file wins for channel grammar; PRODUCT_STATUS wins after ship.

- [ ] **Step 1: Update format doc** — embed field map, Unmapped coverage paragraph, Headlines/Advisories, no `//` titles on Discord, Telegram HTML, 2000 cap does not apply to Discord embeds.

- [ ] **Step 2: PRODUCT_STATUS Daily brief row** — embed + headlines; Admin → Daily brief; no inbound commands.

- [ ] **Step 3: API_REFERENCE** — `brief.headlines`, `brief.advisories`, `discord_embeds` on preview.

- [ ] **Step 4: `./scripts/verify-local.sh`** from repo root.

- [ ] **Step 5: Commit**

```bash
git add docs/design/daily-brief-format.md docs/PRODUCT_STATUS.md docs/API_REFERENCE.md
git commit -m "docs: daily brief embed grammar and admin report page"
```

---

## Spec coverage (self-review)

| Spec section | Task |
|--------------|------|
| Unmapped copy + snapshot | 1 |
| Human labels / ops | 1 |
| Headlines / advisories | 2 |
| Embed / HTML | 3 |
| Engine | 4 |
| Admin + watchlist | 5 |
| Docs | 6 |
| No commands / no instance health | Global constraints |

No TBD. Types: `headlines`/`advisories` lists of `{source, title, url}`; `discord_embeds` list of Discord embed dicts; `DISCORD_EMBED_COLOR = 0xE85533`.
