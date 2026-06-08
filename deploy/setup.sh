#!/usr/bin/env bash
# BRIEFR backend setup script — Debian 11 / 12 / 13
# Run as root: bash setup.sh
set -euo pipefail

REPO_URL="https://github.com/Soldier0x0/briefr.git"
INSTALL_DIR="/opt/briefr"
APP_USER="briefr"

echo "========================================================"
echo " BRIEFR Backend Setup"
echo "========================================================"

# ── Step 1: Detect Debian version ──────────────────────────
echo ""
echo "==> [1/7] Detecting OS"
. /etc/os-release
echo "    OS: ${PRETTY_NAME}"
DEBIAN_VERSION="${VERSION_ID:-0}"

# ── Step 2: Install Python (version depends on Debian release) ─
echo ""
echo "==> [2/7] Installing Python and system packages"
apt-get update -qq
apt-get install -y -qq git curl ufw

pick_python() {
    # Return the best available python binary (>=3.10)
    for bin in python3.13 python3.12 python3.11 python3.10; do
        if command -v "$bin" &>/dev/null; then
            echo "$bin"
            return
        fi
    done
    echo ""
}

if [ "${DEBIAN_VERSION}" = "13" ]; then
    # Debian 13 (Trixie) ships Python 3.13 — already present, nothing to install
    echo "    Debian 13 (Trixie): using built-in Python 3.13"
    apt-get install -y -qq python3 python3-venv
    PYTHON_BIN="python3.13"

elif [ "${DEBIAN_VERSION}" = "12" ]; then
    # Debian 12 (Bookworm) ships Python 3.11; get 3.12 from backports
    echo "    Debian 12 (Bookworm): installing python3.12 from backports"
    if ! grep -q "bookworm-backports" /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null; then
        echo "deb http://deb.debian.org/debian bookworm-backports main" \
            > /etc/apt/sources.list.d/backports.list
        apt-get update -qq
    fi
    apt-get install -y -qq -t bookworm-backports python3.12 python3.12-venv
    PYTHON_BIN="python3.12"

elif [ "${DEBIAN_VERSION}" = "11" ]; then
    # Debian 11 (Bullseye) ships Python 3.9; compile 3.12 from source
    echo "    Debian 11 (Bullseye): compiling Python 3.12 from source (~5 min)..."
    apt-get install -y -qq build-essential libssl-dev zlib1g-dev libbz2-dev \
        libreadline-dev libsqlite3-dev wget libncursesw5-dev xz-utils tk-dev \
        libxml2-dev libxmlsec1-dev libffi-dev liblzma-dev
    PY_SRC="3.12.3"
    if ! command -v python3.12 &>/dev/null; then
        wget -q "https://www.python.org/ftp/python/${PY_SRC}/Python-${PY_SRC}.tgz"
        tar xf "Python-${PY_SRC}.tgz"
        cd "Python-${PY_SRC}"
        ./configure --enable-optimizations --prefix=/usr/local > /dev/null 2>&1
        make -j"$(nproc)" > /dev/null 2>&1
        make altinstall > /dev/null 2>&1
        cd ..
        rm -rf "Python-${PY_SRC}" "Python-${PY_SRC}.tgz"
    fi
    PYTHON_BIN="python3.12"

else
    # Unknown Debian version — pick whatever >=3.10 is available
    echo "    Unknown Debian version '${DEBIAN_VERSION}'. Looking for Python >=3.10..."
    apt-get install -y -qq python3 python3-venv 2>/dev/null || true
    PYTHON_BIN="$(pick_python)"
    if [ -z "${PYTHON_BIN}" ]; then
        echo "ERROR: No Python >=3.10 found. Install it manually and re-run."
        exit 1
    fi
fi

echo "    Using: ${PYTHON_BIN} — $("${PYTHON_BIN}" --version)"

# ── Step 3: Clone or update repo ───────────────────────────
echo ""
echo "==> [3/7] Cloning repository to ${INSTALL_DIR}"
if [ -d "${INSTALL_DIR}/.git" ]; then
    echo "    Repo exists — pulling latest..."
    git -C "${INSTALL_DIR}" pull --ff-only
else
    git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

# ── Step 4: Create venv and install packages ───────────────
echo ""
echo "==> [4/7] Creating virtual environment and installing packages"
"${PYTHON_BIN}" -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/backend/requirements.txt"

