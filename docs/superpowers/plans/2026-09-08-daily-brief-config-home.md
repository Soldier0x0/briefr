# Daily brief page + config home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Operators enable EOD and standup independently on Daily brief with honest GET config, then see process-env pins and secret-not-in-DB warnings on Config.

**Architecture:** Reuse `POST /api/admin/config` and `persist_operator_setting`. Wave 1 fills missing `DAILY_BRIEF_*` keys on GET and adds schedule controls on `DailyBriefPage`. Wave 2 returns `meta` + `persisted_to_db`. No new event types. No auto-subscribe.

**Tech Stack:** FastAPI, `config_schema` / `operator_settings`, React admin (`ToggleSwitch`, `Select`), node:test for copy helpers, pytest.

**Spec:** `docs/superpowers/specs/2026-09-08-daily-brief-config-home-design.md`  
**Unified plan:** `docs/plans/2026-09-08-001-feat-daily-brief-config-home-plan.md`

## Global Constraints

- Process env (`PROCESS_ENV_KEYS`) still wins over `app_settings`.
- Secret-typed keys never persist plaintext; skip DB when `BRIEFR_SETTINGS_KEY` is unset (ADR-006).
- One `daily_brief` subscription covers both slots. Do not auto-tick dest events.
- Slot control is Preview/test only.
- Merge gate `./scripts/verify-local.sh`. Update PRODUCT_STATUS + API_REFERENCE with behavior.
- Dark admin tokens; `ToggleSwitch` / existing `admin-*` classes. No new primary color.

---

### Task 1: GET `/api/admin/config` includes daily-brief keys

**Files:**
- Modify: `backend/routers/admin/config.py` (`_get_config_response` `scheduler` and `ml` dicts)
- Test: `backend/tests/test_admin_config.py`

**Interfaces:**
- Consumes: `_env`, `_env_int` in `config.py`
- Produces: `scheduler.DAILY_BRIEF_EOD_ENABLED` etc. as strings/ints matching sibling keys

- [ ] **Step 1: Write the failing test**

Add to `backend/tests/test_admin_config.py`:

```python
def test_config_includes_daily_brief_defaults(admin_client):
    data = admin_client.get("/api/admin/config").json()
    sched = data["scheduler"]
    assert sched["DAILY_BRIEF_EOD_ENABLED"] == "0"
    assert sched["DAILY_BRIEF_STANDUP_ENABLED"] == "0"
    assert sched["DAILY_BRIEF_EOD_HOUR"] == 18
    assert sched["DAILY_BRIEF_EOD_MINUTE"] == 0
    assert sched["DAILY_BRIEF_STANDUP_HOUR"] == 7
    assert sched["DAILY_BRIEF_STANDUP_MINUTE"] == 0
    assert data["ml"]["DAILY_BRIEF_LLM_ENABLED"] == "0"


def test_config_daily_brief_enabled_round_trip(admin_client):
    r = admin_client.post("/api/admin/config", json={"key": "DAILY_BRIEF_EOD_ENABLED", "value": "1"})
    assert r.status_code == 200
    sched = admin_client.get("/api/admin/config").json()["scheduler"]
    assert sched["DAILY_BRIEF_EOD_ENABLED"] == "1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_admin_config.py::test_config_includes_daily_brief_defaults -q`

Expected: FAIL (`KeyError` or `None`) because `_get_config_response` omits these keys.

- [ ] **Step 3: Write minimal implementation**

In `_get_config_response` `scheduler` dict, after `CACHE_REFRESH_MINUTE` (or adjacent cron keys), add:

```python
"DAILY_BRIEF_EOD_ENABLED": _env("DAILY_BRIEF_EOD_ENABLED", "0"),
"DAILY_BRIEF_STANDUP_ENABLED": _env("DAILY_BRIEF_STANDUP_ENABLED", "0"),
"DAILY_BRIEF_EOD_HOUR": _env_int("DAILY_BRIEF_EOD_HOUR", 18),
"DAILY_BRIEF_EOD_MINUTE": _env_int("DAILY_BRIEF_EOD_MINUTE", 0),
"DAILY_BRIEF_STANDUP_HOUR": _env_int("DAILY_BRIEF_STANDUP_HOUR", 7),
"DAILY_BRIEF_STANDUP_MINUTE": _env_int("DAILY_BRIEF_STANDUP_MINUTE", 0),
```

In `ml` dict add:

```python
"DAILY_BRIEF_LLM_ENABLED": _env("DAILY_BRIEF_LLM_ENABLED", "0"),
```

- [ ] **Step 4: Run the tests and make sure they pass**

