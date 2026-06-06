#!/usr/bin/env bash
# Post-deploy smoke check for Intel integrations (OTX + CVE API).
set -euo pipefail

BASE_URL="${BRIEFR_SMOKE_URL:-http://127.0.0.1:8000}"
CVE_ID="${BRIEFR_SMOKE_CVE:-CVE-2021-44228}"

echo "==> Smoke: ${BASE_URL}/api/cves/${CVE_ID}"

if ! command -v jq >/dev/null 2>&1; then
  echo "FAIL: jq is required for smoke-intel.sh"
  exit 1
fi

resp="$(curl -sf "${BASE_URL}/api/cves/${CVE_ID}")"
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
  journalctl -u briefr-backend -n 30 --no-pager 2>/dev/null | grep -iE 'otx|pulse' || true
  exit 1
fi

echo "OK: Intel smoke passed for ${CVE_ID}"
