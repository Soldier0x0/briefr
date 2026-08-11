"""Endpoint tests for the public threat-intel export routes.

Covers the release-gate behavior of /api/threat-intel/blocklist.txt and
/api/threat-intel/blocklist.json (routers/threat_intel.py):
- 503 when THREAT_INTEL_TOKEN is unset — the export fails closed.
- 401 when the X-BRIEFR-Intel-Token header is missing or mismatched.
- 200 with the correct token (both the TXT and JSON content types).
- 429 when the per-client token bucket is drained.

infra_classifications is a Postgres-only app-schema table, so the 200-path
stubs fetch_infra_classifications out with the same _no_infra seam used by
tests/test_threat_intel_blocklist_fixes.py; otherwise SQLite raises on the
missing app.infra_classifications table.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient

import blocklist.build as build_mod
import database
import db.blocklist as db_blocklist
import rate_limit
from settings import settings

# TestClient connections report this client host; it is the bucket key.
TESTCLIENT_KEY = "testclient"

_BLOCKLIST_PATHS = (
    "/api/threat-intel/blocklist.txt",
    "/api/threat-intel/blocklist.json",
)
_INTEL_TOKEN = "test-export-token"


async def _no_infra(db):
    return []


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "threat_intel_public.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(settings, "rate_limit_enabled", False)

    from main import app

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def test_public_blocklist_unconfigured_token_returns_503(client, monkeypatch):
    """Fails closed: with nothing set for THREAT_INTEL_TOKEN both export
    routes return 503 before any token comparison happens. The token is
    forced to '' so the assertion is independent of ambient env."""
    monkeypatch.setattr(settings, "threat_intel_token", "")
    for path in _BLOCKLIST_PATHS:
        resp = client.get(path)
        assert resp.status_code == 503, f"{path} must 503 when token is unset"


def test_public_blocklist_missing_token_returns_401(client, monkeypatch):
    """A configured export requires the X-BRIEFR-Intel-Token header."""
    monkeypatch.setattr(settings, "threat_intel_token", _INTEL_TOKEN)
    for path in _BLOCKLIST_PATHS:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} must 401 when header is missing"


def test_public_blocklist_wrong_token_returns_401(client, monkeypatch):
    """A mismatched header value must not authenticate."""
    monkeypatch.setattr(settings, "threat_intel_token", _INTEL_TOKEN)
    headers = {"X-BRIEFR-Intel-Token": "wrong-token"}
    for path in _BLOCKLIST_PATHS:
        resp = client.get(path, headers=headers)
        assert resp.status_code == 401, f"{path} must 401 when header is wrong"


def test_public_blocklist_correct_token_returns_200_txt_and_json(client, monkeypatch):
    """With the right token both exports render. infra_classifications is
    PG-only, so the same _no_infra stub seam is applied to keep SQLite green."""
    monkeypatch.setattr(settings, "threat_intel_token", _INTEL_TOKEN)
    monkeypatch.setattr(db_blocklist, "fetch_infra_classifications", _no_infra)
    monkeypatch.setattr(build_mod, "fetch_infra_classifications", _no_infra)

    headers = {"X-BRIEFR-Intel-Token": _INTEL_TOKEN}

    txt = client.get("/api/threat-intel/blocklist.txt", headers=headers)
    assert txt.status_code == 200
    assert txt.headers["content-type"].startswith("text/plain")
    assert txt.headers["cache-control"] == "no-store", (
        "TXT export must not be cacheable by a shared proxy"
    )

    exported = client.get("/api/threat-intel/blocklist.json", headers=headers)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("application/json")
    assert exported.headers["cache-control"] == "no-store", (
        "JSON export must not be cacheable by a shared proxy"
    )


def test_public_blocklist_rate_limited_returns_429(client, monkeypatch):
    """A drained token bucket returns 429 before token auth (the rate-limit
    dependency runs first). The spilled bucket key is removed afterwards so
    the rest of the suite is not poisoned."""
    monkeypatch.setattr(settings, "threat_intel_token", _INTEL_TOKEN)
    monkeypatch.setattr(settings, "rate_limit_enabled", True)
    rate_limit.threat_intel_bucket._buckets[TESTCLIENT_KEY] = (
        0.0,
        time.monotonic(),
    )
    try:
        resp = client.get(
            "/api/threat-intel/blocklist.txt",
            headers={"X-BRIEFR-Intel-Token": _INTEL_TOKEN},
        )
        assert resp.status_code == 429
    finally:
        rate_limit.threat_intel_bucket._buckets.pop(TESTCLIENT_KEY, None)