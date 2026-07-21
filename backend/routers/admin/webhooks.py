"""Admin dashboard API — webhook test and destinations CRUD.

Part of the `routers.admin` package (F1.2 / W7 split). Aggregate router is
re-exported from `routers.admin`.

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""

from __future__ import annotations

from fastapi import HTTPException, Query, Request

from database import get_db
from dependencies import audit
from destructive_actions import require_confirm

from .router import router

@router.post("/config/webhook-test")
async def test_webhook(request: Request, body: dict):
    from webhooks.destinations import load_destinations
    from webhooks.sender import send_test_message

    destination_id = body.get("destination_id") or body.get("channel", "")
    destinations = await load_destinations()
    valid_ids = {dest.id for dest in destinations}
    if destination_id not in valid_ids:
        raise HTTPException(
            400,
            f"destination_id must be one of: {', '.join(sorted(valid_ids)) or 'none configured'}",
        )

    result = await send_test_message(destination_id, "BRIEFR admin webhook test")
    await audit(request, f"webhook.test.{destination_id}", destination_id)
    return result


@router.get("/webhooks/destinations")
async def get_webhook_destinations(request: Request):
    from webhooks.destinations import destination_to_api_dict, load_destinations

    destinations = await load_destinations()
    return {"destinations": [destination_to_api_dict(dest) for dest in destinations]}


@router.post("/webhooks/destinations")
async def create_webhook_destination(request: Request, body: dict):
    from database import count_webhook_destinations_by_kind, create_webhook_destination as db_create
    from webhooks.destinations import (
        ALL_EVENT_TYPES,
        MAX_DESTINATIONS_PER_KIND,
        generate_destination_id,
        load_destinations,
        parse_event_types,
        validate_destination_config,
        validate_destination_id,
        validate_destination_kind,
        destination_to_api_dict,
    )

    kind = body.get("kind")
    if not isinstance(kind, str):
        raise HTTPException(400, "kind is required")
    try:
        validate_destination_kind(kind)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    raw_id = body.get("id")
    if raw_id is None or raw_id == "":
        destination_id = generate_destination_id(kind)
    else:
        if not isinstance(raw_id, str):
            raise HTTPException(400, "id must be a string")
        destination_id = raw_id.strip()
        try:
            validate_destination_id(destination_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    label = body.get("label", "")
    if not isinstance(label, str):
        raise HTTPException(400, "label must be a string")
    label = label.strip() or destination_id

    enabled = body.get("enabled", True)
    if not isinstance(enabled, bool):
        raise HTTPException(400, "enabled must be a boolean")

    event_types = body.get("event_types")
    if event_types is None:
        event_types = list(ALL_EVENT_TYPES)
    elif not isinstance(event_types, list):
        raise HTTPException(400, "event_types must be an array")
    else:
        normalized = parse_event_types(event_types)
        unknown = [item for item in normalized if item not in ALL_EVENT_TYPES]
        if unknown:
            raise HTTPException(400, f"unknown event_types: {', '.join(unknown)}")
        event_types = normalized

    config_body = body.get("config")
    if not isinstance(config_body, dict):
        raise HTTPException(400, "config is required")
    try:
        config = validate_destination_config(kind, config_body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    if any(dest.id == destination_id for dest in await load_destinations()):
        raise HTTPException(409, f"Destination '{destination_id}' already exists")

    db = await get_db()
    try:
        count = await count_webhook_destinations_by_kind(db, kind)
        if count >= MAX_DESTINATIONS_PER_KIND:
            raise HTTPException(
                400,
                f"maximum {MAX_DESTINATIONS_PER_KIND} destinations per kind reached for {kind}",
            )
        await db_create(
            db,
            destination_id=destination_id,
            kind=kind,
            label=label,
            enabled=enabled,
            event_types=event_types,
            config=config,
        )
        await db.commit()
    finally:
        await db.close()

    await audit(request, f"webhook.destination.create.{destination_id}", destination_id)
    dest = next(
        (item for item in await load_destinations() if item.id == destination_id),
        None,
    )
    if dest is None:
        raise HTTPException(500, "destination created but not found on reload")
    return {"ok": True, "destination": destination_to_api_dict(dest)}


@router.delete("/webhooks/destinations/{destination_id}")
async def delete_webhook_destination_route(
    request: Request,
    destination_id: str,
    confirm_text: str = Query(default=""),
):
    from database import delete_webhook_destination as db_delete, get_webhook_destination_source
    from webhooks.destinations import RESERVED_ENV_IDS, load_destinations, sync_env_destinations_to_db

    if destination_id in RESERVED_ENV_IDS:
        raise HTTPException(
            400,
            "env bootstrap destinations cannot be deleted; disable them instead",
        )

    await sync_env_destinations_to_db()
    if not any(dest.id == destination_id for dest in await load_destinations()):
        raise HTTPException(404, f"Destination '{destination_id}' not found")

    db = await get_db()
    try:
        source = await get_webhook_destination_source(db, destination_id)
        if source is None:
            raise HTTPException(404, f"Destination '{destination_id}' not found")
        if source != "db":
            raise HTTPException(
                400,
                "only database-backed destinations can be deleted; disable env destinations instead",
            )
        confirm_text = confirm_text or ""
        try:
            require_confirm("webhook.destination.delete", confirm_text)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        deleted = await db_delete(db, destination_id)
        if not deleted:
            raise HTTPException(404, f"Destination '{destination_id}' not found")
        await db.commit()
    finally:
        await db.close()

    await audit(request, f"webhook.destination.delete.{destination_id}", destination_id)
    return {"ok": True, "destination_id": destination_id}


@router.patch("/webhooks/destinations/{destination_id}")
async def patch_webhook_destination(request: Request, destination_id: str, body: dict):
    from webhooks.destinations import (
        ALL_EVENT_TYPES,
        destination_to_api_dict,
        load_destinations,
        parse_event_types,
        sync_env_destinations_to_db,
        validate_destination_config,
    )

    enabled = body.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise HTTPException(400, "enabled must be a boolean")

    event_types = body.get("event_types")
    if event_types is not None:
        if not isinstance(event_types, list):
            raise HTTPException(400, "event_types must be an array")
        normalized = parse_event_types(event_types)
        unknown = [item for item in normalized if item not in ALL_EVENT_TYPES]
        if unknown:
            raise HTTPException(400, f"unknown event_types: {', '.join(unknown)}")
        event_types = normalized

    label = body.get("label")
    if label is not None and not isinstance(label, str):
        raise HTTPException(400, "label must be a string")

    config_body = body.get("config")
    if config_body is not None and not isinstance(config_body, dict):
        raise HTTPException(400, "config must be an object")

    if enabled is None and event_types is None and label is None and config_body is None:
        raise HTTPException(400, "no fields to update")

    await sync_env_destinations_to_db()
    destinations = await load_destinations()
    dest = next((item for item in destinations if item.id == destination_id), None)
    if dest is None:
        raise HTTPException(404, f"Destination '{destination_id}' not found")

    config_update = None
    if config_body is not None:
        if dest.source != "db":
            raise HTTPException(
                400,
                "config can only be updated for database-backed destinations",
            )
        try:
            config_update = validate_destination_config(dest.kind, config_body)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    db = await get_db()
    try:
        from database import update_webhook_destination

        updated = await update_webhook_destination(
            db,
            destination_id,
            enabled=enabled,
            event_types=event_types,
            label=label.strip() if isinstance(label, str) else None,
            config=config_update,
        )
        if not updated:
            raise HTTPException(404, f"Destination '{destination_id}' not found")
        await db.commit()
    finally:
        await db.close()

    await audit(request, f"webhook.destination.update.{destination_id}", destination_id)
    dest = next((item for item in await load_destinations() if item.id == destination_id), None)
    if dest is None:
        raise HTTPException(404, f"Destination '{destination_id}' not found")
    return {"ok": True, "destination": destination_to_api_dict(dest)}

