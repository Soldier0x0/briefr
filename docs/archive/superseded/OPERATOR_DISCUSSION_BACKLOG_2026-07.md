# Operator discussion backlog (2026-07-10)

**Purpose:** single note for future work discussed in operator sessions — **no
implementation until maintainer says “go ahead.”**  
**Rule:** back-and-forth in chat = planning only; items land here (and sprint
tracks) for later PRs.

**Last reconciled:** 2026-07-10 against `main` @ #418–#420.

---

## Status legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Shipped on `main` (verify in UI) |
| 📋 | Documented in sprint/planning, not built |
| 🔶 | Partially shipped (backend or copy only) |
| 💬 | Discussed; operator decision recorded |

---

## A — Admin UI: API keys & config (your question)

Source: `docs/planning/specs/ux-audit.md` **Issues 20, 25, 26, 27**
and UX audit **PR8** scope.

### What we discussed

| Topic | Plan |
|-------|------|
| **Long scroll** | Segregate settings into **collapsible sections** (accordion / dropdown per group) so you don’t scroll the entire page |
| **Section groups** | API Keys · Webhooks (legacy bootstrap) · Scheduler · Ingest · AI/ML · App behaviour · Backup — each collapsible, remember expand state |
| **Sticky apply** | When you edit fields, a **bottom bar** stays visible: “N pending changes” → **Review** → **Apply** (not buried at end of page) |
| **Save vs Apply** | **Two-phase:** edit multiple keys locally → one **Apply** batch (uses `apply_strategy`: immediate / reschedule / restart) |
| **Human labels** | Show “Backup interval (hours)” not raw `BACKUP_INTERVAL_HOURS` in the primary label |

### What actually shipped (PR #408 — “PR8”)

✅ Backend `config_schema`: `display_label`, `unit`, `apply_strategy`  
✅ Per-field **Save** / **Save & restart** with reschedule/restart badges  
✅ Scheduler interval **reschedule** without full restart when possible  
✅ `DiffReviewModal.jsx` component exists (bulk review UI primitive)

### What did **not** ship (still your pain today)

📋 **Collapsible / dropdown sections** on `ApiKeysPage.jsx` — still one long vertical stack of `admin-card` blocks  
📋 **Sticky pending-changes bar** — `DiffReviewModal` is **not wired** to ApiKeysPage; no dirty-state queue  
📋 **Batch edit flow** — still one-key-at-a-time save (apply-all exists in API but not as primary config UX)  
📋 **Full-width** config layout (audit asked to drop cramped max-width feel)

**Proposed track:** **O-1 — Config page IA v2** (see §F below).

---

## B — Security & backups (this session)

| ID | Topic | Status | Notes |
|----|-------|--------|-------|
| **M** | Audit log partial key exposure | 📋 Track M | You’re OK skipping rotation; audit still stores `value[:100]` on save |
| **M-4** | Backup runs ~2 min after every restart | 📋 Track M | Independent of interval setting |
| 💬 | Backup **24h** interval, **retain 20** | Operator plan | Set via Admin → Backup: `BACKUP_INTERVAL_HOURS=24`, `BACKUP_RETENTION_COUNT=20` — works today; restart spike remains until M-4 |

Doc: [`SECURITY_AND_OPS_AUDIT_2026-07.md`](SECURITY_AND_OPS_AUDIT_2026-07.md)

---

## C — LLM / Groq (this session)

| ID | Topic | Status |
|----|-------|--------|
| **K5** | Prompt hygiene + multi-provider pacing headroom | 📋 Spec K §2 |
| 💬 | Keep `gpt-oss-20b` / `120b` on Groq | Confirmed OK for your limits |
| 💬 | No code until go-ahead | Agreed |

---

## D — Wallboard (this session)

| ID | Topic | Status |
|----|-------|--------|
| **N-1** | `WALLBOARD_TOKEN` missing from Admin config UI | 📋 Security page copy is **wrong** — only `.env` works today |
| **N-2** | Theme match BRIEFR terminal aesthetic | 📋 |
| **N-3** | Richer stack-aware tiles; compact ingest strip | 📋 |
| 💬 | Token works via `.env` + restart | Your workflow validated |

Doc: [`WALLBOARD_V2_PLAN.md`](WALLBOARD_V2_PLAN.md)

---

## E — UX audit queue (pre-session — what merged vs deferred)

