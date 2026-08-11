# Audit Stabilization — Release Report (Part K)

Date: 2026-08-11
Status: RELEASE READY — verified, tests green, no scope expansion.

This report closes the threat-intel blocklist audit-stabilization pass:
three HIGH-severity audit fixes are implemented and regression-tested, Part A
invariants are verified, deferred architecture items are documented for a
follow-up project (NOT implemented), and the full test matrix is green.

---

## PART 1 — CURRENT RELEASE

### 1.1 Implemented fixes (APPROVED, three HIGH)

#### Fix 1 — OTX `observed_at` → blocklist evidence & freshness
- `backend/feeds/otx.py:243` — maps OTX pulse IOC `created` into `observed_at`
  (falls back to `created_date`, else `None`).
- `backend/db/correlation.py:455` `replace_otx_pulse_iocs` persists `observed_at`.
- `backend/db/blocklist.py` `_OTX_CANDIDATE_*` selects include `observed_at`.
- `backend/blocklist/build.py:103` `_evidence_row` surfaces
  `first_seen = row.get("first_seen") or row.get("observed_at")`.
- `backend/blocklist/build.py:250,296` `confidence_for_ioc_edge` consumes
  `observed_at`, so a stale OTX IOC decays below 1.0 (and is NOT credited with
  `freshness_fallback`). Absent `observed_at` degrades safely with a flagged
  fallback rather than crashing.
- Regression: `tests/test_threat_intel_blocklist_fixes.py` (5 tests), verified
  to FAIL without the fix and PASS with it.

#### Fix 2 — exact-IOC context preserved (`evidence[]` + raw_ioc/host_ioc)
- `backend/blocklist/build.py:92-107` `_evidence_row` carries `raw_ioc` and
  `host_ioc`.
- `_candidate_record` signature previously was `*`-keyword-only but callers
  passed `domain` positionally — latent bug fixed.
- Evidence provenance: OTX rows tag `source: "otx"` (via `pulse_id` presence) so
  an OTX report is never silently conflated with catalog corroboration.
- Regression: exact-IOC-vs-host tests (drive.google.com / t.me /
  steamcommunity.com) assert exact and host IOCs remain distinct.

#### Fix 3 — NVD `cpe_matches` persistence (both dialects)
- `backend/db/cve.py` `_UPSERT_CVE_SQLITE` / `_UPSERT_CVE_PG` now upsert a full
  18-column tuple including `cpe_matches` (guarded ON CONFLICT CASE so the field
  is only written when present, never wiping a stored value).
- `_cve_upsert_params` emits `json.dumps(cpe_matches)`; `$17`/`$18` placeholder
  parity maintained across dialects.
- `_GET_CVES_FOR_LLM` also treats empty/`'[]'` as "none".
- Migration: `alembic/versions/001_initial_schema.py:39` declares
  `cpe_matches TEXT DEFAULT '[]'` for PG `cves`.
- Regression: `backend/tests/test_db_cve.py::test_cpe_matches_persist_across_upsert_without_field`
  — verified FAILS with the pre-fix 17-column upsert and PASSES after.

### 1.2 Part A invariants (verified)
- Invariant C: drive.google.com / t.me / steamcommunity.com =
  SHARED_LEGITIMATE_INFRASTRUCTURE.
- Invariant E: google.com / microsoft.com / apple.com = LEGITIMATE_DOMAIN.
- Invariant F: UNKNOWN never trusted; disabled classifications are not excluded
  from the seed set.
- No parent-domain folding; canonical host normalization; seed set is frozen.
- 7 pure tests: `tests/test_threat_intel_invariants.py`.

### 1.3 API / export surface (unchanged this pass)
- `GET /api/threat-intel/blocklist.txt` and `/blocklist.json` — token-gated,
  rate-limited, fail closed (503 unset token / 401 bad token / 429 rate limit).
- JSON export includes upstream-derived fields (`raw_ioc`, `ref_id`, `pulse_id`,
  `malware`, `threat_type`, `description`, `confidence_level`). For human and
  legal review re redistribution — flagged, NOT removed this pass
  (token-gated export, unannounced). See Part I register in
  `2026-08-11-002-data-utilization-future-findings.md`.

### 1.4 Verification results (Part J)
- Backend full suite: **1766 passed, 21 skipped** (baseline 1753 → +13 new).
- Frontend: `npm run build` green; `npm run test:unit` **378 pass / 0 fail**.
- Lint: `ruff check --select F,E9,B .` clean (6 unused imports removed from
  `backend/routers/threat_intel.py`).
- `scripts/lint-design-tokens.sh` pass.
- `pip-audit -r backend/requirements.txt`: no known vulnerabilities.
- `npm run audit:ci`: 0 vulnerabilities.
- PG schema verification against live PostgreSQL 16 (`briefr-pg-test`):
  - `app.infra_classifications` present (PG-only) ✓
  - `intel.otx_pulse_iocs` has `observed_at`, `raw_ioc`, `host_ioc` ✓
  - `app.ti_mirror_iocs` has `confidence_level`, `host_ioc`, `ioc_value` ✓
  - `alembic/versions/001_initial_schema.py` declares `cves.cpe_matches` ✓
- `./scripts/verify-local.sh` requires system `python3` with pytest; not
  available on this machine (`/usr/bin/python3: No module named pytest`).
  All constituent gates were run individually via `backend/.venv` and passed.

### 1.5 Interface changes for consumers
- Schema: `cves.cpe_matches` (PG alembic 001), `otx_pulse_iocs.observed_at`.
- Evidence provenance: JSON export now carries exact `raw_ioc`/`host_ioc` and
  OTX rows are attributed `source: "otx"`.
- No breaking change to the blocklist TXT format (one canonical domain per line).

---

## PART 2 — FOLLOW-UP ARCHITECTURE ROADMAP (deferred, NOT implemented)

Full designs live in `docs/plans/2026-08-11-001-correlation-source-independence-plan.md`
and the findings register in `docs/plans/2026-08-11-002-data-utilization-future-findings.md`.

### P0 / HIGH — Correlation source independence project
- Problem: confidence is double-counted when the same adversary publishes the
  same IOC through abuse.ch (ThreatFox vs URLhaus) or when URLhaus recent
  (live) and bulk feeds overlap; OTX pulses repeat across pulses.
- Design: `source_group` (provider-level grouping), provider vs feed identity,
  independent evidence counting, abuse.ch grouping, OTX grouping, live/bulk
  dedup, exact-vs-host receipt separation, per-source reliability, declared
  `confidence_level`.
- Migration strategy: compatibility flag, regression suite, before/after score
  comparison. See Part D doc for implementation order.

### P1 / MEDIUM
- URLhaus `tags` schema capture.
- ThreatFox `host_ioc` as exact-URL enabler (currently works for host-level
  corroboration via downcast `ioc_value` — future enabler, not a bug fix).
- Exact-vs-host confidence receipts.
- `ioc_degree.pulse_count` correlation metric.
- OTX `attack_ids`; MITRE ATLAS ingestion.

### P2 / LOW
- MITRE platforms/detection capture.
- EPSS percentile history.

---

## PART 3 — MERGE POLICY

`./scripts/verify-local.sh` green is sufficient when CI quota is exhausted.
On this machine run gates via `backend/.venv` (system python lacks pytest):
backend suite, frontend build+lint+unit, ruff, design-token lint, both audits.
All pass. Postgres verified on the live container.