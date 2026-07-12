"""Tests for detection.rule_sources — GitHub-backed community rule search.

QA-F1 regression coverage: unauthenticated GitHub code search is slow and
unreliable (10 req/min unauthenticated rate limit), and the DETECT tab's
endpoint calls find_sigma_rules/find_elastic_rules sequentially by design
(they share one asyncpg connection — see routers/cves.py's comment on why
they cannot be parallelized). The fix is not to parallelize; it's to skip
the network call entirely when no token is configured, the same honest
early-exit pattern used elsewhere (GreyNoise/OTX "not configured").
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import detection.rule_sources as rule_sources


def test_github_search_skips_network_call_when_no_token(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    called = {"n": 0}

    async def fail_if_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("resilient_get must not be called without a GitHub token")

    monkeypatch.setattr(rule_sources, "resilient_get", fail_if_called)

    result = asyncio.run(rule_sources._github_search("CVE-2024-1234+repo:SigmaHQ/sigma"))

    assert result == []
    assert called["n"] == 0


def test_github_search_still_calls_out_when_token_provided(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    called = {"n": 0}

    class FakeResponse:
        def json(self):
            return {"items": [{"path": "rules/x.yml"}]}

    async def fake_get(*args, **kwargs):
        called["n"] += 1
        return FakeResponse()

    monkeypatch.setattr(rule_sources, "resilient_get", fake_get)

    result = asyncio.run(
        rule_sources._github_search("CVE-2024-1234+repo:SigmaHQ/sigma", token="ghp_explicit_token")
    )

    assert called["n"] == 1
    assert result == [{"path": "rules/x.yml"}]


def test_find_sigma_rules_returns_empty_fast_without_token(monkeypatch, tmp_path):
    """End-to-end: with no GITHUB_TOKEN, find_sigma_rules must not touch the
    network at all -- it should return the same 'no community rules' shape
    it always has, just without the 15-30s of doomed unauthenticated calls."""
    import database as db_module
    from database import get_db, init_db

    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("DB_PATH", str(tmp_path / "rule_sources.db"))
    monkeypatch.setattr(db_module, "DB_PATH", str(tmp_path / "rule_sources.db"))

    called = {"n": 0}

    async def fail_if_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("must not reach the network without a token")

    monkeypatch.setattr(rule_sources, "resilient_get", fail_if_called)

    async def run():
        await init_db()
        db = await get_db()
        try:
            return await rule_sources.find_sigma_rules(db, "CVE-2024-1234", ["T1190"])
        finally:
            await db.close()

    result = asyncio.run(run())
    assert result == []
    assert called["n"] == 0
