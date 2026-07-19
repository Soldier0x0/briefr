# BRIEFR Owner's Learning Path

**Audience:** the maintainer. **Goal:** be able to explain every subsystem of
BRIEFR — design, security decisions, trade-offs — without notes, to an
interviewer or a contributor.

**Method (read this first):** you do not learn a codebase by reading
documentation — you learn it by *tracing* it and *re-explaining* it. For each
module below: (1) read the listed files top to bottom, (2) do the trace
exercise with the app running, watching logs and the DB, (3) write your own
explanation in a private notebook **in your own words** — if you can't write
it, you don't know it yet, (4) answer the self-check questions out loud as if
in an interview. One module per week is a realistic pace. Order matters —
each module builds on the previous one.

Existing deep references when stuck: `SYSTEM_DESIGN.md`,
[`archive/snapshots/APPLICATION_EXECUTION_MAP.md`](archive/snapshots/APPLICATION_EXECUTION_MAP.md), `docs/HOW_IT_WORKS.md`.

For full textbook-depth coverage of every subsystem (concept primers, real
code walkthroughs, and self-check questions per chapter) open
[`STUDY_GUIDE.html`](STUDY_GUIDE.html) in a browser — a single self-contained
interactive document, not part of the reader-facing doc set. Completeness
audit (file inventory, gaps, corrected TOC for the planned multi-file shell):
[`planning/specs/study-guide-audit/`](planning/specs/study-guide-audit/README.md).

---

## Module 1 — The request path (how a click becomes SQL)

**Files:** `backend/main.py` → `backend/routers/cves.py` →
`backend/dependencies.py` → `backend/database.py` (skim; it's 3,197 lines —
read only the functions your trace hits).

**Trace:** open the FEED tab in the browser with dev tools open. Follow
`GET /api/cves?page=1` from the network tab → router function → the SQL it
runs → the JSON that comes back. Add a temporary `logger.info` in the router
and watch it fire.

**Self-check:** What does FastAPI's dependency injection do in
`dependencies.py`? Why is every DB function `async`? What limits `limit=50`
and why does a public API need that cap?

## Module 2 — The data layer (the most important module)

**Files:** `backend/db/config.py`, `backend/db/connection.py`,
`backend/db/dialect.py`, `backend/alembic/versions/` (read 2–3 migrations).

**Trace:** find `_postgres_translate_sql` in `dialect.py`. Pick three regex
rewrites and, for each, write down: the SQLite SQL that goes in, the Postgres
SQL that comes out, and what would break without the rewrite.

**Self-check:** Why do `SqliteConnection` and `PostgresConnection` expose the
same method surface? What is a connection pool and what happens when it's
exhausted (`PoolExhaustedError`)? Why is a regex SQL translator risky, and
what is the long-term fix? Why are migrations forward-only?

## Module 3 — Ingest and the scheduler (where the data comes from)

**Files:** `backend/scheduler.py` (the job registration section),
`backend/feeds/nvd.py`, `backend/feeds/kev.py`, `backend/feeds/epss.py`,
`backend/feeds/cvelistv5.py`, `backend/api_queue.py`,
`backend/resilient_client.py`.

**Trace:** trigger `POST /api/refresh/nvd` and follow the logs: watermark
read from `sync_state` → NVD API page fetches through the outbound queue →
`upsert_cves` → change rows written → watermark advanced. Then kill it
mid-run and re-run: observe why nothing is duplicated (idempotency).

**Self-check:** What is the NVD watermark and what goes wrong without it?
Why does the outbound API queue exist (#221)? What does
`resilient_client.py` do on a 429 or timeout? Why does cvelistV5 sync via a
git HEAD SHA instead of timestamps?

## Module 4 — Scoring and the morning brief (the product's brain)

**Files:** `backend/scoring/risk.py`, `backend/scoring/asset_match.py`,
`backend/brief/service.py`, `backend/matching/`.

**Trace:** pick one CVE from your feed. By hand, on paper, compute its Risk
Score v1.1b from the six weighted components (asset 0.35, KEV 0.25, EPSS
0.15, exploit 0.10, CVSS 0.10, momentum 0.05). Compare to what the API
returns. Then change your saved stack and watch the score move.

**Self-check:** Why is asset exposure the heaviest weight? Why consume EPSS
rather than re-derive it? Why is the score explainable (fixed weights)
instead of an ML model? What is CPE matching and where does it run?

## Module 5 — Correlation engine (the differentiator)

**Files:** `backend/correlation/engine.py`, `campaigns.py`, `ioc_graph.py`,
`confidence.py`, `hub_suppress.py`, `backend/feeds/otx_continuous.py`.

**Trace:** open a KEV CVE's Intel tab. Follow the correlation request: why
is it a pure DB read at request time? Then find the nightly OTX job in the
scheduler and trace what it pre-computes.

**Self-check:** What are the three correlation levels? What is a "hub" IOC
and why must it be suppressed (what false positives would a shared
Cloudflare IP create)? Why nightly pre-compute instead of live API calls?

## Module 6 — Detection content (Forge)

**Files:** `backend/detection/sigma_generator.py`, `yara_generator.py`,
`siem_queries.py`, `rule_sources.py`, `backend/routers/forge.py`.

**Trace:** open the Detect tab for a CVE with an ATT&CK mapping and one
without. Explain the difference in output. Read the T1190 template line by
line and explain what each detection key matches.

**Self-check:** Be precise: which parts of the rule are CVE-specific and
which are template? Why is every generated rule marked `experimental` with a
confidence note? What would "CVE-specific artifact injection" from Nuclei
templates add (see `docs/planning/STRATEGY.md` §4)?

## Module 7 — Auth, sessions, and application security

**Files:** `backend/auth/` (all four modules), `backend/routers/auth.py`,
`backend/rate_limit.py`, `backend/webhooks/engine.py` (SSRF protections),
`docs/archive/THREAT_MODEL.md`.

**Trace:** register/login while watching the `sessions` rows in Postgres.
Find where the password hash is computed and which algorithm is used. Then
hit `/api/ioc/lookup` 31 times in a minute and observe the 429.

**Self-check:** Why are passwords hashed and not encrypted, and with what?
How does a session token differ from a JWT, and why did BRIEFR drop
Cloudflare JWT validation (#93)? What is SSRF and how does the generic
webhook defend against it? What is a token bucket?

## Module 8 — Operations: backups, deploy, hardening

**Files:** `backend/backup/` , `deploy/briefr-backup.sh`,
`deploy/briefr-restore.sh`, `deploy/setup.sh`, the systemd unit,
`backend/structured_logging.py`.

**Trace:** run a manual backup, list archives, restore into a scratch
database. Find where the age key lives and explain why it's outside
`BACKUP_DIR`. Read the systemd unit and explain `ProtectSystem=strict`.

**Self-check:** What is a dead-man check and why 2× the backup interval?
Why age-encrypt archives? What does `request_id` in the JSON logs enable?

---

## After the eight modules

1. Write the ADRs listed in `docs/planning/STRATEGY.md` §7 — each one is now a
   30-minute exercise instead of research.
2. Do one full mock interview: have someone (or an AI) grill you per module
   using the self-check questions, no notes allowed.
3. The definition of done: you can whiteboard the whole system — browser →
   nginx → FastAPI → scheduler → Postgres → external APIs — and defend every
   arrow on it.
