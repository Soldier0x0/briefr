# Stack, Watchlist, and Alert Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make My Stack a per-user product inventory, make Watchlist a per-user pin + product-subscription list, and let each user choose *which* stack/watchlist events fire — with one versioned webhook envelope so Discord/Telegram/generic destinations stay readable instead of spammy.

**Architecture:** Split **inventory** (`user_assets`) from **subscriptions** (`user_cve_pins`, per-asset alert overrides) from **policy** (`user_alert_policies`). A scheduler job scores *recently changed* CVEs with existing `matching.cpe.score_cve_for_assets` (never description `LIKE` for alerts). Candidates are filtered by per-user policy, then either dispatched immediately (KEV / PoC / pin lifecycle) or batched into an hourly digest (new published matches). Destinations still live at instance level; user policy decides *generation*, destination `event_types` decide *delivery*.

**Tech Stack:** FastAPI, Alembic (revision after `043_ioc_value_digest`), Postgres-native SQL with `_SQLITE` / `_PG` twins, React/Vite, Radix Checkbox/Select/Switch, existing `webhooks/engine.py` + SSRF client. No new HTTP libraries.

## Why the current code is wrong

| Surface | Code today | Problem |
|---------|------------|---------|
| My Stack terms | `_stack_match_clause` does `LIKE %term%` on `description` / `affected_products` | `python` matches every CVE that mentions the language; not inventory |
| Stack for alerts | `get_effective_stack_terms()` = env **or last-updated user** | Alerts are not “your” stack; they are whoever saved last |
| Asset wizard | Session profile + optional `POST /api/cves/match` full-table scan | Version matching exists but is **not** used by KEV-on-stack webhooks |
| CVE watchlist | `watchlist.cve_id` PK, no `user_id` | Pins are instance-global |
| Watchlist alerts | Pinned CVE KEV / EPSS / PoC only | No product/version watches; no severity picker |
| Webhooks | `{"text", "event_type", "source": "briefr", "dedupe_key?"}` | Unstructured prose; Discord and generic share the same blob |
| Defaults | Any KEV that substring-matches stack terms | Easy to spam a channel |

This plan does **not** build a CMDB, scanner, or per-user webhook URLs. IOC watchlist stays as-is (`ioc_watchlist` is already per-user).

## Target product model

**My Stack** = products I run (vendor, product, optional version, optional CPE). Used for:

- Feed chip `my_stack_only` (product/CPE match; keyword `LIKE` only if the row’s `match_mode` is `keyword`)
- Environment relevance (existing profile JSON can stay)
- Optional **stack alerts** if the user turns them on

**Watchlist** = things I am monitoring:

- **CVE pins** (today’s pin, but keyed by `user_id`)
- **Product watches** — either a stack row with alerts enabled, or a watch-only product not in inventory

A product can be in stack without alerts. Enabling “alert me” on a stack row writes the override; it does not duplicate the product.

**Alert policy (per user)** answers three questions in the UI, in this order:

1. **Sources:** Stack matches / Watchlist (pins + watched products) / both / neither (off)
2. **Triggers:** which *kinds* of change (new published, KEV, EPSS jump, PoC, CVSS/severity increase)
3. **Severity floor:** CRITICAL only vs HIGH+ vs all, plus “include UNKNOWN”
4. **Cadence:** immediate vs hourly digest (defaults below)

Per-product overrides can raise the floor or disable triggers; they cannot enable a source the user turned off globally.

## Anti-spam defaults (ship these; do not make them “all on”)

On first policy row create:

```text
sources.stack            = false
sources.watchlist        = true     # preserves today’s pin alerts for migrated pins
triggers.new_published   = false    # the spammy one — opt-in
triggers.kev             = true
triggers.epss_jump       = true     # pins only unless product override
triggers.poc             = true
triggers.severity_up     = false
min_severity             = CRITICAL  # for stack/product matches
include_unknown          = false
epss_min_delta           = 0.05     # keep WATCHLIST_EPSS_MIN_DELTA
cadence.kev              = immediate
cadence.poc              = immediate
cadence.epss_jump        = immediate
cadence.new_published    = digest_hourly
digest_max_items         = 15
digest_hour_utc          = 0–23 local via user timezone already on preferences
```

Migrated `stack_terms` become `user_assets` with `match_mode=keyword` and **`alert_enabled=false`**. Existing global pins copy to every active user (same visibility as today) with watchlist source on. No new webhook event types fire until the user saves policy (migrated pins keep `watchlist_alert` KEV/EPSS/PoC only).

Hard caps (scheduler):

- Score at most 500 candidate CVE IDs per tick (recent changes + newly KEV + newly published in window)
- Never call `match_cves_for_assets` full-table scan from the alert job
- One digest message per destination per user per hour (not one Discord message per CVE)

## Webhook envelope (`briefr.alert/v1`)

