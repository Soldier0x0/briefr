"""Tests for LLM product extraction (V1.3 Theme 7).

Covers: env gating (disabled by default), response parsing/normalization,
write-only-when-empty + 'llm' provenance, negative caching, and the upsert
supersede rules (official CPE replaces LLM data; empty feed payloads do not
wipe it). No network calls — the Groq client is monkeypatched.
"""

import asyncio
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import database
import ml.product_extraction as pex
from database import (
    get_cves_for_llm_product_extraction,
    init_db,
    set_llm_affected_products,
    upsert_cve,
)
from ml.product_extraction import (
    llm_product_extraction_enabled,
    parse_products_payload,
    products_to_affected_keys,
    run_llm_product_extraction,
)


def test_disabled_by_default(monkeypatch):
    monkeypatch.delenv("LLM_PRODUCT_EXTRACTION_ENABLED", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert llm_product_extraction_enabled() is False


def test_requires_both_flag_and_groq_key(monkeypatch):
    monkeypatch.setenv("LLM_PRODUCT_EXTRACTION_ENABLED", "1")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert llm_product_extraction_enabled() is False
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert llm_product_extraction_enabled() is True


def test_parse_products_payload_normalizes_tokens():
    content = json.dumps(
        {
            "products": [
                {"vendor": "Palo Alto Networks", "product": "PAN-OS", "version_range": "< 11.0"},
                {"vendor": "", "product": "OpenSSL"},  # vendor falls back to product
                {"vendor": "palo alto networks", "product": "pan-os"},  # duplicate
                {"product": ""},  # no product → dropped
                "not-a-dict",
            ]
        }
    )
    products = parse_products_payload(content)
    assert products[0]["vendor"] == "palo_alto_networks"
    assert products[0]["product"] == "pan-os"
    assert products[0]["version_range"] == "< 11.0"
    assert {"vendor": "openssl", "product": "openssl", "version_range": ""} in products
    assert len(products) == 2  # dedupe + invalid entries dropped


def test_parse_products_payload_strips_fences_and_survives_garbage():
    fenced = "```json\n{\"products\": [{\"vendor\": \"nginx\", \"product\": \"nginx\"}]}\n```"
    assert parse_products_payload(fenced)[0]["product"] == "nginx"
    assert parse_products_payload("not json at all") == []
    assert parse_products_payload("") == []
    assert parse_products_payload('{"products": "nope"}') == []


def test_parse_products_payload_handles_conversational_wrapping():
    """PR #110 review: prefixes/suffixes around the JSON (with or without
    fences) must not poison the result with a 7-day negative cache."""
    prefixed_fence = (
        "Here is the JSON you asked for:\n"
        "```json\n"
        '{"products": [{"vendor": "nginx", "product": "nginx", "version_range": "< 1.25"}]}\n'
        "```\n"
        "Let me know if you need anything else."
    )
    out = parse_products_payload(prefixed_fence)
    assert out == [{"vendor": "nginx", "product": "nginx", "version_range": "< 1.25"}]

    bare_prefix = (
        'Sure! {"products": [{"vendor": "acme", "product": "widget"}]} Hope this helps.'
    )
    assert parse_products_payload(bare_prefix)[0]["product"] == "widget"

    # Nested braces inside the object must survive the outermost-span extraction.
    nested = (
        "Result: {\"products\": [{\"vendor\": \"a\", \"product\": \"b\", "
        "\"version_range\": \"{1.0}\"}]}"
    )
    assert parse_products_payload(nested)[0]["version_range"] == "{1.0}"

    # Top-level JSON arrays keep working through the bracket-span fallback.
    array_prefix = 'Answer: [{"vendor": "x", "product": "y"}]'
    assert parse_products_payload(array_prefix)[0]["product"] == "y"


def test_products_to_affected_keys_matches_existing_format():
    products = [{"vendor": "google", "product": "tensorflow", "version_range": "all"}]
    assert products_to_affected_keys(products) == ["google:tensorflow"]


def test_set_llm_affected_products_only_writes_when_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "llm.db"))

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products) "
                "VALUES ('CVE-2024-0001', 'x', ?, '[]')",
                (today,),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products) "
                "VALUES ('CVE-2024-0002', 'y', ?, ?)",
                (today, json.dumps(["nginx:nginx"])),
            )
            await db.commit()

            wrote_empty = await set_llm_affected_products(db, "CVE-2024-0001", ["acme:widget"])
            wrote_full = await set_llm_affected_products(db, "CVE-2024-0002", ["acme:widget"])
            await db.commit()

            rows = await db.execute_fetchall(
                "SELECT cve_id, affected_products, affected_products_source "
                "FROM cves ORDER BY cve_id"
            )
            return wrote_empty, wrote_full, [dict(r) for r in rows]
        finally:
            await db.close()

    wrote_empty, wrote_full, rows = asyncio.run(run())
    assert wrote_empty is True
    assert wrote_full is False  # never overwrites a populated field
    assert json.loads(rows[0]["affected_products"]) == ["acme:widget"]
    assert rows[0]["affected_products_source"] == "llm"  # provenance marker
    assert json.loads(rows[1]["affected_products"]) == ["nginx:nginx"]
    assert rows[1]["affected_products_source"] == ""


