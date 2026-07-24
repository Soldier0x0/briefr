"""delete_user cascade behavior (F2-R audit follow-up: erasure must actually
work, not just be promised in the Privacy Policy).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: Apache-2.0
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from auth.repo import (
    create_session,
    create_user,
    delete_user,
    get_session_by_token,
    get_user_by_id,
)
from database import get_db, init_db
from db.ioc_watchlist import list_ioc_watchlist, upsert_ioc_watchlist_entry
from preferences.repo import upsert_user_stack
from tests.conftest import run_db_test


def test_delete_user_removes_account_and_all_owned_data():
    async def _run():
        await init_db()
        db = await get_db()
        try:
            user = await create_user(db, "erase-me", "correct horse battery staple9")
            await create_session(db, user["id"], "some-refresh-token", "2099-01-01 00:00:00")
            await upsert_user_stack(db, user["id"], "nginx, postgres")
            await upsert_ioc_watchlist_entry(
                db, user["id"], "ip", "203.0.113.1", label="test"
            )
            await db.commit()

            deleted = await delete_user(db, user["id"])
            await db.commit()
            assert deleted is True

            assert await get_user_by_id(db, user["id"]) is None
            assert await get_session_by_token(db, "some-refresh-token") is None
            assert await list_ioc_watchlist(db, user["id"]) == []
        finally:
            await db.close()

    run_db_test(_run())


def test_delete_user_returns_false_for_unknown_id():
    async def _run():
        await init_db()
        db = await get_db()
        try:
            assert await delete_user(db, 999_999) is False
        finally:
            await db.close()

    run_db_test(_run())
