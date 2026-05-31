#!/usr/bin/env bash
# VEKTOR backend one-shot setup script for Debian/Ubuntu
# Run as root: bash setup.sh
set -euo pipefail

REPO_URL="https://github.com/Soldier0x0/vektor.git"
INSTALL_DIR="/opt/vektor"
APP_USER="vektor"
PYTHON="python3"

echo "==> [1/8] Installing system dependencies"
apt-get update -qq
apt-get install -y -qq git python3 python3-pip python3-venv nginx ufw curl

echo "==> [2/8] Creating system user '${APP_USER}'"
id -u "${APP_USER}" &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"

echo "==> [3/8] Cloning / updating repository to ${INSTALL_DIR}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    git -C "${INSTALL_DIR}" pull --ff-only
else
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

echo "==> [4/8] Creating Python virtual environment"
${PYTHON} -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/backend/requirements.txt"

echo "==> [5/8] Setting up .env"
if [ ! -f "${INSTALL_DIR}/backend/.env" ]; then
    cp "${INSTALL_DIR}/backend/.env.example" "${INSTALL_DIR}/backend/.env"
    echo ""
    echo "  *** IMPORTANT: edit ${INSTALL_DIR}/backend/.env and fill in your API keys ***"
    echo "  Then re-run:  systemctl restart vektor-backend"
    echo ""
fi

echo "==> [6/8] Setting file permissions"
chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}/backend"
chmod 750 "${INSTALL_DIR}/backend"
chmod 640 "${INSTALL_DIR}/backend/.env"

echo "==> [7/8] Installing and enabling systemd service"
cp "${INSTALL_DIR}/deploy/vektor-backend.service" /etc/systemd/system/vektor-backend.service
systemctl daemon-reload
systemctl enable vektor-backend
systemctl restart vektor-backend

echo "==> [8/8] Configuring firewall (ufw)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo ""
echo "==> Setup complete!"
echo ""
echo "Service status:"
systemctl status vektor-backend --no-pager -l | head -20
echo ""
echo "Next steps:"
echo "  1. Edit /opt/vektor/backend/.env with your real API keys"
echo "  2. Install nginx config: cp ${INSTALL_DIR}/deploy/nginx-vektor.conf /etc/nginx/sites-available/vektor"
echo "  3. Enable nginx site: ln -s /etc/nginx/sites-available/vektor /etc/nginx/sites-enabled/"
echo "  4. Get SSL cert: certbot --nginx -d projectjupiter.in -d www.projectjupiter.in"
echo "  5. Reload nginx: systemctl reload nginx"
echo ""
echo "Test the API (local):"
echo "  curl http://localhost:8000/api/health"
