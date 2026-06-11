"""Tests for CF Access JWT identity, audit_log writes, and admin fail-closed."""

import asyncio
import json
import sqlite3
import sys
import time
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jwt.algorithms import RSAAlgorithm

import cf_access
import database
import main
from backup.manager import restore_backup, run_backup
from tests.test_backup_manager import _cfg, _corrupt_db, _make_db

TEAM = "testteam"
ISSUER = "https://testteam.cloudflareaccess.com"
AUD = "a" * 64
KID = "test-key-1"


@pytest.fixture
def signing_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture
def cf_env(monkeypatch, signing_key):
    """Configure CF Access env and serve the matching JWKS without network."""
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", TEAM)
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    cf_access.reset_jwks_cache()

    jwk = json.loads(RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk.update({"kid": KID, "alg": "RS256", "use": "sig"})
    payload = {"keys": [jwk]}
    calls: list[str] = []

    class _FakeResponse:
        def json(self):
            return payload

    async def _fake_resilient_get(source, url, **kwargs):
        calls.append(url)
        return _FakeResponse()

    monkeypatch.setattr(cf_access, "resilient_get", _fake_resilient_get)
    yield calls
    cf_access.reset_jwks_cache()


def _token(key, *, kid=KID, **overrides):
    now = int(time.time())
    claims = {
        "aud": [AUD],
        "iss": ISSUER,
        "email": "Tester@Example.com",
        "iat": now,
        "exp": now + 3600,
        "sub": "tester-sub",
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return pyjwt.encode(claims, key, algorithm="RS256", headers={"kid": kid})


def _request(headers: dict) -> types.SimpleNamespace:
    return types.SimpleNamespace(headers=headers, state=types.SimpleNamespace())


def test_valid_assertion_yields_lowercased_email(cf_env, signing_key):
    token = _token(signing_key)
    email = asyncio.run(cf_access.identity_from_token(token))
    assert email == "tester@example.com"
    assert len(cf_env) == 1  # JWKS fetched once and cached


def test_jwks_cache_reused_across_tokens(cf_env, signing_key):
    asyncio.run(cf_access.identity_from_token(_token(signing_key)))
    asyncio.run(cf_access.identity_from_token(_token(signing_key)))
    assert len(cf_env) == 1


def test_wrong_audience_rejected(cf_env, signing_key):
    token = _token(signing_key, aud=["b" * 64])
    assert asyncio.run(cf_access.identity_from_token(token)) is None


def test_wrong_issuer_rejected(cf_env, signing_key):
    token = _token(signing_key, iss="https://evil.example.com")
    assert asyncio.run(cf_access.identity_from_token(token)) is None


def test_expired_token_rejected(cf_env, signing_key):
    now = int(time.time())
    token = _token(signing_key, iat=now - 7200, exp=now - 3600)
    assert asyncio.run(cf_access.identity_from_token(token)) is None


def test_token_without_expiry_rejected(cf_env, signing_key):
    token = _token(signing_key, exp=None)
    assert asyncio.run(cf_access.identity_from_token(token)) is None


def test_forged_signature_rejected(cf_env):
    attacker_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _token(attacker_key)  # same kid, wrong private key
    assert asyncio.run(cf_access.identity_from_token(token)) is None


def test_unknown_kid_rejected(cf_env, signing_key):
    token = _token(signing_key, kid="rotated-away")
    assert asyncio.run(cf_access.identity_from_token(token)) is None


def test_garbage_token_rejected(cf_env):
    assert asyncio.run(cf_access.identity_from_token("not.a.jwt")) is None


def test_unconfigured_env_disables_identity(monkeypatch, signing_key):
    monkeypatch.delenv("CF_ACCESS_TEAM_DOMAIN", raising=False)
    monkeypatch.delenv("CF_ACCESS_AUD", raising=False)
    cf_access.reset_jwks_cache()
    request = _request({"Cf-Access-Jwt-Assertion": _token(signing_key)})
    assert asyncio.run(cf_access.identity_from_request(request)) is None


def test_plain_email_header_is_never_trusted(cf_env):
    """LAN path spoof: forged email header without a valid JWT → no identity."""
    request = _request({"Cf-Access-Authenticated-User-Email": "admin@example.com"})
    assert asyncio.run(cf_access.identity_from_request(request)) is None


def test_identity_from_request_validates_assertion(cf_env, signing_key):
    request = _request({"Cf-Access-Jwt-Assertion": _token(signing_key)})
    assert asyncio.run(cf_access.identity_from_request(request)) == "tester@example.com"


def test_team_domain_normalization(monkeypatch):
    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "myteam")
    monkeypatch.setenv("CF_ACCESS_AUD", AUD)
    assert cf_access.get_cf_access_config() == ("myteam.cloudflareaccess.com", AUD)

    monkeypatch.setenv("CF_ACCESS_TEAM_DOMAIN", "https://myteam.cloudflareaccess.com/")
    assert cf_access.get_cf_access_config() == ("myteam.cloudflareaccess.com", AUD)


# --- audit_log ---------------------------------------------------------------


def test_write_audit_log_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "audit.db"))

    async def _run():
        await database.init_db()
        db = await database.get_db()
        try:
            await database.write_audit_log(
                db, "tester@example.com", "refresh.full", "nvd+kev+epss"
            )
            await database.write_audit_log(db, None, "refresh.kev", "kev")
            await db.commit()
            rows = await db.execute_fetchall(
                "SELECT actor, action, target, created_at FROM audit_log ORDER BY id"
            )
            return [dict(r) for r in rows]
        finally:
            await db.close()

    rows = asyncio.run(_run())
    assert rows[0]["actor"] == "tester@example.com"
    assert rows[0]["action"] == "refresh.full"
    assert rows[0]["target"] == "nvd+kev+epss"
    assert rows[0]["created_at"]
    assert rows[1]["actor"] == ""  # no identity → empty actor, never a forged email