**Closed 2026-07-10:** PR1–PR11 + PR8 (#396–#408) per `docs/SPRINT_2026-07.md`.

**Post-audit polish on `main` (not UX audit PRs):**

| PR | Shipped |
|----|---------|
| #413–#415 | PR12 multi-webhook destinations |
| #416–#417 | AI-1 / AI-2 AI operations |
| #418 | Operator table retention |
| #419 | AI Activity filters |
| #420 | AI token usage capture |

| PR | Shipped (high level) | Admin/config relevance |
|----|----------------------|-------------------------|
| PR1 | Scheduler job catalog, DISABLED semantics | Scheduler page labels |
| PR2 | API queue metadata | Status bar / feed health |
| PR3–PR4 | Tooltips, toasts | Cross-admin |
| PR5–PR6 | Ops charts, KEV chart | Overview |
| PR7 | Structured logging | Ingest logs |
| PR9 | Admin density, danger zones, Security wallboard **copy** | Security explainer only |
| PR10 | Postgres integrity honesty | Diagnostics |
| PR11 | IOC input, responsive | Analyst UI |
| **PR8** | Schema v2, per-field save, reschedule | **Not** collapsible sections / sticky bar |

**Still deferred from original audit:**

| PR | Item | Sprint |
|----|------|--------|
| PR12 | Multi-webhook (mostly ✅ shipped later as #413–415) | Done |
| **PR13** | Read-only DB explorer (dropdown tables) | 📋 Active in sprint |

---

## F — Proposed new track: **O — Operator config UX v2**

When you say go-ahead, implement as one or two PRs:

### O-1 — Config page structure (frontend)

- Collapsible `admin-card` per `SECTIONS` group in `ApiKeysPage.jsx`
- `localStorage` expand state per section
- Optional: section nav **jump list** (sticky left or top chips: API · Scheduler · Backup…)

### O-2 — Pending changes + sticky apply (frontend + wire existing API)

- Dirty tracking: `{ key → newValue }` map across sections
- Bottom **sticky bar** when `dirtyCount > 0`
- **Review** opens `DiffReviewModal` (already built)
- **Apply** calls `POST /api/admin/config/apply-all` with batch; honour `RestartBanner` / health poll
- Show per-key outcome: immediate / rescheduled jobs / restart required

### O-3 — Security / kiosk fields (ties to N-1)

- Add `WALLBOARD_TOKEN` to `config_schema` + UI subsection (Security or App)
- Fix `SecurityPage.jsx` copy to point at real control

**Acceptance:** operator can change backup 24h + retention 20 + one API key in one review-and-apply flow without scrolling to bottom; sections collapsed by default except edited section.

---

## G — Other audit items worth remembering (not discussed today)

From UX audit / archive plans — not in latest M/N docs:

| Issue | Topic | Status |
|-------|-------|--------|
| 21 | API key suffix + provider health ping | 📋 |
| 8 | Durable notification center | Deferred |
| UI overhaul 3a | Dismissible config banner (not permanent amber) | 📋 |
| UI overhaul 3b | Status legend component | 📋 |
| UI overhaul §6 | Restart dropdown portal (clipped menu) | 📋 |

---

## I — Full pending inventory (reconciled 2026-07-10)

Authoritative **build order** is `docs/SPRINT_2026-07.md` execution queue. Everything
below is either queued, watchlist, discussion-only, or parked.

### I-1 · Official execution queue (build when approved)

| Item | Status |
|------|--------|
| **PR13** | Read-only DB explorer — not started |
| **F2** + F3-tail | AGPL LICENSE, CONTRIBUTING, FUNDING, header reconciliation |
| **G0** → G1–G4 | LEARNING_PATH / ONBOARDING refresh + maintainer modules |
| **AI-3** | Quota/catalog refresh/routing automation — **conditional** (#420 = data only) |

### I-2 · Discussion tracks (§A–F above — go-ahead required)

| Track | Items |
|-------|-------|
| **K5** | LLM prompt hygiene + multi-provider pacing headroom |
| **M** | M-1…M-10 security/backup/scheduler hygiene (`SECURITY_AND_OPS_AUDIT_2026-07.md`) |
| **N** | N-1…N-4 wallboard config + theme + stack-aware tiles |
| **O** | O-1…O-3 collapsible config, sticky apply, `WALLBOARD_TOKEN` in schema |

### I-3 · Quality watchlist (sprint — verify then queue)

| Item | Status |
|------|--------|
| Entry bundle regression (~1.7MB raw vs I8 ≤500KB) | ✅ Verified — entry 317 kB; total lazy JS ~1.8 MB |
| Windows backup tests `skipif` when `age`/`pg_dump` missing | ✅ Done — unreachable Postgres + missing pg tools skip cleanly |
| Gemini review replacement (sunset 2026-07-17) | Decision needed |

### I-4 · UX / archive backlog (not in tracks M/N/O)

Issues **8, 21, 28–31** (notification center, API key health ping, log/audit expand,
time-range filters, failure E2E); PR3 follow-up (`title=` migration on feed/drawer);
`docs/archive/planned/UI_UX_OVERHAUL_PLAN.md` §3a/3b/§6.

### I-5 · Parked (explicit maintainer signal)

STIX/Sigma export (V1.5 Phase 4); Track I Phase 3 perf; embeddings automation;
full V2.0 compose; AI doc long-term (chat/RAG/agents).

### I-6 · Optional tails

LLM summary auth (open). JWT role revalidation **shipped** (#392). API key rotation
skipped per operator decision.

### I-7 · Recently shipped (do **not** re-queue)

PR8 #408; PR12 #413–415; AI-1/2 #416–417; retention #418; AI filters #419; tokens
#420; Track L Wave 4 #366–372; operator table retention closes C3 watchlist.

---

## H — Where to add new discussion items

1. Append a row to the relevant section in **this file**.  
2. If it’s a sprint-sized chunk, add a checkbox under **Track M / N / O** in
   `docs/SPRINT_2026-07.md`.  
3. Do **not** implement until explicit “go ahead.”

---

## Quick answer: “Where did the admin UI plans go?”

They live in **BRIEFR_VISUAL_OPERATIONAL_UX_AUDIT.md** (Issues 20, 25, 26).
PR8 delivered the **backend apply lifecycle** and **per-field save**, but **not**
the **collapsible sections** or **sticky apply bar**. Those are **O-1 / O-2**
above — intentionally **not** in the M/N/security docs you saw last.
