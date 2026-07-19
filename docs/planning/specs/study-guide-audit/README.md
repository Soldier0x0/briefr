# Study guide audit — how to re-run

Automated completeness audit for `docs/STUDY_GUIDE.html` against runtime code.

## Regenerate mechanical reports

From repo root:

```bash
python scripts/audit_study_guide.py
# or
backend/.venv/bin/python scripts/audit_study_guide.py
```

Writes (safe to overwrite):

- `inventory.json` / `inventory.md`
- `gaps.md`
- `coverage-skeleton.md`
- `summary.md`

Does **not** overwrite curated files: `CORRECTED_TOC.md`, `INTERVIEW_COVERAGE.md`, `STALE_CLAIMS.md`, this `README.md`.

## Tests

```bash
cd backend && .venv/bin/python -m pytest tests/test_audit_study_guide.py -q
```

## Curated analysis

After regenerating, review:

1. `summary.md` — counts + top gap directories  
2. `gaps.md` — every gap/orphan with heuristic chapter home  
3. `STALE_CLAIMS.md` — verified mismatches (RCA)  
4. `INTERVIEW_COVERAGE.md` — Concept/Why/How/Self-check scores  
5. `CORRECTED_TOC.md` — outline for the multi-file shell sub-project  

## Scope reminder

- File inventory: `backend/` (not `tests/`), `frontend/src/`, `deploy/`
- Truth order: code → `PRODUCT_STATUS.md` → study guide
- Next work: shell redesign (multi-file, responsive), then Part-by-Part rewrites