Generic HTTPS destinations receive this JSON. Discord/Telegram receive `text` only (formatted from the same object).

```json
{
  "schema": "briefr.alert/v1",
  "id": "01J…",
  "event_type": "watchlist_alert",
  "occurred_at": "2026-08-24T08:00:00Z",
  "source": "watchlist",
  "trigger": "kev",
  "severity": "CRITICAL",
  "digest": false,
  "item_count": 1,
  "cve": {
    "id": "CVE-2026-12345",
    "severity": "CRITICAL",
    "cvss": 9.8,
    "epss": 0.81,
    "kev": true,
    "has_poc": false,
    "summary": "…"
  },
  "match": {
    "user_id": 1,
    "kind": "asset",
    "vendor": "f5",
    "product": "nginx",
    "version": "1.24.0",
    "mode": "cpe",
    "score": 100
  },
  "items": [],
  "text": "BRIEFR watchlist · KEV · CVE-2026-12345 · nginx 1.24.0 · CRITICAL",
  "dedupe_key": "u1:watchlist:kev:CVE-2026-12345"
}
```

Digest: `digest: true`, `cve` null, `items` array of `{cve, match, trigger, severity}` truncated to `digest_max_items` with `item_count` = full count.

**Event types (destination subscriptions):**

| `event_type` | Meaning | Alias |
|--------------|---------|--------|
| `stack_match` | **New** — stack/product match (usually digest) | none |
| `watchlist_alert` | Pin or watched-product lifecycle | keep |
| `kev_alert` | Keep for **operator** KEV-on-stack until Task 8 cuts over; then `kev_alert` is an alias that destinations still accept, implemented as `stack_match` + trigger `kev` | `kev_stack` already aliases this |

Do not invent `stack_match_alert` vs `stack_match`. One id.

`dispatch_event` gains optional `envelope: dict`. If present, generic POST uses the envelope; Discord/Telegram still POST `content`/`text` = `envelope["text"]`. If absent, keep today’s `{text, event_type, source, dedupe_key}` for backup/health/IOC.

## File map

| File | Responsibility |
|------|----------------|
| Create: `backend/alerts/types.py` | Constants, defaults, TypedDicts |
| Create: `backend/alerts/policy.py` | Merge global policy + asset override; `passes_policy()` |
| Create: `backend/alerts/envelope.py` | Build v1 envelope + Discord/Telegram `text` |
| Create: `backend/alerts/match.py` | Score candidate CVEs against one user’s assets |
| Create: `backend/alerts/evaluate.py` | Load users, filter, split immediate vs digest |
| Create: `backend/db/user_assets.py` | CRUD assets + derived `stack_terms` |
| Create: `backend/db/user_cve_pins.py` | Per-user pins |
| Create: `backend/db/user_alert_policies.py` | Policy JSON |
| Create: `backend/alembic/versions/044_user_assets_alerts.py` | Tables + backfill |
| Modify: `backend/db/init.py` | SQLite parity CREATE TABLE |
| Modify: `backend/db/schema_inventory.py` | Add three APP tables |
| Modify: `backend/routers/me.py` | `/assets`, `/alert-policy` |
| Modify: `backend/routers/watchlist.py` | Require user; use `user_cve_pins` |
| Modify: `backend/webhooks/destinations.py` | `EVENT_STACK_MATCH` |
| Modify: `backend/webhooks/engine.py` | Envelope dispatch |
| Modify: `backend/webhooks/ssrf.py` | `webhook_json_payload` optional envelope |
| Modify: `backend/webhooks/alerts.py` | Call evaluate; stop `get_effective_stack_terms` for user alerts |
| Modify: `backend/scheduler.py` | Hourly `user_alert_evaluate` job |
| Modify: `backend/routers/admin/jobs.py` | Job map id |
| Modify: `backend/notifications/emit.py` | Emit to **the matching user_id**, not all analysts |
| Create: `frontend/src/utils/alertPolicy.js` | Client defaults + labels |
| Create: `frontend/src/components/AlertPolicyPanel.jsx` | Source / trigger / severity / cadence |
| Modify: `frontend/src/components/AssetProfileManage.jsx` | Per-product alert row |
| Modify: `frontend/src/hooks/useWatchlist.js` | Auth-scoped pins |
| Modify: `frontend/src/pages/admin/WebhooksPage.jsx` | `stack_match` option |
| Modify: `docs/PRODUCT_STATUS.md`, `docs/API_REFERENCE.md` | Shipped contract |

**Do not** reuse `_stack_match_clause` for alert generation. Keep it only for: keyword `match_mode` feed filter, wallboard when `BRIEFR_STACK_TERMS` is set, and Forge scope until those call sites are switched to `user_assets` (Task 10).

**Do not** put alert evaluation on `GET /api/cves` or `POST /api/cves/match`.

