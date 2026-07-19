# Learn pathways (Phase 1) — Design

**Date:** 2026-07-19  
**Status:** Thin static overlays next to the study guide  

## Goal

Three learning pathways (System Design, Security analyst, Security architect) that **link into** `docs/study-guide/` — no duplicate textbook, no host-specific packaging.

## Layout

```
docs/learn/pathways.json     # editable overlays
docs/learn/index.html        # generated chooser
docs/learn/pathways/*.html   # generated step lists → ../study-guide/pages/
docs/study-guide/            # audited textbook (existing)
```

Publish however you already publish static folders from the repo. Pathways are just HTML next to the book.

## Non-goals

- Nested copy of the study guide  
- Host- or vendor-specific deploy requirements  
- Separate learn repository (optional later, not required)  
