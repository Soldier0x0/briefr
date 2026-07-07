# Session handover log

**Purpose:** running context for AI agents (Cursor, Claude) and the
maintainer. Newest entry first. Each entry answers: what changed, why,
where it was decided, and what comes next — so a fresh agent session can
continue without re-deriving anything. Append a new dated entry per
significant working session; never rewrite old entries.

**Read order for a fresh agent:** `CLAUDE.md` (rules) →
`docs/PRODUCT_STATUS.md` (what's true in prod) → this file's top entry
(recent context) → `docs/SPRINT_2026-07.md` (what to do next).

---

## 2026-07-07 — K1–K3 free-tier LLM router

**Session:** Implemented **K1–K3** — Groq model migration (`openai/gpt-oss-20b` /
`openai/gpt-oss-120b` for PDF summaries); new `ai/llm_router.py` with failover
Groq → Gemini Flash-Lite → Cerebras → OpenRouter `:free`; wired
`ml/product_extraction.py` and `ai/summary.py` through the router; dropped
Anthropic from the PDF chain; `feed_cache` provenance now records
`{provider, model}`.

### Next steps

**D4** unblocked for deterministic Nuclei slice; full LLM extract (K4) can follow.
Post-B Postgres-native `db/` before D4 if not started.

---

## 2026-07-07 — D5 Detect tab UI framing

**Session:** Implemented **D5** — Detect tab reframed as class-aware hunt
starters; `generated_sigma` always returned (supplement when community rules
exist); `generated_sigma_meta` API field; `briefr_basis` / experimental
tooltips in `DetectTab.jsx`.

### Next steps

**D4** blocked on K1–K3 (LLM router). Post-B Postgres-native `db/` before D4.

---

## 2026-07-07 — D3 unified class router

**Session:** Implemented **D3** — `_resolve_detection_class(cve)` in
`class_router.py`; class-keyed SIEM/log-pattern templates in
`class_queries.py`; wired through `sigma_generator`, `get_siem_queries`,
detection + forge endpoints. Sigma, SIEM, and log patterns now agree on
detection class when no ATT&CK technique is mapped.

### Next steps

**D4–D5** (D4 blocked on K1–K3 for LLM extract). Post-B Postgres-native
`db/` before D4.

---

## 2026-07-07 — D2 DetectionContext scaffold

**Session:** Implemented **D2** — `DetectionContext` cache scaffold for the
detection compose pipeline. New modules `detection/context.py` and
`detection/context_sync.py`; scheduler job `detection_context_sync`
(env-gated, default off); `generate_sigma_rule` reads cached envelope
(product/CWE/class); detection API returns `detection_context`; retention
prefix `detection_ctx:` in `cache_retention.py`.

### Next steps

Per execution queue: **K1–K3** (Groq migration deferred by user until closer
to Aug 2026), then **D3–D5**. Post-B Postgres-native `db/` after D1 (before
D4).

---

## 2026-07-07 — Sprint doc + D1 CWE Sigma templates

**Session:** Updated `docs/SPRINT_2026-07.md` with execution queue, expanded
Track D (detection compose pipeline), Track K (free-tier LLM), Post-B
Postgres-native note, C2 runner-up ticks. Implemented **D1**: CWE class
templates in `sigma_generator.py`, `briefr_basis` on generated rules,
`cwe_ids` wired through detection + forge endpoints.

### Next steps

Per execution queue: **K1–K3** (Groq migration + free-tier LLM router), then
**D2–D5**. Post-B Postgres-native `db/` after D1 (before D4).

---

## 2026-07-06 — Sprint topics reconciled; Track J (deployment) added

**Session:** docs only — no code changed. Four planning sessions on
`Soldier0x0/briefr` ended abruptly; this session recovers their topics
into `docs/SPRINT_2026-07.md` so nothing is lost. Branch
`claude/sprint-document-topics-i1xvjp`.

### What changed

- **Reconciliation note** (top of the sprint doc): maps each abrupt
  session to its track — *Codebase architecture review* → Track B
  (closed, B1–B5), *Production performance optimization* → Track I,
  *Production UI component architecture* → Track H, *Production
  deployment planning* → new Track J.
- **Track J — Production deployment / release planning** (new). Records
  the grounded deploy surface to plan against (`deploy/` scripts +
  systemd units + the OPERATIONS/ROADMAP compatibility promise), not
  fabricated specs — the originating session was cut off before its
  decisions were written down. Items: J1 update/rollback safety audit,
  J2 backup→restore round-trip in CI, J3 post-deploy smoke gate, J4
  release/version phasing checklist. Cross-references (not duplicated):
  multi-worker → I Phase 3, nginx gzip → I2, CI Postgres round-trip →
  "After Track B" note.

### Verified against code (`main` @ `5713682`) before writing

- Track B: `backend/database.py` is a 45-line shim, `backend/db/` split
  is in code → B correctly closed.
- Track H: `frontend/src/components/ui/` does not exist yet; `Toast.jsx`
  already at `components/` → H open items stand as written.
- Track I: `db/` files present, no gzip in `deploy/nginx-briefr.conf`
  → I open items stand. No adjustments needed to A–I.

### Next steps

Track J needs a real spec once the deployment-planning session's
decisions are recovered — until then J items are plan/audit only, per
the doc's "verify code first" convention. Open code work per sprint:
**Track D — D1** (CWE→Sigma mapping, spec ready) or **Track H/I** items.

---

## 2026-07-06 — Track C closed (C1–C3); C2 fields shipped

**Session:** C3 retention/TTL audit + implementation. C2 PRs #279–#281 merged on `main`
before this session (CAPEC drawer, SSVC parser/drawer, KEV ransomware feed badge).

### What merged / shipped

- **C2 — PRs #279–#281.** CIRCL `capec_ids` chips in drawer; Vulnrichment SSVC
  parsed to `feed_cache` + drawer section; `kev_ransomware_use` on feed cards.
- **C3 — PR pending.** Retention map in `docs/SPRINT_2026-07.md`; new
  `backend/db/cache_retention.py` + daily `cache_retention_cleanup` scheduler job;
  admin `change_history_old` purge fixed (`detected_at` column, was broken).

### Next steps

Track C (C1–C3) is complete. Next per sprint plan: **Track D — D1**
(CWE→Sigma template mapping in `sigma_generator.py`), or interleave **Track I**
(performance) / **Track H** (UI primitives) per maintainer preference.

---

## 2026-07-06 — Track A closed out (A4–A7); Track B is next

**Session:** docs sync only — no code changed this session. Confirmed
against `origin/main` (local `main` was 5 commits stale) that Track A
finished since the 2026-07-05 entry below, via PRs #265–#267. Two more
commits landed after that, outside the sprint tracks: #268 (Mermaid
architecture diagrams refreshed) and #269 (graphify knowledge-graph
integration added for Cursor — `.cursor/rules/graphify.mdc`,
`.graphifyignore`, `graphify-out/` now committed).

