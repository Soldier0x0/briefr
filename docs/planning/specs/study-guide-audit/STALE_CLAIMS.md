# Study guide — stale claims & orphan paths (RCA)

_Verified against repo HEAD on 2026-07-19. Code / `PRODUCT_STATUS.md` win over guide prose._

## Mechanical orphan (path named, file missing)

| Mention | Chapters | RCA | Disposition |
|---------|----------|-----|-------------|
| `backend/db/dialect.py` | `be-data`, `roadmap-reversed` | **Not a content bug.** Post-B (2026-07) deleted the general SQL translator. Guide prose correctly teaches that it was removed and replaced by paired `_SQLITE`/`_PG` constants + narrow `pg_adapt.py`. The auditor flags any non-existent path. | Keep historical prose. Do **not** add a file chip for the deleted path. Optional: wrap the name in plain `<code>` only (already done). |

No other `orphan_mention` rows remain after path-normalization fixes (`frameworks/*` → `security_architecture/frameworks/*`, `scripts/*` → `backend/scripts/*`).

## Content gaps vs PRODUCT_STATUS (shipped, thin or missing in guide)

These are **not** always zero mentions — they are incomplete relative to what production documents as shipped.

| Topic | Evidence in product | Guide today | RCA | Recommended chapter action |
|-------|---------------------|-------------|-----|----------------------------|
| Retrieval ops health | `GET /api/admin/retrieval/health`, `services/retrieval_health.py`, AI ops panel; `EMBEDDINGS_AUTO_ON_INGEST` default on (E8 era) | Embeddings chapters exist; **ops health / auto-on-ingest operator story thin** | Guide lagged the 2026-07-18 retrieval-ops + auto-on-ingest work | New section under `ie-ml` **or** new `api-retrieval-ops` chapter |
| Operator settings in DB | `operator_settings.py`, `app_settings`, ADR-006 encryption | Config chapter covers crypto; **module never named** (audit `gap`) | File added after chapter chips were written | Add chip + How subsection in `be-config` / `api-usersettings` |
| Read cache | `read_cache.py` (gap) | Mentioned conceptually in resource/connectivity chapters | No file chip | Name in `api-ops` or `be-bootstrap` |
| API metering / queue ops | `api_metering.py`, `api_queue_operations.py` (gaps) | Queue chapter covers `api_queue.py` | Sibling modules never chipped | Extend `in-queue` |
| Storage / resource metrics | `storage_metrics.py`, `resource_collector.py` (gaps) | Ops chapter partial | Admin Storage/Resources UI shipped; guide under-names collectors | Extend `api-ops` |
| Frontend surface area | 350+ files under `pages/` / `components/` / `utils/` almost all `gap` | Part I is decision-level (React/tokens/state), not UI map | Intentional textbook focus on *why*, but interview “where is X page?” fails | New Part I-B chapters: analyst shell, admin shell, Forge/wallboard UI |
| Deploy helpers | doctor, backup timers, update/restore, compose, nginx snippets (gaps) | Ch 32 names primary unit + nginx + setup | Satellite deploy scripts omitted | Extend `devops-deploy` with a deploy-script map |
| Sec-architecture corpus YAML | 14 corpus files gap | Ch 26 explains feature; corpus treated as data not curriculum | Acceptable as weak/data; still should be named | Chip `security_architecture/corpus/*` in Ch 26 |
| Security digest chapters (`sec-*`) | Summaries exist | **No self-checks**; short | Recap chapters never got the interview loop | Add 2–3 self-check questions each |
| `api-secarch` | Long How | Self-check block missing / empty in parser | Incomplete chapter footer | Add self-check |
| Primer (`primer-mechanics`) | Concept cards | No self-check; How is card-grid not traces | Primer by design | Optional light self-check; or mark non-interview |

## False assumptions to avoid when rewriting

1. **“dialect.py missing means the guide is wrong”** — the guide is right; the scanner is literal.
2. **“403 gaps means the backend textbook is empty”** — ~345 gaps are frontend source files the current Part I never attempted to inventory file-by-file.
3. **“Weak == bad chapter”** — `weak` means sibling-dir association only; many packages are intentionally taught via representative files + glob chips.

## Verification commands

```bash
backend/.venv/bin/python scripts/audit_study_guide.py
rg 'orphan_mention' docs/planning/specs/study-guide-audit/gaps.md
test ! -f backend/db/dialect.py   # still deleted
```
