# Quickstart — run BRIEFR locally

Get the app running in development in ~15 minutes. For production deploy, see [production.md](production.md).

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (local Docker compose or native)

## 1. Clone and backend

```bash
git clone https://github.com/Soldier0x0/briefr.git
cd briefr/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Set `DATABASE_URL` in `.env` (see [postgres.md](postgres.md)).

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 2. Frontend

```bash
cd ../frontend
npm install
npm run dev
```

Open http://localhost:5173 (proxies `/api` → :8000).

## 3. First-run data

- **&lt;10 CVEs:** backend runs full ingest (NVD → KEV → EPSS) — slow, needs network.
- **Instant sample data:** from repo root with venv active:

```bash
python scripts/seed_screenshot_data.py
```

## 4. First-run auth

Visit the app → complete **setup** (`/api/auth/setup`) to create the admin user.

## Next steps

| Topic | Doc |
|-------|-----|
| PostgreSQL | [postgres.md](postgres.md) |
| Production | [production.md](production.md) |
| Env vars | [../reference/environment-variables.md](../reference/environment-variables.md) |
| Contributor detail | [../develop/onboarding.md](../develop/onboarding.md) |