---

## Global Constraints

- Postgres-native DDL in Alembic; SQLite twins in `db/init.py` so default pytest stays green.
- Forward-only migration; revision id `044_user_assets_alerts`, `down_revision = "043_ioc_value_digest"`.
- Scheduler `id=` string must match `routers/admin/jobs.py` `_JOB_RUN_MAP`.
- Heavy matching only in scheduler / existing match POST — never on list endpoints.
- Secrets never in log strings.
- Dark terminal UI; Radix Checkbox/Select/Switch; semantic tokens only.
- Runtime/API change → `PRODUCT_STATUS.md` + `API_REFERENCE.md` in the same PR as the code.
- Merge gate: `./scripts/verify-local.sh`.
- `BRIEFR_STACK_TERMS` remains **wallboard/operator override only**, never a user’s alert inventory.
- Alert `LIKE` matching is forbidden except `match_mode=keyword` assets the user explicitly kept.

---

### Task 1: Policy types and `passes_policy` (pure)

**Files:**
- Create: `backend/alerts/__init__.py`
- Create: `backend/alerts/types.py`
- Create: `backend/alerts/policy.py`
- Test: `backend/tests/test_alert_policy.py`

**Interfaces:**
- Consumes: nothing from later tasks
- Produces: `DEFAULT_ALERT_POLICY: dict`, `SEVERITIES` ordered tuple, `severity_rank(s) -> int`, `passes_policy(policy, *, source, trigger, cve_severity, asset_override=None) -> bool`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_alert_policy.py
from alerts.policy import DEFAULT_ALERT_POLICY, passes_policy


def test_defaults_block_stack_and_new_published():
    p = dict(DEFAULT_ALERT_POLICY)
    assert passes_policy(p, source="stack", trigger="kev", cve_severity="CRITICAL") is False
    assert passes_policy(p, source="watchlist", trigger="kev", cve_severity="CRITICAL") is True
    assert passes_policy(p, source="watchlist", trigger="new_published", cve_severity="CRITICAL") is False


def test_min_severity_floor():
    p = {
        **DEFAULT_ALERT_POLICY,
        "sources": {"stack": True, "watchlist": True},
        "min_severity": "CRITICAL",
        "triggers": {**DEFAULT_ALERT_POLICY["triggers"], "kev": True},
    }
    assert passes_policy(p, source="stack", trigger="kev", cve_severity="HIGH") is False
    assert passes_policy(p, source="stack", trigger="kev", cve_severity="CRITICAL") is True
    assert passes_policy(p, source="stack", trigger="kev", cve_severity="UNKNOWN") is False


def test_asset_override_cannot_enable_disabled_source():
    p = {**DEFAULT_ALERT_POLICY, "sources": {"stack": False, "watchlist": False}}
    override = {"alert_enabled": True, "min_severity": "LOW"}
    assert passes_policy(
        p, source="stack", trigger="kev", cve_severity="CRITICAL", asset_override=override
    ) is False


def test_asset_override_raises_floor():
    p = {
        **DEFAULT_ALERT_POLICY,
        "sources": {"stack": True, "watchlist": False},
        "min_severity": "HIGH",
        "triggers": {**DEFAULT_ALERT_POLICY["triggers"], "kev": True, "new_published": False},
    }
    override = {"alert_enabled": True, "min_severity": "CRITICAL"}
    assert passes_policy(p, source="stack", trigger="kev", cve_severity="HIGH", asset_override=override) is False
    assert passes_policy(p, source="stack", trigger="kev", cve_severity="CRITICAL", asset_override=override) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_alert_policy.py -q`

Expected: FAIL `ModuleNotFoundError: alerts`

- [ ] **Step 3: Write minimal implementation**

`backend/alerts/types.py`:

```python
SCHEMA = "briefr.alert/v1"
SOURCES = ("stack", "watchlist")
TRIGGERS = ("new_published", "kev", "epss_jump", "poc", "severity_up")
CADENCES = ("immediate", "digest_hourly")
SEVERITIES = ("CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN")
MATCH_MODES = ("cpe", "keyword")
EVENT_STACK_MATCH = "stack_match"
EVENT_WATCHLIST_ALERT = "watchlist_alert"

DEFAULT_ALERT_POLICY = {
    "sources": {"stack": False, "watchlist": True},
    "triggers": {
        "new_published": False,
        "kev": True,
        "epss_jump": True,
        "poc": True,
        "severity_up": False,
    },
    "min_severity": "CRITICAL",
    "include_unknown": False,
    "epss_min_delta": 0.05,
    "cadence": {
        "new_published": "digest_hourly",
        "kev": "immediate",
        "epss_jump": "immediate",
        "poc": "immediate",
        "severity_up": "digest_hourly",
    },
    "digest_max_items": 15,
}
```

`backend/alerts/policy.py`:

```python
from copy import deepcopy
from alerts.types import DEFAULT_ALERT_POLICY, SEVERITIES

