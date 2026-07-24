# Maintainer export — study guide interview section

This folder is a **drop-in package** for the private [`briefr-maintainer`](https://github.com/Soldier0x0/briefr-maintainer) repository. It is **not** part of the public `briefr` product repo (study guide migrated out in PR #751).

## What this adds

**Part VII · Interview preparation** — 15 HTML pages inserted **after Roadmap** and **before Glossary** (self-check remains last). Addresses [briefr#498](https://github.com/Soldier0x0/briefr/issues/498).

| Page | Topic |
|------|--------|
| `iv-part.html` | How to use this section |
| `iv-architecture.html` | Architecture & system design |
| `iv-security.html` | Security & trust boundaries |
| `iv-backend-db.html` | Backend & database |
| `iv-nvd-pipeline.html` | **NVD ingestion & feed pipeline** (priority) |
| `iv-ingest-scheduler.html` | Ingest & scheduler |
| `iv-correlation-scoring.html` | Correlation & scoring |
| `iv-campaign-ioc.html` | **Campaign, IOC & graph logic** (priority) |
| `iv-ml-embeddings.html` | ML & embeddings |
| `iv-detection-forge.html` | Detection & Forge |
| `iv-frontend-ux.html` | Frontend & UX |
| `iv-api-ops.html` | API & operations |
| `iv-devops-deploy.html` | DevOps & deploy |
| `iv-tests-docs.html` | **Tests, docs & roadmap** (priority) |
| `iv-product-behavioral.html` | Product, behavioral & solo owner |

**300 interview Q&A pairs** (209 base + 91 priority-area expansion), each categorized into:

- What it does · Core implementation · Integration · Failure modes & edge cases · Performance · Security · Architecture tradeoffs

## Copy into `briefr-maintainer`

```bash
git clone git@github.com:Soldier0x0/briefr-maintainer.git
cd briefr-maintainer

rsync -av /path/to/maintainer-export/study-guide/ docs/study-guide/

mkdir -p scripts/maintainer
cp /path/to/maintainer-export/*.py scripts/maintainer/

git add docs/study-guide scripts/maintainer
git commit -m "docs(study-guide): Part VII interview prep for briefr#498"
git push
```

Open locally: `docs/study-guide/index.html` → **Part VII · Interview preparation**.

## Regenerate after edits

```bash
cd maintainer-export
python3 generate_interview_guide.py
```

## Related GitHub issue

[Soldier0x0/briefr#498](https://github.com/Soldier0x0/briefr/issues/498) — close after merging into `briefr-maintainer`.

## Source

Recovered from `briefr` git history (`f8051f5e^`) before maintainer docs migration, plus generated interview content (2026-07-24).