echo "    Installed:"
"${INSTALL_DIR}/venv/bin/pip" list --format=columns \
    | grep -E "fastapi|uvicorn|httpx|apscheduler|pydantic|aiosqlite|python-dotenv"

# ── Step 5: Configure .env ─────────────────────────────────
echo ""
echo "==> [5/7] Configuring environment"
if [ ! -f "${INSTALL_DIR}/backend/.env" ]; then
    cp "${INSTALL_DIR}/backend/.env.example" "${INSTALL_DIR}/backend/.env"
    echo ""
    echo "  ┌─────────────────────────────────────────────────────┐"
    echo "  │  ACTION REQUIRED — edit your API keys:              │"
    echo "  │  nano /opt/briefr/backend/.env                      │"
    echo "  │  Then: systemctl restart briefr-backend             │"
    echo "  └─────────────────────────────────────────────────────┘"
    echo ""
else
    echo "    .env already exists — skipping (edit manually if needed)"
fi

# ── Step 6: System user + file permissions ─────────────────
echo ""
echo "==> [6/7] Creating system user '${APP_USER}' and setting permissions"
id -u "${APP_USER}" &>/dev/null || \
    useradd --system --no-create-home --shell /usr/sbin/nologin "${APP_USER}"
mkdir -p /var/lib/briefr/backups/logs
chown -R "${APP_USER}:${APP_USER}" /var/lib/briefr
chown -R "${APP_USER}:${APP_USER}" "${INSTALL_DIR}/backend"
chmod 750 "${INSTALL_DIR}/backend"
[ -f "${INSTALL_DIR}/backend/.env" ] && chmod 640 "${INSTALL_DIR}/backend/.env"

# ── Step 7: Systemd service + firewall ─────────────────────
echo ""
echo "==> [7/7] Installing systemd service and configuring firewall"

# Patch the ExecStart line to use whatever python venv was created
sed -i "s|ExecStart=.*|ExecStart=${INSTALL_DIR}/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --log-level info|" \
    "${INSTALL_DIR}/deploy/briefr-backend.service"
sed -i "s|WorkingDirectory=.*|WorkingDirectory=${INSTALL_DIR}/backend|" \
    "${INSTALL_DIR}/deploy/briefr-backend.service"
sed -i "s|EnvironmentFile=.*|EnvironmentFile=${INSTALL_DIR}/backend/.env|" \
    "${INSTALL_DIR}/deploy/briefr-backend.service"
sed -i "s|ReadWritePaths=.*|ReadWritePaths=${INSTALL_DIR}/backend /var/lib/briefr/backups|" \
    "${INSTALL_DIR}/deploy/briefr-backend.service"
sed -i "s|Environment=.*|Environment=PATH=${INSTALL_DIR}/venv/bin|" \
    "${INSTALL_DIR}/deploy/briefr-backend.service"

cp "${INSTALL_DIR}/deploy/briefr-backend.service" /etc/systemd/system/briefr-backend.service
sed "s|/opt/briefr|${INSTALL_DIR}|g" "${INSTALL_DIR}/deploy/briefr-backup.service" \
  > /etc/systemd/system/briefr-backup.service
cp "${INSTALL_DIR}/deploy/briefr-backup.timer" /etc/systemd/system/briefr-backup.timer
systemctl daemon-reload
systemctl enable briefr-backend briefr-backup.timer
systemctl restart briefr-backend
systemctl start briefr-backup.timer

# Open port 8000 for LAN testing (no nginx yet)
ufw allow OpenSSH
ufw allow 8000/tcp
ufw --force enable

# ── Done ───────────────────────────────────────────────────
echo ""
echo "========================================================"
echo " Setup complete!"
echo "========================================================"
sleep 3

echo ""
echo "Service status:"
systemctl status briefr-backend --no-pager -l | head -15

SERVER_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "Test the API from any machine on your LAN:"
echo "  curl http://${SERVER_IP}:8000/api/health"
echo "  curl http://${SERVER_IP}:8000/api/stats"
echo "  curl http://${SERVER_IP}:8000/api/usage"
echo ""
echo "Or open in a browser:"
echo "  http://${SERVER_IP}:8000/api/docs   (Swagger UI)"
echo ""
echo "Watch live logs:"
echo "  journalctl -u briefr-backend -f"
echo ""
echo "Pull updates later:"
echo "  git -C ${INSTALL_DIR} pull && systemctl restart briefr-backend"
