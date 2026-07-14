#!/usr/bin/env bash
# Local pre-merge verification — mirrors .github/workflows when GitHub Actions
# is unavailable (free-tier exhausted, etc.). Run from repo root:
#   ./scripts/verify-local.sh          # required gates (SQLite + audits + build)
#   ./scripts/verify-local.sh --full   # also Postgres + gitleaks + Playwright smoke
set -eu
set -o pipefail 2>/dev/null || true

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

FULL=0
if [[ "${1:-}" == "--full" ]]; then
  FULL=1
fi

pass() { printf '\033[32m✓ %s\033[0m\n' "$*"; }
skip() { printf '\033[33m⊘ %s\033[0m\n' "$*"; }
fail() { printf '\033[31m✗ %s\033[0m\n' "$*"; exit 1; }
step() { printf '\n── %s\n' "$*"; }

step "SQLite backend tests (required — matches CI job: test)"
(
  cd backend
  DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python3 -m pytest tests/ -q
)
pass "SQLite pytest"

step "Design token lint (required — E0-1 gates)"
"$REPO_ROOT/scripts/lint-design-tokens.sh"
pass "design-token lint"

step "Frontend production build (required — matches playwright-smoke job build step)"
(
  cd frontend
  if [[ ! -d node_modules ]]; then
    npm ci --ignore-scripts
  fi
  npm run build
)
pass "npm run build"

step "Python dependency audit (required — matches CI job: dependency-audit)"
python3 -m pip install -q --disable-pip-version-check pip-audit 2>/dev/null || true
pip-audit -r backend/requirements.txt
pass "pip-audit"

step "npm dependency audit (required — matches CI job: dependency-audit)"
(
  cd frontend
  npm run audit:ci
)
pass "npm audit:ci"

if [[ "$FULL" -eq 1 ]]; then
  step "PostgreSQL backend tests (optional — matches CI job: test-postgres)"
  PG_URL="${DATABASE_URL:-}"
  if [[ -z "$PG_URL" ]] && command -v docker >/dev/null 2>&1; then
    if docker compose -f deploy/docker-compose.postgres.yml ps --status running 2>/dev/null | grep -q postgres; then
      PG_URL="postgresql://briefr:briefr@127.0.0.1:5432/briefr"
    elif [[ -x "$REPO_ROOT/scripts/postgres-dev.sh" ]]; then
      if docker inspect briefr-pg-test >/dev/null 2>&1; then
        PG_URL="$("$REPO_ROOT/scripts/postgres-dev.sh" url)"
      else
        PG_URL="$( "$REPO_ROOT/scripts/postgres-dev.sh" start 2>/dev/null | sed -n 's/^DATABASE_URL=//p' )"
      fi
    fi
  fi
  if [[ -n "$PG_URL" ]] && [[ "$PG_URL" == postgresql* ]]; then
  (
    cd backend
    DATABASE_URL="$PG_URL" BRIEFR_REQUIRE_POSTGRES=1 \
      JWT_SECRET="${JWT_SECRET:-ci-test-jwt-secret-not-for-production}" \
      python3 -m pytest tests/ -q
  )
    pass "Postgres pytest"
  else
    skip "Postgres pytest — set DATABASE_URL, run ./scripts/postgres-dev.sh start, or start deploy/docker-compose.postgres.yml"
  fi

  step "gitleaks secret scan (optional — matches CI workflow: gitleaks)"
  if command -v gitleaks >/dev/null 2>&1; then
    gitleaks detect --source . --config .gitleaks.toml --redact --verbose
    pass "gitleaks"
  else
    skip "gitleaks not installed — brew install gitleaks / see .github/workflows/gitleaks.yml"
  fi

  step "Playwright smoke (optional — matches CI job: playwright-smoke)"
  if [[ -d backend/.venv ]]; then
    # shellcheck disable=SC1091
    source backend/.venv/bin/activate
  fi
  if python3 -c "import playwright" 2>/dev/null; then
    (
      cd backend
      PLAYWRIGHT_SMOKE=1 python3 -m pytest tests/test_playwright_smoke.py -q
    )
    pass "Playwright smoke"
  else
    skip "Playwright not installed — pip install -r backend/requirements-dev.txt && playwright install chromium"
  fi
else
  skip "Skipped Postgres / gitleaks / Playwright (pass --full to include)"
fi

printf '\n\033[32mAll required local checks passed.\033[0m\n'
printf 'Merge policy: green ./scripts/verify-local.sh is sufficient when GitHub Actions is unavailable.\n'
if [[ "$FULL" -eq 0 ]]; then
  printf 'Before production deploy, also run: ./scripts/verify-local.sh --full\n'
fi
