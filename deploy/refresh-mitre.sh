#!/usr/bin/env bash
# Refresh MITRE ATT&CK techniques and CVE→technique mappings (weekly job uses same logic)
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"
APP_HOME="/var/lib/briefr"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash $0"
  exit 1
fi

mkdir -p "${APP_HOME}/.cache/pip"
chown -R "${APP_USER}:${APP_USER}" "${APP_HOME}" 2>/dev/null || true

echo "==> Refreshing MITRE ATT&CK data"
runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" \
  bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c \"
import asyncio
from database import init_db, get_db
from feeds.mitre import refresh_mitre_data

async def main():
    await init_db()
    db = await get_db()
    stats = await refresh_mitre_data(db)
    await db.close()
    print('MITRE refresh:', stats)

asyncio.run(main())
\""

echo "==> Done. Restart backend if needed: systemctl restart briefr-backend"
