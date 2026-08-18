"""Export-mode tests for classified shared-infrastructure hosts."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import blocklist.build as build_mod
import database
import db.blocklist as db_blocklist
from blocklist.infra_seed import SHARED_LEGITIMATE_INFRASTRUCTURE
from blocklist.serialize import to_csv, to_txt
from database import get_db, init_db
from tests.conftest import run_db_test


async def _infra_drive_google(db):
    return [{
        "host": "drive.google.com",
        "classification": SHARED_LEGITIMATE_INFRASTRUCTURE,
        "enabled": 1,
        "provenance": "curated",
        "reason": "shared infra",
        "notes": "",
    }]


async def _seed_url_row(db):
    await db.execute(
        """
        INSERT INTO ti_mirror_iocs (
            source, ref_id, ioc_type, ioc_value, raw_ioc, host_ioc, malware,
            threat_type, confidence_level, first_seen
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "threatfox",
            "tf-drive",
            "domain",
            "drive.google.com",
            "https://drive.google.com/uc?export=download&id=ABC",
            "drive.google.com",
            "redline",
            "botnet_cc",
            90,
            "2024-06-01",
        ),
    )
    await db.commit()


def test_classified_host_excluded_from_domain_txt_but_url_mode(tmp_path, monkeypatch):
    async def run():
        db_path = str(tmp_path / "classified.db")
        monkeypatch.setenv("DB_PATH", db_path)
        monkeypatch.setattr(database, "DB_PATH", db_path)
        await init_db()
        db = await get_db()
        try:
            monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _infra_drive_google)
            monkeypatch.setattr(build_mod, "fetch_infra_classifications", _infra_drive_google)
            await _seed_url_row(db)

            payload = await build_mod.build_blocklist(db)
            rec = next(r for r in payload["domains"] if r["domain"] == "drive.google.com")
            assert rec["eligible"] is True
            assert rec["eligible_domain"] is False
            assert rec["eligible_url"] is True

            domain_txt = to_txt(payload, mode="domains")
            assert "drive.google.com" not in [
                line for line in domain_txt.splitlines() if line and not line.startswith("#")
            ]

            url_txt = to_txt(payload, mode="urls")
            assert "https://drive.google.com/uc?export=download&id=ABC" in url_txt

            csv_domains = to_csv(payload, mode="domains")
            assert "drive.google.com" not in csv_domains
            csv_urls = to_csv(payload, mode="urls")
            assert "https://drive.google.com/uc?export=download&id=ABC" in csv_urls
        finally:
            await db.close()

    run_db_test(run())