def test_upsert_supersede_rules_for_llm_products(tmp_path, monkeypatch):
    """NVD upserts: an empty payload must NOT wipe LLM products; a non-empty
    official product list supersedes them and clears the provenance marker."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "supersede.db"))

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            base = {
                "cve_id": "CVE-2024-7777",
                "description": "Fresh CVE, NVD not analyzed yet.",
                "published": date.today().isoformat(),
                "affected_products": [],
            }
            await upsert_cve(db, base)
            await set_llm_affected_products(db, "CVE-2024-7777", ["acme:widget"])
            await db.commit()

            # NVD re-sync, still unanalyzed (empty products) → LLM data kept.
            await upsert_cve(db, dict(base))
            await db.commit()
            after_empty = dict(
                (await db.execute_fetchall(
                    "SELECT affected_products, affected_products_source FROM cves "
                    "WHERE cve_id = 'CVE-2024-7777'"
                ))[0]
            )

            # NVD analysis lands (official CPE) → supersedes, marker cleared.
            official = dict(base)
            official["affected_products"] = ["acme:widget", "acme:gadget"]
            await upsert_cve(db, official)
            await db.commit()
            after_official = dict(
                (await db.execute_fetchall(
                    "SELECT affected_products, affected_products_source FROM cves "
                    "WHERE cve_id = 'CVE-2024-7777'"
                ))[0]
            )
            return after_empty, after_official
        finally:
            await db.close()

    after_empty, after_official = asyncio.run(run())
    assert json.loads(after_empty["affected_products"]) == ["acme:widget"]
    assert after_empty["affected_products_source"] == "llm"
    assert json.loads(after_official["affected_products"]) == ["acme:widget", "acme:gadget"]
    assert after_official["affected_products_source"] == ""


def test_candidate_query_targets_only_unanalyzed_cves(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "cand.db"))

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0001', 'no cpe yet', ?, '[]', '[]')",
                (today,),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0002', 'analyzed', ?, ?, ?)",
                (today, json.dumps(["nginx:nginx"]), json.dumps(["cpe:2.3:a:nginx"])),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0003', '', ?, '[]', '[]')",  # no description
                (today,),
            )
            await db.commit()
            return await get_cves_for_llm_product_extraction(db, limit=10)
        finally:
            await db.close()

    candidates = asyncio.run(run())
    assert [c["cve_id"] for c in candidates] == ["CVE-2024-0001"]


def test_run_extraction_writes_products_and_negative_caches(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "run.db"))
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    calls: list[str] = []

    async def fake_extract(description: str, api_key: str) -> list[dict]:
        calls.append(description)
        if "widget" in description:
            return [{"vendor": "acme", "product": "widget", "version_range": "< 2.0"}]
        return []  # model could not determine products

    monkeypatch.setattr(pex, "extract_products_via_groq", fake_extract)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            today = date.today().isoformat()
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0001', 'RCE in acme widget', ?, '[]', '[]')",
                (today,),
            )
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0002', 'vague description', ?, '[]', '[]')",
                (today,),
            )
            await db.commit()

            stats = await run_llm_product_extraction(db)
            stats_second = await run_llm_product_extraction(db)  # all cached now

            row = dict(
                (await db.execute_fetchall(
                    "SELECT affected_products, affected_products_source FROM cves "
                    "WHERE cve_id = 'CVE-2024-0001'"
                ))[0]
            )
            cache_rows = await db.execute_fetchall(
                "SELECT cache_key, result FROM feed_cache WHERE cache_key LIKE 'llm_products:%' "
                "ORDER BY cache_key"
            )
            return stats, stats_second, row, [dict(r) for r in cache_rows]
        finally:
            await db.close()

    stats, stats_second, row, cache_rows = asyncio.run(run())
    assert stats == {"candidates": 2, "extracted": 1, "written": 1, "errors": 0}
    assert json.loads(row["affected_products"]) == ["acme:widget"]
    assert row["affected_products_source"] == "llm"

    # Both attempts cached (incl. the empty extraction) → no repeat quota burn.
    assert len(cache_rows) == 2
    cached = json.loads(cache_rows[0]["result"])
    assert cached["written"] is True
    assert cached["products"][0]["version_range"] == "< 2.0"
    assert stats_second == {"candidates": 0, "extracted": 0, "written": 0, "errors": 0}
    assert len(calls) == 2  # one Groq call per CVE, never re-called


def test_run_extraction_errors_are_not_negative_cached(tmp_path, monkeypatch):
    """PR #110 review: transient Groq/network failures must NOT be cached for
    7 days — the CVE stays a candidate and is retried on the next run."""
    monkeypatch.setattr(database, "DB_PATH", str(tmp_path / "errs.db"))
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    attempts = {"n": 0}

    async def flaky_extract(description: str, api_key: str) -> list[dict]:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("simulated timeout")  # first run fails
        return [{"vendor": "acme", "product": "widget", "version_range": ""}]

    monkeypatch.setattr(pex, "extract_products_via_groq", flaky_extract)

    async def run():
        await init_db()
        db = await database.get_db()
        try:
            await db.execute(
                "INSERT INTO cves (cve_id, description, published, affected_products, cpe_matches) "
                "VALUES ('CVE-2024-0001', 'RCE in acme widget', ?, '[]', '[]')",
                (date.today().isoformat(),),
            )
            await db.commit()

            stats_first = await run_llm_product_extraction(db)
            cache_after_error = await db.execute_fetchall(
                "SELECT cache_key FROM feed_cache WHERE cache_key LIKE 'llm_products:%'"
            )
            stats_second = await run_llm_product_extraction(db)  # retry succeeds
            row = dict(
                (await db.execute_fetchall(
                    "SELECT affected_products, affected_products_source FROM cves "
                    "WHERE cve_id = 'CVE-2024-0001'"
                ))[0]
            )
            return stats_first, len(cache_after_error), stats_second, row
        finally:
            await db.close()

    stats_first, cache_count, stats_second, row = asyncio.run(run())
    assert stats_first == {"candidates": 1, "extracted": 0, "written": 0, "errors": 1}
    assert cache_count == 0  # error not negative-cached
    assert stats_second == {"candidates": 1, "extracted": 1, "written": 1, "errors": 0}
    assert json.loads(row["affected_products"]) == ["acme:widget"]
    assert row["affected_products_source"] == "llm"


def test_scheduler_llm_job_noop_when_disabled(monkeypatch):
    monkeypatch.delenv("LLM_PRODUCT_EXTRACTION_ENABLED", raising=False)
    from scheduler import run_llm_extraction_sync

    assert asyncio.run(run_llm_extraction_sync()) is False
