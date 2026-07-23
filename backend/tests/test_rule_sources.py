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


def test_github_search_handles_none_token_without_crashing(monkeypatch):
    """Gemini review on PR #484: token might be explicitly None (not just
    the default ""), which would raise AttributeError on .strip() before
    this fix (_gh_headers had the same pattern, fixed alongside)."""
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    result = asyncio.run(rule_sources._github_search("query", token=None))
    assert result == []

    headers = rule_sources._gh_headers(token=None)
    assert "Authorization" not in headers


def test_sigma_mentions_cve_from_path_and_tags():
    path = "rules-emerging-threats/2021/Exploits/CVE-2021-44228/web_cve_2021_44228.yml"
    assert rule_sources._sigma_mentions_cve("CVE-2021-44228", path, None) is True
    content = "tags:\n    - cve.2021.44228\nauthor: Alice\n"
    assert rule_sources._sigma_mentions_cve(
        "CVE-2021-44228", "rules/web/other.yml", content
    ) is True
    assert rule_sources._sigma_mentions_cve(
        "CVE-2021-44228", "rules/web/other.yml", "title: Unrelated\n"
    ) is False


def test_classify_and_rank_prefer_cve_exact():
    exact = {"title": "B", "match_basis": "cve_exact", "path": "a.yml"}
    search = {"title": "A", "match_basis": "cve_search", "path": "b.yml"}
    tech = {"title": "C", "match_basis": "technique_related", "path": "c.yml"}
    ranked = rule_sources._rank_sigma_rules([tech, search, exact])
    assert [r["match_basis"] for r in ranked] == [
        "cve_exact",
        "cve_search",
        "technique_related",
    ]

    assert (
        rule_sources._classify_sigma_match(
            "CVE-2021-44228",
            "rules/web/log4j.yml",
            "tags:\n  - cve.2021.44228\n",
            search_mode="cve",
        )
        == "cve_exact"
    )
    assert (
        rule_sources._classify_sigma_match(
            "CVE-2021-44228",
            "rules/windows/proc_creation_powershell.yml",
            "title: PowerShell\n",
            search_mode="technique",
        )
        == "technique_related"
    )


def test_apply_sigma_provenance_sets_drl_attribution():
    rule = {
        "path": "rules-emerging-threats/2021/Exploits/CVE-2021-44228/x.yml",
        "title": "Log4Shell",
    }
    content = "title: Log4Shell\nauthor: Neo23x0\nstatus: test\ntags:\n  - cve.2021.44228\n"
    rule_sources._apply_sigma_provenance(
        rule, cve_id="CVE-2021-44228", search_mode="cve", content=content
    )
    assert rule["match_basis"] == "cve_exact"
    assert rule["license"] == "DRL-1.1"
    assert "Detection-Rule-License" in rule["license_url"]
    assert rule["author"] == "Neo23x0"
    assert "Neo23x0" in rule["attribution"]
