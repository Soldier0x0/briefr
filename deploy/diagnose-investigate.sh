#!/usr/bin/env bash
# Simpler diagnose script — no dependency on smoke-intel internals.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
BASE_URL="${BRIEFR_SMOKE_URL:-http://127.0.0.1:8000}"
CVE_ID="${BRIEFR_SMOKE_CVE:-CVE-2021-44228}"
CRED_FILE="${BRIEFR_SMOKE_CREDENTIALS_FILE:-/var/lib/briefr/keys/smoke-credentials}"

echo "==> INVESTIGATE diagnose"
echo "    url=${BASE_URL} cve=${CVE_ID}"
echo "    commit=$(git -C "${INSTALL_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"

if [ -f "${CRED_FILE}" ]; then
  set -a
  # shellcheck source=/dev/null
  source "${CRED_FILE}"
  set +a
fi

if [ -z "${BRIEFR_SMOKE_USER:-}" ] || [ -z "${BRIEFR_SMOKE_PASSWORD:-}" ]; then
  echo "FAIL: export BRIEFR_SMOKE_USER and BRIEFR_SMOKE_PASSWORD, or create ${CRED_FILE}"
  exit 1
fi

COOKIE_JAR="$(mktemp)"
trap 'rm -f "${COOKIE_JAR}"' EXIT

login_body="$(jq -nc --arg u "${BRIEFR_SMOKE_USER}" --arg p "${BRIEFR_SMOKE_PASSWORD}" \
  '{username:$u,password:$p}')"
curl -sf -c "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/login" \
  -H 'Content-Type: application/json' \
  -d "${login_body}" >/dev/null

echo "--- resolve ---"
curl -s -w "\nHTTP %{http_code}\n" -b "${COOKIE_JAR}" \
  "${BASE_URL}/api/investigations/resolve?q=${CVE_ID}" | head -20

echo "--- relationships ---"
curl -s -w "\nHTTP %{http_code}\n" -b "${COOKIE_JAR}" \
  "${BASE_URL}/api/investigations/entities/cve/${CVE_ID}/relationships" | head -20

echo "--- recent backend errors ---"
journalctl -u briefr-backend -n 40 --no-pager 2>/dev/null | grep -iE 'investigation|error|exception' | tail -15 || true