### What merged

- **A4 + A5 — PR #265.** `PoolExhaustedError` handler now returns a fixed
  "Server is busy..." message instead of `str(exc)` (exception stays in the
  log only; the old test asserting `str(exc)`-in-response was updated).
  A5 was an inventory-then-fix pass over every analyst-facing async view
  (`CVEFeed`, `MorningBrief`, `IOCLookup`, `CaseStudies`, `DetailDrawer`/
  `openCveDrawer.js`, `BriefCharts`, `TimelineHeatmap`, `WhatChangedPanel`,
  `Sidebar`, `StatsRow`, `Forge`) — each now has message + `ref:<request-id>`
  + retry, no silent failures. Full per-component before/after inventory is
  in `docs/SPRINT_2026-07.md` under A5. Explicitly left silent:
  `FeedRefreshStatus` and DetailDrawer's best-effort secondary tabs
  (momentum, detection sparkline) — documented rationale, not an oversight.
- **A6 — PR #266.** `settings.production_posture_warnings()` reports every
  unsafe flag (`RATE_LIMIT_ENABLED=0`, `AUTH_COOKIE_SECURE=0`,
  `WALLBOARD_TOKEN` unset) as one warning per flag at startup when
  `BRIEFR_ENV=production`; `GET /api/admin/security` surfaces the same list
  in the existing Security panel as amber callouts. Also fixed a stale
  "Auth: None on any endpoint" line in `API_REFERENCE.md` left over from
  pre-A0.
- **A7 — PR #267.** Wallboard token now header-only
  (`X-BRIEFR-Wallboard-Token`); `?token=` query param rejected (leaked into
  access logs/history). Dropped the deprecated `X-XSS-Protection` header
  from backend middleware and all nginx configs. CSP tightened to
  self-only for `style-src`/`font-src` — fonts turned out to already be
  self-hosted via `@fontsource` (`main.jsx`), so the Google Fonts CSP
  allowances were dead weight, not an active dependency the item expected
  to remove. Fixed the stale "SQLite pins us to one worker" docstring in
  `rate_limit.py`; documented in `briefr-backend.service` that
  `--workers 1` is deliberate (in-memory rate-limit buckets are per-worker).

### Next steps

Track A (A0–A7) is fully closed. Next is **Track B — structural refactor**,
starting with **B1** (CVE ID validator helper, ~25 lines) per
`docs/REFACTOR_PLAN.md`. Rules unchanged: one phase = one PR = one deploy,
full `pytest` + `npm run build` green before advancing, B3 (`database.py`
split) is the risky phase and needs a careful diff review, B4–B5
additionally need hand verification in the browser (drawer tabs, PDF/XLSX
export).

