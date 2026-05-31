#!/usr/bin/env bash
# Update EPSS scores only (FIRST CSV + API fallback) — does not re-fetch NVD
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

echo "==> Loading CVE IDs and fetching EPSS scores"
runuser -u "${APP_USER}" -- env HOME="${APP_HOME}" \
  bash -c "cd '${INSTALL_DIR}/backend' && '${INSTALL_DIR}/venv/bin/python' -c \"
import asyncio
from database import init_db, get_db, get_all_cve_ids, update_epss_scores
from feeds.epss import fetch_epss

async def main():
    await init_db()
    db = await get_db()
    ids = await get_all_cve_ids(db)
    await db.close()
    if not ids:
        print('No CVEs in database. Run: curl -X POST http://127.0.0.1:8000/api/refresh')
        return
    print('Fetching EPSS for', len(ids), 'CVEs...')
    scores = await fetch_epss(ids)
    db = await get_db()
    await update_epss_scores(db, scores)
    await db.commit()
    row = await db.execute_fetchall('SELECT COUNT(*) FROM cves WHERE epss_score IS NOT NULL')
    await db.close()
    print('EPSS scores written:', len(scores))
    print('CVEs with epss_score in DB:', row[0][0])

asyncio.run(main())
\""

echo "==> Done. Restart backend if needed: systemctl restart briefr-backend"
