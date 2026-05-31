#!/usr/bin/env bash
# BRIEFR update script — pull latest main and restart services
set -euo pipefail

INSTALL_DIR="/opt/briefr"

echo "==> Stopping BRIEFR services"
systemctl stop briefr.target briefr-frontend briefr-backend 2>/dev/null || true

echo "==> Pulling latest from main"
cd "${INSTALL_DIR}"
git pull origin main

echo "==> Updating Python dependencies"
"${INSTALL_DIR}/venv/bin/pip" install -r backend/requirements.txt

echo "==> Updating frontend dependencies"
cd "${INSTALL_DIR}/frontend"
npm install

echo "==> Starting BRIEFR services"
systemctl daemon-reload
systemctl start briefr.target

echo ""
echo "==> Service status"
systemctl status briefr.target --no-pager -l || true
systemctl status briefr-backend --no-pager -l | head -12 || true
systemctl status briefr-frontend --no-pager -l | head -12 || true
