# Study Guide Truth Hardening (Phase 0) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Drive the study-guide inventory to Phase 0 ship gates (G1–G5): every in-scope file is `covered` or explicit justified `out_of_scope`, claims match HEAD/`PRODUCT_STATUS`, book regenerates cleanly — before any multi-profile learn repo.

**Architecture:** Upgrade `scripts/audit_study_guide.py` with a `--strict` ship mode and clearer out-of-scope rules for FE gate tests and empty package markers. Then directory-sweep `docs/STUDY_GUIDE.html` chips/How text by reading real modules, regenerate `docs/study-guide/`, and re-audit until `weak=0` under policy. Phase 1 (profiles / `docs.`) stays blocked.

**Tech Stack:** Python auditor + pytest; HTML textbook; `scripts/build_study_guide_book.py`.

## Global Constraints

- Facts only from HEAD code and `docs/PRODUCT_STATUS.md` (code wins).
- Editable SSOT remains `docs/STUDY_GUIDE.html`; never hand-edit `docs/study-guide/`.
- `gap` must stay `0` after every content PR.
- Phase 1 learn-repo / profile pathways are **forbidden** until G1–G5 green.
- Branch pattern: `cursor/study-guide-truth-<topic>-9180`.
- Prefer reading each module over inventing How prose.
- After content edits: `backend/.venv/bin/python scripts/build_study_guide_book.py` then `backend/.venv/bin/python scripts/audit_study_guide.py`.

## Baseline (2026-07-19)

- covered **441** / weak **244** / gap **0** / orphan **1** (`backend/db/dialect.py` intentional)
- Weak breakdown: ~54 `*.test.js`, ~43 `.css`, ~24 `__init__.py`, ~123 other code

## File map

| Path | Role |
|------|------|
| `scripts/audit_study_guide.py` | Inventory + `--strict` + OOS rules |
| `backend/tests/test_audit_study_guide.py` | Auditor regression |
| `docs/STUDY_GUIDE.html` | All prose/chip edits |
| `docs/study-guide/**` | Generated only |
| `docs/planning/specs/study-guide-audit/*` | Regenerated reports |
| `docs/planning/specs/study-guide-audit/STALE_CLAIMS.md` | Claim RCA |
| `docs/HANDOVER.md` | Update protocol + progress |
| `docs/superpowers/specs/2026-07-19-study-guide-truth-hardening-design.md` | Design SSOT |

---

### Task 1: Auditor `--strict` + FE test / empty-init OOS

**Files:**
- Modify: `scripts/audit_study_guide.py`
- Modify: `backend/tests/test_audit_study_guide.py`
- Modify: `docs/HANDOVER.md` (Phase 0 pointer + update protocol one-liner)

**Interfaces:**
- Consumes: existing `classify_files` / `run` / `main`
- Produces: `main([...])` returns exit code `1` when `--strict` and (`gap>0` or `weak>0`); `*.test.js` under `frontend/src/` classified `out_of_scope`; empty (or docstring-only) package `__init__.py` under inventory roots classified `out_of_scope` with notes

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_audit_study_guide.py`:

```python
def test_frontend_test_js_is_out_of_scope(audit, tmp_path: Path):
    (tmp_path / "frontend" / "src" / "utils").mkdir(parents=True)
    (tmp_path / "frontend" / "src" / "utils" / "cveFilters.js").write_text("export {}", encoding="utf-8")
    (tmp_path / "frontend" / "src" / "utils" / "cveFilters.test.js").write_text("test", encoding="utf-8")
    (tmp_path / "backend").mkdir()
    (tmp_path / "deploy").mkdir()
    inventory = audit.iter_inventory_files(tmp_path)
    assert "frontend/src/utils/cveFilters.test.js" in inventory
    chapters = {
        "fe-shared-utils": audit.Chapter(
            id="fe-shared-utils",
            title="Utils",
            mentioned_paths={"frontend/src/utils/cveFilters.js"},
        )
    }
    rows = audit.classify_files(inventory, chapters, chapters["fe-shared-utils"].mentioned_paths, root=tmp_path)
    by = {r.path: r for r in rows}
    assert by["frontend/src/utils/cveFilters.js"].status == "covered"
    assert by["frontend/src/utils/cveFilters.test.js"].status == "out_of_scope"
    assert "gate" in by["frontend/src/utils/cveFilters.test.js"].notes.lower() or "test" in by["frontend/src/utils/cveFilters.test.js"].notes.lower()


