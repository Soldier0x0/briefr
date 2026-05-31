#!/usr/bin/env bash
# VEKTOR backend setup script for Debian 11 / 12
# Run as root: bash setup.sh
set -euo pipefail

REPO_URL="https://github.com/Soldier0x0/vektor.git"
INSTALL_DIR="/opt/vektor"
APP_USER="vektor"
REQUIRED_PYTHON="python3.12"

echo "========================================================"
echo " VEKTOR Backend Setup"
echo "========================================================"

# ── Step 1: Detect Debian version ──────────────────────────
echo ""
echo "==> [1/7] Detecting OS"
. /etc/os-release
echo "    OS: ${PRETTY_NAME}"
DEBIAN_VERSION="${VERSION_ID:-0}"

# ── Step 2: Install Python 3.12 ────────────────────────────
echo ""
echo "==> [2/7] Installing Python 3.12 and system packages"
apt-get update -qq
apt-get install -y -qq git curl ufw

if command -v python3.12 &>/dev/null; then
    echo "    python3.12 already installed: $(python3.12 --version)"
else
    if [ "${DEBIAN_VERSION}" = "12" ]; then
        # Debian 12 (Bookworm): python3.12 available in backports
        echo "    Adding bookworm-backports for python3.12..."
        echo "deb http://deb.debian.org/debian bookworm-backports main" \
            > /etc/apt/sources.list.d/backports.list
        apt-get update -qq
        apt-get install -y -qq -t bookworm-backports python3.12 python3.12-venv
    elif [ "${DEBIAN_VERSION}" = "11" ]; then
        # Debian 11 (Bullseye): install from source via deadsnakes mirror or pyenv
        echo "    Debian 11: installing build deps for Python 3.12 via source..."
        apt-get install -y -qq build-essential libssl-dev zlib1g-dev \
            libbz2-dev libreadline-dev libsqlite3-dev wget libncursesw5-dev \
            xz-utils tk-dev libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
        PY_VER="3.12.3"
        wget -q "https://www.python.org/ftp/python/${PY_VER}/Python-${PY_VER}.tgz"
        tar xf "Python-${PY_VER}.tgz"
        cd "Python-${PY_VER}"
        ./configure --enable-optimizations --prefix=/usr/local > /dev/null 2>&1
        make -j"$(nproc)" > /dev/null 2>&1
        make altinstall > /dev/null 2>&1
        cd ..
        rm -rf "Python-${PY_VER}" "Python-${PY_VER}.tgz"
        echo "    Python 3.12 built and installed."
    else
        echo "    Unknown Debian version '${DEBIAN_VERSION}'. Trying apt..."
        apt-get install -y -qq python3.12 python3.12-venv || {
            echo "ERROR: Could not install python3.12. Install it manually and re-run."
            exit 1
        }
    fi
fi

# verify
python3.12 --version

# ── Step 3: Clone or update repo ───────────────────────────
echo ""
echo "==> [3/7] Cloning repository to ${INSTALL_DIR}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "    Repo exists — pulling latest..."
    git -C "${INSTALL_DIR}" pull --ff-only
else
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

# ── Step 4: Create venv with Python 3.12 ───────────────────
echo ""
echo "==> [4/7] Creating Python 3.12 virtual environment"
python3.12 -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/backend/requirements.txt"
echo "    Installed packages:"
"${INSTALL_DIR}/venv/bin/pip" list --format=columns | grep -E "fastapi|uvicorn|httpx|apscheduler|pydantic|aiosqlite"

# ── Step 5: Configure .env ─────────────────────────────────
echo ""
echo "==> [5/7] Configuring environment"
if [ ! -f "${INSTALL_DIR}/backend/.env" ]; then
    cp "${INSTALL_DIR}/backend/.env.example" "${INSTALL_DIR}/backend/.env"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  EDIT YOUR API KEYS NOW:                            │"
    echo "  │  nano /opt/vektor/backend/.env                      │"
    echo "  │  Then: systemctl restart vektor-backend             │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
else
    echo "    .env already exists — skipping (edit manually if needed)"
fi

# ── Step 6: System user + permissions ──────────────────────
echo ""
echo "==> [6/7] Creating system user and setting permissions"
id -u "${APP_USER}" &>/dev/null || \
    useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}/backend"
chmod 750 "${INSTALL_DIR}/backend"
[ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"

# ── Step 7: Systemd + firewall ─────────────────────────────
echo ""
echo "==> [7/7] Installing systemd service and configuring firewall"
cp "${INSTALL_DIR}/deploy/vektor-backend.service" /etc/systemd/system/vektor-backend.service
systemctl daemon-reload
systemctl enable vektor-backend
systemctl restart vektor-backend

# Open port 8000 for LAN access (no nginx yet)
ufw allow OpenSSH
ufw allow 8000/tcp
ufw --force enable

# ── Done ───────────────────────────────────────────────────
echo ""
echo "========================================================"
echo " Setup complete!"
echo "========================================================"
sleep 2
echo ""
echo "Service status:"
systemctl status vektor-backend --no-pager -l | head -15
echo ""
echo "Test the API:"
echo "  curl http://$(hostname -I | awk '{print $1}'):8000/api/health"
echo "  curl http://$(hostname -I | awk '{print $1}'):8000/api/stats"
echo ""
echo "Watch logs:"
echo "  journalctl -u vektor-backend -f"
