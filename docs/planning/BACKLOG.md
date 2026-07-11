# Planning backlog (open / parked / optional)

**Purpose:** single queue for work that is **not** done — extracted from merged planning
docs so nothing is lost when specs move to [`archive/superseded/`](../archive/superseded/) or stay in [`specs/`](specs/).

**Rules**

| Symbol | Meaning |
|--------|---------|
| 📋 | Ready to implement when maintainer activates |
| 🔶 | Partially shipped — see note |
| 💬 | Needs operator/maintainer decision before build |
| 🅿️ | Parked — explicit signal required |
| ✅ | Shipped — listed only so it is **not** re-queued |

**Authoritative runtime truth:** [`../PRODUCT_STATUS.md`](../PRODUCT_STATUS.md) and
[`../HANDOVER.md`](../HANDOVER.md). **Build order when activated:** add checkboxes to
[`../SPRINT_2026-07.md`](../SPRINT_2026-07.md) or a future sprint doc.

**Last reconciled:** 2026-07-11 against `main` post-#454.

---

## 1. Sprint checklist (still open)

| ID | Item | Status | Source |
|----|------|--------|--------|
| **O-3** | `WALLBOARD_TOKEN` in `config_schema` + admin save/rotate (Security copy already points at API keys & config; field is **env-only** today) | 📋 | Sprint Track O; [`specs/ux-audit.md`](specs/ux-audit.md) Issue 23–24 |
| **G0** | Refresh `LEARNING_PATH.md` + `ONBOARDING.md` for final shipped system | 🅿️ end-of-lifecycle | Sprint §G |
| **G1–G4** | Maintainer modules 1–4 (trace + private notes) | 🅿️ end-of-lifecycle | Sprint §G |
| **Phase 4 STIX/Sigma export** | V1.5 tail | 🅿️ | Sprint V1.5 |

---

## 2. Correlation engine v3 program

**Canonical spec:** [`specs/correlation-engine-v2.md`](specs/correlation-engine-v2.md)  
**Shipped tail only:** #434 (phase 4–5 partial — `cve_id` cluster filter, structured job logs).  
**Full PR-1…PR-13 program below is still open** unless marked ✅.

| PR | Title (phase) | Status |
|----|---------------|--------|
| PR-1 | Rank infrastructure peers by evidence (0) | 📋 |
| PR-2 | Composite index + drop `correlation_infrastructure` (0) | 📋 |
| PR-3 | `ioc_degree` + degree-penalized edge confidence (1) | 📋 |
| PR-4 | Remove severity/size from confidence (1) | 📋 |
| PR-5 | Confidence factor vector in API + drawer (1) | 📋 |
| PR-6 | Capture `observed_at` on pulse IOCs (2) | 📋 |
| PR-7 | Lifecycle + momentum use observation time (2) | 📋 |
| PR-8 | Read-time freshness decay + UI staleness (2) | 📋 |
| PR-9 | Pulse families + campaign dedup + retraction (3) | 📋 |
| PR-10 | ThreatFox corroboration on IOC edges (3) | 📋 |
| PR-11 | Alias-aware attribution + conflict surfacing (4) | 📋 |
| PR-12 | Analyst confirm feedback (4) | 📋 |
| PR-13 | `correlation_metrics` nightly + admin + feed-boost gating (4) | 📋 |

**Maintainer open questions (§21):** confidence regression comms (PR-4+5); pulse-family
thresholds (PR-9); suppression migration on dedup (PR-9); confirm-link UI vs API-only
(PR-12); half-life defaults (PR-8); feed ordering change (PR-13/D9); scale verification
before PR-9.

---

## 3. Codebase security / reliability / performance audit

**Canonical spec:** [`specs/codebase-audit.md`](specs/codebase-audit.md)  
**Shipped in #449:** AUTH-001, AUTH-002, VAL-002, IDEM-001/TXN-001, DB-001, DB-002.

### Remaining remediation PRs (§17)

| PR | Title | Status |
|----|-------|--------|
| PR-P3 | Index `cves.modified` | 📋 |
| PR-P4 | KEV upsert batching | 📋 optional |
| PR-O1 | Feed empty → scheduler `had_error` | 📋 |
| PR-O2 | Correlation GET read-only split (CACHE-001) | 📋 |
| PR-F1 | Admin nav role gate + 403 redirect | 📋 |
| PR-F2 | `safeExternalUrl` for feed links | 📋 |
| PR-F3 | Font-weight token alignment | 📋 |
| PR-F4 | `loadStats` sequence guard | 📋 |

