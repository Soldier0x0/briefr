# Program — Product polish & open-core readiness

**Status:** Active (2026-07-10)  
**Purpose:** Single execution plan for SaaS-grade self-host UX, user data on
Postgres, and safe intel distribution — without bloating `SPRINT_2026-07.md`.

**Read order:** `CLAUDE.md` → `PRODUCT_STATUS.md` → `HANDOVER.md` (top entry) →
this file → `POSTGRES_NATIVE_PLAN.md` (Post-B detail).

---

## Locked decisions

| Topic | Decision |
|-------|----------|
| Production database | **PostgreSQL 16+** required. BYO host (Docker, RDS, on-prem) OK. Not SQLite/Mongo/MySQL at runtime. |
| Intel for open core | **Postgres snapshot first** (`pg_dump` allowlist). Portable JSONL import later. |
| Operator production data | **Never** raw `pg_dump` of prod. Export via allowlist script only. |
| User prefs / stack | Postgres per user; unified stack API; optional “session only vs remember on server”. |
| Open-core economics (v1) | **Code free**; first intel snapshot **free monthly** (adoption over revenue). |
| July sprint | **Closed for new scope** — interleave D4 + Post-B; program waves 1–3 **done**. |

---

## Agent workflow (mandatory)

Same process for every PR — full detail in `HANDOVER.md` top entry (2026-07-08):

1. `cursor/<name>-6fd2` branch → 2. local `pytest` / `npm run build` →
3. push + non-draft PR → 4. address Gemini inline comments →
5. CI green → 6. docs if behavior changed → 7. merge.

**Co-founder mindset:** execute locked program order; specs over improvisation;
CI + Gemini gate merges; minimum correct diff; `PRODUCT_STATUS.md` is truth.

---

## Public promise (one sentence)

> Self-hosted CVE intel ranked for your stack, with correlation and detection
> content — your PostgreSQL, your keys, no vendor lock-in.

Do not over-claim ML (see `STRATEGY.md` claims table).

---

## Database policy (FAQ)

**Supported:** PostgreSQL 16+ on any host you control.

**Not supported for production:** SQLite (single-writer, scheduler contention),
MongoDB (wrong relational shape), MySQL (second dialect tax; Post-B removes
translation shim for a reason).

**Freedom we provide:** hosting choice, `pg_dump` export, optional portable
intel import (later). **Freedom we do not provide:** untested alternate SQL
engines.

See `DATA_SNAPSHOT.md` (added in Wave 3) for intel bundle format.

---

## Execution waves

One concern per PR unless noted. Browser-verify UI items. Update
`PRODUCT_STATUS.md` when runtime behavior changes.

### Wave 1 — Product feel (no schema risk) · **2 PRs** — **DONE** (#308–#309)

| PR | Scope | Acceptance |
|----|-------|------------|
| **1** | Admin config Save UX | Per-field Save; button “Save” vs “Save & restart”; fix misleading copy; stop toasting “added to queue”; bool toggles save inline |
| **2** | Toast + restart UX | Pause on hover/focus; fewer success toasts; restart **banner** until `/api/health` OK; copy-ID feedback; notification policy in this doc § below |

### Wave 2 — One stack, one truth · **3–4 PRs** — **DONE** (#310–#314)

| PR | Scope | Acceptance |
|----|-------|------------|
| **3** | Migration + `GET/PUT /api/me/stack` | Terms + optional profile JSON; keyed by `user_id` |
| **4** | Frontend unified stack | Remove `briefr_stack` localStorage split; feed + webhooks + wallboard read same API |
| **5** | `GET/PATCH /api/me/preferences` | Display prefs, timezone; migrate off localStorage |
| **6** | Asset profile persistence | Toggle: session-only (default shared terminal) vs remember-on-server |

Update `PrivacyPage.jsx` when 4–5 land (stack not “browser only”).

Optional **7:** field-level encryption for profile blobs (`BRIEFR_DATA_KEY`) — defer
until open-core flip unless required.

### Wave 3 — Open-core data plane · **2 PRs** — **DONE** (#315–#317)

| PR | Scope | Acceptance |
|----|-------|------------|
| **8** | ADR + `DATA_SNAPSHOT.md` | INTEL vs OPERATOR table lists; F1 schema split ADR |
| **9** | `scripts/export_intel_snapshot.py` | Allowlist export; restore docs; CI restore smoke (align Track J2) |

