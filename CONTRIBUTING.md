# Contributing to BRIEFR

Thank you for your interest in BRIEFR. This project is licensed under
**AGPL-3.0-or-later** (see [`LICENSE`](LICENSE)). The repository is maintained
by [Sai Harsha Vardhan](https://projectjupiter.in); the public flip is planned
after beta feedback — contributions are welcome on `main` via pull request.

## Before you start

1. Read [`docs/ONBOARDING.md`](docs/ONBOARDING.md) and [`CLAUDE.md`](CLAUDE.md)
   (danger zones, SQL conventions, UI rules).
2. Production uses **PostgreSQL** (`DATABASE_URL`). The default test suite runs
   on SQLite; any `db/` change should also be validated against Postgres when
   possible (`DATABASE_URL=postgresql://… pytest tests/ -q`).
3. Do not commit secrets, real API keys, or production `.env` files.

## Development setup

```bash
# Backend (from backend/)
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --port 8000

# Frontend (from frontend/)
npm ci && npm run dev   # proxies /api → :8000
```

Local merge gate (required before opening a PR):

```bash
./scripts/verify-local.sh
```

Use `--full` when Postgres and optional tools are available.

## Pull request guidelines

- **One focused change per PR** — match existing style; minimum diff.
- **Tests:** backend changes need `pytest tests/ -q` green; frontend changes
  need `npm run build` green.
- **Docs:** if runtime behavior or API changes, update `docs/PRODUCT_STATUS.md`
  and `docs/API_REFERENCE.md` in the same PR (see `CLAUDE.md` docs rules).
- **Migrations:** Alembic only, forward-only — never edit applied revisions.
- **Security:** do not weaken `require_admin`, webhook SSRF checks, or DB
  explorer allowlists without an explicit design discussion.

## What we especially welcome

- Detection-engineering templates (Sigma / hunt starters) with tests
- Bug fixes with a failing test or clear repro steps
- Documentation corrections against **current** code (`docs/PRODUCT_STATUS.md`
  wins over stale snapshots)

## What to avoid

- Large refactors unrelated to the issue
- New dependencies without strong justification
- Light-theme or component-library rewrites (dark terminal aesthetic is intentional)
- STIX export / V2.0 platform scope (parked per roadmap)

## Security issues

See [`SECURITY.md`](SECURITY.md) — **do not** open public issues for
vulnerabilities. Email **harsha@projectjupiter.in**.

## Code of conduct

Be direct, technical, and respectful. Security work is stressful; assume good
intent, cite evidence, and keep review threads actionable.
