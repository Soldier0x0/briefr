"""Tests for DetectionContext scaffold (Sprint D2)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

import database
from database import init_db, upsert_cve
from detection.context import (
    build_detection_context,
    detection_context_cache_key,
    get_detection_context,
    merge_detection_inputs,
    resolve_detection_class,
    set_detection_context,
)
from detection.context_sync import (
    detection_context_sync_enabled,
    get_cves_for_detection_context_sync,
    run_detection_context_sync,
)
from detection.sigma_generator import generate_sigma_rule


def _load_rule(yaml_text: str) -> dict:
    data = yaml.safe_load(yaml_text)
    assert isinstance(data, dict)
    return data


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DETECTION_CONTEXT_SYNC_ENABLED", raising=False)
    assert detection_context_sync_enabled() is False


def test_enabled_with_flag(monkeypatch):
    monkeypatch.setenv("DETECTION_CONTEXT_SYNC_ENABLED", "1")
    assert detection_context_sync_enabled() is True


def test_resolve_detection_class_technique_wins():
    assert resolve_detection_class("T1190", ["CWE-22"]) == "web_exploit"


def test_resolve_detection_class_cwe_fallback():
    assert resolve_detection_class("", ["CWE-89"]) == "sqli"
    assert resolve_detection_class("", ["CWE-9999"]) == "generic"


def test_build_detection_context_shape():
    ctx = build_detection_context(
        cve_id="CVE-2024-0001",
        cwe_ids=["CWE-78"],
        technique_id="",
        affected_products=json.dumps(["acme:widget_app"]),
    )
    assert ctx["cwe_ids"] == ["CWE-78"]
    assert ctx["product"] == "widget app"
    assert ctx["class"] == "cmd_injection"
    assert ctx["artifacts"] == []
    assert ctx["model"] == ""
    assert ctx["provider"] == "briefr"
    assert ctx["generated_at"]


def test_merge_detection_inputs_prefers_explicit_over_cache():
    product, cwe_ids, technique = merge_detection_inputs(
        product="Override",
        cwe_ids=["CWE-22"],
        technique_id="T1190",
        detection_context={
            "product": "Cached",
            "cwe_ids": ["CWE-89"],
        },
    )
    assert product == "Override"
    assert cwe_ids == ["CWE-22"]
    assert technique == "T1190"


def test_merge_detection_inputs_fills_from_cache():
    product, cwe_ids, _ = merge_detection_inputs(
        detection_context={
            "product": "pan-os",
            "cwe_ids": ["CWE-89"],
        },
    )
    assert product == "pan-os"
    assert cwe_ids == ["CWE-89"]


def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "briefr.db"))

    async def _run():
        await init_db()
        db = await database.get_db()
        try:
            ctx = build_detection_context(
                cve_id="CVE-2024-0100",
                cwe_ids=["CWE-22"],
                affected_products=json.dumps(["vendor:portal"]),
            )
            await set_detection_context(db, "CVE-2024-0100", ctx)
            await db.commit()
            loaded = await get_detection_context(db, "CVE-2024-0100")
            assert loaded == ctx
            assert detection_context_cache_key("cve-2024-0100") == "detection_ctx:CVE-2024-0100"
        finally:
            await db.close()

    run_db_test(_run())


def test_sync_backfills_missing_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "briefr.db"))

    async def _run():
        await init_db()
        db = await database.get_db()
        try:
            await upsert_cve(
                db,
                {
                    "cve_id": "CVE-2024-0200",
                    "description": "SQL injection in widget",
                    "cwe_ids": ["CWE-89"],
                    "affected_products": ["acme:widget"],
                    "published": "2024-01-01",
                },
            )
            await db.commit()

            pending = await get_cves_for_detection_context_sync(db, 10)
            assert [row["cve_id"] for row in pending] == ["CVE-2024-0200"]

            stats = await run_detection_context_sync(db)
            await db.commit()
            assert stats["candidates"] == 1
            assert stats["written"] == 1

            cached = await get_detection_context(db, "CVE-2024-0200")
            assert cached["class"] == "sqli"
            assert cached["product"] == "widget"

            stats_again = await run_detection_context_sync(db)
            assert stats_again["candidates"] == 0
        finally:
            await db.close()

    run_db_test(_run())


def test_generate_sigma_rule_uses_detection_context_product_and_class():
    ctx = build_detection_context(
        cve_id="CVE-2024-0300",
        cwe_ids=["CWE-89"],
        affected_products=json.dumps(["acme:reporting_db"]),
    )
    rule = _load_rule(
        generate_sigma_rule(
            "CVE-2024-0300",
            "",
            cwe_ids=[],
            detection_context=ctx,
        )
    )
    assert "reporting db" in rule["title"].lower()
    assert rule["briefr_basis"] == "cwe"
    assert rule["briefr_class"] == "sqli"


def test_scheduler_job_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("DETECTION_CONTEXT_SYNC_ENABLED", raising=False)
    from scheduler import run_detection_context_sync_job

    assert run_db_test(run_detection_context_sync_job()) is False