_RANK = {name: i for i, name in enumerate(SEVERITIES)}  # CRITICAL=0 … UNKNOWN=4


def severity_rank(value: str | None) -> int:
    key = (value or "UNKNOWN").strip().upper()
    return _RANK.get(key, _RANK["UNKNOWN"])


def passes_policy(
    policy: dict,
    *,
    source: str,
    trigger: str,
    cve_severity: str | None,
    asset_override: dict | None = None,
) -> bool:
    p = policy or DEFAULT_ALERT_POLICY
    if not p.get("sources", {}).get(source):
        return False
    if not p.get("triggers", {}).get(trigger):
        return False
    if asset_override is not None and not asset_override.get("alert_enabled", True):
        return False
    floor = (asset_override or {}).get("min_severity") or p.get("min_severity") or "CRITICAL"
    sev = (cve_severity or "UNKNOWN").strip().upper()
    if sev == "UNKNOWN":
        return bool(p.get("include_unknown"))
    if source == "watchlist" and trigger in {"kev", "epss_jump", "poc"} and (asset_override or {}).get("kind") == "cve_pin":
        return True  # pin lifecycle is not severity-gated (today’s behavior)
    return severity_rank(sev) <= severity_rank(floor)
```

Empty `backend/alerts/__init__.py`.

Pin lifecycle: CVE pins ignore the global min_severity so a MEDIUM pinned CVE still alerts on KEV. Product watches **are** severity-gated.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_alert_policy.py -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/alerts backend/tests/test_alert_policy.py
git commit -m "feat(alerts): add policy defaults and passes_policy"
```

---

### Task 2: Envelope builder

**Files:**
- Create: `backend/alerts/envelope.py`
- Test: `backend/tests/test_alert_envelope.py`

**Interfaces:**
- Consumes: `SCHEMA` from `alerts.types`
- Produces: `build_envelope(...) -> dict`, `format_text(envelope) -> str`

- [ ] **Step 1: Write the failing test**

```python
from alerts.envelope import build_envelope, format_text


def test_single_item_envelope_has_stable_keys():
    env = build_envelope(
        event_type="watchlist_alert",
        source="watchlist",
        trigger="kev",
        severity="CRITICAL",
        user_id=1,
        cve={"id": "CVE-2026-1", "severity": "CRITICAL", "summary": "x" * 400, "kev": True},
        match={"kind": "cve_pin", "product": None},
        digest=False,
    )
    assert env["schema"] == "briefr.alert/v1"
    assert env["event_type"] == "watchlist_alert"
    assert env["digest"] is False
    assert env["item_count"] == 1
    assert env["cve"]["id"] == "CVE-2026-1"
    assert len(env["cve"]["summary"]) <= 280
    assert env["dedupe_key"].startswith("u1:watchlist:kev:CVE-2026-1")
    text = format_text(env)
    assert "CVE-2026-1" in text
    assert "KEV" in text.upper() or "kev" in text.lower()


def test_digest_envelope_truncates_items():
    items = [
        {"cve": {"id": f"CVE-2026-{i}", "severity": "CRITICAL"}, "match": {"product": "nginx"}, "trigger": "new_published", "severity": "CRITICAL"}
        for i in range(20)
    ]
    env = build_envelope(
        event_type="stack_match",
        source="stack",
        trigger="new_published",
        severity="CRITICAL",
        user_id=2,
        items=items,
        digest=True,
        digest_max_items=15,
    )
    assert env["digest"] is True
    assert env["item_count"] == 20
    assert len(env["items"]) == 15
    assert "20" in env["text"]
```

- [ ] **Step 2: Run test — expect FAIL import**

Run: `cd backend && pytest tests/test_alert_envelope.py -q`

- [ ] **Step 3: Implement**

