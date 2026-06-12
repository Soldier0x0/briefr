# BRIEFR — Agent Session Plan & Prompts (V1.3 → V1.5)

Copyright © 2026 Sai Harsha Vardhan. All rights reserved. Proprietary and confidential.

**Last updated:** 2026-06-12
**Status:** Temporary working document — companion to [`HANDOVER.md`](HANDOVER.md). Delete when V1.5 ships.
**Usage:** 1 prompt = 1 agent session = 1 PR. Default model: **Composer 2.5**. Upgrade only where flagged. Paste the [boilerplate](#boilerplate--append-to-every-prompt) at the end of every prompt. Merge PRs **one at a time** after testing; within a parallel group, launch all sessions off the same fresh `main`.

---

## Boilerplate — append to EVERY prompt

```text
Workflow (mandatory): read docs/HANDOVER.md §7 and follow it strictly. Branch
cursor/<descriptive-name> off fresh main. One PR, this item ONLY — do not touch
other roadmap items. Run `cd backend && pytest tests/ -q` before every push
(never red). If frontend changed: `cd frontend && npm run build` must pass.
Update in the SAME PR: API_REFERENCE.md (endpoint changes), SYSTEM_DESIGN.md
(runtime behavior), TECHNICAL_INVENTORY.md (schema/scheduler changes),
backend/.env.example + README.md + docs/ONBOARDING.md (new env vars), the item
status in the Beta V1.x.md doc, and the PR ledger in docs/HANDOVER.md §3.
Compatibility: additive API responses only; forward-only idempotent migrations
(the ALTER TABLE try/except list in database.py:init_db); env defaults
unchanged; SQLite = 1 uvicorn worker. Conventions: imports at top of module;
resilient_client for ALL outbound HTTP; feed_cache for caching; cancellation
guards in frontend effects; useModalLayer for any new overlay. Do not start a
live dev server — pytest and npm build only. Do not re-read the whole repo;
read only the files this task names plus the release-doc section.

PR description (mandatory): include (1) a "Post-merge verification" section
with copy-pasteable commands for the production box (http://127.0.0.1:8000,
journalctl -u briefr-backend, sqlite3 /opt/briefr/backend/briefr.db), and
(2) a "Manual testing" section listing the exact browser clicks/keys to verify
every change you actually made — written for the operator, not a developer.
```

---

## V1.3 (Tranche 2)

**Wave 1 — T2-S1 … T2-S6 can run in parallel** (separate modules/surfaces).
**Wave 2 — T2-S7 → T2-S8 → T2-S9 strictly in this order, after wave 1 merges.**

### T2-S1 — What-changed UI + KEV due-date countdown (Composer)

```text
Read Beta V1.3.md (rows: Change intelligence, KEV due-date countdown) and
docs/HANDOVER.md §6 Tranche 2. Implement BOTH in one PR:
1. What-changed UI: surface the existing GET /api/changes endpoint (see
   API_REFERENCE.md — no new backend logic expected) in the frontend: a
   "What changed" panel showing recent cvss_score/epss_score/is_kev/has_poc
   deltas, filter chips for field type and window (24h/48h/7d via
   since_hours), each row opens the CVE drawer.
2. KEV countdown: "Due in N days" chip on CVE cards for KEV entries. Data
   source: kev_deadlines.due_date — verify whether it is already in the
   /api/cves list payload; if not, add it additively. Urgency colors: <7 days
   red, <14 amber, else neutral. Add a deadline-sorted list using
   GET /api/kev/deadlines?sort=urgent.
Follow existing card/filter patterns from PR #90 (anchored scroll on filter
click, cancellation guards in effects).
```

### T2-S2 — Forge MVP (Composer; **upgrade to Fable 5 High recommended** — new subsystem, design decisions)

```text
Read Beta V1.3.md § Forge (authoritative spec) and the strategy note in
docs/JUPITER_VISION.md. Implement ONLY the MVP scoped for V1.3: detection
coverage map, hunt-packs API, CVE→pack linkage. Backend: new router + tables
exactly per spec (idempotent migrations). Frontend: Forge tab per spec,
plain JSX+CSS consistent with the existing app. Do NOT build anything the
spec marks for later phases.
```

### T2-S3 — New intel sources, batch 1: Vulnrichment + cvelistV5 (Composer)

```text
Read docs/HANDOVER.md §6 Tranche 2 (new intel sources) and the matching rows
in Beta V1.3.md. First read one existing feed module end-to-end as the
pattern (backend/feeds/osv.py) plus scheduler.py job registration.
Implement TWO feed modules: CISA Vulnrichment and cvelistV5. Both are
snapshot-type sources — no watermark needed. Each: backend/feeds/<name>.py
using resilient_client (source name must appear in /api/health
feeds.sources), scheduler job with env-configurable interval, data merged
additively into existing cves columns (severity/CWE enrichment per spec) —
never overwrite richer data with poorer data. Scheduler-side only — nothing
on the request path. Tests with fixture JSON files under tests/fixtures.
```

### T2-S4 — New intel sources, batch 2: PoC-in-GitHub + ExploitDB + Metasploit + Nuclei (Composer)

```text
Same pattern as batch 1 (read backend/feeds/osv.py + scheduler.py first;
see also how cve_exploits and has_poc are populated today via
feeds/extended.py). Implement FOUR exploit-availability sources:
PoC-in-GitHub index, ExploitDB CSV, Metasploit module metadata, Nuclei
templates index. Feed cve_exploits rows and set has_poc=1 additively —
NEVER downgrade has_poc from 1 to 0. Scheduler-side only, throttled,
resilient_client, fixture-based tests.
```

### T2-S5 — Embeddings + LLM product extraction (Composer; **upgrade to Fable 5 High strongly recommended** — ML gating + fallback design)

```text
Read Beta V1.3.md § embeddings, docs/HANDOVER.md §6, and the ML placement
rules in docs/ROADMAP.md (env-gated, CPU-only, scheduler-side only,
deterministic fallback mandatory, tool fully functional with ML disabled).
Implement:
1. CVE description embeddings stored as BLOBs in SQLite; NumPy brute-force
   cosine similarity as the default path; use sqlite-vec ONLY if importable,
   never as a hard dependency. Powers "similar CVEs": extend
   GET /api/cves/{id}/related additively (keep the existing heuristic as the
   fallback when embeddings are disabled/absent).
2. LLM product extraction for NVD-unanalyzed CVEs (no CPE data): env-gated
   via GROQ_API_KEY, scheduler job, writes affected_products ONLY when the
   field is empty, marks provenance so LLM-derived data is distinguishable.
Default state: disabled (EMBEDDINGS_ENABLED=0). Document every new env var.
```

### T2-S6 — First webhook channel + KEV-on-stack rule + backup dead-man ping (Composer; Sonnet 4.6 suggested)

```text
[CONFIRM BEFORE PASTING: Telegram or Discord — pick one and state it here.]
Read Beta V1.3.md § alerts/webhook and docs/HANDOVER.md §6. Implement:
1. Env-configured webhook sender module for the chosen channel
   (resilient_client, retries=2, disabled unless the webhook env var is set).
2. KEV-on-stack rule: scheduler hook after each KEV sync — when a CVE
   matching the operator's stack enters KEV, send one alert. Dedupe so each
   CVE alerts exactly once (marker table or sync_state). If the spec leaves
   the stack source ambiguous (asset profile is client-side), use an env var
   BRIEFR_STACK_TERMS (comma-separated) and document it.
3. Backup dead-man ping: if no successful backup within 2× the backup
   interval, send a warning through the same channel (scheduler check).
```

### T2-S7 — Morning brief API + explainable risk UI (Composer; **Fable 5 High or Sonnet 4.6 recommended** — IA change + scoring UI)

```text
[CONFIRM BEFORE PASTING — HANDOVER §9 Q1: does the brief become the landing
view with the full feed demoted to a second view? Default recommendation:
yes. State the decision here.]
Read Beta V1.3.md § morning brief + § explainable risk. Implement:
1. GET /api/brief: server-computed brief per spec (e.g. top movers since
   yesterday, new KEV entries, KEV due soon, stack matches) — read-path
   queries only, no new ingest.
2. Brief view UI per the landing-view decision above.
3. Explainable risk UI in the drawer: component breakdown (KEV / EPSS /
   stack match / momentum) using GET /api/config/risk weights and
   GET /api/cves/{id}/momentum signals — show the math, no black box.
```

### T2-S8 — Chart.js brief dashboard (Composer) — after T2-S7 merges

```text
Read Beta V1.3.md § dashboard. Add Chart.js charts to the brief view:
severity/volume timeline (GET /api/stats/timeline), KEV due-date histogram,
top EPSS movers. Chart.js must be an npm dependency bundled locally — no
CDN (CSP is strict, see add_security_headers in backend/main.py). Lazy-load
the chart bundle; respect prefers-reduced-motion (PR #90 conventions).
```

### T2-S9 — Watchlist / pin / snooze (Composer) — after T2-S8 merges

```text
Read Beta V1.3.md § watchlist row. NOTE the auth decision (ROADMAP amendment
2026-06-11): single-user for now — no user keying; built-in app login adds
it later. Implement: watchlist table (cve_id, state pin|snooze,
snooze_until, created_at; idempotent migration), additive
GET/POST/DELETE /api/watchlist endpoints, pin/snooze controls on CVECard +
drawer, pinned CVEs float to feed top, snoozed hidden until expiry, a
watchlist filter chip. Persist server-side (DB), not localStorage.
```

---

## V1.4 (Tranche 3)

**T3-S1, T3-S2, T3-S3 can run in parallel. T3-S4 only after T3-S2 merges.**
**T3-S0 (app login) is NOT optional before public release — schedule it with best available model.**

### T3-S0 — Built-in app login (⚠️ **Fable 5 High strongly recommended** — auth/security; run before or alongside T3-S2)

```text
Decision 2026-06-11 (see docs/ROADMAP.md amendments): BRIEFR auth = built-in
app login, shipped before public release. Design and implement: users table
(single admin user bootstrapped from env on first start), argon2/bcrypt
password hashing, session cookie (httponly, samesite=lax, secure in
production), login/logout endpoints + minimal login page, gate all write/
admin routes when login is enabled (env flag, default off during beta),
wire request.state.user_email so audit_log.actor is populated (hook already
exists in main.py:_audit). No multi-user, no roles beyond admin-or-not, no
OAuth. Read docs/THREAT_MODEL.md § Spoofing first.
```

### T3-S1 — Webhook engine (⚠️ **Fable 5 High strongly recommended** — SSRF security-critical; if run on Composer, audit afterwards)

```text
Read Beta V1.4.md § webhooks and docs/THREAT_MODEL.md (SSRF rows). Generalize
the V1.3 single-channel sender into an engine: multiple destinations
(env/DB config per spec), event types (kev_alert, backup_failure, health),
per-destination enable/disable, dedupe.
MANDATORY SSRF protections — implement ALL, exactly:
- resolve the destination hostname and BLOCK private/reserved ranges:
  RFC1918, 127.0.0.0/8, ::1, link-local 169.254.0.0/16 (cloud metadata),
  0.0.0.0, unique-local IPv6;
- disable redirect following on webhook requests (a redirect could point
  to an internal address after the check);
- https scheme only;
- never attach internal API keys/secrets to outbound webhook headers;
- 10s timeout; failures recorded via resilient_client health.
Unit tests MUST cover every blocked address class and the redirect case.
```

### T3-S2 — Lean admin pane (Composer)

```text
Read Beta V1.4.md § admin, including the lean-first scope amendment.
Implement ONLY: system health section, backups (list + manual trigger +
integrity badge), ingest/scheduler controls (pause/resume, manual refresh),
per-feed health (feeds.sources), audit log viewer (audit_log table, newest
first, filter by action). Defer everything else the amendment defers
(config editor, integrations UI, users stub, restore wizard, support pack).
Gate /api/admin/* with X-BRIEFR-Admin-Key for now (app login integration
comes with T3-S0 if not yet merged — check git log). Frontend: /admin
route, plain JSX+CSS consistent with the app, read-only except the trigger
actions listed above. Every admin action writes an audit_log row.
```

### T3-S3 — Wallboard (Composer)

```text
Read Beta V1.4.md § wallboard. Read-only rotating display view per spec.
Endpoints token-gated with WALLBOARD_TOKEN env (read-only scope, rate
limited — reuse the V1.2 §5.5 rate limiter), no admin data exposed. Build
it last in this wave if you must choose; lowest priority of the tranche.
```

### T3-S4 — Log viewer (Composer) — after T3-S2 merges

```text
Read Beta V1.4.md § log viewer. Surface the structured JSON logs (request-ID
logging from V1.2 §5.5) inside the admin pane: an in-process ring buffer or
log-file tail endpoint /api/admin/logs with level + request_id filters.
No shelling out to journalctl from the app. Admin-gated like the rest of
the pane.
```

---

## V1.5 (Tranche 4)

**All five sessions can run in parallel** (separate subsystems). Merge one at a time.

### T4-S1 — Threat model UI (Composer)

```text
Read Beta V1.5.md § threat model UI (authoritative spec) and implement
exactly that scope: analyst-facing environment threat scenarios view.
Frontend-led; any backend additions must be additive read endpoints.
```

### T4-S2 — Rule proof bench, file-based (Composer; Sonnet 4.6 if credits allow)

```text
Read Beta V1.5.md § rule proof bench. File-based as specified — no new
infrastructure/services. Implement per spec; tests with fixture log/event
files under tests/fixtures.
```

### T4-S3 — KEV delta backlog (Composer)

```text
Read Beta V1.5.md § KEV delta backlog and implement per spec, building on
the existing kev_deadlines table + KEV sync job. Idempotent migrations;
additive API.
```

### T4-S4 — STIX 2.1 export + Sigma pack zip (Composer; **Sonnet 4.6 / Fable recommended** — interop correctness)

```text
Read Beta V1.5.md § STIX/Sigma export. Implement STIX 2.1 bundle export and
Sigma pack zip download endpoints per spec. STIX output MUST be validated
in tests against the official `stix2` Python library (add as a dependency)
— hand-rolled JSON that merely looks like STIX is not acceptable. Zip
streaming for the Sigma pack; no temp-file leaks.
```

### T4-S5 — IOC watchlist + ThreatFox + retro-match + VulnCheck KEV tier (Composer; Sonnet 4.6 suggested)

```text
Read Beta V1.5.md § IOC watchlist/ThreatFox/VulnCheck and the ROADMAP
amendment row (retro-match = zero extra API quota: match new feed IOCs
against the local watchlist table, no per-IOC enrichment calls). Implement:
ioc_watchlist table INDEXED ON IOC VALUE (idempotent migration), CRUD API +
UI in the IOC tab, ThreatFox feed module (resilient_client, scheduler-side,
abuse.ch auth key reused), retro-match job flagging watchlist hits on new
ThreatFox data, VulnCheck KEV tier per spec (env-gated API key).
```

---

## After V1.5 ships

Per HANDOVER §9.4: bump version, regenerate `SYSTEM_DESIGN.pdf` +
`TECHNICAL_INVENTORY.xlsx` (commands in `ONBOARDING.md` §8), retire
HANDOVER.md and this file. Run a final security audit session (best
available model) focused on: webhook SSRF, app login/session handling,
admin pane authz, export endpoints.
