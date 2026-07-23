#!/usr/bin/env bash
# BRIEFR first-time install — production zone (local artifact, no git clone).
#
# Assumes a release tree is already on disk at INSTALL_DIR (default /opt/briefr).
# Creates the briefr user, Python venv, optional .env, firewall rules, then runs
# briefr-deploy.sh to build frontend, install systemd/nginx, and start services.
#
# Run as root: bash /opt/briefr/deploy/briefr-install.sh
#
# Optional env:
#   INSTALL_DIR=/opt/briefr
#   BRIEFR_SKIP_UFW=1          — do not configure ufw (common in locked-down zones)
#   BRIEFR_SKIP_BACKUP=1       — passed through to briefr-deploy (first install)
#   BRIEFR_BUILD_COMMIT=…      — version stamp when tree is not git
#
# Internet-connected bootstrap (git clone): use deploy/setup.sh instead.
set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/briefr}"
SCRIPT_PATH="$(readlink -f "${BASH_SOURCE[0]}")"
# shellcheck source=lib.sh
source "${INSTALL_DIR}/deploy/lib.sh"

require_root "${SCRIPT_PATH}" || exit 1
require_install_tree || exit 1

echo "========================================================"
echo " BRIEFR production install (local tree)"
echo " Install: ${INSTALL_DIR}"
echo "========================================================"

echo ""
echo "==> [1/5] System user and data directories"
ensure_app_home

echo ""
echo "==> [2/5] Python virtual environment"
ensure_python_venv

echo ""
echo "==> [3/5] Environment file"
if [ ! -f "${INSTALL_DIR}/backend/.env" ]; then
  cp "${INSTALL_DIR}/backend/.env.example" "${INSTALL_DIR}/backend/.env"
  chmod 640 "${INSTALL_DIR}/backend/.env"
  chown "${APP_USER}:${APP_USER}" "${INSTALL_DIR}/backend/.env"
  echo ""
  echo "  ┌─────────────────────────────────────────────────────┐"
  echo "  │  ACTION REQUIRED — edit production secrets:         │"
  echo "  │  nano ${INSTALL_DIR}/backend/.env                   │"
  echo "  │  Set DATABASE_URL, JWT_SECRET, ALLOWED_ORIGINS      │"
  echo "  └─────────────────────────────────────────────────────┘"
  echo ""
else
  echo "    .env already exists — leaving unchanged"
fi

echo ""
echo "==> [4/5] Host firewall (SSH + HTTP)"
if [ "${BRIEFR_SKIP_UFW:-0}" != "1" ]; then
  if command -v ufw &>/dev/null; then
    ufw allow OpenSSH
    ufw allow 80/tcp
    ufw --force enable
    echo "    ufw enabled (OpenSSH + :80)"
  else
    echo "    ufw not installed — skipping (set BRIEFR_SKIP_UFW=1 to silence)"
  fi
else
  echo "    Skipped (BRIEFR_SKIP_UFW=1)"
fi

echo ""
echo "==> [5/5] Production deploy (build, migrate, systemd, nginx)"
export BRIEFR_SKIP_BACKUP="${BRIEFR_SKIP_BACKUP:-1}"
exec bash "${INSTALL_DIR}/deploy/briefr-deploy.sh"
