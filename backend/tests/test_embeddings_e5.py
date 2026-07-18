"""Embeddings E5 — search API tokens (bcrypt, scopes, middleware)."""

from __future__ import annotations

import os
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from auth_middleware import search_token_path_allowed
from database import init_db
from db.search_tokens import (
    TOKEN_PREFIX,
    create_search_token,
    list_search_tokens,
    revoke_search_token,
    verify_search_token,
)
from tests.conftest import run_db_test


def test_search_token_path_allowlist():
    assert search_token_path_allowed("/api/search/semantic", "GET")
    assert search_token_path_allowed("/api/cves/CVE-2024-1234", "GET")
    assert search_token_path_allowed("/api/cves/CVE-2024-1234/related", "GET")
    assert search_token_path_allowed("/api/cves/CVE-2024-1234/drawer", "GET")
    assert not search_token_path_allowed("/api/cves/export", "GET")
    assert not search_token_path_allowed("/api/admin/system", "GET")
    assert not search_token_path_allowed("/api/search/semantic", "POST")


def test_create_verify_revoke_search_token(tmp_path, monkeypatch):
    if os.environ.get("DATABASE_URL", "").startswith("postgresql"):
        pytest.skip("SQLite path")
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "e5tok.db"))

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            created = await create_search_token(
                db, name="Agent A", created_by="admin"
            )
            await db.commit()
            assert created["token"].startswith(TOKEN_PREFIX)
            assert "token_hash" not in created
            listed = await list_search_tokens(db)
            assert listed[0]["token_prefix"] == created["token_prefix"]
            assert listed[0]["active"] is True
            meta = await verify_search_token(db, created["token"])
            assert meta is not None
            assert meta["id"] == created["id"]
            assert await revoke_search_token(db, created["id"]) is True
            await db.commit()
            assert await verify_search_token(db, created["token"]) is None
            return created
        finally:
            await db.close()

    created = run_db_test(run())
    assert created["scopes"]


@pytest.fixture
def search_token_client(tmp_path, monkeypatch):
    db_path = tmp_path / "e5api.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "0")
    monkeypatch.setenv("EMBEDDINGS_ENABLED", "0")

    async def seed():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published) VALUES (?, ?, ?)",
                ("CVE-2024-5555", "token scoped read", date.today().isoformat()),
            )
            created = await create_search_token(db, name="e5-test")
            await db.commit()
            return created["token"]
        finally:
            await db.close()

    token = run_db_test(seed())

    from fastapi.testclient import TestClient
    from main import app

    with TestClient(app) as client:
        yield client, token


def test_search_token_can_call_semantic_and_cve_detail(search_token_client):
    client, token = search_token_client
    headers = {"Authorization": f"Bearer {token}"}
    # No session cookie — middleware should accept search token alone.
    client.cookies.clear()
    sem = client.get("/api/search/semantic", params={"q": "token", "mode": "keyword"}, headers=headers)
    assert sem.status_code == 200, sem.text
    detail = client.get("/api/cves/CVE-2024-5555", headers=headers)
    assert detail.status_code == 200
    related = client.get("/api/cves/CVE-2024-5555/related", headers=headers)
    assert related.status_code == 200


def test_search_token_denied_admin(search_token_client):
    client, token = search_token_client
    client.cookies.clear()
    res = client.get(
        "/api/admin/system",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Admin still requires admin session — search token is not enough.
    assert res.status_code in (401, 403)


def test_search_token_denied_off_allowlist(search_token_client):
    client, token = search_token_client
    client.cookies.clear()
    res = client.get(
        "/api/cves/export",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
