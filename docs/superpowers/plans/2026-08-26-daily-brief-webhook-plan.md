# Daily brief webhooks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship instance-level EOD and standup **daily briefs** on existing Discord/Telegram/generic webhooks, with a PDF-like section grammar, SQL facts, and optional LLM lede.

**Architecture:** Collect a `DailyBrief` dataclass from local tables for a UTC window; format with `docs/design/daily-brief-format.md`; optionally rewrite only `headline` via `chat_completion_task("pdf_summary")`; `dispatch_event("daily_brief", …)` from two cron jobs. Destinations opt in via `event_types`. Slots default **off**.

**Tech Stack:** FastAPI, APScheduler CronTrigger, existing webhook engine, LLM router (optional), React Admin Webhooks + Config.

**Spec:** `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`  
**Format:** `docs/design/daily-brief-format.md`

## Global Constraints

- No email, no per-user webhook URLs, no `last_login_at` windows, no KEV backlog in the brief.
- Facts are local SQL only. LLM never authors COUNTS or list IDs.
- Discord 2000 / Telegram 4096 truncation order is in the format doc.
- `DAILY_BRIEF_*_ENABLED` default `0`. `DAILY_BRIEF_LLM_ENABLED` default `0`.
- Timezone: `SCHEDULER_TIMEZONE` (same `sched_tz` as other cron jobs).
- Merge gate: `./scripts/verify-local.sh`. Scheduler `id=` strings must match `_JOB_RUN_MAP`.
- Semantic tokens / dark UI; HelpTip not emoji; `// SECTION` titles in the brief body.

---

### File map

| File | Responsibility |
|------|----------------|
| Create: `backend/reports/daily_brief.py` | Window math, collector, template lede, formatter, overflow |
| Create: `backend/reports/__init__.py` | Re-export `build_daily_brief`, `format_daily_brief_text`, `run_daily_brief_slot` |
| Create: `backend/tests/test_daily_brief.py` | Collector, format, overflow, LLM reject-hallucination, skip disabled |
| Modify: `backend/webhooks/destinations.py` | `EVENT_DAILY_BRIEF`, `ALL_EVENT_TYPES` |
| Modify: `backend/webhooks/ssrf.py` | Optional `extra` on `webhook_json_payload` |
| Modify: `backend/webhooks/engine.py` | Pass `brief` extra on generic POST; import event constant |
| Modify: `backend/webhooks/engine.py` `dispatch_event` | Optional `payload_extra: dict` |
| Modify: `backend/config_schema.py` | Six config fields; reschedule keys |
| Modify: `backend/.env.example` | Commented defaults |
| Modify: `backend/scheduler.py` | Two jobs + run functions |
| Modify: `backend/routers/admin/jobs.py` | `_JOB_RUN_MAP` |
| Modify: `backend/routers/admin/webhooks.py` | Preview + test-send routes |
| Modify: `frontend/src/pages/admin/WebhooksPage.jsx` | Event option, preview/test UI |
| Modify: `docs/API_REFERENCE.md`, `docs/PRODUCT_STATUS.md` | Contract |

---

### Task 1: DailyBrief model, window, collector, formatter

**Files:**
- Create: `backend/reports/__init__.py`
- Create: `backend/reports/daily_brief.py`
- Test: `backend/tests/test_daily_brief.py`

**Interfaces:**
- Consumes: `cves.published`, `kev_deadlines.date_added`, `user_notifications` (`category` in `watchlist`, `ioc_watchlist`, `job_error`, `api_key_unhealthy`, `webhook_failure`)
- Produces: `DailyBriefSlot = Literal["eod", "standup"]`; `async def collect_daily_brief(db, *, slot, window_start_utc: datetime, window_end_utc: datetime, tz_name: str) -> DailyBrief`; `def format_daily_brief_text(brief: DailyBrief, *, limit: int) -> str`; `def template_headline(brief: DailyBrief) -> str`

- [ ] **Step 1: Write the failing tests**

