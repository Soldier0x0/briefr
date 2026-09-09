# Daily brief omit unconfigured My Stack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Daily brief human copy includes My Stack only when admin My Stack assets exist.

**Architecture:** Add `DailyBrief.stack_configured` from `get_alert_stack_assets`. One `glance_lines(brief)` drives Discord, HTML, text, and Admin preview. Matcher unchanged.

**Tech Stack:** FastAPI / pytest, React admin, node:test for glance helper.

**Spec:** `docs/superpowers/specs/2026-09-09-daily-brief-stack-configured-design.md`

## Global Constraints

- Configured = non-empty `get_alert_stack_assets()` (admin profile or `stack_terms`).
- Unconfigured: omit glance line, omit My Stack field, omit Summary stack sentence. Do not print “not configured”.
- Configured with zero hits: still print `Matches My Stack: 0`.
- `counts.stack_matches` remains in JSON; add `stack_configured` on payload.
- Out of scope: wallboard, analyst BRIEF, header wizard, matcher rewrite.
- Merge gate `./scripts/verify-local.sh`. Update PRODUCT_STATUS + API_REFERENCE + `docs/design/daily-brief-format.md`.
- Dark admin tokens; reuse existing `daily-brief-*` classes.

---

### Task 1: glance_lines + stack_configured on DailyBrief

**Files:**
- Modify: `backend/reports/daily_brief.py`
- Test: `backend/tests/test_daily_brief.py`

**Interfaces:**
- Consumes: `DailyBrief.counts`, `DailyBrief.stack_configured`
- Produces: `glance_lines(brief) -> list[str]`; `_glance_text` joins with `"\n"`

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_daily_brief.py`:

```python
def test_glance_omits_stack_when_unconfigured():
    from reports.daily_brief import COUNT_KEYS, DailyBrief, glance_lines

    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="Quiet window.",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
        stack_configured=False,
    )
    lines = glance_lines(brief)
    assert lines[0] == "New on CISA KEV: 0"
    assert all("My Stack" not in line for line in lines)
    assert "Pinned-CVE alerts: 0" in lines


def test_glance_includes_stack_zero_when_configured():
    from reports.daily_brief import COUNT_KEYS, DailyBrief, glance_lines

    brief = DailyBrief(
        slot="eod",
        tz_name="UTC",
        window_start_local="2026-08-25 18:00",
        window_end_local="2026-08-26 18:00",
        generated_local="2026-08-26 18:00",
        headline="Quiet window.",
        lede_source="template",
        counts={key: 0 for key in COUNT_KEYS},
        kev=[],
        stack=[],
        watchlist=[],
        ioc=[],
        ops=[],
        stack_configured=True,
    )
    lines = glance_lines(brief)
    assert "Matches My Stack: 0" in lines
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_daily_brief.py::test_glance_omits_stack_when_unconfigured tests/test_daily_brief.py::test_glance_includes_stack_zero_when_configured -q`

Expected: FAIL (`TypeError` unknown field or `glance_lines` missing).

- [ ] **Step 3: Write minimal implementation**

On `DailyBrief` add `stack_configured: bool = False`.

```python
def glance_lines(brief: DailyBrief) -> list[str]:
    lines = [f"New on CISA KEV: {brief.counts['kev_new']}"]
    if brief.stack_configured:
        lines.append(f"Matches My Stack: {brief.counts['stack_matches']}")
    lines.extend(
        [
            f"Pinned-CVE alerts: {brief.counts['watchlist']}",
            f"IOC watch hits: {brief.counts['ioc_hits']}",
            f"New Critical or High: {brief.counts['critical_high_new']}",
            f"Instance problems: {brief.counts['ops_issues']}",
        ]
    )
    return lines


def _glance_text(brief: DailyBrief) -> str:
    return "\n".join(glance_lines(brief))
```

Replace the duplicated glance list inside `format_daily_brief_text` `build_sections` `"counts"` with `["At a glance"] + glance_lines(brief)`.

In `template_headline`, change `if c["stack_matches"]:` to `if brief.stack_configured and c["stack_matches"]:`.

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_daily_brief.py::test_glance_omits_stack_when_unconfigured tests/test_daily_brief.py::test_glance_includes_stack_zero_when_configured tests/test_daily_brief.py::test_quiet_window_format -q`

Expected: PASS. Also assert in `test_quiet_window_format` that `"Matches My Stack" not in text`.

- [ ] **Step 5: Commit**

```bash
git add backend/reports/daily_brief.py backend/tests/test_daily_brief.py
git commit -m "fix(daily-brief): omit My Stack glance when stack is not configured"
```

---

### Task 2: collect_daily_brief + payload + formatter tests

**Files:**
- Modify: `backend/reports/daily_brief.py` (`collect_daily_brief`, `brief_to_payload`)
- Test: `backend/tests/test_daily_brief.py`

**Interfaces:**
- Consumes: `get_alert_stack_assets`
- Produces: `stack_configured=bool(assets)` on collect; payload key `stack_configured`

- [ ] **Step 1: Write the failing test**