Ops (not a code PR): publish `briefr-intel-YYYY-MM.pgdump.gz` from export script.

### Wave 4 — Launch gate — **DONE** (#366–#372)

| Item | PR / note |
|------|-----------|
| Watchlist monitor alerts (`watchlist_alert` webhooks) | #366 |
| Operator settings in DB (`app_settings`) | #368 |
| `briefr doctor` / support pack export | #370 |
| First-hour onboarding checklist + external Postgres profile | #371 |
| Intel snapshot versioning + upgrade runbook | #372 |

**Track F2 (license) is done** — `LICENSE`, `NOTICE`, `CONTRIBUTING.md`, `FUNDING.yml`, and SPDX
headers reflect **Apache License 2.0** (see `STRATEGY.md` §6; relicense 2026-07-24).
Full V2.0 platform compose remains parked per `ROADMAP.md`.

---

## INTEL vs OPERATOR tables

**Include in public intel snapshot** (derived public intel + BRIEFR compute):

`cves`, `kev_deadlines`, `epss_history`, `cve_change_history`, `mitre_techniques`,
`cve_technique_map`, `atlas_techniques`, `atlas_case_studies`, `cve_atlas_map`,
`cve_exploits`, `feed_cache`, `otx_cve_pulses`, `otx_pulse_iocs`, `otx_pulses`,
`correlation_actor`, `correlation_temporal`,
`correlation_campaigns`, `correlation_campaign_members`, `cve_embeddings`,
`mitre_groups`, `group_technique_map`, ingest watermarks in `sync_state` (allowlist keys only).

**Never include** (operator / sensitive):

`users`, `sessions`, `watchlist`, `audit_log`, `ioc_cache`, `api_usage`,
`webhook_destinations`, `webhook_delivery_log`, `webhook_alert_log`,
`correlation_suppressions`, `hunt_packs`, scheduler pause flags in `sync_state`.

Full spec in `DATA_SNAPSHOT.md` (Wave 3 PR 8).

---

## Notification policy (toast vs inline vs banner)

| Event | Channel |
|-------|---------|
| Config saved (live) | Inline ✓ on row or single calm toast (8s, pauses on hover) |
| “Added to queue” | **No toast** — queued badge only |
| Backend restarting | Top **banner** + health poll; not a 4s toast |
| API error | Persistent error toast until dismissed; actions: copy ref, view log |
| Routine admin OK (“job paused”) | Inline table state or short toast; no bright slide-in stack |
| Long job | Operation strip (admin) or progress UI (analyst exports) |

---

## Sprint cross-links

| Sprint item | Program home |
|-------------|--------------|
| **E7** (new) | Wave 1 PR 1 — config Save UX |
| **H1a** (new) | Wave 1 PR 2 — toast policy |
| **F1** | Wave 3 PR 8 — intel/app ADR |
| **J2** | Wave 3 PR 9 — snapshot restore CI |

---

## Parallel work (do not stop)

| Track | Status |
|-------|--------|
| **D4** | **Done** (#312) — Nuclei parser + Sigma artifact injection |
| **Post-B** | **Done** (#318–#328, #343) — Postgres-native `db/`, dialect deleted |
| **F3** | **Mostly done** (#319) — gitleaks + `SECURITY.md`; F2/LICENSE before flip |
| **Wave 4** | **Done** (#366–#372) — see table above |

---

## Success markers

| Milestone | Signal |
|-----------|--------|
| Wave 1 | Change API key without restart confusion; toasts feel professional |
| Wave 2 | Stack in feed = stack for KEV alerts; survives browser change |
| Wave 3 | Publish intel snapshot with zero operator rows |
| Launch-ready | F3 pass + compose + free snapshot + README database FAQ |

---

## PR sequence (historical — waves 1–3 complete)

```
✅ Wave 1  #308–#309  Config Save + toast/restart
✅ Wave 2  #310–#314  Stack API + frontend + prefs + profile
✅ Wave 3  #315–#317  DATA_SNAPSHOT + export script
✅ Wave 4  #366–#372  Monitor alerts, operator settings, doctor, onboarding, snapshot versioning
✅ D4      #312       Nuclei parser + Sigma wiring
✅ Post-B  #318–#343  Postgres-native db/ + CI backup round-trip
✅ F3      #319       SECURITY.md + gitleaks
```

**Total to open-core-ready:** Waves 1–4 + Post-B + F3 done; **F2** license flip remains.
