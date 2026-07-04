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
