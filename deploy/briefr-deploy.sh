#!/usr/bin/env bash
# BRIEFR production deploy — apply release from local install tree (no git pull).
#
# Use in production / air-gapped zones where releases arrive out-of-band
# (rsync, tarball, CI artifact). Does NOT contact GitHub.
#
# Run as root: bash /opt/briefr/deploy/briefr-deploy.sh
#
# Optional env:
#   BRIEFR_SKIP_BACKUP=1       — skip pre-deploy backup
#   BRIEFR_SKIP_MIGRATE=1      — skip Alembic upgrade head
#   BRIEFR_SKIP_BUILD=1        — skip npm ci + frontend build (dist must exist)
#   BRIEFR_SKIP_HEALTH=1       — skip post-restart health gate
#   BRIEFR_SKIP_SMOKE=1        — skip Intel smoke after deploy
#   BRIEFR_STRICT_SMOKE=0      — warn-only on Intel smoke failure
#   BRIEFR_INSTALL_DEV_DEPS=1  — install backend dev/test deps
#   BRIEFR_BUILD_COMMIT=…      — stamp when install tree is not a git checkout
#   BRIEFR_BUILD_AT=…          — ISO timestamp override for .build-info.json
#   USE_TLS=1                  — force HTTPS nginx site config
#
# For git pull + rollback workflow, use briefr-update.sh (legacy / internet-connected).
set -euo pipefail

INSTALL_DIR="/opt/briefr"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib.sh
source "${INSTALL_DIR}/deploy/lib.sh"

require_root "${SCRIPT_PATH}" || exit 1
require_install_tree || exit 1

echo "========================================================"
echo " BRIEFR production deploy (local tree — no git pull)"
echo " Install: ${INSTALL_DIR}"
echo "========================================================"

if [ "${BRIEFR_SKIP_BACKUP:-0}" != "1" ]; then
  run_pre_update_backup
else
  echo "==> Skipping pre-deploy backup (BRIEFR_SKIP_BACKUP=1)"
fi

stop_briefr_services

if ! deploy_apply_release; then
  echo ""
  echo "FAIL: Deploy failed — services may be stopped or unhealthy."
  echo "       Diagnose: journalctl -u briefr-backend -n 50 --no-pager"
  echo "       Restore from backup if needed: bash ${INSTALL_DIR}/deploy/briefr-restore.sh --list"
  exit 1
fi

print_service_status_summary

if ! run_post_deploy_smoke; then
  exit 1
fi

SERVER_IP="$(hostname -I | awk '{print $1}')"
echo ""
echo "Deploy complete."
echo "Production UI:  http://${SERVER_IP}/"
echo "API (nginx):    http://${SERVER_IP}/api/health"
echo ""
echo "Service control: bash ${INSTALL_DIR}/deploy/briefr-service.sh restart|status|health"
echo "Ensure ALLOWED_ORIGINS in ${INSTALL_DIR}/backend/.env includes your public URL."
