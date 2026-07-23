#!/usr/bin/env bash
# BRIEFR operator diagnostics — health checks and optional support-pack export.
#
# Usage:
#   briefr-doctor.sh                    # health + import checks (no auth)
#   briefr-doctor.sh --support-pack     # also download admin support pack
#
# Environment:
#   BRIEFR_URL          Base URL (default http://127.0.0.1:8000)
#   INSTALL_DIR         Install root (default /opt/briefr)
#   APP_USER            Unix user (default briefr)
#   BRIEFR_ADMIN_COOKIE Admin session cookie value for briefr_at (support pack only)
#
# Support pack requires an authenticated admin session. Export the `briefr_at`
# cookie from a logged-in browser session or use the API after login.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
APP_USER="${APP_USER:-briefr}"
BRIEFR_URL="${BRIEFR_URL:-http://127.0.0.1:8000}"
EXPORT_PACK=0
OUTPUT_DIR="${OUTPUT_DIR:-.}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --support-pack) EXPORT_PACK=1; shift ;;
    -o|--output) OUTPUT_DIR="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,16p' "$0"
      exit 0
      ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done

FAIL=0

echo "=== BRIEFR doctor ==="
echo "URL: ${BRIEFR_URL}"

echo ""
echo "=== liveness (/api/health/live) ==="
if curl -sf "${BRIEFR_URL}/api/health/live" | tee /dev/stderr | grep -q '"status"'; then
  echo "OK"
else
  echo "FAILED — backend not responding" >&2
  FAIL=1
fi

echo ""
echo "=== readiness (/api/health) ==="
if curl -sf "${BRIEFR_URL}/api/health" >/tmp/briefr-doctor-health.json; then
  python3 - <<'PY'
import json
with open("/tmp/briefr-doctor-health.json") as f:
    h = json.load(f)
print(f"status={h.get('status')} cve_count={h.get('cve_count')} backend={h.get('database', {}).get('backend')}")
PY
else
  echo "FAILED — /api/health unreachable" >&2
  FAIL=1
fi

if [[ -d "${INSTALL_DIR}/backend" ]]; then
  echo ""
  echo "=== import test (${APP_USER}) ==="
  if [[ "$(id -u)" -eq 0 ]]; then
    runuser -u "${APP_USER}" -- "${INSTALL_DIR}/venv/bin/python" -c "import sys; sys.path.insert(0, '${INSTALL_DIR}/backend'); import main; print('OK: main imported')" || {
      echo "FAILED — run: bash ${INSTALL_DIR}/deploy/briefr-deploy.sh" >&2
      FAIL=1
    }
  else
    cd "${INSTALL_DIR}/backend"
    "${INSTALL_DIR}/venv/bin/python" -c "import main; print('OK: main imported')" || FAIL=1
  fi
fi

if [[ "${EXPORT_PACK}" -eq 1 ]]; then
  echo ""
  echo "=== support pack export ==="
  if [[ -z "${BRIEFR_ADMIN_COOKIE:-}" ]]; then
    echo "SKIP — set BRIEFR_ADMIN_COOKIE to the briefr_at cookie value" >&2
    FAIL=1
  else
    mkdir -p "${OUTPUT_DIR}"
    out="${OUTPUT_DIR}/briefr-support-pack.json"
    if curl -sf -H "Cookie: briefr_at=${BRIEFR_ADMIN_COOKIE}" \
      "${BRIEFR_URL}/api/admin/diagnostics/support-pack" -o "${out}"; then
      echo "Wrote ${out}"
      python3 - <<PY
import json
with open("${out}") as f:
    p = json.load(f)
print(f"support_pack_version={p.get('support_pack_version')} generated_at={p.get('generated_at')}")
print(f"log_entries={len(p.get('logs', {}).get('entries', []))}")
PY
    else
      echo "FAILED — support pack export (check admin cookie / session)" >&2
      FAIL=1
    fi
  fi
fi

echo ""
if [[ "${FAIL}" -eq 0 ]]; then
  echo "All checks passed."
  exit 0
fi
echo "One or more checks failed." >&2
exit 1
