#!/usr/bin/env bash
# BRIEFR initial server setup — Debian 11 / 12 / 13
# Run as root: bash deploy/setup.sh
#
# Full production install checklist: docs/SELF_HOST.md §3
# Bootstraps Python, clones the repo, creates the venv, then delegates to
# briefr-update.sh for nginx, frontend build, and systemd units.
set -euo pipefail

REPO_URL="https://github.com/Soldier0x0/briefr.git"
INSTALL_DIR="/opt/briefr"

echo "========================================================"
echo " BRIEFR Backend Setup"
echo "========================================================"

# ── Step 1: Detect Debian version ──────────────────────────
echo ""
echo "==> [1/6] Detecting OS"
. /etc/os-release
echo "    OS: ${PRETTY_NAME}"
DEBIAN_VERSION="${VERSION_ID:-0}"

# ── Step 2: Install Python (version depends on Debian release) ─
echo ""
echo "==> [2/6] Installing Python and system packages"
apt-get update -qq
apt-get install -y -qq git curl ufw

pick_python() {
  for bin in python3.13 python3.12 python3.11 python3.10; do
    if command -v "$bin" &>/dev/null; then
      echo "$bin"
      return
    fi
  done
  echo ""
}

if [ "${DEBIAN_VERSION}" = "13" ]; then
  echo "    Debian 13 (Trixie): using built-in Python 3.13"
  apt-get install -y -qq python3 python3-venv
  PYTHON_BIN="python3.13"

elif [ "${DEBIAN_VERSION}" = "12" ]; then
  echo "    Debian 12 (Bookworm): installing python3.12 from backports"
  if ! grep -q "bookworm-backports" /etc/apt/sources.list /etc/apt/sources.list.d/*.list 2>/dev/null; then
    echo "deb http://deb.debian.org/debian bookworm-backports main" \
      > /etc/apt/sources.list.d/backports.list
    apt-get update -qq
  fi
  apt-get install -y -qq -t bookworm-backports python3.12 python3.12-venv
  PYTHON_BIN="python3.12"

elif [ "${DEBIAN_VERSION}" = "11" ]; then
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
echo "==> [3/6] Cloning repository to ${INSTALL_DIR}"
if [ -d "${INSTALL_DIR}/.git" ]; then
  echo "    Repo exists — pulling latest..."
  git -C "${INSTALL_DIR}" pull --ff-only
else
  git clone "${REPO_URL}" "${INSTALL_DIR}"
fi

# ── Step 4: Create venv and install packages ───────────────
echo ""
echo "==> [4/6] Creating virtual environment and installing packages"
"${PYTHON_BIN}" -m venv "${INSTALL_DIR}/venv"
"${INSTALL_DIR}/venv/bin/pip" install --quiet --upgrade pip
"${INSTALL_DIR}/venv/bin/pip" install --quiet -r "${INSTALL_DIR}/backend/requirements.txt"

echo "    Installed:"
"${INSTALL_DIR}/venv/bin/pip" list --format=columns \
  | grep -E "fastapi|uvicorn|httpx|apscheduler|pydantic|aiosqlite|python-dotenv"

# ── Step 5: Configure .env ─────────────────────────────────
echo ""
echo "==> [5/6] Configuring environment"
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

# ── Step 6: Production deploy (nginx + frontend + systemd) ─
echo ""
echo "==> [6/6] Running production deploy (nginx, frontend build, systemd)"
ufw allow OpenSSH
ufw allow 80/tcp
ufw --force enable

export BRIEFR_UPDATE_REEXECED=1
exec bash "${INSTALL_DIR}/deploy/briefr-update.sh"
