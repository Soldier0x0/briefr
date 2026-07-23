#!/usr/bin/env bash
# BRIEFR production update — pull main, build frontend, reload nginx, restart backend
# Run as root: bash /opt/briefr/deploy/briefr-update.sh
#
# Legacy / internet-connected path: git pull from GitHub, optional rollback on failure.
# Production zones without outbound git: use briefr-deploy.sh (local tree) and
# briefr-service.sh (start/stop/restart) instead.
#
# Serves the UI from /opt/briefr/frontend/dist via nginx (not Vite on 5173).
# Optional: USE_TLS=1 to force HTTPS nginx config (default: auto if certbot cert exists).
# Optional env:
#   BRIEFR_INSTALL_DEV_DEPS=1 — install backend dev/test deps for on-box verification
#   BRIEFR_SKIP_SMOKE=1       — skip OTX Intel smoke after deploy
#   BRIEFR_STRICT_SMOKE=0     — warn-only on Intel smoke failure (default: strict / exit 1)
#   BRIEFR_SMOKE_USER/PASSWORD — analyst login for smoke-intel.sh (or file
#     /var/lib/briefr/keys/smoke-credentials, chmod 600)
#   BRIEFR_SKIP_ROLLBACK=1    — on health-gate failure, exit without git reset (break-glass)
#
# Update safety (J1): records the pre-pull git commit, runs Alembic upgrade head
# before restart (Postgres), enforces a real health gate (curl + check-backend.sh),
# and rolls back to the prior commit when the new backend fails the gate.
set -euo pipefail

INSTALL_DIR="/opt/briefr"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib.sh
source "${INSTALL_DIR}/deploy/lib.sh"

require_root "${SCRIPT_PATH}" || exit 1

# Pull first, then re-exec so we always run the latest script body (bash does not
# re-read the file after git pull while a run is in progress).
if [ "${BRIEFR_UPDATE_REEXECED:-}" != "1" ]; then
  PRE_UPDATE_COMMIT="$(git -C "${INSTALL_DIR}" rev-parse HEAD 2>/dev/null || echo "")"
  export BRIEFR_PRE_UPDATE_COMMIT="${PRE_UPDATE_COMMIT}"

  echo "==> Pulling latest from main (prior commit: ${PRE_UPDATE_COMMIT:-unknown})"
  git config --global --add safe.directory "${INSTALL_DIR}" 2>/dev/null || true
  git -C "${INSTALL_DIR}" remote set-url origin https://github.com/Soldier0x0/briefr.git 2>/dev/null || true
  restore_git_permission_drift
  if ! git -C "${INSTALL_DIR}" diff --quiet; then
    echo "ERROR: Local changes would block git pull:"
    git -C "${INSTALL_DIR}" diff --stat
    echo ""
    echo "Permission-only drift is reset automatically before pull."
    echo "If this persists (common on deploy/briefr-pg-backup.sh after chmod 644), run once:"
    echo "  git -C ${INSTALL_DIR} checkout-index -f -- deploy/briefr-pg-backup.sh"
    echo "For other tracked files, restore upstream copies (.env is gitignored):"
    echo "  git -C ${INSTALL_DIR} restore <path>"
    echo "Then re-run: bash ${SCRIPT_PATH}"
    exit 1
  fi
  git -C "${INSTALL_DIR}" pull origin main
  export BRIEFR_UPDATE_REEXECED=1
  exec bash "${SCRIPT_PATH}" "$@"
fi

ensure_app_home
run_pre_update_backup

stop_briefr_services

if ! deploy_apply_release; then
  echo ""
  echo "FAIL: Deploy failed before or during health gate."
  if [ "${BRIEFR_SKIP_ROLLBACK:-0}" = "1" ]; then
    echo "       BRIEFR_SKIP_ROLLBACK=1 — leaving tree as-is; diagnose manually."
    echo "       journalctl -u briefr-backend -n 50 --no-pager"
    exit 1
  fi
  rollback_failed_update "Deploy apply failed"
  exit 1
fi

print_service_status_summary

if ! run_post_deploy_smoke; then
  exit 1
fi

SERVER_IP="$(hostname -I | awk '{print $1}')"
echo ""
echo "Production UI:  http://${SERVER_IP}/"
echo "API (nginx):    http://${SERVER_IP}/api/health"
echo ""
echo "Ensure ALLOWED_ORIGINS in ${INSTALL_DIR}/backend/.env includes your public URL."