```python
# backend/alerts/envelope.py
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from alerts.types import SCHEMA

_SUMMARY_MAX = 280


def _clip(text: str, n: int = _SUMMARY_MAX) -> str:
    t = (text or "").strip()
    return t if len(t) <= n else t[: n - 1] + "…"


def _cve_brief(cve: dict[str, Any] | None) -> dict[str, Any] | None:
    if not cve:
        return None
    return {
        "id": cve.get("id") or cve.get("cve_id"),
        "severity": (cve.get("severity") or "UNKNOWN").upper(),
        "cvss": cve.get("cvss"),
        "epss": cve.get("epss"),
        "kev": bool(cve.get("kev")),
        "has_poc": bool(cve.get("has_poc")),
        "summary": _clip(cve.get("summary") or cve.get("description") or ""),
    }


def format_text(envelope: dict[str, Any]) -> str:
    if envelope.get("digest"):
        n = envelope.get("item_count") or len(envelope.get("items") or [])
        src = envelope.get("source")
        shown = envelope.get("items") or []
        lines = [f"BRIEFR {src} digest · {n} matching CVE(s)"]
        for item in shown:
            cve = item.get("cve") or {}
            match = item.get("match") or {}
            prod = match.get("product") or "—"
            lines.append(f"• {cve.get('id')} · {cve.get('severity')} · {prod}")
        hidden = n - len(shown)
        if hidden > 0:
            lines.append(f"… +{hidden} more in BRIEFR")
        return "\n".join(lines)
    cve = envelope.get("cve") or {}
    match = envelope.get("match") or {}
    trigger = (envelope.get("trigger") or "").replace("_", " ")
    prod = match.get("product")
    ver = match.get("version")
    asset = " ".join(x for x in (prod, ver) if x) or (match.get("kind") or "")
    return (
        f"BRIEFR {envelope.get('source')} · {trigger} · {cve.get('id')} · "
        f"{cve.get('severity')}"
        + (f" · {asset}" if asset else "")
    )


def build_envelope(
    *,
    event_type: str,
    source: str,
    trigger: str,
    severity: str,
    user_id: int,
    cve: dict | None = None,
    match: dict | None = None,
    items: list[dict] | None = None,
    digest: bool = False,
    digest_max_items: int = 15,
    occurred_at: str | None = None,
) -> dict[str, Any]:
    brief = _cve_brief(cve)
    capped = (items or [])[:digest_max_items]
    item_count = len(items) if digest else 1
    cve_id = (brief or {}).get("id") or ""
    dedupe = f"u{user_id}:{source}:{trigger}:{cve_id or 'digest'}"
    env = {
        "schema": SCHEMA,
        "event_type": event_type,
        "occurred_at": occurred_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "trigger": trigger,
        "severity": (severity or "UNKNOWN").upper(),
        "digest": digest,
        "item_count": item_count,
        "cve": None if digest else brief,
        "match": None if digest else (match or {}),
        "items": capped if digest else [],
        "dedupe_key": dedupe,
    }
    env["text"] = format_text(env)
    return env
```

Skip `id` ULID unless already used in-repo; `dedupe_key` is the idempotency handle.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit** `feat(alerts): add briefr.alert/v1 envelope builder`

---

### Task 3: Schema — `user_assets`, `user_cve_pins`, `user_alert_policies`

**Files:**
- Create: `backend/alembic/versions/044_user_assets_alerts.py`
- Modify: `backend/db/init.py` (SQLite CREATE TABLE next to `watchlist`)
- Modify: `backend/db/schema_inventory.py` — append `"user_assets"`, `"user_cve_pins"`, `"user_alert_policies"` to `APP_TABLES`
- Test: `backend/tests/test_schema_044_user_assets.py` (SQLite init creates tables)

**Interfaces:**
- Produces tables (Postgres + SQLite):

