"""Tests for DetectionContext LLM artifact extraction (Track K4)."""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
from database import init_db, merge_cve_exploits, upsert_cve
from detection.artifact_extract import (
    nuclei_raw_url_from_blob,
    parse_artifacts_payload,
)
from detection.context import get_detection_context
from detection.context_llm_sync import (
    detection_context_llm_enabled,
    get_cves_for_detection_context_llm,
    run_detection_context_llm_sync,
)
from ai.llm_router import LLMCompletion


def test_parse_artifacts_payload_normalizes_fields():
    content = json.dumps(
        {
            "artifacts": [
                {
                    "paths": ["/api/login", "/api/login"],
                    "params": ["username", "password"],
                    "keywords": ["syntax error"],
                    "method": "post",
                },
                {"paths": [], "params": [], "keywords": []},
                "not-a-dict",
            ]
        }
    )
    artifacts = parse_artifacts_payload(content)
    assert len(artifacts) == 1
    assert artifacts[0]["paths"] == ["/api/login"]
    assert artifacts[0]["params"] == ["username", "password"]
    assert artifacts[0]["keywords"] == ["syntax error"]
    assert artifacts[0]["method"] == "POST"


def test_parse_artifacts_payload_strips_fences():
    fenced = (
        "```json\n"
        '{"artifacts": [{"paths": ["/admin"], "params": [], "keywords": [], "method": ""}]}\n'
        "```"
    )
    assert parse_artifacts_payload(fenced)[0]["paths"] == ["/admin"]


def test_nuclei_raw_url_from_blob():
    blob = (
        "https://github.com/projectdiscovery/nuclei-templates/blob/main/"
        "http/cves/2021/CVE-2021-44228.yaml"
    )
    assert nuclei_raw_url_from_blob(blob) == (
        "https://raw.githubusercontent.com/projectdiscovery/nuclei-templates/main/"
        "http/cves/2021/CVE-2021-44228.yaml"
    )
    raw = (
        "https://raw.githubusercontent.com/projectdiscovery/nuclei-templates/main/"
        "http/cves/2021/CVE-2021-44228.yaml"
    )
    assert nuclei_raw_url_from_blob(raw) == raw
    assert nuclei_raw_url_from_blob("https://example.com/nope") is None


def test_parse_artifacts_payload_accepts_single_object():
    content = json.dumps({"paths": ["/api"], "params": ["q"], "keywords": [], "method": "GET"})
    artifacts = parse_artifacts_payload(content)
    assert artifacts[0]["paths"] == ["/api"]


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DETECTION_CONTEXT_LLM_ENABLED", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert detection_context_llm_enabled() is False


def test_requires_flag_and_provider_key(monkeypatch):
    monkeypatch.setenv("DETECTION_CONTEXT_LLM_ENABLED", "1")
    for key in ("GROQ_API_KEY", "GEMINI_API_KEY", "CEREBRAS_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    assert detection_context_llm_enabled() is False
    monkeypatch.setenv("GEMINI_API_KEY", "gem_test")
    assert detection_context_llm_enabled() is True


def test_candidate_query_targets_has_poc_with_exploits(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "cand.db"))

    async def _run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-1001",
                    "description": "RCE in widget login",
                    "published": today,
                    "has_poc": 1,
                },
            )
            await upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-1002",
                    "description": "no exploit row",
                    "published": today,
                    "has_poc": 1,
                },
            )
            await merge_cve_exploits(
                db,
                "CVE-2024-1001",
                [
                    {
                        "title": "Nuclei template",
                        "type": "poc",
                        "source": "Nuclei",
                        "url": "https://github.com/projectdiscovery/nuclei-templates/blob/main/x.yaml",
                    }
                ],
            )
            await db.commit()
            return await get_cves_for_detection_context_llm(db, 10)
        finally:
            await db.close()

    candidates = asyncio.run(_run())
    assert [c["cve_id"] for c in candidates] == ["CVE-2024-1001"]


def test_run_llm_sync_writes_artifacts_and_negative_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "run.db"))
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    import detection.context_llm_sync as sync_mod

    async def fake_extract(text: str):
        return (
            [{"paths": ["/api/login"], "params": ["user"], "keywords": [], "method": "POST"}],
            LLMCompletion(content="{}", provider="groq", model="openai/gpt-oss-20b"),
        )

    async def fake_build_text(**_kwargs):
        return "CVE description:\nSQL injection in login endpoint /api/login param user"

    monkeypatch.setattr(sync_mod, "extract_artifacts_via_llm", fake_extract)
    monkeypatch.setattr(sync_mod, "build_extraction_text", fake_build_text)

    async def _run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-2001",
                    "description": "SQLi in login",
                    "published": today,
                    "has_poc": 1,
                    "cwe_ids": ["CWE-89"],
                },
            )
            await merge_cve_exploits(
                db,
                "CVE-2024-2001",
                [
                    {
                        "title": "PoC",
                        "type": "poc",
                        "source": "ExploitDB",
                        "url": "https://example.com/poc",
                    }
                ],
            )
            await db.commit()

            stats = await run_detection_context_llm_sync(db)
            stats_again = await run_detection_context_llm_sync(db)
            ctx = await get_detection_context(db, "CVE-2024-2001")
            cache_rows = await db.execute_fetchall(
                "SELECT cache_key, result FROM feed_cache "
                "WHERE cache_key LIKE 'detection_ctx_llm:%'"
            )
            return stats, stats_again, ctx, [dict(r) for r in cache_rows]
        finally:
            await db.close()

    stats, stats_again, ctx, cache_rows = asyncio.run(_run())
    assert stats == {"candidates": 1, "extracted": 1, "written": 1, "errors": 0, "skipped": 0}
    assert ctx["artifacts"][0]["paths"] == ["/api/login"]
    assert ctx["provider"] == "groq"
    assert ctx["model"] == "openai/gpt-oss-20b"
    assert len(cache_rows) == 1
    assert stats_again["candidates"] == 0


def test_scheduler_job_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("DETECTION_CONTEXT_LLM_ENABLED", raising=False)
    from scheduler import run_detection_context_llm_job

    assert asyncio.run(run_detection_context_llm_job()) is False