Run: `cd backend && pytest tests/test_admin_config.py::test_config_includes_daily_brief_defaults tests/test_admin_config.py::test_config_daily_brief_enabled_round_trip -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/routers/admin/config.py backend/tests/test_admin_config.py
git commit -m "fix(admin): expose daily brief flags on GET /config"
```

---

### Task 2: Daily brief copy helper + schedule UI

**Files:**
- Create: `frontend/src/pages/admin/dailyBriefCopy.js`
- Create: `frontend/src/pages/admin/dailyBriefCopy.test.js`
- Modify: `frontend/src/pages/admin/DailyBriefPage.jsx`
- Modify: `frontend/src/pages/admin/DailyBriefPage.css`

**Interfaces:**
- Consumes: `GET /config` keys from Task 1; `GET /webhooks/destinations`
- Produces: `dailyBriefDeliveryCopy({ loading, error, labels })` → `{ kind: 'loading'|'error'|'empty'|'ok', text }`

- [ ] **Step 1: Write the failing test**

`frontend/src/pages/admin/dailyBriefCopy.test.js`:

```javascript
import { describe, it } from 'node:test'
import assert from 'node:assert/strict'
import { dailyBriefDeliveryCopy } from './dailyBriefCopy.js'

describe('dailyBriefDeliveryCopy', () => {
  it('alerts when nothing is subscribed', () => {
    const out = dailyBriefDeliveryCopy({ loading: false, error: null, labels: [] })
    assert.equal(out.kind, 'empty')
    assert.match(out.text, /Daily brief/i)
  })

  it('lists destination labels when subscribed', () => {
    const out = dailyBriefDeliveryCopy({
      loading: false,
      error: null,
      labels: ['discord'],
    })
    assert.equal(out.kind, 'ok')
    assert.match(out.text, /discord/)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && node --test src/pages/admin/dailyBriefCopy.test.js`

Expected: FAIL module not found.

- [ ] **Step 3: Implement helper + page**

`dailyBriefCopy.js` exports `dailyBriefDeliveryCopy` as in the test.

On `DailyBriefPage.jsx`:

- Load `adminApi.getJson('/config')` with destinations.
- Two `ToggleSwitch` (`DAILY_BRIEF_EOD_ENABLED`, `DAILY_BRIEF_STANDUP_ENABLED`) posting `{ key, value: next ? '1' : '0' }`.
- Hour/minute number inputs posting the matching `*_HOUR` / `*_MINUTE` keys. Show `config.scheduler.SCHEDULER_TIMEZONE`.
- Rename Slot label to **Preview / test slot**. `setSlot` must not POST enable keys.
- Delivery: if `kind === 'empty'`, use `className="daily-brief-error"` and keep the Webhooks `Link`.
- Subtitle: enable on this page, then subscribe dests; real-time stays on Webhooks.

Disable all schedule controls while any POST is in flight (`busy` string). Pattern: `AiOperationsPage` `busyProvider`.

CSS: schedule row uses existing `admin-filter-bar`; no max-width centering.

- [ ] **Step 4: Run tests**