```python
"""Daily brief collector + format grammar."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from database import get_db, init_db
from tests.conftest import run_db_test

pytestmark = pytest.mark.no_auth


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    import database as db_module
    from settings import settings as _settings

    db_path = tmp_path / "daily_brief.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("BRIEFR_REQUIRE_POSTGRES", raising=False)
    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    monkeypatch.setattr("db.init.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.connection.is_postgres", lambda url=None: False)
    monkeypatch.setattr("db.config.is_postgres", lambda url=None: False)
    run_db_test(init_db())
    return db_path


def test_quiet_window_format(db_env):
    from reports.daily_brief import collect_daily_brief, format_daily_brief_text, template_headline

    end = datetime(2026, 8, 26, 1, 30, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _go():
        db = await get_db()
        try:
            brief = await collect_daily_brief(
                db,
                slot="standup",
                window_start_utc=start,
                window_end_utc=end,
                tz_name="UTC",
            )
            brief = brief.model_copy(update={"headline": template_headline(brief)}) if hasattr(brief, "model_copy") else brief
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_go())
    assert brief.counts["kev_new"] == 0
    assert "Quiet window." in text
    assert "// COUNTS" in text
    assert "KEV new: 0" in text
    assert "slot=standup" in text
    assert "lede=template" in text


def test_kev_in_window_listed(db_env):
    from reports.daily_brief import collect_daily_brief, format_daily_brief_text

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _seed():
        db = await get_db()
        try:
            await db.execute(
                """
                INSERT INTO cves (cve_id, description, severity, published, is_kev)
                VALUES ('CVE-2026-1111', 'demo', 'CRITICAL', '2026-08-26 00:00:00', 1)
                """
            )
            await db.execute(
                """
                INSERT INTO kev_deadlines (cve_id, product, short_description, date_added)
                VALUES ('CVE-2026-1111', 'demo', 'demo kev', '2026-08-26')
                """
            )
            await db.commit()
            brief = await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
            return brief, format_daily_brief_text(brief, limit=2000)
        finally:
            await db.close()

    brief, text = run_db_test(_seed())
    assert brief.counts["kev_new"] == 1
    assert "CVE-2026-1111" in text
    assert "// KEV" in text


def test_overflow_drops_ops_before_kev():
    from reports.daily_brief import DailyBrief, format_daily_brief_text

    items = [f"CVE-2026-{i:04d}" for i in range(40)]
    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="Busy.",
        lede_source="template",
        counts={
            "kev_new": 40,
            "stack_matches": 0,
            "watchlist": 0,
            "ioc_hits": 0,
            "critical_high_new": 0,
            "ops_issues": 20,
        },
        kev=[{"cve_id": c, "reason": "added to KEV", "severity": "HIGH"} for c in items],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[{"id": f"job-{i}", "reason": "boom " * 40} for i in range(20)],
    )
    text = format_daily_brief_text(brief, limit=500)
    assert len(text) <= 500
    assert "// COUNTS" in text
    assert "// OPS" not in text or "more in BRIEFR" in text
```

If `cves` INSERT columns differ on SQLite, match `backend/tests/test_detection_backlog.py` (include `cvss_score`, `epss_score`). Use a dataclass, not pydantic `model_copy` — the test's `model_copy` branch is only a sketch; the collector should set `headline=""` and the test should call `template_headline` then `dataclasses.replace`.

Replace the quiet-window test body with `dataclasses.replace(brief, headline=template_headline(brief))`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_daily_brief.py -q`

Expected: FAIL (`reports` package missing).

- [ ] **Step 3: Implement collector + formatter**

`backend/reports/__init__.py`:

```python
from reports.daily_brief import (
    DailyBrief,
    collect_daily_brief,
    format_daily_brief_text,
    template_headline,
)

__all__ = [
    "DailyBrief",
    "collect_daily_brief",
    "format_daily_brief_text",
    "template_headline",
]
```

`backend/reports/daily_brief.py` — implement:

```python
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

DailyBriefSlot = Literal["eod", "standup"]

COUNT_KEYS = (
    "kev_new",
    "stack_matches",
    "watchlist",
    "ioc_hits",
    "critical_high_new",
    "ops_issues",
)

LIST_DROP_ORDER = ("ops", "ioc", "watchlist", "stack", "kev")


@dataclass
class DailyBrief:
    slot: DailyBriefSlot
    tz_name: str
    window_start_local: str
    window_end_local: str
    generated_local: str
    headline: str
    lede_source: str
    counts: dict[str, int]
    kev: list[dict[str, str]]
    stack: list[dict[str, str]]
    watchlist: list[dict[str, str]]
    ioc: list[dict[str, str]]
    ops: list[dict[str, str]]