def test_empty_package_init_is_out_of_scope(audit, tmp_path: Path):
    (tmp_path / "backend" / "feeds").mkdir(parents=True)
    (tmp_path / "backend" / "feeds" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "backend" / "feeds" / "nvd.py").write_text("x", encoding="utf-8")
    (tmp_path / "frontend" / "src").mkdir(parents=True)
    (tmp_path / "deploy").mkdir()
    inventory = audit.iter_inventory_files(tmp_path)
    chapters = {
        "in-feeds": audit.Chapter(
            id="in-feeds",
            title="Feeds",
            mentioned_paths={"backend/feeds/nvd.py"},
        )
    }
    rows = audit.classify_files(
        inventory, chapters, {"backend/feeds/nvd.py"}, root=tmp_path
    )
    by = {r.path: r for r in rows}
    assert by["backend/feeds/__init__.py"].status == "out_of_scope"


def test_strict_exits_nonzero_on_weak(audit, tmp_path: Path, monkeypatch):
    guide = tmp_path / "STUDY_GUIDE.html"
    guide.write_text(
        """
        <nav id="toc"><a class="toc-link" href="#in-feeds">Feeds</a></nav>
        <section class="page chapter" id="in-feeds">
          <span class="chip">backend/feeds/nvd.py</span>
        </section>
        """,
        encoding="utf-8",
    )
    root = tmp_path / "repo"
    (root / "backend" / "feeds").mkdir(parents=True)
    (root / "backend" / "feeds" / "nvd.py").write_text("x", encoding="utf-8")
    (root / "backend" / "feeds" / "kev.py").write_text("x", encoding="utf-8")
    (root / "frontend" / "src").mkdir(parents=True)
    (root / "deploy").mkdir()
    out = tmp_path / "out"
    code = audit.main(["--guide", str(guide), "--out", str(out), "--root", str(root), "--strict"])
    assert code == 1
```

- [ ] **Step 2: Run tests — expect FAIL**

```bash
cd /workspace/backend && .venv/bin/python -m pytest tests/test_audit_study_guide.py::test_frontend_test_js_is_out_of_scope tests/test_audit_study_guide.py::test_empty_package_init_is_out_of_scope tests/test_audit_study_guide.py::test_strict_exits_nonzero_on_weak -q --tb=short
```

Expected: FAIL (functions/flags missing).

- [ ] **Step 3: Implement minimal auditor changes**

In `scripts/audit_study_guide.py`:

1. Add helpers:

```python
def is_frontend_gate_test(path: str) -> bool:
    return path.startswith("frontend/src/") and path.endswith(".test.js")


def is_empty_package_init(path: str, root: Path = ROOT) -> bool:
    if not path.endswith("/__init__.py"):
        return False
    fp = root / path
    if not fp.is_file():
        return False
    text = fp.read_text(encoding="utf-8", errors="replace").strip()
    # empty or module docstring / comments only
    if not text:
        return True
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not lines:
        return True
    if len(lines) == 1 and (lines[0].startswith('"""') or lines[0].startswith("'''")):
        return True
    return False