Run: `cd frontend && node --test src/pages/admin/dailyBriefCopy.test.js && npm run test:unit`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/dailyBriefCopy.js frontend/src/pages/admin/dailyBriefCopy.test.js frontend/src/pages/admin/DailyBriefPage.jsx frontend/src/pages/admin/DailyBriefPage.css
git commit -m "feat(admin): enable both daily brief slots on the report page"
```

---

### Task 3: persist_operator_setting result + config meta

**Files:**
- Modify: `backend/operator_settings.py`
- Modify: `backend/routers/admin/config.py` (`set_config`, `apply_all_config`, `_get_config_response`)
- Test: `backend/tests/test_operator_settings.py`, `backend/tests/test_admin_config.py`

**Interfaces:**
- Consumes: `PROCESS_ENV_KEYS`, `WRITABLE_CONFIG_KEYS`, `encrypt_secret`
- Produces: `persist_operator_setting` → `dict` with `persisted_to_db: bool` and optional `warning: str`

- [ ] **Step 1: Write the failing test**

```python
def test_config_secret_without_settings_key_warns(admin_client, monkeypatch):
    monkeypatch.delenv("BRIEFR_SETTINGS_KEY", raising=False)
    r = admin_client.post(
        "/api/admin/config",
        json={"key": "DISCORD_WEBHOOK_URL", "value": "https://discord.com/api/webhooks/1/aaa"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["persisted_to_db"] is False
    assert "warning" in body and body["warning"]


def test_config_meta_process_pinned_keys(admin_client, monkeypatch):
    data = admin_client.get("/api/admin/config").json()
    assert "meta" in data
    assert "settings_key_configured" in data["meta"]
    assert isinstance(data["meta"]["process_pinned_keys"], list)
```

Monkeypatch `PROCESS_ENV_KEYS` in the GET test if the default env in tests includes a writable key; assert membership of a key you add to the frozenset.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_admin_config.py::test_config_secret_without_settings_key_warns tests/test_admin_config.py::test_config_meta_process_pinned_keys -q`

Expected: FAIL missing keys.

- [ ] **Step 3: Implementation**

`persist_operator_setting`: on encrypt `None` path, return `{"persisted_to_db": False, "warning": "Secret not stored in the database (set BRIEFR_SETTINGS_KEY). This process holds it until restart."}`. After successful `set_app_setting` commit, return `{"persisted_to_db": True, "warning": None}`.

`set_config` / `apply_all`: merge last write’s `persisted_to_db` (False if any secret skipped).

GET: `"meta": {"settings_key_configured": bool(os.environ.get("BRIEFR_SETTINGS_KEY", "").strip()), "process_pinned_keys": sorted(k for k in WRITABLE_CONFIG_KEYS if k in PROCESS_ENV_KEYS)}`.

Do not put secret *values* in `meta`.

- [ ] **Step 4: Run tests**

Run: `cd backend && pytest tests/test_admin_config.py tests/test_operator_settings.py -q`

Expected: PASS (fix any persist return-value callers).

- [ ] **Step 5: Commit**

```bash
git add backend/operator_settings.py backend/routers/admin/config.py backend/tests/test_admin_config.py backend/tests/test_operator_settings.py
git commit -m "feat(admin): config meta pins and secret persist warning"
```

---

### Task 4: Config UI badges, env.example, living docs

**Files:**
- Modify: `frontend/src/pages/admin/ApiKeysPage.jsx`
- Modify: `backend/.env.example`
- Modify: `docs/PRODUCT_STATUS.md`
- Modify: `docs/API_REFERENCE.md`
- Modify: `docs/decisions/ADR-006-encrypted-app-settings-secrets.md` only if it still says Admin save writes `.env` for secrets (align to: process `os.environ` this run; DB only with settings key; JWT generate still `set_key`)

**Interfaces:**
- Consumes: `config.meta` from Task 3
- Produces: pin badge; toast `data.warning`

- [ ] **Step 1: UI**

In `ConfigRow`, if `config.meta.process_pinned_keys.includes(envKey)`, render `<span className="badge badge-warn">pinned by process env</span>` with title: restart restores the pin.

`saveKey`: if `data.warning`, toast that string (keep success variant or warning — warning is clearer).

Daily brief HelpTip already covers subscribe; add one line on Webhooks legacy bootstrap if missing: explicit `DISCORD_WEBHOOK_EVENTS` does not auto-gain `daily_brief`.

- [ ] **Step 2: `.env.example`**

At top, after the copy-to-`.env` line, add:

```bash
# Bootstrap (host / first boot): DATABASE_URL, JWT_SECRET, BRIEFR_SETTINGS_KEY, ALLOWED_ORIGINS.
# Operator toggles (daily brief, most scheduler bools): Admin → API keys & config (app_settings).
# Keys listed below as comments are optional process pins — if set in systemd they win over Admin.
```

Keep `DAILY_BRIEF_*` commented. Add to Discord events comment: `# include daily_brief for scheduled briefs, or leave blank for all events`.

- [ ] **Step 3: Living docs**

PRODUCT_STATUS Daily brief: enables live on Daily brief page; GET config includes flags; subscribe still Webhooks. Admin operator-settings: process env wins; secrets need `BRIEFR_SETTINGS_KEY`; Admin Save does **not** rewrite `.env` except generated `JWT_SECRET`.

API_REFERENCE: document GET `scheduler.DAILY_BRIEF_*`, `meta.process_pinned_keys`, POST `persisted_to_db`.

- [ ] **Step 4: verify-local**

Run: `./scripts/verify-local.sh`

Expected: green (SQLite fallback OK).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/admin/ApiKeysPage.jsx backend/.env.example docs/PRODUCT_STATUS.md docs/API_REFERENCE.md docs/decisions/ADR-006-encrypted-app-settings-secrets.md
git commit -m "docs(admin): config-home honesty and env.example bootstrap split"
```

---

## Self-review

1. Spec coverage: Wave 1 R1–R5 → Tasks 1–2; Wave 2 R6–R9 → Tasks 3–4. Auto-subscribe absent by design.
2. No TBD/placeholder steps.
3. `persisted_to_db` naming matches tests and API_REFERENCE.