def _fmt_local(dt: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def template_headline(brief: DailyBrief) -> str:
    c = brief.counts
    if all(c[k] == 0 for k in COUNT_KEYS):
        return "Quiet window."
    parts = []
    if c["kev_new"]:
        parts.append(f"{c['kev_new']} new KEV.")
    if c["stack_matches"]:
        parts.append(f"{c['stack_matches']} stack match(es).")
    if c["watchlist"]:
        parts.append(f"Watchlist: {c['watchlist']}.")
    if c["ioc_hits"]:
        parts.append(f"{c['ioc_hits']} IOC hit(s).")
    if c["critical_high_new"] and not c["kev_new"]:
        parts.append(f"{c['critical_high_new']} new Critical/High.")
    if c["ops_issues"]:
        parts.append(f"{c['ops_issues']} ops issue(s).")
    return " ".join(parts) or "Quiet window."


def _line_cve(row: dict[str, str]) -> str:
    sev = (row.get("severity") or "").strip()
    extra = f" · {sev}" if sev else ""
    return f"• {row['cve_id']} — {row['reason']}{extra}"


def format_daily_brief_text(brief: DailyBrief, *, limit: int) -> str:
    slot_label = "EOD" if brief.slot == "eod" else "STANDUP"
    sections: dict[str, list[str]] = {
        "masthead": [
            f"BRIEFR {slot_label}",
            f"{brief.window_start_local} → {brief.window_end_local} ({brief.tz_name})",
        ],
        "headline": ["// HEADLINE", brief.headline or "Quiet window."],
        "counts": ["// COUNTS"] + [
            f"KEV new: {brief.counts['kev_new']}",
            f"Stack matches: {brief.counts['stack_matches']}",
            f"Watchlist: {brief.counts['watchlist']}",
            f"IOC hits: {brief.counts['ioc_hits']}",
            f"Critical/High new: {brief.counts['critical_high_new']}",
            f"Ops issues: {brief.counts['ops_issues']}",
        ],
        "kev": ["// KEV"] + [_line_cve(r) for r in brief.kev[:8]],
        "stack": ["// STACK"] + [_line_cve(r) for r in brief.stack[:8]],
        "watchlist": ["// WATCHLIST"] + [_line_cve(r) for r in brief.watchlist[:8]],
        "ioc": ["// IOC"] + [
            f"• {r.get('type','')} {r.get('value','')} — {r.get('reason','')}".strip()
            for r in brief.ioc[:5]
        ],
        "ops": ["// OPS"] + [f"• {r['id']} — {r['reason']}" for r in brief.ops[:5]],
        "footer": [
            f"BRIEFR — generated {brief.generated_local} {brief.tz_name} | slot={brief.slot} | facts=local | lede={brief.lede_source}",
        ],
    }
    for key in ("kev", "stack", "watchlist", "ioc", "ops"):
        if len(sections[key]) == 1:
            sections[key] = []

    def assemble(drop: set[str], headline: str) -> str:
        chunks = []
        sections["headline"] = ["// HEADLINE", headline]
        for name in ("masthead", "headline", "counts", "kev", "stack", "watchlist", "ioc", "ops", "footer"):
            if name in drop:
                continue
            body = sections[name]
            if not body:
                continue
            chunks.append("\n".join(body))
        return "\n\n".join(chunks)

    headline = brief.headline or "Quiet window."
    dropped: set[str] = set()
    text = assemble(dropped, headline)
    if len(text) <= limit:
        return text
    for name in LIST_DROP_ORDER:
        dropped.add(name)
        text = assemble(dropped, headline)
        if len(text) <= limit:
            hidden = 0
            if name == "ops":
                hidden = max(0, brief.counts["ops_issues"] - 0)
            text = text.replace(
                sections["footer"][0],
                f"+more in BRIEFR.\n\n{sections['footer'][0]}",
            ) if False else text
            if len(text) <= limit:
                return text
    first = headline.split(". ")[0].rstrip(".") + "."
    text = assemble(dropped, first)
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"
```

Fix overflow: after dropping a section, if that section had items, append `+{n} more in BRIEFR.` as its own paragraph before footer (n = count for that bucket). Keep the implementation honest with the format doc.

Collector SQL (SQLite `?` / Postgres `$n` via existing `_is_postgres_connection` pattern from `db/user_notifications.py` — copy the small helper into this module):

- KEV: `SELECT k.cve_id, c.severity, k.short_description FROM kev_deadlines k LEFT JOIN cves c ON c.cve_id = k.cve_id WHERE k.date_added >= ? AND k.date_added < ?` — `date_added` may be date-only; compare as text `YYYY-MM-DD` using local dates of the window **or** store ISO. For tests use `date_added` date strings that fall inside the local window dates.
- Critical/High: `SELECT cve_id, severity FROM cves WHERE published >= ? AND published < ? AND UPPER(severity) IN ('CRITICAL','HIGH')`
- Watchlist: `SELECT title, body, entity_id, created_at FROM user_notifications WHERE category = 'watchlist' AND created_at >= ? AND created_at < ?`
- IOC: `category = 'ioc_watchlist'`
- Ops: `category IN ('job_error','api_key_unhealthy','webhook_failure')`

**Stack matches in Task 1:** set `stack_matches` to `0` and `stack=[]` with a comment `filled in Task 2`. Counts key still present. Test_kev does not assert stack.

`collect_daily_brief` returns `DailyBrief` with `headline=""` and `lede_source="template"`. Callers apply `template_headline` or LLM later.

- [ ] **Step 4: Run tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_daily_brief.py -q`

Expected: PASS (stack still zero).

- [ ] **Step 5: Commit**

```bash
git add backend/reports backend/tests/test_daily_brief.py
git commit -m "feat(reports): collect and format daily brief facts"
```

---

### Task 2: Stack CPE intersection (no description LIKE)

**Files:**
- Modify: `backend/reports/daily_brief.py`
- Modify: `backend/tests/test_daily_brief.py`
- Read: `backend/webhooks/alerts.py` (KEV-on-stack match helper — reuse, do not fork LIKE matching)

**Interfaces:**
- Consumes: whatever `kev_alert` uses for admin My Stack (search `match_stack` / `cpe` in `webhooks/alerts.py` or stack services)
- Produces: `stack` list + `counts["stack_matches"]` = KEV-new ∪ Critical/High-new that match admin stack CPE

- [ ] **Step 1: Find the existing matcher**

Grep `cpe_matches` / `stack` in `backend/webhooks/alerts.py`. Import that function into the collector. If it is nested, extract a `async def cves_matching_admin_stack(db, cve_ids: list[str]) -> set[str]` next to the alert helper (same file or `db/stack_match.py` if one exists). **Do not** use `BRIEFR_STACK_TERMS` or description LIKE.

- [ ] **Step 2: Test**

Add a test that inserts a stack-matching CVE in window and a non-matching Critical CVE; assert only the matching id is in `brief.stack` and `critical_high_new` still counts both.

- [ ] **Step 3: Implement + pytest + commit**

```bash
git add backend/reports/daily_brief.py backend/webhooks/alerts.py backend/tests/test_daily_brief.py
git commit -m "feat(reports): daily brief stack matches use My Stack CPE"
```

---

### Task 3: Optional LLM lede (pdf_summary chain, template fallback)

**Files:**
- Modify: `backend/reports/daily_brief.py` — `async def apply_headline(brief, *, llm_enabled: bool) -> DailyBrief`
- Modify: `backend/tests/test_daily_brief.py`

**Interfaces:**
- Consumes: `ai.llm_router.chat_completion_task`, `any_llm_provider_configured`
- Produces: `headline`, `lede_source` in `{template, groq, gemini, cerebras, openrouter, custom}`

- [ ] **Step 1: Failing tests**

```python
def test_llm_lede_rejects_unknown_cve(db_env, monkeypatch):
    from reports.daily_brief import DailyBrief, apply_headline

    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="a",
        window_end_local="b",
        generated_local="c",
        headline="",
        lede_source="template",
        counts={k: 0 for k in (
            "kev_new", "stack_matches", "watchlist", "ioc_hits", "critical_high_new", "ops_issues"
        )} | {"kev_new": 1},
        kev=[{"cve_id": "CVE-2026-1111", "reason": "added to KEV", "severity": "HIGH"}],
        stack=[], watchlist=[], ioc=[], ops=[],
    )

    class Fake:
        content = "Also see CVE-1999-0001 which is critical."
        provider = "groq"
        model = "x"

    async def _fake(*args, **kwargs):
        return Fake()

    monkeypatch.setattr("reports.daily_brief.chat_completion_task", _fake)
    monkeypatch.setattr("reports.daily_brief.any_llm_provider_configured", lambda: True)

    async def _go():
        return await apply_headline(brief, llm_enabled=True)

    out = run_db_test(_go())
    assert "CVE-1999-0001" not in out.headline
    assert out.lede_source == "template"


def test_llm_disabled_never_calls(monkeypatch):
    called = {"n": 0}

    async def _fake(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("should not call")

    monkeypatch.setattr("reports.daily_brief.chat_completion_task", _fake)
    from reports.daily_brief import DailyBrief, apply_headline, template_headline, COUNT_KEYS

    zeros = {k: 0 for k in COUNT_KEYS}
    brief = DailyBrief(
        slot="standup", tz_name="UTC", window_start_local="a", window_end_local="b",
        generated_local="c", headline="", lede_source="template", counts=zeros,
        kev=[], stack=[], watchlist=[], ioc=[], ops=[],
    )

    async def _go():
        return await apply_headline(brief, llm_enabled=False)

    out = run_db_test(_go())
    assert called["n"] == 0
    assert out.headline == template_headline(brief)
```

Fix dict merge if Python < 3.9 is not used (repo is 3.12 — `|` is fine). Import `COUNT_KEYS` from the module.

- [ ] **Step 2: pytest fail** then implement:

```python
async def apply_headline(brief: DailyBrief, *, llm_enabled: bool) -> DailyBrief:
    templated = replace(brief, headline=template_headline(brief), lede_source="template")
    if not llm_enabled or not any_llm_provider_configured():
        return templated
    allowed = {row["cve_id"] for row in brief.kev + brief.stack + brief.watchlist}
    fact_block = format_daily_brief_text(templated, limit=1500)
    completion = await chat_completion_task(
        "pdf_summary",
        messages=[
            {
                "role": "system",
                "content": "Write 1-3 short sentences for a SOC morning brief. Use only CVE IDs present in the user message. No markdown.",
            },
            {"role": "user", "content": fact_block},
        ],
        max_tokens=120,
        context_type="daily_brief",
        context_id=f"{brief.slot}:{brief.window_end_local[:10]}",
    )
    if completion is None or not (completion.content or "").strip():
        return templated
    text = completion.content.strip().split("\n")[0:3]
    lede = " ".join(line.strip() for line in text if line.strip())
    import re
    cited = set(re.findall(r"CVE-\d{4}-\d+", lede, flags=re.I))
    cited_norm = {c.upper() for c in cited}
    if cited_norm - {a.upper() for a in allowed} and cited_norm:
        return templated
    return replace(templated, headline=lede[:400], lede_source=completion.provider)
```

Place imports at module top (`re`, `chat_completion_task`, `any_llm_provider_configured`). Empty `allowed` with a lede that cites a CVE → template. Empty allowed + no CVE in lede → accept.

- [ ] **Step 3: pytest pass + commit**

```bash
git add backend/reports/daily_brief.py backend/tests/test_daily_brief.py
git commit -m "feat(reports): optional LLM daily-brief lede with template fallback"
```

---

### Task 4: Event type, dispatch extra, config, scheduler jobs

**Files:**
- Modify: `backend/webhooks/destinations.py`
- Modify: `backend/webhooks/ssrf.py` — `webhook_json_payload(..., extra: dict | None = None)`
- Modify: `backend/webhooks/engine.py` — `dispatch_event(..., payload_extra=None)` thread into generic deliver
- Modify: `backend/config_schema.py` — fields + `_SCHEDULER_RESCHEDULE_KEYS`
- Modify: `backend/.env.example`
- Modify: `backend/scheduler.py`
- Modify: `backend/routers/admin/jobs.py`
- Modify: `backend/reports/daily_brief.py` — `async def run_daily_brief_slot(slot: DailyBriefSlot) -> dict`
- Modify: `backend/tests/test_webhooks_engine.py` — dest without event skipped
- Modify: `backend/tests/test_daily_brief.py` — disabled skip; watermark

**Interfaces:**
- Produces: `EVENT_DAILY_BRIEF = "daily_brief"`; jobs `daily_brief_eod`, `daily_brief_standup`; env keys from spec §7

- [ ] **Step 1: Event constant**

Add `EVENT_DAILY_BRIEF = "daily_brief"` to `ALL_EVENT_TYPES`. Re-export in `engine.py` imports. Tests that snapshot the full event tuple must add the new name.

- [ ] **Step 2: `webhook_json_payload` extra**

```python
def webhook_json_payload(message: str, *, event_type: str, dedupe_key: str | None = None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {
        "text": message,
        "event_type": event_type,
        "source": "briefr",
    }
    if dedupe_key:
        body["dedupe_key"] = dedupe_key
    if extra:
        body.update(extra)
    return body
```

`dispatch_event` gains `payload_extra: dict[str, Any] | None = None` and `_deliver_generic` uses it.

- [ ] **Step 3: `run_daily_brief_slot`**

```python
async def run_daily_brief_slot(slot: DailyBriefSlot) -> dict[str, Any]:
    import os
    from database import get_db
    from webhooks.destinations import EVENT_DAILY_BRIEF
    from webhooks.engine import DISCORD_MAX_CONTENT, dispatch_event

    flag = "DAILY_BRIEF_EOD_ENABLED" if slot == "eod" else "DAILY_BRIEF_STANDUP_ENABLED"
    if os.environ.get(flag, "0").strip().lower() in {"0", "false", "no", "off", ""}:
        return {"status": "skipped", "reason": "disabled", "slot": slot}

    tz_name = os.environ.get("SCHEDULER_TIMEZONE") or os.environ.get("DEFAULT_TIMEZONE") or "UTC"
    # compute window_end = now; window_start = end-24h for eod;
    # standup: read sync_state daily_brief:last_eod_end or end-12h
    # if (end-start) < 15 minutes: return skipped overlapping
    db = await get_db()
    try:
        brief = await collect_daily_brief(...)
        brief = await apply_headline(
            brief,
            llm_enabled=os.environ.get("DAILY_BRIEF_LLM_ENABLED", "0").strip() not in {"0", "false", "no", "off", ""},
        )
        text = format_daily_brief_text(brief, limit=DISCORD_MAX_CONTENT)
        extra = {"brief": {
            "slot": brief.slot,
            "counts": brief.counts,
            "headline": brief.headline,
            "lede_source": brief.lede_source,
            "kev": brief.kev,
            "stack": brief.stack,
            "watchlist": brief.watchlist,
            "ioc": brief.ioc,
            "ops": brief.ops,
            "window_start_local": brief.window_start_local,
            "window_end_local": brief.window_end_local,
            "tz": brief.tz_name,
        }}
        local_date = brief.window_end_local[:10]
        result = await dispatch_event(
            EVENT_DAILY_BRIEF,
            text,
            dedupe_key=f"{slot}:{local_date}",
            payload_extra=extra,
        )
        from db.sync_state import set_sync_state_value

        if slot == "eod" and result.get("status") in {"ok", "partial"}:
            await set_sync_state_value(
                db,
                "daily_brief:last_eod_end",
                window_end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            )
            await db.commit()
        return {**result, "slot": slot}
    finally:
        await db.close()
```

Standup window start: `get_sync_state_value(db, "daily_brief:last_eod_end")` parsed as UTC, else `window_end_utc - timedelta(hours=12)`. `dispatch_event` already returns a no-subscriber skip (`test_webhooks_engine.py`).

Telegram: `dispatch_event` sends the same `text` to Telegram (engine truncates to 4096). Building at 2000 is conservative and matches Discord; Telegram still readable.

- [ ] **Step 4: Config fields**

Copy existing `IOC` hour pattern. Section `scheduler_cron` for hours/flags; LLM flag in the same section as other `LLM_*` keys (find `LLM_PRODUCT_EXTRACTION_ENABLED` in `config_schema.py` and place `DAILY_BRIEF_LLM_ENABLED` beside it). Add hour keys to `_SCHEDULER_RESCHEDULE_KEYS`.

`.env.example`:

```
# Daily brief webhooks (off until enabled). Timezone = SCHEDULER_TIMEZONE.
# DAILY_BRIEF_EOD_ENABLED=0
# DAILY_BRIEF_STANDUP_ENABLED=0
# DAILY_BRIEF_EOD_HOUR=18
# DAILY_BRIEF_EOD_MINUTE=0
# DAILY_BRIEF_STANDUP_HOUR=7
# DAILY_BRIEF_STANDUP_MINUTE=0
# DAILY_BRIEF_LLM_ENABLED=0
```

- [ ] **Step 5: Scheduler**

Mirror `ioc_retro_match` CronTrigger. Two jobs. `run_daily_brief_eod` / `run_daily_brief_standup` in `scheduler.py` call `run_daily_brief_slot`. `_JOB_RUN_MAP` entries required.

If hours env missing, use spec defaults.

- [ ] **Step 6: Tests + commit**

Engine test: destination `event_types=["kev_alert"]` does not receive `daily_brief`.

```bash
git add backend/webhooks backend/config_schema.py backend/.env.example backend/scheduler.py backend/routers/admin/jobs.py backend/reports backend/tests
git commit -m "feat(webhooks): daily_brief event, cron slots, structured generic payload"
```

---

### Task 5: Admin preview / test + Webhooks UI

**Files:**
- Modify: `backend/routers/admin/webhooks.py`
- Modify: `frontend/src/pages/admin/WebhooksPage.jsx`
- Test: `backend/tests/test_webhooks_destinations_crud.py` or new `test_daily_brief_admin.py`

**Interfaces:**
- Produces: `GET /api/admin/webhooks/daily-brief/preview?slot=eod|standup` → `{text, brief}` (no dispatch); `POST /api/admin/webhooks/daily-brief/test {slot, destination_id?}` → `dispatch_event(..., skip_dedupe=True)`

- [ ] **Step 1: Failing API test** (admin client fixture from `test_webhooks_destinations_crud.py`)

Assert preview 200, body contains `// COUNTS`, and `webhook_delivery_log` row count unchanged.

- [ ] **Step 2: Routes** — `require_admin`, slot query 422 if not `eod`/`standup`.

- [ ] **Step 3: UI**

`EVENT_OPTIONS` append `{ id: 'daily_brief', label: 'Daily brief (EOD / standup)' }`.

Above destination list: slot `<Select>` + Preview button + Send test. Preview renders in `<pre>` with `font-family: var(--font-mono)`, `font-size: 0.75rem`, existing surface token background. HelpTip: scheduled rollup; enable slots in Config; does not replace real-time alerts.

Do not use inline `fontSize` unless neighboring controls already do (Webhooks page pattern).

- [ ] **Step 4: frontend unit if EVENT_OPTIONS is extracted** — optional; if the array stays in the page, skip new Jest file.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/admin/webhooks.py backend/tests frontend/src/pages/admin/WebhooksPage.jsx
git commit -m "feat(admin): daily brief preview and test send"
```

---

### Task 6: Docs + verify-local

**Files:**
- Modify: `docs/API_REFERENCE.md` — event type table; new preview/test routes; config keys
- Modify: `docs/PRODUCT_STATUS.md` — one bullet: Daily brief EOD/standup webhooks, format doc, LLM optional
- Verify: format doc already in repo from this planning PR

- [ ] **Step 1: API_REFERENCE** next to webhook destinations: `daily_brief` event; preview GET; test POST; note jobs off by default; env-all-events destinations will include the type once jobs are enabled.

- [ ] **Step 2: PRODUCT_STATUS** Last updated date 2026-08-26.

- [ ] **Step 3: Optional `graphify update .` (do not commit `graphify-out/`). Then `./scripts/verify-local.sh`**

Expected: green (SQLite path OK).

- [ ] **Step 4: Commit**

```bash
git add docs/API_REFERENCE.md docs/PRODUCT_STATUS.md
git commit -m "docs: daily brief webhook event and admin preview"
```

---

## Self-review (spec coverage)

| Spec § | Task |
|--------|------|
| Slots EOD/standup, defaults off | 4 |
| No last_login | 1–4 (window from clock) |
| Format grammar + overflow | 1 + `docs/design/daily-brief-format.md` |
| AI optional / template | 3 |
| Stack CPE not LIKE | 2 |
| Event + dest checkbox | 4–5 |
| Preview/test | 5 |
| Quiet send | 1 + 4 |
| Watermark / 15m overlap skip | 4 |
| Docs | 6 |
| Out of scope email/per-user | not tasked |