---

## 2026-07-05 — Security architecture review; sprint gains A0/A6/F3

**Session:** maintainer + AI security review. **Docs-only — no code
changed.** Findings verified by reading `dependencies.py`, `routers/auth.py`,
`settings.py`, `rate_limit.py`, `db/connection.py`, `utils/exportXlsx.js` —
not from docs. Since the 2026-07-03 entry, main also picked up PR #257
(DETECT tab 500 on Postgres — a live danger-zone-#1 hit) and PR #258
(admin log search); branch `fix/deploy-npm-ci-not-install` (npm ci for
production frontend builds) was open at session time.

### Findings (verified against code)

1. **`require_admin` fails open by default.** `allow_legacy_admin_key`
   defaults true; with `BRIEFR_ADMIN_API_KEY` unset (the normal case since
   built-in login shipped) every admin route is **unauthenticated** unless
   CF Access happens to sit in front. Decision: **delete the legacy key
   path entirely** — not gate it. Sprint A0 + Spec A0.
2. `require_admin` never checks the JWT `role` claim — any authenticated
   user is admin. Latent until a second user exists; folded into A0.
3. `audit()` catches only `sqlite3.OperationalError`; the Postgres wrapper
   raises raw asyncpg errors, so an audit-write failure can 500 a valid
   admin action in production (danger zone #1 in exception space, not SQL
   space). Immediate fix in A0; class fix added to the post-Track-B
   native-SQL conversion notes.
4. Wallboard token accepted via query string (leaks into access logs /
   history; low severity, read-only surface). Sprinted as **A7** together
   with the deprecated `X-XSS-Protection` header, Google-Fonts CSP
   allowance (vendor the fonts for air-gap credibility), and the stale
   single-worker rate-limit docstring.
5. **Clean checks — no action:** XLSX export uses ExcelJS string cells
   (no formula injection from upstream CVE text), no
   `dangerouslySetInnerHTML` anywhere, webhook SSRF tests exist, refresh
   rotation + reuse detection solid, rate-limit proxy trust solid.

### Plan changes (edited `docs/SPRINT_2026-07.md` this session)

- Track A: new **A0** (delete legacy key + role check + audit fix +
  security-invariant tests; one PR, mostly deletions — do **before**
  A2/A3), **A6** (production posture self-check), and **A7** (security
  hygiene: wallboard header-only, drop X-XSS-Protection, vendor fonts,
  worker-pin note). A1 ticked (PR #255).
- After-Track-B notes: one app-level DB exception type, no `sqlite3.*`
  handling outside `db/`, CI dump→restore round-trip for backups.
- Track F: new **F3** pre-flip security pass (gitleaks over full history,
  rotate any committed key, `SECURITY.md`, reconcile "All rights reserved"
  headers with AGPL) — blocks the open-source flip.
- Appendix: **Spec A0** with the verified removal scope. Gemini review of
  PR #260 caught that the legacy key is **runtime-rotatable** (SecurityPage
  Rotate flow → `POST /config/apply-all` → `APPLY_ALL_EXTRA_KEYS`) and that
  `api.js` still attaches `X-BRIEFR-Admin-Key` on adminApi requests — spec
  expanded to delete the whole rotation chain, frontend included.

### Explicitly rejected (don't re-litigate)

2FA/OIDC, CSRF tokens, Redis-backed rate limiting — wrong size for a
single-operator self-hosted app with `SameSite=Strict` cookies and
optional CF Access. Scoped API tokens only when a real machine consumer
appears.

### Next steps

1. **A0** per Spec A0 (check the production crontab/systemd timers for
   `X-BRIEFR-Admin-Key` callers before merging).
2. A2+A3 per spec; A4 rides along. Then Track B unchanged.

---

## 2026-07-03 — Strategy, repo cleanup, error-loop plan, July sprint

**Session:** maintainer + AI planning/execution session. All output landed
on branch `claude/briefer-tool-strategy-0mj158` → **PR #246-era main, PR
#255**. Commits: strategy doc → embeddings dead-code fix → learning path →
CLAUDE.md/doc cleanup → sprint checklist → this handover.

### What changed and why

| Change | Where | Why |
|---|---|---|
| Product strategy written | `docs/STRATEGY.md` | Define the path from late-beta personal project to adopted community tool: detection-quality ladder (templates → CWE mapping → exploit-artifact injection → pySigma validation → proof bench), measured "minutes saved" metric, adoption plan (license → Docker → launch), interview-readiness (ADRs). Explicitly rejects training a custom rule-generation ML model. |
| Dead `sqlite-vec` path removed | `backend/ml/embeddings.py` + live docs | The accelerator could never run: not in requirements, and the Postgres connection wrapper exposes no `enable_load_extension`. Docstring/docs claimed vectors lived "in SQLite" — false in production. Tests: 25 passed. |
| Learning curriculum | `docs/LEARNING_PATH.md` | Maintainer must be able to defend every subsystem without AI help (career goal). Eight modules, trace exercises, interview self-checks. |
| `CLAUDE.md` rewritten project-specific | `CLAUDE.md` | Was generic LLM advice. Now: commands, source-of-truth order, six danger zones (SQL dialect translation #1), error-handling conventions, UI rules (incl. **no wide side margins / no centered narrow columns** — repeated agent failure mode), docs rules. |
| Snapshot banners + stale-claim fixes | `CODEBASE_CONTEXT.md`, `FOLDER_STRUCTURE_GUIDE.md`, `APPLICATION_EXECUTION_MAP.md`, `TECHNICAL_INVENTORY.md` | These lag the code (CODEBASE_CONTEXT claimed SQLite storage; TECHNICAL_INVENTORY claimed React 18). Banner: `docs/PRODUCT_STATUS.md` and the code win. |
| Root cleanup | deleted `Beta V*.md` stubs, `SYSTEM_DESIGN.pdf`, `TECHNICAL_INVENTORY.xlsx`, `architecture-map.html` (now gitignored) | Redirect stubs served their purpose; binary artifacts are generated on demand by `scripts/` and only drift in git. All referencing docs updated. |
| July sprint checklist | `docs/SPRINT_2026-07.md` | Single execution list; tracks A–G with per-item acceptance criteria. |

### Key findings about the codebase (verified, not assumed)

1. **SQLite is not fully gone.** Production is Postgres-only, but all SQL in
   `database.py` is SQLite-dialect, translated at runtime by regex in
   `db/dialect.py`; tests run SQLite. This layer is the highest-risk code.
2. **`docs/REFACTOR_PLAN.md` is accurate as of 2026-07-03** — line tables
   verified against code (11 CVE-ID duplications, 14 locks, `database.py`
   = 3,197 lines, function line numbers exact). Safe to execute.
3. **Error handling backend is done, frontend is half-done.** Backend:
   request_id middleware, `X-Request-ID` header, generic 500 + full
   traceback logged, secret redaction. Admin log viewer **already filters
   by request_id**. Missing: `frontend/src/api.js` drops the header, so
   users can't quote the ref id; no app-wide error toast (one exists under
   `pages/admin/shared/Toast.jsx` only); `PoolExhaustedError` handler
   returns `str(exc)`.
4. **CI is strong:** backend tests, a Postgres services job, pip/npm
   audits, Playwright smoke that builds the frontend. No lint config.
5. Detection generation is **template-based** (14 ATT&CK-technique Sigma
   templates + hash-led YARA); the only ML is optional embeddings +
   optional LLM product extraction. Describe it accurately everywhere.

### Decisions with rationale (agreed by maintainer)

1. **Order of operations: structural refactor FIRST, Postgres-native SQL
   second.** The plan is fresh now; moves are behavior-neutral and safe
   under SQLite tests; post-split modules convert to native SQL one PR at
   a time; delete `db/dialect.py` last.
2. **Refactor execution rules:** one phase = one PR = one deploy; full
   `pytest` + `npm run build` between phases; never proceed past red.
3. **Future DB boundary: Postgres schemas `intel` (shareable CVE/KEV/EPSS/
   ATT&CK + own-derived data) vs `app` (users, sessions, caches, audit).**
   NOT a return to a separate SQLite file. Third-party API caches
   (VT/AbuseIPDB/GreyNoise/OTX) must stay private — upstream ToS forbid
   redistribution, which also rules out selling enriched DB dumps.
4. **Monetization reality:** career ROI first; then open-core, managed
   hosting (customers' own API keys), self-authored detection content
   packs, GitHub Sponsors (`.github/FUNDING.yml` at open-source flip).
   License recommendation: AGPL-3.0, decided at flip time (Track F).
5. **No custom-trained ML for rule generation** — deterministic synthesis
   from exploit artifacts + validation is the differentiator.
6. **UI direction:** keep terminal identity; polish = designed
   loading/empty/error/data states, stat-tile deltas, tooltip coverage,
   IOC auto-detect, restrained motion (120–180ms) — not margins, not
   decoration. Screenshots reviewed were a few days old; re-verify
   individual critique items against the live app before fixing.

### Next steps (in order — see `docs/SPRINT_2026-07.md` for full detail)

1. Merge **PR #255** (contains everything above).
2. **Track A:** A2 (capture `X-Request-ID` in `api.js`) + A3 (app-wide
   error toast, ref id links to admin log viewer pre-filtered) — smallest
   visible win, do before the refactor.
3. **Track B:** refactor phases 1–5 per `docs/REFACTOR_PLAN.md`.
4. Tracks C–G per sprint doc; weekly rhythm at its bottom.
