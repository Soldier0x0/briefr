# SigmaHQ local rule index (Postgres)

**Status:** Design — ready to implement  
**Created:** 2026-07-23  
**Scope:** Sigma **only** (no YARA / Elastic index in this program)  
**Depends on:** Detect community-first framing (PR #736 / D5)  
**Related:** [`detection-composer-design.md`](detection-composer-design.md), STRATEGY Pillar 1 Level 2–3  

---

## 1. Goal

Mirror **SigmaHQ/sigma** into BRIEFR’s Postgres, upsert on a watermarked schedule, and serve CVE-relevant community Sigma from the local index on Detect (and later Forge) — **no live GitHub search on the request path**.

Same shape as existing bulk intel syncs (PoC-in-GitHub commit watermark, EPSS file `sha256` identity): download once → parse → upsert → skip if unchanged.

---

## 2. Locked decisions

| Topic | Lock |
|-------|------|
| Content | **SigmaHQ Sigma rules only** this program |
| YARA / Elastic local index | **Out of scope** (keep live Elastic search optional; YARA stays OTX-hash until a later program) |
| Database | **Postgres-native** schema + SQL. No SQLite dual dialect for these tables. Tests that need the index run with Postgres (`verify-local --full` / CI Postgres job). |
| Ingest method | **Codeload / archive tarball of a resolved git commit SHA** (not per-file GitHub API; not recursive code search) |
| Apply model | **Upsert by rule identity** + soft-retire missing paths — never wipe-and-replace the whole table mid-sync |
| Watermark | Store **commit SHA + archive sha256** in `sync_state` / file-identity helper; skip parse/apply when both match |
| Cadence | Default **weekly** scheduler job; Admin **Run now** + **Force re-sync** in the same places as other feeds (Scheduler, config, Feed Health) |
| Request path | Read **index first**; GitHub code search becomes **optional degraded fallback** (token required), off when index healthy |
| LLM | **Never** on sync or Detect read |
| License | **DRL-1.1** compliance baked into schema + API + UI (see §6) |
| Admin | **Full multi-surface wiring** required in SH-2 (§7) — not a lone API endpoint |

---

## 3. How we get the data (ingest)

### 3.1 Resolve tip commit

```
GET https://api.github.com/repos/SigmaHQ/sigma/commits/master
→ sha (40-char)
```

- Use existing resilient HTTP client + `GITHUB_TOKEN` when present (higher rate limit); public unauthenticated OK for low-frequency weekly job.
- Record `commit_sha` as the logical watermark tip.

### 3.2 Download archive (one call)

```
GET https://codeload.github.com/SigmaHQ/sigma/tar.gz/<commit_sha>
→ bytes
sha256(bytes) → archive_digest
```

- **One download** per sync (same idea as EPSS CSV.GZ), not thousands of raw-file fetches.
- Optional: prefer GitHub Releases tarball if we pin a release tag later; v1 locks to **commit SHA archive** so we track tip accurately.
- Cap / stream to temp file under `data/sigmahq/` or OS temp; never hold full archive in RAM if avoidable (stream to disk, hash while writing).

### 3.3 Watermark skip (EPSS pattern)

Reuse `feeds/file_identity.py` style:

| Key | Value |
|-----|--------|
| `sigmahq_archive_identity` | `{ "commit_sha", "sha256", "synced_at" }` |

On each run:

1. Resolve `commit_sha`.
2. If stored `commit_sha` equals tip **and** we still trust prior apply → **skip download** (cheap HEAD/commits check only).
3. Else download archive; if `sha256` equals stored `sha256` → **skip parse/apply**, refresh `synced_at` only.
4. Else extract → parse → upsert → set identity **only after successful commit**.

Failure mid-apply: **do not** advance watermark (same rule as NVD/EPSS).

### 3.4 Extract + walk

- Extract tarball to a versioned dir: `data/sigmahq/<commit_sha>/` (or wipe previous extract after successful apply).
- Walk **only** rule trees:
  - `rules/**/*.yml`
  - `rules-emerging-threats/**/*.yml`
  - `rules-threat-hunting/**/*.yml`
  - `rules-compliance/**/*.yml` (include; mark `rule_family=compliance`)
- Skip: docs, tests that are not rules, `.github`, Python tooling, non-`.yml`.
- Path stored **repo-relative** (strip archive root prefix `sigma-<sha>/`).

### 3.5 Parse each rule

Prefer `yaml.safe_load` with size guard (e.g. skip files > 256 KiB).

Extract:

| Field | Source |
|-------|--------|
| `rule_uid` | Sigma `id` if valid UUID-like; else stable `sha256(repo_path)[:32]` hex (deterministic) |
| `repo_path` | relative path (unique natural key) |
| `title`, `status`, `author`, `description`, `date`, `modified` | YAML fields |
| `level`, `falsepositives`, `logsource` | optional JSONB |
| `tags` | list → JSONB + normalized link rows |
| `references` | list → JSONB |
| `detection` | keep in full YAML body; do not need separate column |
| `content_yaml` | full file text (UTF-8); needed for Copy/Download without re-fetch |
| `content_sha256` | hash of file bytes |

**CVE extraction (for mapping):**

1. Tags matching `cve.YYYY.NNNNN` → `CVE-YYYY-NNNNN`
2. `CVE-YYYY-NNNNN` in `references`, `title`, `description`
3. Path / filename slugs (`CVE-2021-44228`, `cve_2021_44228`)

Only rows that pass (1)–(3) get `detection_rule_cves` with `match_basis = 'cve_exact'`.

**ATT&CK extraction (optional related index):**

- Tags `attack.t####` / `attack.t####.###` → `detection_rule_techniques`
- Used later for “technique-related” packs; **Detect primary path uses CVE links only** in v1 (avoids the noisy T1190 dump problem).

### 3.6 Upsert semantics (not wipe-replace)

Natural key: **`source = 'sigmahq'` + `repo_path`**.

Per file in the archive:

```
INSERT … ON CONFLICT (source, repo_path) DO UPDATE SET
  …columns…,
  content_yaml = EXCLUDED.content_yaml,
  content_sha256 = EXCLUDED.content_sha256,
  commit_sha = EXCLUDED.commit_sha,
  retired_at = NULL,
  updated_at = now()
WHERE detection_rules.content_sha256 IS DISTINCT FROM EXCLUDED.content_sha256
   OR detection_rules.commit_sha IS DISTINCT FROM EXCLUDED.commit_sha
   OR detection_rules.retired_at IS NOT NULL;
```

- Unchanged `content_sha256` → skip heavy updates (optional optimization).
- After full walk: any row with `source='sigmahq'` whose `repo_path` was **not seen** in this apply → set `retired_at = now()` (soft delete). Do **not** hard-delete (preserves audit / avoids flicker if parse skipped a file).
- Re-appearing path → clear `retired_at`.
- CVE/technique link tables: **replace links for that `rule_id`** inside the same transaction as the rule upsert (delete old links for rule + insert new).

**Transaction strategy:** batch commits (e.g. 100 rules per transaction) so a crash loses at most one batch; watermark advances only when **all batches + retire pass** succeed. Alternative (stricter): one transaction for whole apply — acceptable for ~4k rules if command_timeout raised for this job only.

**Locked for v1:** batch commits + final “retire missing” pass; watermark after full success.

---

## 4. Schema (Postgres-native)

Alembic migration only. No SQLite adapters for these objects.

```sql
-- detection_rules
CREATE TABLE detection_rules (
  id              BIGSERIAL PRIMARY KEY,
  source          TEXT NOT NULL CHECK (source = 'sigmahq'),  -- extend later if needed
  repo_path       TEXT NOT NULL,
  rule_uid        TEXT NOT NULL,
  title           TEXT NOT NULL DEFAULT '',
  status          TEXT NOT NULL DEFAULT 'experimental',
  author          TEXT NOT NULL DEFAULT '',
  description     TEXT NOT NULL DEFAULT '',
  level           TEXT,
  rule_family     TEXT NOT NULL DEFAULT 'rules', -- rules|emerging|hunting|compliance
  tags            JSONB NOT NULL DEFAULT '[]',
  references      JSONB NOT NULL DEFAULT '[]',
  logsource       JSONB,
  content_yaml    TEXT NOT NULL,
  content_sha256  TEXT NOT NULL,
  commit_sha      TEXT NOT NULL,
  license_id      TEXT NOT NULL DEFAULT 'DRL-1.1',
  license_url     TEXT NOT NULL DEFAULT 'https://github.com/SigmaHQ/Detection-Rule-License/blob/main/LICENSE.Detection.Rules.md',
  html_url        TEXT NOT NULL DEFAULT '',  -- https://github.com/SigmaHQ/sigma/blob/<sha>/<path>
  retired_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (source, repo_path)
);

CREATE INDEX detection_rules_active_idx
  ON detection_rules (source) WHERE retired_at IS NULL;

CREATE TABLE detection_rule_cves (
  rule_id     BIGINT NOT NULL REFERENCES detection_rules(id) ON DELETE CASCADE,
  cve_id      TEXT NOT NULL,  -- CVE-YYYY-N+
  match_basis TEXT NOT NULL DEFAULT 'cve_exact'
              CHECK (match_basis = 'cve_exact'),
  PRIMARY KEY (rule_id, cve_id)
);

CREATE INDEX detection_rule_cves_cve_idx ON detection_rule_cves (cve_id);

CREATE TABLE detection_rule_techniques (
  rule_id       BIGINT NOT NULL REFERENCES detection_rules(id) ON DELETE CASCADE,
  technique_id  TEXT NOT NULL,  -- T1059 or T1059.001
  PRIMARY KEY (rule_id, technique_id)
);

CREATE INDEX detection_rule_techniques_tid_idx
  ON detection_rule_techniques (technique_id);
```

Optional later: `detection_rule_sync_runs` for Admin history (rows applied, duration, error). v1 can log + `sync_state` only.

---

## 5. Read path

### 5.1 `find_sigma_rules` (Detect)

1. If index has any non-retired `sigmahq` rows (or `sync_state` shows successful sync):  
   `SELECT … FROM detection_rules r JOIN detection_rule_cves c ON … WHERE c.cve_id = $1 AND r.retired_at IS NULL ORDER BY title`.
2. Shape API objects like today: `title`, `status`, `source=SigmaHQ`, `path`, `content`, `author`, `license`, `license_url`, `attribution`, `match_basis=cve_exact`, `html_url`, `download_url` (raw.githubusercontent.com with commit sha **or** omit download and rely on `content`).
3. **Do not** fall back to technique-related index hits on Detect v1 (keeps precision). Technique index is for Forge/coverage later.
4. If index empty / never synced: optional GitHub search fallback (current code) behind `SIGMAHQ_INDEX_FALLBACK_SEARCH=1` default **on** until first successful sync, then default **off** in a follow-up — **lock v1:** fallback on when `rule_count == 0`.

### 5.2 Cache

- Keep 24h `feed_cache` key `sigma:{CVE}` **or** drop it once index reads are cheap (`SELECT` by CVE).  
- **Lock v1:** short TTL cache (e.g. 1h) still OK to shield DB under drawer spam; invalidate not required on sync (TTL expiry enough).

### 5.3 Forge

- Follow-up PR: `include_community=True` using **index only** (no GitHub). Attach CVE-exact Sigma YAML into hunt pack when present; empty string if none (already coerced).

### 5.4 Composer / templates

- Unchanged from community-first: suppress BRIEFR template when community (index) hits exist; refuse generic.

---

## 6. License & legalities (DRL-1.1) — must not miss

SigmaHQ rules use **Detection Rule License 1.1** ([SigmaHQ/Detection-Rule-License](https://github.com/SigmaHQ/Detection-Rule-License)).

### 6.1 What we must do

| Requirement | Implementation |
|-------------|----------------|
| Retain author identification | Persist `author` column; API `author` + `attribution` (`SigmaHQ · {author}`); UI shows it |
| Link to rule / rule set | Persist `html_url` to blob at sync commit; UI “View on SigmaHQ”; docs link to repo |
| Indicate DRL + link license text | `license_id`, `license_url` on every row + API; UI license link; Detect framing copy mentions DRL-1.1 |
| Attribution on **matches** (if we ever show SIEM hit UI) | Future: any “this alert matched rule X” view must show author — note in SYSTEM_DESIGN; not in v1 Detect copy-only |
| Do not strip license metadata from YAML | Store **full** `content_yaml` unmodified |
| Commercial use of BRIEFR | Allowed under DRL with attribution; BRIEFR is Apache 2.0 — do **not** relicense Sigma content as BRIEFR-proprietary |

### 6.2 What we must not do

- Claim SigmaHQ rules as BRIEFR-authored (author stays upstream; BRIEFR templates keep `author: BRIEFR (generated)` only for *our* YAML).
- Strip `author` / references from downloaded YAML.
- Ship a “BRIEFR exclusive rule pack” that is just a SigmaHQ mirror without credit.
- Mix DRL content into PDFs/exports without author + license note (PDF path: if embedding community Sigma, include attribution block — gate in export PR).

### 6.3 Docs / operator notice

- `OPERATIONS.md`: SigmaHQ sync, disk, DRL note.
- Admin Feed Health / Scheduler: “SigmaHQ index” card with commit, sha256, rule counts, last success — not a license waiver, but operator visibility.
- `PRODUCT_STATUS`: “community Sigma served from local DRL-attributed index”.

---

## 7. Scheduler, config & Admin surfaces (mandatory)

Manual control must land in the **same places other feed jobs do** — not a one-off button. Mirror EPSS / `detection_context_sync` / `exploit_sources_sync`.

### 7.1 Job identity

| Item | Value |
|------|--------|
| Job id | `sigmahq_index_sync` (must match `add_job(id=…)`, lock map, catalog) |
| Default interval | **7 days** — `SIGMAHQ_INDEX_SYNC_INTERVAL_HOURS` default `168` (or weekly cron equivalent already used in scheduler) |
| Enable flag | `SIGMAHQ_INDEX_SYNC_ENABLED` default `1` |
| Lock | `scheduler_locks.py` entry for `sigmahq_index_sync` |
| Progress | `_job_progress["sigmahq_index_sync"]` while download/parse/upsert (Scheduler LOCKED + message) |
| Last-run history | `scheduler.last_run.sigmahq_index_sync` via existing `_write_job_last_run` |

### 7.2 Backend wiring checklist (all required in SH-2)

| Surface | What to add |
|---------|-------------|
| `scheduler.py` | `run_sigmahq_index_sync()` + `add_job(id="sigmahq_index_sync", …)`; honor enable flag; interval from env; `INTERVAL_JOB_ENV_MAP` / reschedule keys if used |
| `scheduler_locks.py` | `"sigmahq_index_sync": asyncio.Lock()` |
| `routers/admin/jobs.py` `_JOB_RUN_MAP` | `"sigmahq_index_sync": "run_sigmahq_index_sync"` — **danger zone: keep in sync with job id** |
| `routers/admin/helpers.py` `_OPT_IN_DISABLED_JOBS` | Gate: `("SIGMAHQ_INDEX_SYNC_ENABLED", "1")` so Scheduler Run now returns 400 with clear copy when disabled |
| `routers/admin/feeds.py` | `POST /api/admin/feeds/sigmahq/force-resync` — clear `sigmahq_archive_identity` watermark (like EPSS); audit `feed.sigmahq.force_resync`; optionally kick job via background spawn **or** document “then Run now” (prefer: clear + spawn job once, same as operator expectation) |
| `POST /api/admin/scheduler/run` | Works automatically once `_JOB_RUN_MAP` + lock + coroutine exist |
| `config_schema.py` | Fields: `SIGMAHQ_INDEX_SYNC_ENABLED` (bool, section feeds/ml/scheduler), `SIGMAHQ_INDEX_SYNC_INTERVAL_HOURS` (int); `apply_strategy`: enable = `immediate` or `scheduler_reschedule`; interval = `scheduler_reschedule` |
| Audit | `scheduler.run.sigmahq_index_sync`, `feed.sigmahq.force_resync` |
| Route snapshot / split tests | Register new admin routes in `test_router_split` allowlist if required |

**Force vs Run now (lock the UX):**

1. **Scheduler → Run now** — normal sync (respects watermark; no-op if tip+sha unchanged).  
2. **Force re-sync** — clears watermark, then runs apply even if tip unchanged (re-parse/upsert). Admin copy: “Clears SigmaHQ archive identity and re-applies the index.”

Do **not** invent a third ad-hoc sync API without wiring it into Scheduler; one job function, multiple entry points.

### 7.3 Frontend Admin wiring checklist (all required in SH-2)

| Surface | What to add |
|---------|-------------|
| `frontend/src/pages/admin/catalog.js` `JOB_CATALOG` | Entry for `sigmahq_index_sync`: label, short, operatorName, analystDescription, `refreshButton: 'Sync SigmaHQ index'` |
| Scheduler page | Appears automatically via catalog + `/scheduler/run`; ensure job shows ACTIVE/PAUSED/LOCKED/DISABLED, progress while LOCKED, “View in application log” |
| API keys & config | Auto from `config_schema` — enable toggle + interval; help text: DRL mirror, weekly default, disk use |
| Feed Health / System health | Status card or panel row: commit, sha256 short, `synced_at`, `rules_active`, `cve_links`, stale age; actions: **Run sync** (scheduler run) + **Force re-sync** (feeds force endpoint) |
| Overview / Needs attention (optional but recommended) | If index never synced or age > 14d → attention item “SigmaHQ index stale or empty” deep-link to Scheduler/Feed Health |
| Onboarding checklist | Item: “SigmaHQ detection index synced at least once” (`rules_active > 0` or successful last_run) |
| `formatters.js` / queue labels | If outbound queue uses source id `sigmahq` / `github` for download, human label “SigmaHQ index” |
| Selective refresh constants | Add to any admin “refresh these feeds” chip lists that include EPSS/NVD if present (`constants.js` / Overview refresh presets) |
| Toast copy tests | Human label in `schedulerJobStarted('sigmahq_index_sync', …)` style tests if catalog-driven |

### 7.4 Operator flows (acceptance)

| Operator action | Expected |
|-----------------|----------|
| Enable/disable in Config | Job DISABLED in Scheduler when off; Run now explains enable path |
| Change interval + Save | Scheduler reschedules without full process restart (`scheduler_reschedule`) |
| Scheduler **Sync SigmaHQ index** | Spawns job; LOCKED + progress; last_run history updates |
| Feed Health **Force re-sync** | Clears watermark, runs apply, audit row; Detect gets updated CVE links after success |
| Job fails | Existing job-error notification path; watermark not advanced |

---

## 8. Failure modes & guards

| Failure | Behavior |
|---------|----------|
| GitHub/commits API down | Log; keep last index; Detect still serves stale rules |
| Codeload fails / partial download | No watermark advance; retry next run |
| Corrupt YAML | Skip file; count `parse_errors`; continue |
| Disk full | Fail job; alert via existing job-error notifications |
| Huge repo growth | Stream extract; optional max file count safety |
| First boot empty index | Detect empty community + optional search fallback; Admin onboarding checklist item “SigmaHQ index synced” |
| Command timeout | Job-specific longer timeout; batch commits |
| Manual run while disabled | `400` from `/scheduler/run` via `_job_is_disabled` (same as detection_context) |
| Manual run while LOCKED | `409` lock held |

---

## 9. Observability

| Place | Fields |
|-------|--------|
| Scheduler job row | status, last 5 runs, `progress_message`, link to app log |
| Feed Health / System health card | `commit_sha`, `archive_sha256`, `synced_at`, `rules_active`, `rules_retired`, `cve_links`, `parse_errors_last_run`, age |
| `GET /api/health` (optional additive) | `sigmahq_index: { ok, age_hours, rule_count, commit_sha }` |
| Support pack | Include identity + counts (no rule bodies) |

---

## 10. Testing

| Layer | Tests |
|-------|--------|
| Parser | Fixture mini-tree (2–3 YAML files with CVE tag, technique tag, no CVE) → assert upsert + link rows |
| Watermark | Same archive sha → second sync applies 0 updates |
| Upsert | Modify one fixture file content → content_sha changes; path removed → `retired_at` set |
| Read | `find_sigma_rules` returns attribution + `cve_exact` only from index |
| License fields | Every returned rule has `license_id`, `license_url`, `author`/`attribution` |
| Migration | Alembic upgrade on Postgres CI |
| Admin run map | `_JOB_RUN_MAP` contains `sigmahq_index_sync`; force-resync clears identity |
| Admin UI catalog | `JOB_CATALOG.sigmahq_index_sync` present (unit gate) |
| No SQLite requirement | Default SQLite pytest suite **skips** or does not import PG-only tests; document in test module |

---

## 11. PR sequence

| PR | Scope |
|----|--------|
| **SH-1** | Alembic tables + parser module + sync function + watermark identity + unit tests with fixtures |
| **SH-2** | **Full Admin + scheduler surface:** job + locks + `_JOB_RUN_MAP` + config_schema + `JOB_CATALOG` + force-resync API + Feed Health/System health card (Run + Force) + disabled-gate + progress; optional onboarding/needs-attention |
| **SH-3** | `find_sigma_rules` prefers index; fallback only if empty; Detect unchanged UX already community-first |
| **SH-4** | Forge hunt-pack generate uses index (`include_community` via DB) |
| **SH-5** | Docs: OPERATIONS, PRODUCT_STATUS, API_REFERENCE, HANDOVER; onboarding checklist copy |

pySigma compile validation = **separate** program (STRATEGY Level 3), not blocking SH-1…5.


---

## 12. Non-goals (explicit)

- Local Elastic detection-rules index
- YARA-Rules mirror
- SIEM push / auto-deploy
- Technique-related Sigma on Detect primary list (v1)
- SQLite support for `detection_rules*`
- LLM enrichment of rules
- Relicensing or stripping DRL attribution

---

## 13. Acceptance criteria (program done)

1. Weekly (or manual) sync populates Postgres from SigmaHQ tarball with commit+sha256 watermark; unchanged tip skips work.  
2. Detect for a CVE with tagged SigmaHQ rules returns those rules from DB with author + DRL-1.1 fields and full YAML.  
3. No GitHub code search on Detect when index is non-empty.  
4. Upsert updates changed rules; removed upstream paths soft-retire; watermark only advances on full success.  
5. Docs and UI state license obligations; exports that include community Sigma keep attribution.  
6. Postgres-native only for this feature; CI covers migration + fixture sync on Postgres.  
7. **Admin parity:** Scheduler Run now, config enable/interval, `_JOB_RUN_MAP` + lock, force-resync, Feed Health/System status with Run+Force, catalog label, disabled-gate — same pattern as EPSS / detection_context jobs.

---

## 14. Open questions (resolve in SH-1 if needed)

| Q | Default if unresolved |
|---|------------------------|
| Store full YAML in DB vs path-on-disk only? | **Full YAML in DB** (simpler backup/restore with `pg_dump`; ~tens of MB acceptable) |
| Include `rules-compliance`? | **Yes**, with `rule_family` |
| Pin to SigmaHQ release tags instead of master? | **master/commit tip** for freshness; revisit if tip breaks often |
| Delete retired rows after N days? | **No** in v1; soft-retire only |
