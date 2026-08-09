#!/usr/bin/env bash
# Local pre-merge verification — mirrors .github/workflows/backend-tests.yml
# (CI job names: test-postgres, frontend, dependency-audit, playwright-smoke,
# plus gitleaks workflow). Run from repo root:
#   ./scripts/verify-local.sh          # required gates (Postgres-first backend + audits + build)
#   ./scripts/verify-local.sh --full   # also gitleaks + Playwright smoke
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

detect_pg_url() {
  # Returns a reachable Postgres DSN or empty. Product default is
  # Postgres-first (settings.briefr_require_postgres=True); SQLite is the
  # opt-in escape hatch for machines with no Postgres at all. A candidate
  # DSN is only returned once it actually answers pg_isready/psql — a stopped
  # container or unreachable DATABASE_URL must fall through to SQLite instead
  # of forcing BRIEFR_REQUIRE_POSTGRES=1 and failing the gate.
  local PG_URL="${DATABASE_URL:-}"
  if [[ -z "$PG_URL" ]] && command -v docker >/dev/null 2>&1; then
    if docker compose -f deploy/docker-compose.postgres.yml ps --status running 2>/dev/null | grep -q postgres; then
      PG_URL="postgresql://briefr:briefr@127.0.0.1:5432/briefr"
    elif [[ -x "$REPO_ROOT/scripts/postgres-dev.sh" ]]; then
      if docker inspect briefr-pg-test >/dev/null 2>&1; then
        if docker ps --filter "name=^/briefr-pg-test$" --filter "status=running" --format '{{.Names}}' 2>/dev/null | grep -q briefr-pg-test; then
          PG_URL="$("$REPO_ROOT/scripts/postgres-dev.sh" url)"
        else
          PG_URL="$( "$REPO_ROOT/scripts/postgres-dev.sh" start 2>/dev/null | sed -n 's/^DATABASE_URL=//p' )"
        fi
      fi
    fi
  fi
  if [[ "$PG_URL" != postgresql* ]]; then
    return 0
  fi
  if _pg_is_live "$PG_URL"; then
    printf '%s' "$PG_URL"
  fi
}

_pg_is_live() {
  # Reachability probe for a Postgres DSN. pg_isready is preferred (no auth
  # needed, just "is the server accepting connections"); psql SELECT 1 is the
  # fallback. If neither client is installed we cannot probe — trust the
  # candidate (tests will surface any connectivity failure).
  local url="$1"
  if command -v pg_isready >/dev/null 2>&1; then
    pg_isready -d "$url" >/dev/null 2>&1
    return $?
  fi
  if command -v psql >/dev/null 2>&1; then
    psql "$url" -tAc "SELECT 1" >/dev/null 2>&1
    return $?
  fi
  return 0
}

step "Backend tests (required — Postgres-first, matches CI job: test-postgres)"
PG_URL="$(detect_pg_url)"
(
  cd backend
  if [[ -n "$PG_URL" ]]; then
    DATABASE_URL="$PG_URL" BRIEFR_REQUIRE_POSTGRES=1 \
      JWT_SECRET="${JWT_SECRET:-ci-test-jwt-secret-not-for-production}" \
      python3 -m pytest tests/ -q
  else
    echo "  No Postgres detected — falling back to SQLite (opt-in escape hatch)."
    echo "  Start one with ./scripts/postgres-dev.sh start or deploy/docker-compose.postgres.yml"
    DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python3 -m pytest tests/ -q
  fi
)
pass "backend pytest"

step "Design token lint (required — E0-1 gates)"
"$REPO_ROOT/scripts/lint-design-tokens.sh"
pass "design-token lint"

step "Backend ruff check F,E9,B (required — F1.1 / Phase 1 W6)"
(
  cd backend
  if ! python3 -m ruff --version >/dev/null 2>&1; then
    python3 -m pip install -q --disable-pip-version-check "ruff==0.16.0"
  fi
  # Initial gate: pyflakes + syntax (F,E9) + bugbear (B). Full E/I/UP + ruff format --check
  # deferred to a follow-on formatting PR (see HANDOVER W6).
  python3 -m ruff check --select F,E9,B .
)
pass "ruff check --select F,E9,B"

step "Frontend production build (required — matches playwright-smoke job build step)"
(
  cd frontend
  if [[ ! -d node_modules ]]; then
    npm ci --ignore-scripts
  fi
  npm run build
)
pass "npm run build"

step "Frontend eslint (required — F1.1 / Phase 1 W6; scoped scoring+admin)"
(
  cd frontend
  if [[ ! -d node_modules ]]; then
    npm ci --ignore-scripts
  fi
  npm run lint
)
pass "npm run lint"

step "Frontend unit tests (required — F1.11)"
(
  cd frontend
  if [[ ! -d node_modules ]]; then
    npm ci --ignore-scripts
  fi
  npm run test:unit
)
pass "npm run test:unit"

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
  skip "Skipped gitleaks / Playwright (pass --full to include)"
fi

printf '\n\033[32mAll required local checks passed.\033[0m\n'
printf 'Merge policy: green ./scripts/verify-local.sh is sufficient when GitHub Actions is unavailable.\n'
if [[ "$FULL" -eq 0 ]]; then
  printf 'Before production deploy, also run: ./scripts/verify-local.sh --full\n'
fi
