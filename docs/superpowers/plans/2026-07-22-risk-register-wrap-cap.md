# Risk Register wrap + live-cap honesty — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wrap long Risk Register title/summary cells and tell operators when live self-stack rows are capped (showing N of M), without building in-app dependency remediation.

**Architecture:** Wire the DataGrid’s documented-but-missing per-column `wrap` flag. Extend `self_stack_risk_rows` / risks section payload with admission stats. Surface copy on Risk Register + optional overview tile help. Dependency upgrades remain manual (operator).

**Tech Stack:** React `DataGrid`, FastAPI `security_architecture/merge.py` + risks section router, pytest.

**Spec SSOT:** [`../specs/2026-07-22-ux-ops-rca-collection-design.md`](../specs/2026-07-22-ux-ops-rca-collection-design.md) Program D.  
**Related parked note:** `docs/superpowers/specs/2026-07-21-self-stack-risk-precision-design.md` (“Risk Register cell wrap UX”).

## Global Constraints

- Do not change CPE admission scores (55/100) in this program.
- Do not add dismiss/mute or auto-patch.
- Live list remains capped at 50 after scoring (existing); expose counts honestly.
- Semantic tokens only; DataGrid stays `table-layout: fixed` with shared `<col>`.
- Postgres + SQLite paths for any SQL touch — run default pytest; if `db/` SQL changes, also Postgres when available.
- Merge gate: `./scripts/verify-local.sh`.

---

### Task 1: DataGrid per-column wrap

**Files:**
- Modify: `frontend/src/components/ui/DataGrid.jsx` (`cellStyle`)
- Modify: `frontend/src/utils/dataGridStandardGate.test.js` (or new unit test)
- Modify: `frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx` (`wrap: true` on `title` + `summary`)

**Interfaces:**
- Consumes: column meta `wrap?: boolean` (default false)
- Produces: wrapped cells use `whiteSpace: 'normal'`, `overflowWrap: 'anywhere'` (or `break-word`), no ellipsis; non-wrap keep nowrap+ellipsis

- [ ] **Step 1: Failing gate test**

```js
it('DataGrid cellStyle honors column.wrap', () => {
  const src = readFileSync('frontend/src/components/ui/DataGrid.jsx', 'utf8')
  assert.match(src, /col\.wrap/)
  assert.match(src, /whiteSpace:\s*col\.wrap\s*\?\s*['"]normal['"]/)
})
```

- [ ] **Step 2: Implement `cellStyle`**

```js
const cellStyle = (col) => ({
  textAlign: col.align || 'center',
  whiteSpace: col.wrap ? 'normal' : 'nowrap',
  overflow: col.wrap ? 'visible' : 'hidden',
  textOverflow: col.wrap ? 'clip' : 'ellipsis',
  overflowWrap: col.wrap ? 'anywhere' : undefined,
  verticalAlign: 'top',
})
```

- [ ] **Step 3: Risk Register columns**

```js
{ id: 'title', label: 'Risk', minWidth: 220, wrap: true, align: 'left', render: ... }
{ id: 'summary', label: 'Mitigation / Summary', minWidth: 260, wrap: true, align: 'left', render: ... }
```

- [ ] **Step 4: Unit/gate + build + commit**

```bash
cd frontend && node --test src/utils/dataGridStandardGate.test.js && npm run build
git add frontend/src/components/ui/DataGrid.jsx frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx frontend/src/utils/dataGridStandardGate.test.js
git commit -m "fix(ui): DataGrid column wrap for Risk Register title/summary"
```

---

### Task 2: Live self-stack cap honesty in API + UI

**Files:**
- Modify: `backend/security_architecture/merge.py` (`self_stack_risk_rows` return shape **or** companion summary)
- Modify: `backend/security_architecture/routers/security_architecture.py` (risks section response)
- Modify: `frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx` (count line)
- Test: `backend/tests/test_security_architecture_self_stack_risk.py` (create/extend)

**Interfaces:**
- Prefer non-breaking additive fields on section payload:

```json
{
  "count": 12,
  "items": [ ... ],
  "live_self_stack": {
    "admitted": 12,
    "scored_matches": 87,
    "candidate_rows": 400,
    "cap": 50
  }
}
```

`self_stack_risk_rows` may return `(rows, stats)` or set stats on a module helper used by the router.

- [ ] **Step 1: Failing test**

```python
async def test_self_stack_risk_rows_reports_cap_stats(db, corpus_with_stack):
    rows, stats = await merge.self_stack_risk_rows_with_stats(db, corpus_with_stack)
    assert stats["cap"] == 50
    assert stats["admitted"] == len(rows)
    assert stats["scored_matches"] >= stats["admitted"]
```

Adapt to whatever signature you choose; keep `self_stack_risk_rows` returning list for callers (`self_cve_exposure_summary`) — add `self_stack_risk_stats` or tuple helper without breaking overview.

- [ ] **Step 2: Implement counting**

While building `live_rows`, track:
- `candidate_rows` = len(SQL result) before score filter
- `scored_matches` = len after score ∈ {55,100}
- `admitted` = len after `[:50]`
- `cap` = 50

- [ ] **Step 3: UI copy**

When `origin` filter is live/all and stats present:

```text
12 rows · live self-stack showing 12 of 87 matches (cap 50)
```

Only show “of M” when `scored_matches > admitted`.

- [ ] **Step 4: Docs**

PRODUCT_STATUS: Risk Register shows admission cap honesty.  
HANDOVER: wrap + cap; note manual patching still operator-owned.

- [ ] **Step 5: pytest + verify-local + commit**

```bash
cd backend && DATABASE_URL="" BRIEFR_REQUIRE_POSTGRES=0 python -m pytest tests/test_security_architecture_self_stack_risk.py -q
./scripts/verify-local.sh
git add backend/security_architecture/merge.py backend/security_architecture/routers/security_architecture.py frontend/src/pages/security-architecture/sections/RiskRegisterSection.jsx backend/tests/ docs/PRODUCT_STATUS.md docs/HANDOVER.md docs/API_REFERENCE.md
git commit -m "feat(secarch): Risk Register wrap + live self-stack cap honesty"
```

---

## Self-review

| Spec item | Task |
|-----------|------|
| Cell wrap | Task 1 |
| Cap honesty | Task 2 |
| No dismiss/mute / no auto-patch | Honored |
| CSV export still current view | Unchanged (document in HANDOVER) |