### Restart / durability bundle (§Z)

| PR | Title | Status |
|----|-------|--------|
| PR-R1 | Await scheduler + background tasks on shutdown | 📋 |
| PR-R2 | LLM extraction idempotency / response staging | 📋 |
| PR-R3 | Webhook claim-before-send (extends IDEM-001) | 🔶 IDEM-001 shipped #449 — verify overlap |
| PR-R4 | Persist migration status to `sync_state` | 📋 |

### Runtime validation (9× NEEDS RUNTIME VALIDATION)

Run on production-like Postgres before closing: production CORS origins (TRANS-002) and
other items flagged in audit §6 — see codebase-audit status table.

### Track M (security/ops audit — mostly shipped)

**Historical source:** [`../archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md`](../archive/superseded/SECURITY_AND_OPS_AUDIT_2026-07.md)  
**Shipped:** M-1…M-7, M-5 (#442), partial M-6–M-10 per sprint.

| ID | Item | Status |
|----|------|--------|
| **M-8** | `app_settings` secret policy (env-only vs encrypted DB) | 🅿️ |
| **M-9** | Ingest `next_run_time` from `scheduler.last_run` (no immediate NVD/KEV/EPSS on restart) | 📋 verify vs #431 |
| **M-10** | Global backup mutex (fcntl) — partial via #431 flock | 🔶 verify completeness |

---

## 4. AI operations (conditional tail)

**Canonical spec:** [`specs/ai-operations.md`](specs/ai-operations.md)  
**Shipped:** AI-1…AI-2 (#416–#417), retention #418, filters #419, tokens #420, quota snapshots #432, K5 pacing #433.

| Item | Status | Notes |
|------|--------|-------|
| **AI-3** (PR-AI-6+7+8) | 💬 conditional | Build only after weeks of `ai_operations` data show fallbacks/quota pressure |
| PR-AI-7 | Model catalog refresh job | 📋 part of AI-3 |
| PR-AI-8 | Routing policy extraction + advisory headroom | 📋 part of AI-3 |
| OpenAI provider | deferred | Not in V1 chain |
| §26 deferred | chat, RAG, agents, STIX-LLM, browser automation | 🅿️ permanent defer |

---

## 5. UX / operator UI (deferred from audit)

**Canonical spec:** [`specs/ux-audit.md`](specs/ux-audit.md)

| ID | Item | Status |
|----|------|--------|
| **28** | Application logs — structured `extra` + expandable row in `IngestLogPage` | 📋 |
| **29** | Audit logs — expandable actor/action context; optional `metadata_json` | 📋 |
| **30** | Log search — server-side time range + `job_id` filter | 📋 |
| **31** | Failure observability — shared `run_id` linking toast → scheduler → logs | 📋 |
| **32** | Scheduler manual trigger duplication (`MANUAL_PIPELINES` vs `JobTable`) | 📋 |
| **33** | Scheduler table — search/filters at ~3 pages of jobs | 📋 |
| **PR3 follow-up** | Migrate analyst `title=` tooltips on `CVECard` / `DetailDrawer` to `HelpTip` | 📋 incremental |
| **Issue 21** | API key suffix + provider health ping in UI | 🔶 backend #435 — UI tail? |
| **UI overhaul 3a** | Dismissible config banner (not permanent amber) | 📋 [`../archive/superseded/UI_UX_OVERHAUL_PLAN.md`](../archive/superseded/UI_UX_OVERHAUL_PLAN.md) |
| **UI overhaul 3b** | Status legend component | 📋 archive plan |
| **UI overhaul §6** | Restart dropdown portal (clipped menu) | 📋 verify if still broken |

**Shipped (do not re-queue):** PR1–PR11, PR12 (#413–#415), PR13 (#422), notification center (#439), O-1/O-2 (#428), wallboard v2 core (#430), K5 (#433).

---

## 6. Threat Modeling & Security Architecture module

**Canonical spec:** [`specs/threat-modeling-security-architecture.md`](specs/threat-modeling-security-architecture.md)  
**Status:** TM-0 design plan — implementation starts after merge to `main`.

| PR | Title | Status |
|----|-------|--------|
| **TM-0** | Design plan (this spec) | 📋 in review |
| **TM-1** | Security Architecture Corpus + API skeleton | 📋 |
| **TM-2** | Shell UI + Overview (route, header tab ARCH, three-panel layout) | 📋 |
| **TM-3** | System Architecture graph + Trust Boundaries + Attack Surface | 📋 |
| **TM-4** | Framework workspaces (STRIDE, OWASP, API Security, NIST, ASVS) | 📋 |
| **TM-5** | MITRE ATT&CK Navigator + CAPEC + CWE explorers | 📋 |
| **TM-6** | Threat Scenarios timeline + Abuse Cases + Controls inventory | 📋 |
| **TM-7** | Risk Register + Security Decisions + Review History + Global search | 📋 |

**Scope:** Interactive operational workspace at `/security-architecture` — not a documentation viewer. Structured corpus + live DB merge. Reuses BRIEFR visual language exactly.

---

## 7. Wallboard optional / kiosk tail

**Core v2 shipped #430; kiosk runbook #442.** Historical plan:
[`../archive/superseded/WALLBOARD_V2_PLAN.md`](../archive/superseded/WALLBOARD_V2_PLAN.md).

| Item | Status |
|------|--------|
| **O-3 / N-1** | `WALLBOARD_TOKEN` in `config_schema` (same as §1) | 📋 |
| `?density=compact` layout mode | 📋 optional |
| Campaign tile, EPSS movers, enriched backend tiles | 📋 optional |
| QR / one-time setup card on Security page (N-4) | 🔶 docs in OPERATIONS.md; QR card not built |
| `RATE_LIMIT_WALLBOARD_PER_MINUTE` in config schema | 📋 optional |

---

## 8. Webhooks / DB explorer follow-ups

**Shipped:** PR12 (#413–#415), PR13 (#422). Historical plan:
[`../archive/superseded/PR12_PR13_IMPLEMENTATION_PLAN.md`](../archive/superseded/PR12_PR13_IMPLEMENTATION_PLAN.md).

| Item | Status |
|------|--------|
| Destination health UI from `webhook_delivery_log` (last success/error) | 📋 optional — only if operators ask |
| Encrypting `config_json` at rest | 🅿️ |
| New webhook provider kinds | 🅿️ |

---

## 9. Quality / process

| Item | Status |
|------|--------|
| Gemini Code Assist replacement (reviews cease **2026-07-17**) | 💬 decision needed — Sprint merge gate §4 |
| F3-tail | SPDX header reconciliation · optional trufflehog | 📋 optional |

---

## 10. Parked (explicit maintainer signal)

| Item | Source |
|------|--------|
| V1.5 Phase 4 STIX/Sigma export | Sprint |
| Full V2.0 `docker-compose.yml` | Sprint, operator backlog |
| Encrypted `app_settings` / secrets SSOT (M-8) | Security audit |
| RSS↔CVE linking | Sprint |
| Track I Phase 3 remainder (if any beyond #436–#438) | HANDOVER |
| LLM summary auth | Sprint optional |

---

## 11. Recently shipped — do **not** re-queue

| Area | PRs / notes |
|------|-------------|
| Notifications v2 | #452 — `user_notifications`, bell, chime |
| Typography px dropdowns | #453 — per-role 9–20px |
| Operator 12-PR bundle | #428–#439 |
| Session auth middleware | #441 |
| Ops backup/wallboard docs | #442 |
| Feed perf I15/I16 | #443 |
| Multi-worker scheduler flag | #444 |
| Security + N+1 audit bundle | #449 |
| AUTH/VAL/IDEM/DB items | See §3 ✅ list |
| Track M core | #429–#431, #442 |
| Track N/O core | #428–#430, #442 |
| PR12/PR13 | #413–#415, #422 |
| AI-1/2 + retention + filters + tokens | #416–#420 |
| F2 LICENSE/CONTRIBUTING | #423 |

---

## Where to add new items

1. Append a row to the relevant section **here**.
2. If sprint-sized, add a checkbox to `SPRINT_2026-07.md` (or next sprint).
3. Deep design context → extend the matching [`specs/`](specs/) doc, not a new duplicate file.