def test_backup_run_writes_audit_row(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)

    result = run_backup(reason="test", config=cfg)
    assert result["status"] == "ok"

    conn = sqlite3.connect(cfg.db_path)
    try:
        rows = conn.execute(
            "SELECT actor, action, target FROM audit_log"
        ).fetchall()
    finally:
        conn.close()
    assert len(rows) == 1
    actor, action, target = rows[0]
    assert actor == "system"
    assert action == "backup.run"
    assert Path(result["archive"]).name in target
    assert "reason=test" in target


def test_restore_writes_audit_row(tmp_path):
    cfg = _cfg(tmp_path)
    _make_db(cfg.db_path)
    archive = Path(run_backup(reason="seed", config=cfg)["archive"])
    _corrupt_db(cfg.db_path)

    result = restore_backup(archive, config=cfg, force=True)
    assert result["status"] == "ok"

    conn = sqlite3.connect(cfg.db_path)
    try:
        rows = conn.execute(
            "SELECT actor, action, target FROM audit_log WHERE action = 'backup.restore'"
        ).fetchall()
    finally:
        conn.close()
    assert rows == [("system", "backup.restore", archive.name)]


# --- admin key fail-closed ----------------------------------------------------


def test_admin_key_fails_closed_in_production(monkeypatch):
    monkeypatch.setattr(main, "_IS_PRODUCTION", True)
    monkeypatch.setattr(main, "BRIEFR_ADMIN_API_KEY", "")
    with pytest.raises(HTTPException) as exc:
        main._require_admin_key(_request({}))
    assert exc.value.status_code == 401


def test_admin_key_open_in_development_when_unset(monkeypatch):
    monkeypatch.setattr(main, "_IS_PRODUCTION", False)
    monkeypatch.setattr(main, "BRIEFR_ADMIN_API_KEY", "")
    main._require_admin_key(_request({}))  # must not raise


def test_admin_key_enforced_when_configured(monkeypatch):
    monkeypatch.setattr(main, "_IS_PRODUCTION", True)
    monkeypatch.setattr(main, "BRIEFR_ADMIN_API_KEY", "secret-key")
    with pytest.raises(HTTPException):
        main._require_admin_key(_request({"X-BRIEFR-Admin-Key": "wrong"}))
    main._require_admin_key(_request({"X-BRIEFR-Admin-Key": "secret-key"}))