```python
def test_collect_sets_stack_configured_false_without_admin_stack(db_env):
    from reports.daily_brief import collect_daily_brief, brief_to_payload, format_daily_brief_embed

    end = datetime(2026, 8, 26, 18, 0, tzinfo=timezone.utc)
    start = end - timedelta(hours=24)

    async def _go():
        db = await get_db()
        try:
            return await collect_daily_brief(
                db, slot="eod", window_start_utc=start, window_end_utc=end, tz_name="UTC"
            )
        finally:
            await db.close()

    brief = run_db_test(_go())
    assert brief.stack_configured is False
    payload = brief_to_payload(brief)
    assert payload["stack_configured"] is False
    names = [field["name"] for field in format_daily_brief_embed(brief)[0]["fields"]]
    assert "My Stack" not in names
    glance = next(f["value"] for f in format_daily_brief_embed(brief)[0]["fields"] if f["name"] == "At a glance")
    assert "My Stack" not in glance
```

Extend `test_stack_matches_admin_cpe_not_description` with `assert brief.stack_configured is True` and `"Matches My Stack:" in format_daily_brief_text(brief, limit=2000)`.

For fixtures that assert `"My Stack" in names` on constructed briefs with stack rows, set `stack_configured=True`.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_daily_brief.py::test_collect_sets_stack_configured_false_without_admin_stack -q`

Expected: FAIL (`stack_configured` missing on payload or always default).

- [ ] **Step 3: Write minimal implementation**

In `collect_daily_brief`, after `assets = await get_alert_stack_assets(db)`:

```python
stack_configured = bool(assets)
stack, stack_total = await _collect_stack(...)
```

Pass `stack_configured=stack_configured` into `DailyBrief(...)`.

In `brief_to_payload`:

```python
"stack_configured": brief.stack_configured,
```

- [ ] **Step 4: Run the tests**

Run: `cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 pytest tests/test_daily_brief.py -q`

Expected: PASS. Fix any constructed `DailyBrief` that expected the stack glance without `stack_configured=True`.

- [ ] **Step 5: Commit**

```bash
git add backend/reports/daily_brief.py backend/tests/test_daily_brief.py
git commit -m "fix(daily-brief): set stack_configured from admin assets"
```

---

### Task 3: Admin preview glance helper + living docs

**Files:**
- Create: `frontend/src/pages/admin/dailyBriefGlance.js`
- Create: `frontend/src/pages/admin/dailyBriefGlance.test.js`
- Modify: `frontend/src/pages/admin/DailyBriefPage.jsx`
- Modify: `docs/design/daily-brief-format.md`
- Modify: `docs/PRODUCT_STATUS.md`
- Modify: `docs/API_REFERENCE.md`

**Interfaces:**
- Consumes: `brief.stack_configured`, `brief.counts`
- Produces: `dailyBriefGlanceLines({ stackConfigured, counts }) -> string[]`

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/admin/dailyBriefGlance.test.js`:

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { dailyBriefGlanceLines } from './dailyBriefGlance.js'

describe('dailyBriefGlanceLines', () => {
  const zeros = {
    kev_new: 0,
    stack_matches: 0,
    watchlist: 0,
    ioc_hits: 0,
    critical_high_new: 0,
    ops_issues: 0,
  }

  it('omits My Stack when unconfigured', () => {
    const lines = dailyBriefGlanceLines({ stackConfigured: false, counts: zeros })
    assert.equal(lines.some((line) => line.includes('My Stack')), false)
    assert.equal(lines[0], 'New on CISA KEV: 0')
  })

  it('includes zero matches when configured', () => {
    const lines = dailyBriefGlanceLines({ stackConfigured: true, counts: zeros })
    assert.equal(lines.includes('Matches My Stack: 0'), true)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/pages/admin/dailyBriefGlance.test.js`

Expected: FAIL module not found.

- [ ] **Step 3: Implement helper + page + docs**

`dailyBriefGlance.js`:

```javascript
export function dailyBriefGlanceLines({ stackConfigured, counts = {} }) {
  const n = (key) => counts[key] ?? 0
  const lines = [`New on CISA KEV: ${n('kev_new')}`]
  if (stackConfigured) {
    lines.push(`Matches My Stack: ${n('stack_matches')}`)
  }
  lines.push(
    `Pinned-CVE alerts: ${n('watchlist')}`,
    `IOC watch hits: ${n('ioc_hits')}`,
    `New Critical or High: ${n('critical_high_new')}`,
    `Instance problems: ${n('ops_issues')}`,
  )
  return lines
}
```

On `DailyBriefPage.jsx` At a glance: `lineList(dailyBriefGlanceLines({ stackConfigured: Boolean(brief.stack_configured), counts: brief.counts }))`. Only render a **My Stack** section if one is added later; do not add a heading when unconfigured (preview already has no stack card).

Format doc: At a glance “always all six” → six when `stack_configured`; omit Matches My Stack otherwise. Quiet example: delete the `Matches My Stack: 0` line.

PRODUCT_STATUS Daily brief: glance omits My Stack unless admin stack is configured.

API_REFERENCE preview: `brief.stack_configured` (bool).

- [ ] **Step 4: Run tests**

Run: `cd frontend && node --test src/pages/admin/dailyBriefGlance.test.js && npm run test:unit`

Then: `./scripts/verify-local.sh`

Expected: green (SQLite fallback OK).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/dailyBriefGlance.js frontend/src/pages/admin/dailyBriefGlance.test.js frontend/src/pages/admin/DailyBriefPage.jsx docs/design/daily-brief-format.md docs/PRODUCT_STATUS.md docs/API_REFERENCE.md
git commit -m "fix(admin): daily brief preview omits unconfigured My Stack"
```

---

## Self-review

1. Spec coverage: omit glance / field / summary; configured zero still shown; payload flag; preview; docs; matcher untouched.
2. No TBD/placeholder steps.
3. `stack_configured` naming matches tests, payload, and frontend `brief.stack_configured`.
