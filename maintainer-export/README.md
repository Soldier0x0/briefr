# Maintainer export — study guide interview section

Drop-in package for private [`briefr-maintainer`](https://github.com/Soldier0x0/briefr-maintainer) (`docs/study-guide/`). Addresses [briefr#498](https://github.com/Soldier0x0/briefr/issues/498).

## Scale

| Part | Pages | Questions | Purpose |
|------|-------|-----------|---------|
| **VII · Interview preparation** | 16 | 363 | Thematic depth (architecture, NVD, correlation, auth, …) |
| **VIII · Component reference** | 15 | 541 | **One Q&A per product module** + every scheduler job |
| **Total** | **31** | **904** | |

**Coverage gate:** `python3 verify_component_coverage.py` asserts every backend `.py` (excl. tests/alembic) and frontend `src` `.js/.jsx` (excl. tests) plus all 30 scheduler job ids appear in `component_registry.json`.

## Source files

| File | Role |
|------|------|
| `interview_qa_data.py` | Thematic chapters (Part VII) |
| `interview_qa_extra.py` | Priority-area chapters |
| `interview_qa_gap_fill.py` | Post–#498 merge gap fill + secarch chapter |
| `interview_qa_components.py` | **Generated** — Part VIII per-file Q&A |
| `build_component_qa.py` | Regenerate `interview_qa_components.py` from repo tree |
| `component_registry.json` | Machine-readable component inventory |
| `verify_component_coverage.py` | Fails if any product module is missing |
| `category_utils.py` | Category ordering for Part VII |
| `generate_interview_guide.py` | Writes all `iv-*.html` pages + TOC |

## Regenerate

```bash
cd maintainer-export
python3 build_component_qa.py      # refresh Part VIII from codebase
python3 generate_interview_guide.py
python3 verify_component_coverage.py
```

## Copy to briefr-maintainer

```bash
rsync -av maintainer-export/study-guide/ docs/study-guide/
mkdir -p scripts/maintainer
cp maintainer-export/*.py scripts/maintainer/
cp maintainer-export/component_registry.json scripts/maintainer/
```

## What Part VIII is / isn't

**Is:** complete inventory — every product source file and scheduler job has at least one interview question naming the path. Answers use module docstrings where present, plus hand-tuned overrides for critical modules.

**Isn't:** line-by-line function coverage inside each file. For that, use study-guide Parts I–VI module chapters. Generic fallback text (`Product module <code>…</code>`) appears when a file has no docstring — re-run `build_component_qa.py` after adding module docs, or add entries to `OVERRIDES` in `build_component_qa.py`.

## Thematic gaps vs component index

Part VII still carries **category-tagged depth** (failure modes, tradeoffs, integration). Part VIII guarantees **no component is unnamed**. Read both: VII for “how would you design/debug this?” and VIII for “what does this file do?”