```sql
CREATE TABLE user_assets (
    id INTEGER PRIMARY KEY,  -- PG: GENERATED BY DEFAULT AS IDENTITY
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    vendor TEXT NOT NULL DEFAULT '',
    product TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT '',
    cpe_uri TEXT NOT NULL DEFAULT '',
    match_mode TEXT NOT NULL DEFAULT 'cpe' CHECK (match_mode IN ('cpe', 'keyword')),
    in_stack INTEGER NOT NULL DEFAULT 1,
    alert_enabled INTEGER NOT NULL DEFAULT 0,
    min_severity TEXT,
    triggers_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, vendor, product, version)
);

CREATE TABLE user_cve_pins (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    cve_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, cve_id)
);

CREATE TABLE user_alert_policies (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    policy_json TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

Backfill in `upgrade()`:

1. For each `user_preferences` row with non-empty `stack_terms`, insert one `user_assets` row per comma term: `product=term`, `vendor=''`, `version=''`, `match_mode='keyword'`, `in_stack=1`, `alert_enabled=0`.
2. For each `watchlist` row with `state='pin'`, insert `user_cve_pins` for every `users.id` (preserves shared pins). Skip snooze rows.
3. For every user that received a pin, insert `user_alert_policies` with `DEFAULT_ALERT_POLICY` JSON if missing.

Keep table `watchlist` in place for one release; `GET /api/watchlist` reads `user_cve_pins` after Task 5. Admin purge can still see legacy `watchlist` until Task 11 docs say to drop in a later revision (do **not** drop in 044).

- [ ] **Step 1: Test** that `init_db()` creates the three tables (query `sqlite_master` / information_schema). Write the test first; it fails until `init.py` is updated.

- [ ] **Step 2:** Implement `init.py` CREATE TABLE blocks (copy the SQL above; SQLite `INTEGER PRIMARY KEY` for `user_assets.id`).

- [ ] **Step 3:** Alembic 044 with the same DDL for Postgres (`IDENTITY`, `CHECK` constraints). Use `json.dumps(DEFAULT_ALERT_POLICY)` in a Python loop via `op.get_bind()` for backfill — do not embed policy JSON by hand in SQL.

- [ ] **Step 4:** `APP_TABLES` update so intel/app split tests stay honest.

- [ ] **Step 5:** `cd backend && pytest tests/test_schema_044_user_assets.py tests/test_schema_split_migration.py -q`

- [ ] **Step 6: Commit** `feat(db): add user_assets, user_cve_pins, user_alert_policies`

---

### Task 4: Persistence helpers + derived stack_terms

**Files:**
- Create: `backend/db/user_assets.py`
- Create: `backend/db/user_cve_pins.py`
- Create: `backend/db/user_alert_policies.py`
- Modify: `backend/preferences/repo.py` — `get_user_stack` also returns `assets: list`
- Test: `backend/tests/test_user_assets_repo.py`

**Interfaces:**
- `list_assets(db, user_id) -> list[dict]`
- `upsert_asset(db, user_id, body) -> dict` — validates product non-empty, `match_mode in {cpe,keyword}`, max 200 assets/user
- `delete_asset(db, user_id, asset_id) -> bool`
- `sync_stack_terms_from_assets(db, user_id) -> str` — writes comma-separated `product` (and `vendor:product` if vendor set) into `user_preferences.stack_terms` so existing feed `stack=` callers keep working
- `list_pins(db, user_id) -> list[str]`
- `add_pin` / `remove_pin`
- `get_policy(db, user_id) -> dict` — missing row returns `deepcopy(DEFAULT_ALERT_POLICY)` without insert
- `put_policy(db, user_id, policy) -> dict` — validate keys; unknown keys 422

Cap: 200 assets, 2000 pins per user.

When `match_mode=cpe` and `product` is set with no `cpe_uri`, matching still uses `score_asset_against_cpe` on vendor/product/version (existing helper).

- [ ] Tests: unique constraint, 201st asset raises `ValueError("asset_limit")`, `sync_stack_terms_from_assets` round-trip.

- [ ] Commit `feat(db): persist user assets, pins, and alert policy`

---

### Task 5: HTTP API

**Files:**
- Modify: `backend/routers/me.py`
- Modify: `backend/routers/watchlist.py` — `Depends(require_user)`; all reads/writes `user_cve_pins`
- Modify: `frontend/src/api.js` — `fetchAssets`, `saveAsset`, `deleteAsset`, `fetchAlertPolicy`, `saveAlertPolicy`; watchlist functions already exist
- Test: `backend/tests/test_me_assets.py`, update `backend/tests/test_watchlist.py` to authed client

**Routes:**

```
GET    /api/me/assets
POST   /api/me/assets          {vendor, product, version, cpe_uri, match_mode, in_stack, alert_enabled, min_severity?}
PATCH  /api/me/assets/{id}     same fields optional
DELETE /api/me/assets/{id}

GET    /api/me/alert-policy
PUT    /api/me/alert-policy    full policy object

