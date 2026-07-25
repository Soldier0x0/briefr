"""Failure payload capture for AI operations (Program E Task 1)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.conftest import run_db_test

from ai import llm_router as router
from ai.llm_router import chat_completion_task
from db.config import is_postgres
from database import count_ai_operations, get_db, init_db, list_ai_operations


def test_failure_payload_not_stored_when_flag_off(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "ai_ops_payloads_off.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("AI_OPERATIONS_STORE_FAILURE_PAYLOADS", "0")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    async def fake_call(_step, **_kwargs):
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        await init_db()
        result = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hello"}],
        )
        db = await get_db()
        try:
            op_count = await count_ai_operations(db)
            rows = await list_ai_operations(db, limit=10)
            payload_rows = await db.execute_fetchall(
                "SELECT operation_id FROM ai_operation_payloads",
            )
        finally:
            await db.close()
        return result, op_count, rows, payload_rows

    result, op_count, rows, payload_rows = run_db_test(run())
    assert result is None
    assert op_count == 1
    assert rows[0]["error_class"] == "empty"
    assert payload_rows == []


def test_failure_payload_stored_when_flag_on(tmp_path, monkeypatch):
    if not is_postgres():
        db_path = tmp_path / "ai_ops_payloads_on.db"
        monkeypatch.setenv("DB_PATH", str(db_path))
        monkeypatch.setattr("database.DB_PATH", str(db_path))
    monkeypatch.setenv("AI_OPERATIONS_RECORD", "1")
    monkeypatch.setenv("AI_OPERATIONS_STORE_FAILURE_PAYLOADS", "1")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")

    async def fake_call(_step, **_kwargs):
        return ""

    monkeypatch.setattr(router, "_call_provider", fake_call)

    async def run():
        await init_db()
        result = await chat_completion_task(
            "product_extraction",
            messages=[{"role": "user", "content": "hello"}],
        )
        db = await get_db()
        try:
            op_rows = await list_ai_operations(db, limit=10)
            payload_rows = await db.execute_fetchall(
                """
                SELECT operation_id, messages_json, task_class, provider, model
                FROM ai_operation_payloads
                """,
            )
        finally:
            await db.close()
        return result, op_rows, payload_rows

    result, op_rows, payload_rows = run_db_test(run())
    assert result is None
    assert op_rows[0]["error_class"] == "empty"
    assert len(payload_rows) == 1
    payload = dict(payload_rows[0])
    assert payload["operation_id"] == op_rows[0]["operation_id"]
    assert payload["task_class"] == "product_extraction"
    assert payload["provider"] == "groq"
    assert "hello" in payload["messages_json"]