```

2. In `classify_files`, before sibling `weak` assignment for inventory files, if `is_frontend_gate_test(path)` or `is_empty_package_init(path, root)` → append `FileRow(..., status="out_of_scope", notes=...)` and continue.

3. Also emit aggregate OOS rows (optional):

```python
FileRow(path="frontend/src/**/*.test.js", status="out_of_scope", notes="FE gate/unit tests; aggregate into Testing strategy")
```

4. `main`: add `--strict`; after `run`, if `--strict` and (`counts['gap']>0` or `counts['weak']>0`): print error to stderr and `return 1`.

- [ ] **Step 4: Re-run tests — expect PASS**

```bash
cd /workspace/backend && .venv/bin/python -m pytest tests/test_audit_study_guide.py -q --tb=short
```

Expected: PASS.

- [ ] **Step 5: Re-audit repo (non-strict) and commit**

```bash
cd /workspace && backend/.venv/bin/python scripts/audit_study_guide.py
# note new weak count (should drop by ~test.js + empty inits)
git add scripts/audit_study_guide.py backend/tests/test_audit_study_guide.py docs/planning/specs/study-guide-audit docs/HANDOVER.md
git commit -m "feat(audit): strict mode and OOS for FE tests and empty inits"
```

---

### Task 2: Cover `backend/ai/` weak modules

**Files:**
- Modify: `docs/STUDY_GUIDE.html` (chapters `ie-ml-providers` / `ie-ml` / related)
- Regenerate: `docs/study-guide/`
- Reports: re-run auditor

**Interfaces:**
- Consumes: real files under `backend/ai/`
- Produces: each non-OOS `backend/ai/*.py` mentioned via chip in the right chapter

- [ ] **Step 1: List remaining weak under backend/ai**

```bash
backend/.venv/bin/python scripts/audit_study_guide.py
# grep inventory.md for backend/ai
```

- [ ] **Step 2: Read each weak module’s top docstring/exports** (e.g. `gemini_client.py`, `groq_config.py`, `llm_payload.py`, `llm_session.py`, `openai_chat.py`, `operations_admin.py`).

- [ ] **Step 3: Add `<span class="chip">…</span>` entries + one factual How sentence each** in the existing ML providers chapter (do not invent APIs).

- [ ] **Step 4: Rebuild + audit; assert no `backend/ai/` weak rows**

```bash
backend/.venv/bin/python scripts/build_study_guide_book.py
backend/.venv/bin/python scripts/audit_study_guide.py
```

- [ ] **Step 5: Commit**

```bash
git commit -m "docs: cover backend/ai modules in study guide"
```

---

### Task 3: Cover `backend/detection/` weak modules

**Files:** `docs/STUDY_GUIDE.html` (`ie-detection`), regenerate book

- [ ] **Step 1: List weak detection paths from inventory**
- [ ] **Step 2: Read each file; add chips + factual How bullets** for: `artifact_extract.py`, `class_queries.py`, `context_llm_sync.py`, `context_nuclei_sync.py`, `context_sync.py`, `nuclei_parser.py`, `rule_sources.py`, `siem_queries.py`, `yara_generator.py` (skip OOS `__init__.py`)
- [ ] **Step 3: Rebuild + audit; no `backend/detection/` weak**
- [ ] **Step 4: Commit** `docs: cover backend/detection modules in study guide`

---

### Task 4: Cover `backend/feeds/` weak modules

**Files:** `docs/STUDY_GUIDE.html` (`in-feeds`), regenerate book

- [ ] **Step 1: List weak feed paths**
- [ ] **Step 2: Read each; add chips + one-line job** for all non-OOS weak feeds (atlas, osv, otx, exploit_*, incident_*, etc.)
- [ ] **Step 3: Rebuild + audit; no `backend/feeds/` weak**
- [ ] **Step 4: Commit** `docs: cover backend/feeds modules in study guide`

---

### Task 5: Cover remaining small backend weak set

**Files:** `docs/STUDY_GUIDE.html` (api-ops, be-auth, wallboard, scripts, etc.)

Weak leftovers after Tasks 1–4 typically include: `backend/wallboard/session.py`, `backend/scripts/delete_user.py`, singleton package dirs already OOS, `backend/security_architecture/routers/__init__.py` (OOS if empty).

- [ ] **Step 1: Dump remaining `backend/` weak paths**
- [ ] **Step 2: Cover each real module with chip + fact**
- [ ] **Step 3: Rebuild + audit**
- [ ] **Step 4: Commit** `docs: cover remaining backend weak inventory`

---

### Task 6: Cover `frontend/src/hooks` + high-value `pages`/`components` code (non-CSS)

**Files:** `docs/STUDY_GUIDE.html` (`fe-shared-utils`, `fe-analyst-shell`, `fe-admin-shell`, `fe-forge-wallboard`)

- [ ] **Step 1: List weak non-`.css` under `frontend/src/hooks`, `pages`, `components`**
- [ ] **Step 2: Read + chip each JS/JSX module with a one-line job**
- [ ] **Step 3: Rebuild + audit**
- [ ] **Step 4: Commit**

---

### Task 7: Cover `frontend/src/utils` code modules

**Files:** `docs/STUDY_GUIDE.html` (`fe-shared-utils` or split tables)

~50+ non-test utils after Task 1 OOS. Batch in one or two PRs; every path must appear as a chip or glob that expands to it.

- [ ] **Step 1: Prefer exact chips or precise globs** (`utils/export*.js`) that the auditor expands
- [ ] **Step 2: Add a mini-table of module → job for the densest groups**
- [ ] **Step 3: Rebuild + audit until no `frontend/src/utils` weak code rows**
- [ ] **Step 4: Commit**

---

### Task 8: Cover companion `.css` files

**Files:** `docs/STUDY_GUIDE.html`

Policy: each `Foo.css` is covered by naming it in the same chapter as `Foo.jsx`/`Foo.tsx` (chip). Do not invent styling claims beyond “stylesheet for X”.

- [ ] **Step 1: List remaining weak `*.css`**
- [ ] **Step 2: Add chips next to their component chapters**
- [ ] **Step 3: Rebuild + audit; `weak=0`**
- [ ] **Step 4: Commit**

---

### Task 9: Claim RCA + enable strict in verify path + Phase 0 closeout

**Files:**
- `docs/planning/specs/study-guide-audit/STALE_CLAIMS.md`
- `docs/HANDOVER.md`
- Optionally wire `--strict` into `scripts/verify-local.sh` or a dedicated gate script
- Mark design status Approved/Implemented for Phase 0 gates

- [ ] **Step 1: Diff guide claims vs `PRODUCT_STATUS.md` Embeddings/Auth/Postgres rows; fix or RCA**
- [ ] **Step 2: Run**

```bash
backend/.venv/bin/python scripts/build_study_guide_book.py
backend/.venv/bin/python scripts/audit_study_guide.py --strict
cd backend && .venv/bin/python -m pytest tests/test_audit_study_guide.py tests/test_build_study_guide_book.py -q
```

Expected: exit 0; `weak=0`; `gap=0`.

- [ ] **Step 3: HANDOVER — Phase 0 green; next = Phase 1 learn-repo design**
- [ ] **Step 4: Final commit + PR**

---

## Verification matrix (every PR)

| Check | Command | Pass |
|-------|---------|------|
| Auditor unit | `pytest backend/tests/test_audit_study_guide.py -q` | green |
| Builder unit | `pytest backend/tests/test_build_study_guide_book.py -q` | green |
| Audit report | `python scripts/audit_study_guide.py` | `gap=0`; weak decreasing |
| Strict (from Task 9) | `python scripts/audit_study_guide.py --strict` | exit 0 |
| Book | `python scripts/build_study_guide_book.py` | exit 0 |

## Self-review

1. **Spec coverage:** G1–G5 → Tasks 1+9; weak sweeps → Tasks 2–8; update protocol → HANDOVER in Task 1/9; Phase 1 blocked → Global Constraints.
2. **Placeholders:** none.
3. **Consistency:** chapter ids match existing TOC; `--strict` semantics match design G1/G2.

## Execution order

1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9 (no Phase 1 in this plan).
