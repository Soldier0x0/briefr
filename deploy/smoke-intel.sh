#!/usr/bin/env bash
# Post-deploy smoke check for Intel integrations (OTX + CVE API).
# Analyst CVE detail routes require session auth (briefr_at cookie).
#
# Credentials (first match wins):
#   1. BRIEFR_SMOKE_COOKIE or BRIEFR_ADMIN_COOKIE — use an existing briefr_at value
#   2. BRIEFR_SMOKE_USER + BRIEFR_SMOKE_PASSWORD — POST /api/auth/login
#   3. File at BRIEFR_SMOKE_CREDENTIALS_FILE (default /var/lib/briefr/keys/smoke-credentials)
#      containing the same USER/PASSWORD variables (chmod 600).
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
APP_HOME="${APP_HOME:-/var/lib/briefr}"
BASE_URL="${BRIEFR_SMOKE_URL:-http://127.0.0.1:8000}"
CVE_ID="${BRIEFR_SMOKE_CVE:-CVE-2021-44228}"
CRED_FILE="${BRIEFR_SMOKE_CREDENTIALS_FILE:-${APP_HOME}/keys/smoke-credentials}"

COOKIE_JAR=""
AUTH_HEADER=""

_cleanup() {
  if [ -n "${COOKIE_JAR}" ] && [ -f "${COOKIE_JAR}" ]; then
    rm -f "${COOKIE_JAR}"
  fi
}
trap _cleanup EXIT

_load_credentials() {
  if [ -n "${BRIEFR_SMOKE_USER:-}" ] && [ -n "${BRIEFR_SMOKE_PASSWORD:-}" ]; then
    return 0
  fi
  if [ -f "${CRED_FILE}" ]; then
    # Warn if the file has insecure permissions (chmod 600 or 400 is expected)
    if command -v stat >/dev/null 2>&1; then
      local perms
      perms="$(stat -c "%a" "${CRED_FILE}" 2>/dev/null || stat -f "%A" "${CRED_FILE}" 2>/dev/null || true)"
      if [ -n "${perms}" ] && [ "${perms}" != "600" ] && [ "${perms}" != "400" ]; then
        echo "WARNING: ${CRED_FILE} has insecure permissions (${perms}). Expected 600 or 400."
      fi
    fi
    # shellcheck disable=SC1090
    set -a
    # shellcheck source=/dev/null
    source "${CRED_FILE}"
    set +a
  fi
}

_acquire_session() {
  local cookie=""
  if [ -n "${BRIEFR_SMOKE_COOKIE:-}" ]; then
    cookie="${BRIEFR_SMOKE_COOKIE}"
  elif [ -n "${BRIEFR_ADMIN_COOKIE:-}" ]; then
    cookie="${BRIEFR_ADMIN_COOKIE}"
  fi
  if [ -n "${cookie}" ]; then
    AUTH_HEADER="briefr_at=${cookie}"
    echo "    auth=cookie"
    return 0
  fi

  _load_credentials
  if [ -z "${BRIEFR_SMOKE_USER:-}" ] || [ -z "${BRIEFR_SMOKE_PASSWORD:-}" ]; then
    echo "FAIL: analyst CVE API requires login"
    echo "      Set BRIEFR_SMOKE_USER + BRIEFR_SMOKE_PASSWORD,"
    echo "      or BRIEFR_SMOKE_COOKIE / BRIEFR_ADMIN_COOKIE,"
    echo "      or create ${CRED_FILE} (chmod 600) with USER/PASSWORD variables"
    exit 1
  fi

  COOKIE_JAR="$(mktemp)"
  local login_body
  login_body="$(jq -nc --arg u "${BRIEFR_SMOKE_USER}" --arg p "${BRIEFR_SMOKE_PASSWORD}" \
    '{username:$u,password:$p}')"
  if ! curl -sf -c "${COOKIE_JAR}" -X POST "${BASE_URL}/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "${login_body}" >/dev/null; then
    echo "FAIL: login failed for smoke user '${BRIEFR_SMOKE_USER}'"
    exit 1
  fi
  echo "    auth=login (${BRIEFR_SMOKE_USER})"
}

_fetch_cve_detail() {
  if [ -n "${AUTH_HEADER}" ]; then
    curl -sf -H "Cookie: ${AUTH_HEADER}" "${BASE_URL}/api/cves/${CVE_ID}"
  else
    curl -sf -b "${COOKIE_JAR}" "${BASE_URL}/api/cves/${CVE_ID}"
  fi
}

_fetch_investigate_relationships() {
  if [ -n "${AUTH_HEADER}" ]; then
    curl -sf -H "Cookie: ${AUTH_HEADER}" \
      "${BASE_URL}/api/investigations/entities/cve/${CVE_ID}/relationships"
  else
    curl -sf -b "${COOKIE_JAR}" \
      "${BASE_URL}/api/investigations/entities/cve/${CVE_ID}/relationships"
  fi
}

echo "==> Smoke: ${BASE_URL}/api/cves/${CVE_ID}"

if ! command -v jq >/dev/null 2>&1; then
  echo "FAIL: jq is required for smoke-intel.sh"
  exit 1
fi

_acquire_session

resp="$(_fetch_cve_detail)"
otx_configured="$(echo "$resp" | jq -r '.otx_configured // false')"
pulse_count="$(echo "$resp" | jq '.otx_pulses | length')"
exploit_count="$(echo "$resp" | jq '.public_exploits | length')"

echo "    otx_configured=${otx_configured}"
echo "    otx_pulses=${pulse_count}"
echo "    public_exploits=${exploit_count}"

if [ "$otx_configured" != "true" ]; then
  echo "WARN: OTX_API_KEY not configured — ACTIVE CAMPAIGNS will be empty"
  exit 0
fi

if [ "$pulse_count" -lt 1 ]; then
  echo "FAIL: expected otx_pulses > 0 for ${CVE_ID}"
  if journalctl -u briefr-backend -n 30 --no-pager 2>/dev/null | grep -qiE 'OTX HTTP [45]'; then
    echo "HINT: AlienVault OTX returned an upstream error (HTTP 4xx/5xx)."
    echo "      Deploy itself succeeded — retry smoke later:"
    echo "        bash ${INSTALL_DIR}/deploy/smoke-intel.sh"
    echo "      Or complete this update with warn-only:"
    echo "        BRIEFR_STRICT_SMOKE=0 bash ${INSTALL_DIR}/deploy/briefr-update.sh"
  fi
  journalctl -u briefr-backend -n 30 --no-pager 2>/dev/null | grep -iE 'otx|pulse' || true
  exit 1
fi

echo "OK: Intel smoke passed for ${CVE_ID}"

echo "==> Smoke: INVESTIGATE relationships for ${CVE_ID}"
if ! _fetch_investigate_relationships | jq -e '.root.node_id' >/dev/null; then
  echo "FAIL: INVESTIGATE relationships did not return a graph page for ${CVE_ID}"
  echo "HINT: bash ${INSTALL_DIR}/deploy/diagnose-investigate.sh"
  exit 1
fi
echo "    investigate    OK"
