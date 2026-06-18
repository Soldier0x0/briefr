#!/usr/bin/env bash
# BRIEFR production update — pull main, build frontend, reload nginx, restart backend
# Run as root: bash /opt/briefr/deploy/briefr-update.sh
#
# Serves the UI from /opt/briefr/frontend/dist via nginx (not Vite on 5173).
# Optional: USE_TLS=1 to force HTTPS nginx config (default: auto if certbot cert exists).
# Optional env:
#   BRIEFR_INSTALL_DEV_DEPS=1 — install backend dev/test deps for on-box verification
#   BRIEFR_SKIP_SMOKE=1       — skip OTX Intel smoke after deploy
#   BRIEFR_STRICT_SMOKE=1     — fail update if Intel smoke fails (default: warn only)
set -euo pipefail

INSTALL_DIR="/opt/briefr"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib.sh
source "${INSTALL_DIR}/deploy/lib.sh"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash ${SCRIPT_PATH}"
  exit 1
fi

# Pull first, then re-exec so we always run the latest script body (bash does not
# re-read the file after git pull while a run is in progress).
if [ "${BRIEFR_UPDATE_REEXECED:-}" != "1" ]; then
  echo "==> Pulling latest from main"
  git config --global --add safe.directory "${INSTALL_DIR}" 2>/dev/null || true
  git -C "${INSTALL_DIR}" remote set-url origin https://github.com/Soldier0x0/briefr.git 2>/dev/null || true
  git -C "${INSTALL_DIR}" pull origin main
  export BRIEFR_UPDATE_REEXECED=1
  exec bash "${SCRIPT_PATH}" "$@"
fi

ensure_app_home
run_pre_update_backup

echo "==> Stopping services"
systemctl stop briefr.target briefr-frontend briefr-backend 2>/dev/null || true

fix_tree_permissions

echo "==> Stamping build info"
GIT_COMMIT="$(git -C "${INSTALL_DIR}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
printf '{"commit": "%s", "built_at": "%s"}\n' \
  "${GIT_COMMIT}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  > "${INSTALL_DIR}/backend/.build-info.json"
chown "${APP_USER}:${APP_USER}" "${INSTALL_DIR}/backend/.build-info.json"

echo "==> Updating Python dependencies"
as_app_user "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"
if [ "${BRIEFR_INSTALL_DEV_DEPS:-}" = "1" ]; then
  echo "==> Updating Python dev/test dependencies"
  as_app_user "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements-dev.txt"
fi

echo "==> Verifying backend imports"
as_app_user bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c 'import main; print(\"import ok\")'"

build_frontend
install_systemd_units
install_nginx_site
disable_vite_dev

echo "==> Starting backend and nginx"
systemctl enable briefr-backend
systemctl restart briefr-backend
nginx -t
systemctl reload nginx

echo ""
echo "==> Service status"
systemctl status briefr-backend --no-pager -l | head -15 || true
systemctl status nginx --no-pager -l | head -10 || true
if systemctl is-active --quiet briefr-frontend 2>/dev/null; then
  echo "WARNING: briefr-frontend (Vite) is still running — run: systemctl stop briefr-frontend && systemctl mask briefr-frontend"
else
  echo "briefr-frontend (Vite :5173): disabled (expected)"
fi

echo ""
echo "==> Health checks (retry up to 15s — backend may still be starting)"
health_ok=0
for _ in 1 2 3 4 5; do
  if curl -sf "http://127.0.0.1:8000/api/health" >/dev/null; then
    health_ok=1
    break
  fi
  sleep 3
done
if [ "${health_ok:-0}" -eq 1 ]; then
  echo "    Backend :8000  OK"
else
  echo "    Backend :8000  FAILED"
  echo "    Diagnose: journalctl -u briefr-backend -n 50 --no-pager"
  echo "             bash ${INSTALL_DIR}/deploy/check-backend.sh"
fi
if curl -sf "http://127.0.0.1/api/health" >/dev/null; then
  echo "    Nginx /api   OK"
else
  echo "    Nginx /api   FAILED (backend must be up; check /etc/nginx/sites-enabled/briefr)"
fi
if [ -f "${INSTALL_DIR}/frontend/dist/index.html" ]; then
  echo "    Frontend dist OK"
fi

SMOKE_SCRIPT="${INSTALL_DIR}/deploy/smoke-intel.sh"
if [ "${BRIEFR_SKIP_SMOKE:-0}" = "1" ]; then
  echo "    Intel smoke    skipped (BRIEFR_SKIP_SMOKE=1)"
elif [ ! -f "${SMOKE_SCRIPT}" ]; then
  echo "    Intel smoke    skipped (smoke-intel.sh not found)"
elif [ "${health_ok:-0}" -ne 1 ]; then
  echo "    Intel smoke    skipped (backend not healthy)"
else
  if bash "${SMOKE_SCRIPT}"; then
    echo "    Intel smoke    OK"
  elif [ "${BRIEFR_STRICT_SMOKE:-0}" = "1" ]; then
    echo "FAIL: Intel smoke check failed (BRIEFR_STRICT_SMOKE=1)"
    exit 1
  else
    echo "    Intel smoke    WARN (failed; deploy completed — set BRIEFR_STRICT_SMOKE=1 to fail)"
  fi
fi

SERVER_IP="$(hostname -I | awk '{print $1}')"
echo ""
echo "Production UI:  http://${SERVER_IP}/"
echo "API (nginx):    http://${SERVER_IP}/api/health"
echo ""
echo "Ensure ALLOWED_ORIGINS in ${INSTALL_DIR}/backend/.env includes your public URL."
