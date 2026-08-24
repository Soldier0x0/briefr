"""Instance-wide CVE watchlist alert policy (one operator).

Quiet defaults notify on KEV, significant EPSS jumps, PoC, and withdrawn
records. Patch-available is off until the operator opts in. Enabling every
trigger is treated as "all activity" and forces digest delivery so the
webhook/inbox is not a per-field firehose.
"""

from __future__ import annotations

import json
from typing import Any

from db.app_settings import get_app_setting, set_app_setting
from db.types import DbConnection

TRIGGER_KEV = "kev"
TRIGGER_EPSS = "epss"
TRIGGER_POC = "poc"
TRIGGER_PATCH = "patch"
TRIGGER_WITHDRAWN = "withdrawn"

TRIGGERS = (
    TRIGGER_KEV,
    TRIGGER_EPSS,
    TRIGGER_POC,
    TRIGGER_PATCH,
    TRIGGER_WITHDRAWN,
)

DEFAULT_TRIGGERS: dict[str, bool] = {
    TRIGGER_KEV: True,
    TRIGGER_EPSS: True,
    TRIGGER_POC: True,
    TRIGGER_PATCH: False,
    TRIGGER_WITHDRAWN: True,
}

POLICY_SETTING_KEY = "watchlist.policy"

_DELIVERY_IMMEDIATE = "immediate"
_DELIVERY_DIGEST = "digest"


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "on"}:
            return True
        if lowered in {"0", "false", "no", "off"}:
            return False
    return default


def _sanitize_triggers(raw: Any) -> dict[str, bool]:
    incoming = raw if isinstance(raw, dict) else {}
    out = dict(DEFAULT_TRIGGERS)
    for key in TRIGGERS:
        if key in incoming:
            out[key] = _as_bool(incoming[key], DEFAULT_TRIGGERS[key])
    return out


def _sanitize_overrides(raw: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for cve_id, spec in raw.items():
        key = str(cve_id or "").strip().upper()
        if not key.startswith("CVE-"):
            continue
        if not isinstance(spec, dict):
            continue
        triggers = spec.get("triggers")
        if not isinstance(triggers, dict):
            continue
        merged = _sanitize_triggers(triggers)
        # Overrides only store explicit trigger keys so missing ones inherit.
        explicit = {
            name: merged[name]
            for name in TRIGGERS
            if name in triggers
        }
        if explicit:
            out[key] = {"triggers": explicit}
    return out


def sanitize_policy(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    triggers = _sanitize_triggers(data.get("triggers"))
    delivery = str(data.get("delivery") or _DELIVERY_IMMEDIATE).strip().lower()
    if delivery not in {_DELIVERY_IMMEDIATE, _DELIVERY_DIGEST}:
        delivery = _DELIVERY_IMMEDIATE
    return {
        "triggers": triggers,
        "delivery": delivery,
        "overrides": _sanitize_overrides(data.get("overrides")),
    }


def _all_triggers_enabled(policy: dict[str, Any]) -> bool:
    triggers = policy.get("triggers") or {}
    return all(bool(triggers.get(name)) for name in TRIGGERS)


def delivery_mode(policy: dict[str, Any]) -> str:
    if policy.get("delivery") == _DELIVERY_DIGEST or _all_triggers_enabled(policy):
        return _DELIVERY_DIGEST
    return _DELIVERY_IMMEDIATE


def trigger_enabled(policy: dict[str, Any], cve_id: str, trigger: str) -> bool:
    if trigger not in TRIGGERS:
        return False
    key = (cve_id or "").upper()
    override = (policy.get("overrides") or {}).get(key) or {}
    override_triggers = override.get("triggers") or {}
    if trigger in override_triggers:
        return bool(override_triggers[trigger])
    return bool((policy.get("triggers") or {}).get(trigger, DEFAULT_TRIGGERS[trigger]))


CHANGE_FIELD_TO_TRIGGER = {
    "epss_score": TRIGGER_EPSS,
    "has_poc": TRIGGER_POC,
    "patch_available": TRIGGER_PATCH,
    "is_kev": TRIGGER_KEV,
}


async def load_policy(db: DbConnection) -> dict[str, Any]:
    raw = await get_app_setting(db, POLICY_SETTING_KEY)
    if not raw:
        return sanitize_policy(None)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return sanitize_policy(None)
    return sanitize_policy(data)


async def save_policy(db: DbConnection, raw: Any) -> dict[str, Any]:
    policy = sanitize_policy(raw)
    await set_app_setting(db, POLICY_SETTING_KEY, json.dumps(policy, sort_keys=True))
    return policy
