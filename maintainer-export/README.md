# Maintainer export — study guide interview section

This folder is a **drop-in package** for the private [`briefr-maintainer`](https://github.com/Soldier0x0/briefr-maintainer) repository. It is **not** part of the public `briefr` product repo (study guide migrated out in PR #751).

## What this adds

**Part VII · Interview preparation** — **16 HTML pages**, **363 categorized Q&A**, inserted **after Roadmap** and **before Glossary**.

Addresses [briefr#498](https://github.com/Soldier0x0/briefr/issues/498) including work merged **after** the issue was filed (2026-07-13) — correlation v3 Phase 4 (CORR-PR-6…13), SigmaHQ index, Program E AI ops, auth #731, deploy #745, Apache 2.0 #748, etc.

| Page | Topic |
|------|--------|
| `iv-part.html` | How to use this section |
| `iv-architecture.html` | Architecture & system design |
| `iv-security.html` | Security & trust boundaries |
| `iv-secarch-threatmodel.html` | **Security architecture & TM-6** (PM-3/4) |
| `iv-backend-db.html` | Backend & database |
| `iv-nvd-pipeline.html` | NVD ingestion & feed pipeline |
| `iv-ingest-scheduler.html` | Ingest & scheduler |
| `iv-correlation-scoring.html` | Correlation & scoring (+ v3 Phase 4) |
| `iv-campaign-ioc.html` | Campaign, IOC & graph logic |
| `iv-ml-embeddings.html` | ML & embeddings |
| `iv-detection-forge.html` | Detection & Forge |
| `iv-frontend-ux.html` | Frontend & UX |
| `iv-api-ops.html` | API & operations |
| `iv-devops-deploy.html` | DevOps & deploy |
| `iv-tests-docs.html` | Tests, docs & roadmap |
| `iv-product-behavioral.html` | Product, behavioral & solo owner |

Each chapter groups questions by issue #498 categories:
**What it does · Implementation · Integration · Failure modes · Performance · Security · Tradeoffs**

### Source files

| File | Role |
|------|------|
| `interview_qa_data.py` | Base 12 chapters (~300 Q) |
| `interview_qa_extra.py` | Priority chapters (NVD, campaign/IOC, tests) |
| `interview_qa_gap_fill.py` | Post–#498 merge coverage + secarch chapter |
| `category_utils.py` | Category inference + ordering |
| `generate_interview_guide.py` | HTML generator |

### Coverage honesty

**Covered well:** ingest/NVD, scoring/OP, detection/SigmaHQ, scheduler locks, auth/sessions, admin ops, embeddings/LLM, Forge, FEED/drawer patterns, webhooks/notifications, stack backfill, Procrastinate basics, correlation v3 tail, security architecture graph.

**Still thinner (every file/module not enumerated):** line-by-line router inventory, every Alembic revision, every admin page field, Playwright smoke steps, MkDocs portal, parked STIX/composer UX, full multi-worker production war stories. The companion study guide Parts I–VI remain the module-deep reference; Part VII is interview Q&A, not a second codebase walk.

**Regenerate after code changes:** edit the `interview_qa_*.py` files, run generator, re-read `PRODUCT_STATUS.md` for drift.

## Copy into `briefr-maintainer`

```bash
git clone git@github.com:Soldier0x0/briefr-maintainer.git
cd briefr-maintainer

rsync -av /path/to/maintainer-export/study-guide/ docs/study-guide/
mkdir -p scripts/maintainer
cp /path/to/maintainer-export/*.py scripts/maintainer/

git add docs/study-guide scripts/maintainer
git commit -m "docs(study-guide): Part VII interview prep for briefr#498 (363 Q&A)"
git push
```

## Regenerate

```bash
cd maintainer-export
python3 generate_interview_guide.py
```

## Related GitHub issue

[Soldier0x0/briefr#498](https://github.com/Soldier0x0/briefr/issues/498)
