# Wallboard v2 plan (2026-07-10)

**Status:** planning only — no implementation yet.  
**Trigger:** operator testing — token works via `.env` but missing from Admin config UI;
theme mismatch; room for richer stack-aware tiles.

---

## Current behaviour (as shipped)

| Piece | Reality |
|-------|---------|
| Route | `/wallboard` (no admin chrome) |
| API | `GET /api/wallboard` — six tiles, ~45s `feed_cache` TTL |
| Auth | Optional `WALLBOARD_TOKEN` in **process env** only (`settings.py`) |
| Client auth | Header `X-BRIEFR-Wallboard-Token`; UI stores in `sessionStorage` |
| URL `?token=` | Frontend still reads query once → sessionStorage (API does **not** accept query — Sprint A7) |
| Stack source | `BRIEFR_STACK_TERMS` env **wins**, else latest non-empty `user_preferences.stack_terms` |
| Tiles today | KEV-on-stack, 24h changes, top risk (global), ingest health, coverage gaps, headlines |

**Gap (confirmed):** `WALLBOARD_TOKEN` is **not** in `config_schema.py` → no field on
**API keys & config** despite `SecurityPage.jsx` copy saying “Set under API keys & config”.
Only `.env` / env injection works (your workflow).

---

## Track N — proposed sprint items

### N-1 · Config surface for wallboard (small, high value)

- Add `WALLBOARD_TOKEN` to `config_schema` (`type: secret`, section `security` or `app`,
  `restart_required=True`).
- Expose in Admin — new **Security / kiosk** subsection on API keys page **or** field on
  Security page with generate + save (like webhook bootstrap).
- Fix `SecurityPage.jsx` copy to match actual location after N-1.
- POST save uses same masking as other secrets; audit row must be redacted (depends on **M-1**).
- Optional: `RATE_LIMIT_WALLBOARD_PER_MINUTE` in schema (today env-only).

**Acceptance:** operator can set/rotate token without editing `.env` manually; restart
badge shown; GET config shows masked token state (`…last4`).

### N-2 · Theme alignment (visual)

Wallboard already uses CSS variables from `App.css`, but **feels different** because:

- Brand uses `--font-display` (DM Serif Display) at huge size — main app is **mono-forward**
  terminal aesthetic per `PRODUCT.md`.
- Tiles use very large metrics (`clamp` up to 6.5rem) — kiosk-friendly but not BRIEFR-dense.
- Active tile glow + ticker animation read more “dashboard TV” than “intel terminal”.

**Direction:**

- Labels: `--font-mono`, uppercase, same pill/tooltip patterns as feed.
- Metrics: one hero number per tile max; secondary stats smaller (ingest → compact strip).
- Colors: `--bg`, `--bg2`, `--border`, `--accent`, `--red`/`--amber`/`--green` only — no new palette.
- Optional layout mode: `?density=compact` for 4K wall vs tablet.

### N-3 · Content & layout v2 (stack-aware)

**Layout proposal (3 tiers):**

```
┌─────────────────────────────────────────────────────────────┐
│ BRIEFR · stack: nginx, pan-os · Updated 19:04 UTC          │
├──────────────────────────┬──────────────────────────────────┤
│ HERO (stack-critical)    │ HERO (global intel)              │
│ · KEV on stack (count)   │ · Top risk CVE + score           │
│ · KEV due <7d on stack   │ · New KEV last 24h               │
├──────────────────────────┴──────────────────────────────────┤
│ STRIP: ingest OK · NVD 2h · circuits 0 · CVEs 20,507 · poll  │
├─────────────────────────────────────────────────────────────┤
│ SECONDARY GRID (rotate or scroll)                            │
│ · 24h action queue · coverage gaps · EPSS movers · campaigns │
├─────────────────────────────────────────────────────────────┤
│ TICKER: incident headlines (existing)                        │
└─────────────────────────────────────────────────────────────┘
```

**Stack logic:**

| Stack configured? | Behaviour |
|-------------------|-----------|
| Yes (`BRIEFR_STACK_TERMS` or saved Feed stack) | Hero left = stack KEV + due dates; changes_24h weighted to `stack_matches`; top_risk **filtered to stack** (today top_risk is global only); coverage gaps already stack-scoped |
| No | Hero left shows “Configure stack” + org-wide KEV count; tiles show global intel; same as today but clearer empty state |

**New / enriched data (backend tiles — no new external APIs):**

- KEV due soon on stack (from morning brief `kev_due_soon` section).
- NVD / KEV last sync age (from `get_ingest_status()` / health — compact strip).
- Open circuits by source name (one line, not full feed health blob).
- Optional: correlation campaign count if any active (DB read).
- EPSS movers top 3 (brief section already exists).

**Deprioritize / shrink:**

- Ingest health: from full tile → **one-line strip** (OK / DEGRADED / SYNCING + ages).
- Headlines: keep ticker; tile can merge into ticker only.

### N-4 · Kiosk ops (later)

- QR / one-time setup card on Security page: URL + “paste token once on display”.
- Document: do not bookmark `?token=` (browser history); use modal once per session.
- Optional static display mode: hide token modal after success for 30 days (localStorage flag).

---

## Dependencies

- **M-1** audit redaction before N-1 saves token via admin API.
- **M-4/M-5** backup interval guard independent of operator setting 24h / retain 20.

---

## Out of scope (v2)

- Charts/graphs requiring new chart library (prefer numbers + sparkline CSS if any).
- Click-through to CVE drawer (kiosk is read-only; no auth).
- STIX / export links.
