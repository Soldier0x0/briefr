"""Admin intel snapshot status and import trigger."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, HTTPException, Request

from database import get_db
from dependencies import audit
from destructive_actions import require_confirm
from http_errors import admin_error_detail
from path_safety import PathValidationError, resolve_intel_snapshot_bundle

from .router import router

_STATUS_KEYS = (
    "intel_snapshot.last_import_at",
    "intel_snapshot.last_import_mode",
    "intel_snapshot.last_manifest_exported_at",
)


@router.get("/intel-snapshot/status")
async def get_intel_snapshot_status(request: Request) -> dict[str, Any]:
    from db.sync_state import get_sync_state_value

    db = await get_db()
    try:
        values: dict[str, str | None] = {}
        for key in _STATUS_KEYS:
            values[key] = await get_sync_state_value(db, key)
    finally:
        await db.close()

    return {
        "last_import_at": values.get("intel_snapshot.last_import_at"),
        "last_import_mode": values.get("intel_snapshot.last_import_mode"),
        "last_manifest_exported_at": values.get("intel_snapshot.last_manifest_exported_at"),
        "docs": {
            "publish": "docs/INTEL_PUBLISH.md",
            "import_cli": "scripts/import_intel_snapshot.py --mode merge|bootstrap",
        },
    }


def _repo_scripts_path() -> Path:
    repo = Path(__file__).resolve().parents[3]
    return repo / "scripts"


def _run_import(path: str, mode: str, database_url: str, replace_intel: bool) -> None:
    scripts_dir = str(_repo_scripts_path())
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    from import_intel_snapshot import import_snapshot

    import_snapshot(
        Path(path),
        database_url,
        mode=mode,
        replace_intel=replace_intel,
        skip_migrations=False,
    )


@router.post("/intel-snapshot/import")
async def start_intel_snapshot_import(
    request: Request,
    background_tasks: BackgroundTasks,
    body: dict,
):
    from db.config import resolve_database_url, is_postgres

    confirm_text = str(body.get("confirm_text", "")).strip()
    try:
        require_confirm("intel_snapshot.import", confirm_text)
    except ValueError as exc:
        raise HTTPException(400, admin_error_detail(exc)) from exc
    mode = str(body.get("mode", "merge")).strip().lower()
    if mode not in {"bootstrap", "merge"}:
        raise HTTPException(400, "mode must be bootstrap or merge")
    input_path = str(body.get("input_path", "")).strip()
    if not input_path:
        raise HTTPException(400, "input_path is required (server-local bundle path)")
    try:
        path = resolve_intel_snapshot_bundle(input_path)
    except PathValidationError as exc:
        raise HTTPException(400, str(exc)) from exc

    database_url = str(body.get("database_url") or resolve_database_url()).strip()
    if not is_postgres(database_url):
        raise HTTPException(400, "intel snapshot import requires PostgreSQL")

    replace_intel = bool(body.get("replace_intel", False))
    if mode == "bootstrap" and body.get("replace_intel") is None:
        replace_intel = True

    await audit(request, "intel_snapshot.import.start", f"{mode}:{path.name}")
    background_tasks.add_task(
        _run_import,
        str(path),
        mode,
        database_url,
        replace_intel,
    )
    return {
        "ok": True,
        "message": f"Import started ({mode}) — poll GET /api/admin/intel-snapshot/status",
    }