GET    /api/watchlist          -> {data: [{cve_id, state: "pin"}], count}  still pin-shaped for UI
POST   /api/watchlist          {cve_id, state: "pin"} only; snooze returns 410
DELETE /api/watchlist/{cve_id}
```

`PUT /api/me/stack` remains: if `stack_terms` is sent, split and upsert keyword assets (alert_enabled false) then `sync_stack_terms_from_assets`. Do not delete CPE assets the user added via `/assets`.

Watchlist: unauthenticated → 401 (today it is global and often open behind app login already — match `require_user` used by `/api/me/stack`).

- [ ] Tests with existing auth fixtures from `test_me_stack.py`.

- [ ] Commit `feat(api): per-user assets, alert policy, and CVE pins`

---

### Task 6: Candidate matching (recent CVEs only)

**Files:**
- Create: `backend/alerts/match.py`
- Test: `backend/tests/test_alert_match.py`

**Interfaces:**
- Consumes: `matching.cpe.score_cve_for_assets`, `score_asset_against_cpe`
- Produces: `async def match_candidates(db, assets: list[dict], cve_rows: list[dict]) -> list[MatchHit]`

`MatchHit` = `{cve_id, asset_id, score, mode, vendor, product, version}`.

Rules:

- Skip assets with empty `product`
- `match_mode=cpe`: parse `cpe_matches` JSON on the CVE row; if empty, parse `affected_products` `vendor:product` strings the same way `match_cves_for_assets` does; require `score_cve_for_assets >= 55` (versionless) or `100` (in-range)
- `match_mode=keyword`: `product` substring against `affected_products` JSON text and CPE product fields **only** — **not** `description`
- One hit per (cve_id, asset_id); keep max score

Fixture: nginx 1.24 in-range CPE → score 100; keyword `python` must **not** match a CVE whose description mentions Python but `affected_products` is `apache:http_server`.

- [ ] Commit `feat(alerts): score candidate CVEs against user assets`

---

### Task 7: Evaluator (immediate vs digest)

**Files:**
- Create: `backend/alerts/evaluate.py`
- Test: `backend/tests/test_alert_evaluate.py`

**Interfaces:**
- `async def evaluate_user_alerts(db, *, since_hours: int = 1) -> list[AlertWork]`
- `AlertWork` = `{user_id, event_type, envelope, cadence}`

Algorithm:

1. Load all user ids that have (`alert_enabled` asset) OR (pins) OR (policy sources.watchlist and pins).
2. Collect candidate CVE ids: `cve_change_history` in window + `cves.published` in window + KEV flags flipped in window (reuse `get_recent_cve_changes` + small SELECT). Cap 500.
3. Fetch those CVE rows (`cve_id, severity, description, summary, epss_score, kev, has_poc, cpe_matches, affected_products, cvss`).
4. For each user:
   - policy = `get_policy`
   - classify each candidate into triggers: `new_published` if published in window; `kev` if field `in_kev`/`kev` flipped true; `epss_jump` if delta ≥ policy `epss_min_delta`; `poc` if `has_poc` 0→1; `severity_up` if severity rank improved
   - pin hits: if `cve_id in pins` and source watchlist and trigger in {kev, epss_jump, poc, severity_up}
   - asset hits: `match_candidates` then `passes_policy` with `asset_override` from that row; `source` is `stack` if `in_stack` else `watchlist`
5. Group passing hits: if cadence is `digest_hourly` and trigger is `new_published`/`severity_up`, append to digest bucket; else one `AlertWork` immediate
6. Deduplicate against `webhook_alert_log` using `envelope["dedupe_key"]` **plus** destination-agnostic claim (existing `claim_webhook_destination_sent` still runs at dispatch)

Do not send in this task — return work items only.

- [ ] Commit `feat(alerts): evaluate per-user alert work items`

---

### Task 8: Scheduler + webhook engine + in-app notify

**Files:**
- Modify: `backend/webhooks/destinations.py` — add `EVENT_STACK_MATCH = "stack_match"` to `ALL_EVENT_TYPES`
- Modify: `backend/webhooks/engine.py` — `dispatch_event(..., envelope: dict | None = None)`; allow `stack_match`; if envelope, generic body = envelope (must include `text`)
- Modify: `backend/webhooks/ssrf.py` — `webhook_json_payload` if `envelope` passed, return it (still include `source: "briefr"` only if missing)
- Modify: `backend/webhooks/alerts.py` — `process_user_alert_tick()`; `process_kev_stack_alerts` becomes: if any user has stack source + kev trigger, skip instance-level `get_effective_stack_terms` path; keep env `BRIEFR_STACK_TERMS` **operator** path only when env is set (wallboard/ops), labeled in payload `match.kind = "operator_env"`
- Modify: `backend/notifications/emit.py` — `emit_user_alert(db, user_id=..., envelope)` — **one user**, not `list_active_user_ids`
- Modify: `backend/scheduler.py` — job `user_alert_evaluate` hourly (same minute as watchlist monitor or +5 min); keep `watchlist_monitor_alerts` calling into `process_user_alert_tick` **or** delete duplicate KEV/EPSS/PoC loops from `process_watchlist_monitor_alerts` once evaluate covers pins (do not double-send; gate old functions behind `USER_ALERTS_V1=1` default on, old path off)
- Modify: `backend/routers/admin/jobs.py` `_JOB_RUN_MAP`
- Modify: `frontend/src/pages/admin/WebhooksPage.jsx` `EVENT_OPTIONS` add `{ id: 'stack_match', label: 'Stack / product match' }`
- Test: extend `backend/tests/test_webhooks_alerts.py` — pin for user A does not notify user B; stack keyword does not fire with `alert_enabled=0`; digest groups two new CVEs

Env flag: `USER_ALERTS_V1` default `1`. When `0`, keep old `process_watchlist_monitor_alerts` / `process_kev_stack_alerts` only (rollback).

- [ ] Commit `feat(alerts): dispatch v1 envelopes from hourly evaluator`

---

### Task 9: Analyst UI — policy + per-product alerts

**Files:**
- Create: `frontend/src/utils/alertPolicy.js` + `alertPolicy.test.js`
- Create: `frontend/src/components/AlertPolicyPanel.jsx` + `.css`
- Modify: `frontend/src/components/AssetProfileManage.jsx` (or wizard manage screen) — table columns: product, version, In stack, Alert, min severity Select, trigger checkboxes (collapsed)
- Modify: `frontend/src/api.js`
- Wire panel into signed-in Header overflow **Alerts** (next to My Stack) and Asset manage dialog
- Test: `frontend/src/utils/alertPolicy.test.js` — default labels, `policyPatch` refuses enabling `new_published` without confirming `sources.stack` or watched product

UI copy (exact):

- Sources: `Stack matches` / `Watchlist` / helper text: “Off sends nothing. Stack uses products you run. Watchlist uses pinned CVEs and products you marked Alert.”
- Triggers: `New CVE` / `Added to KEV` / `EPSS jump` / `PoC appeared` / `Severity increased`
- Floor: `Critical only` / `High and above` / `Medium and above` / `All rated` + checkbox `Include unknown severity`
- Cadence: `Send new-CVE matches as hourly digest` (Switch, default on when New CVE is on)

Preview: static example Discord block using `format` from a tiny duplicated JS `formatAlertText` in `alertPolicy.js` (keep strings in sync with Python tests via one fixture JSON `backend/tests/fixtures/alert_envelope_example.json` read by both if easy; otherwise duplicate the one-line format and comment “keep in sync with envelope.format_text”).

Radix Checkbox/Select/Switch; loading/empty/error on policy GET.

- [ ] `cd frontend && npm run test:unit` for the new test file; `npm run build`

- [ ] Commit `feat(ui): alert policy panel and per-product alert toggles`

---

### Task 10: Feed filter uses assets; stop last-user stack for alerts

**Files:**
- Modify: `frontend/src/utils/cveFilters.js` — `my_stack_only` still sends `stack=` derived terms (server `sync_stack_terms_from_assets`)
- Modify: `backend/routers/cves/list.py` — when `stack` query is present, optional later improvement: if request is authed, ignore the query string and match `user_assets` in SQL:
  - keyword rows: existing LIKE on **affected_products only** (change from description OR products)
  - cpe rows: JSON/product key match is expensive; v1 keep sending derived terms but **strip description** from `_stack_match_clause` for non-CVE-ID terms: match `affected_products` only
- Modify: `backend/preferences/repo.py` `get_effective_stack_terms` — **do not use last-updated user for webhooks**. Return env `BRIEFR_STACK_TERMS` or `""`. Wallboard: if env empty, use **request-less** fallback: first admin user’s derived terms (document in PRODUCT_STATUS). Add `get_wallboard_stack_terms(db)` separate from alerts.
- Test: update any test that expected description LIKE for stack (search `test_stack` / `_stack_match_clause`)

This is the “make My Stack right” feed behavior: `openssl` no longer matches a Windows-only CVE that mentions OpenSSL in the prose unless `affected_products`/CPE says so.

- [ ] Commit `fix(stack): match products not description; stop last-user alert stack`

---

### Task 11: Docs + admin webhook labels

**Files:**
- Modify: `docs/PRODUCT_STATUS.md` — My Stack, Watchlist, webhooks rows
- Modify: `docs/API_REFERENCE.md` — `/api/me/assets`, `/api/me/alert-policy`, watchlist per-user, envelope schema, `stack_match` event
- Modify: `docs/SYSTEM_DESIGN.md` — short alerts paragraph
- Modify: `frontend/src/pages/admin/WebhooksPage.jsx` helper: destination subscriptions vs user policy (“Destinations choose channels. Each analyst chooses what is generated under Alerts.”)

- [ ] Commit `docs: stack, watchlist, and v1 alert envelope`

---

### Task 12: Verify and cutover note

- [ ] Run `./scripts/verify-local.sh`
- [ ] Manual: two users — pin as A, confirm B’s bell and Discord do not get A’s pin; enable stack alerts CRITICAL+KEV on nginx asset; insert a CRITICAL KEV nginx CVE in test DB; expect one formatted webhook
- [ ] Commit if verify required extra test fixes

**Deploy:** Alembic 044, restart backend, rebuild frontend. Users must open **Alerts** once if they want stack webhooks (defaults leave stack source off).

---

## Execution notes for later (not this plan’s code)

- Drop legacy `watchlist` table in a **future** revision after one production release.
- Per-user webhook URLs: out of scope.
- Full CPE feed SQL (no derived `stack=` string): follow-up if keyword false-positives remain on `affected_products`.

## Self-review

| Requirement | Task |
|-------------|------|
| Stack is inventory, not description search | 10 + 6 |
| Watchlist per-user pins + product watches | 3–5, 9 |
| Alerts for stack products / versions | 6–9 |
| Per-product severity + trigger choice | 1, 4, 9 |
| Sources: stack / watchlist / both | 1, 9 |
| Choose what is sent (not spam) | defaults in 1, digest in 2+7, New CVE off |
| Standardized webhooks | 2, 8 |
| In-app notify the right user | 8 `emit_user_alert` |

No TBD placeholders in task bodies. `passes_policy` pin exception and keyword-not-on-description are explicit.
