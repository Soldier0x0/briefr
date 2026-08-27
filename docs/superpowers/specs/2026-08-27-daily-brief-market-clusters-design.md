# Daily brief MARKET clusters — design spec

**Date:** 2026-08-27  
**Status:** Approved for implementation (operator: ship recommended A + weighted rank first)  
**Parent:** `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`  
**Format:** `docs/design/daily-brief-format.md`  
**Plan:** `docs/superpowers/plans/2026-08-27-daily-brief-market-clusters.md`

This spec adds a `// MARKET` section to the existing daily brief. It does **not** reopen destination routing, AI-required facts, email, or per-user windows.

---

## 1. Problem

NVD can publish hundreds to ~2000 CVEs in a window. Listing them on Discord (2000) / Telegram (4096) is impossible and unreadable. COUNTS already give Critical/High totals; they do not show **nginx / python / Oracle Database** volume.

## 2. Chosen approach

**MARKET-A + weighted rank (no AI):**

- Cluster **every CVE published** in the brief window (not Critical/High-only).
- Grain is **CPE product** (nginx, python, oracle_database), not company vendor.
- **One CVE → one cluster** (primary product). Sum of cluster totals + tail = `published`.
- Rank by `critical×10 + high×3 + medium×1 + low×0`. Tie-break: total desc, then label asc.
- Show top **8** product lines + `+{n} products in BRIEFR.`
- Empty CPE / empty `affected_products` → bucket label `unanalyzed` (never description LIKE).
- **No AI API call** to build MARKET. Optional `DAILY_BRIEF_LLM_ENABLED` lede may mention MARKET numbers already in the formatted facts; it still must not invent CVE IDs or author COUNTS.

Instant `kev_alert` / `watchlist_alert` stay on destinations via `event_types`. Out of scope here.

## 3. Primary product

For each CVE, in order:

1. First dict in parsed `cpe_matches` JSON list with a non-empty `product`.
2. Else first `affected_products` entry: `vendor:product` → product; bare token → that token.
3. Else `unanalyzed`.

Cluster key = product lowercased, `_` kept in key; **display label** = key with `_` replaced by spaces (e.g. `oracle database`). Same product from different CPE vendors (`f5` vs `nginx`) **merges**. If two different keys would display identically after space-replace, keep the slug.

## 4. MARKET grammar

Always render `// MARKET` when `published > 0`. Omit the section when `published == 0` (quiet day).

```
// MARKET
Published: {n}  ·  C {c} · H {h} · M {m} · L {l}
• {label}  {total}  (C {c} · H {h} · M {m} · L {l})
…
+{omitted} products in BRIEFR.
```

Omit the `+N` line when omitted is 0. `{n}` is the untruncated published count. Header C/H/M/L are untruncated severity totals for the window (unknown/blank severity counts as **M**).

Section order: after `// COUNTS`, before `// KEV`.

Overflow: **never drop** `market` (same as masthead/headline/counts/footer). Cap is already 8 product lines.

## 5. Quiet headline

`Quiet window.` only when `published == 0` **and** all existing COUNT_KEYS are 0. If 742 Medium CVEs and no KEV, headline is not quiet (template may say `{n} published.` and optionally `{top_label} led volume.`).

## 6. Payload

`brief_to_payload` adds `market`: `{published, critical, high, medium, low, products: [top 8], omitted_products}`. LLM never authors these fields.

## 7. Out of scope (improve later)

Split 6+2 volume slots; drop Low from lines; AI market essay; clustering all CPE products per CVE.
