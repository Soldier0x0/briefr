# Learn Site (Phase 1) — Design

**Date:** 2026-07-19  
**Status:** Implement now as **deploy-ready static artifact**; live `docs.<domain>` DNS deferred  
**Depends on:** Phase 0 inventory gates green (`audit_study_guide.py --strict`)

## Goal

Ship a chooser + three learning pathways (System Design, Security analyst, Security architect) that **overlay** the audited study-guide textbook. No invented architecture. Ready to publish the moment a subdomain or static host is configured.

## Constraints (maintainer)

- Subdomain **not configured yet** — do not require live DNS, Cloudflare, or production deploy in this PR.
- Keep a **single folder artifact** that can be pointed at later (`docs/learn-site/`).
- Separate public learn repo remains optional later; BRIEFR hosts the generator + committed artifact until then.

## Architecture

```
docs/STUDY_GUIDE.html          # textbook SSOT (unchanged)
scripts/build_study_guide_book.py
docs/study-guide/              # textbook book (existing)

docs/learn/pathways.json       # pathway overlays (editable)
scripts/build_learn_site.py    # generator
docs/learn-site/               # DEPLOYABLE ARTIFACT (generated)
  index.html                   # chooser
  pathways/*.html
  book/                        # nested copy of study-guide
  assets/
  DEPLOY.md                    # when DNS is ready
```

Truth flow: regenerate study-guide → build learn-site (copies book + writes overlays). Pathways only list chapter ids that exist in the book.

## Pathways (v1)

| id | Audience | Job |
|----|----------|-----|
| `system-design` | Engineers learning SD from a real product | Scratch → mastery via BRIEFR as case study |
| `analyst` | Security analyst | How an analyst views/uses BRIEFR day-to-day |
| `architect` | Security architect | Trust boundaries, controls, posture |

## Non-goals

- Live DNS / TLS / Cloudflare Zero Trust setup in this PR  
- Operator / detection-engineer profiles  
- Rewriting textbook facts inside pathway pages  

## Success

- `python scripts/build_learn_site.py` produces a browsable tree  
- Local preview: `python -m http.server` from `docs/learn-site/`  
- When subdomain exists: point the host root at `docs/learn-site/` (see `DEPLOY.md`)  
- `--strict` study-guide audit still green; learn-site does not weaken truth gates  
