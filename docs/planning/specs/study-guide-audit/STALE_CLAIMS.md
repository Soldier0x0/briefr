# Study guide — stale claims & orphan paths (RCA)

_Verified against repo HEAD on 2026-07-21 (full docs-library refresh after Waves 1–7 / Phase 1 / UX RCA). Code / `PRODUCT_STATUS.md` win over guide prose._

## Mechanical orphan (path named, file missing)

| Mention | Chapters | RCA | Disposition |
|---------|----------|-----|-------------|
| `backend/db/dialect.py` | `be-data`, `roadmap-reversed` | **Not a content bug.** Post-B (2026-07) deleted the general SQL translator. Guide prose correctly teaches that it was removed and replaced by paired `_SQLITE`/`_PG` constants + narrow `pg_adapt.py`. The auditor flags any non-existent path. | Keep historical prose. Do **not** add a file chip for the deleted path. |

No other `orphan_mention` rows remain after the 2026-07-21 source refresh (router packages, Recharts-complete, durable LLM job, Catch-up mode).

## Phase 0 / refresh inventory gates

Latest audit: `covered=646 weak=0 gap=0 orphan=1 out_of_scope=86`.

| Gate | Status (2026-07-21) |
|------|---------------------|
| G1 `gap=0` | **Pass** |
| G2 `weak=0` | **Pass** (FE `*.test.js` + empty `__init__.py` → `out_of_scope`) |
| G3 orphans | **Pass** — only intentional `dialect.py` historical mention |

Auditor: `scripts/audit_study_guide.py --strict`

## Closed in 2026-07-21 refresh (was stale mid-July)

| Topic | Disposition |
|-------|-------------|
| `routers/cves.py` / `routers/admin.py` monoliths | **Closed** — guide teaches `routers/cves/` + `routers/admin/` packages; `_JOB_RUN_MAP` → `admin/jobs.py` |
| Chart.js mid-migration | **Closed** — Recharts-only; Chart.js marked removed |
| Durable jobs inventory | **Closed** — `health_ping` + `stack_backfill_tick` + `llm_product_extraction` |
| Catch-up mode | **Closed** — scheduler + admin shell chapters |
| Learn pathway hrefs | **Closed** — `../../study-guide/pages` from `docs/learn/pathways/` |

## Former PRODUCT_STATUS thin spots — disposition

| Topic | Disposition |
|-------|-------------|
| Retrieval ops health | **Closed** — chapter `ie-retrieval-ops` |
| Operator settings | **Closed** — chips in config/usersettings chapters |
| Read cache / storage / resource collectors | **Closed** — named in `api-ops` |
| API metering / queue ops | **Closed** — named in queue chapter |
| Frontend surface inventory | **Closed** — Part I-B + globs |
| Deploy helpers / sec-arch corpus | **Closed** in earlier coverage PRs |
| Digest / primer self-checks | **Closed** — digests have ≥3 self-check items |

## False assumptions to avoid

1. **“dialect.py missing means the guide is wrong”** — the guide is right; the scanner is literal.
2. **“weak=0 means every sentence is verified”** — it means every in-scope file is named or explicit OOS. Claim prose vs PRODUCT_STATUS still needs re-check on each maintainer **update**.
3. **“Glob chips cover tests”** — `frontend/src/**/*.test.js` stays `out_of_scope` even if a glob would match them.

## Verification commands

```bash
backend/.venv/bin/python scripts/audit_study_guide.py --strict
backend/.venv/bin/python scripts/build_study_guide_book.py
python3 scripts/build_learn_site.py
cd backend && .venv/bin/python -m pytest tests/test_audit_study_guide.py tests/test_build_study_guide_book.py -q
```
