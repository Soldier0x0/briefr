#!/usr/bin/env bash
# Refresh MITRE ATLAS techniques and case studies (also runs with weekly MITRE job)
set -euo pipefail

INSTALL_DIR="/opt/briefr"
APP_USER="briefr"
APP_HOME="/var/lib/briefr"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: bash $0"
  exit 1
fi

echo "==> Refreshing MITRE ATLAS data"
runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" \
  bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/pip' install -q PyYAML==6.0.2 && '${INSTALL_DIR}/venv/bin/python' -c \"
import asyncio
import logging
from database import init_db, get_db
from feeds.atlas import refresh_atlas_data

logging.basicConfig(level=logging.INFO, format='%(message)s')

async def main():
    await init_db()
    db = await get_db()
    stats = await refresh_atlas_data(db)
    await db.close()
    print('ATLAS refresh:', stats)

asyncio.run(main())
\""

echo "==> Done. Restart backend: sudo systemctl restart briefr-backend"
