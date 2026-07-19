"""TM-6: analyst-facing framework workspaces.

Unlike the spec's original §4.5 self-stack framing ("BRIEFR watches BRIEFR"),
these workspaces point the frameworks at the *user's own* live threat surface
-- the ingested CVE corpus, filtered to their saved stack, their watchlist,
or KEV-only -- so the module is useful to anyone defending anything, not just
to BRIEFR's maintainer.

Every framework is a projection of one live aggregation: the CWE weakness
classes present in `cves.cwe_ids` across the selected scope. From that single
live signal we project:

- CWE     -- the weakness classes themselves (direct)
- OWASP   -- CWE -> OWASP Top 10 2021 category rollup (official CWE lists)
- CAPEC   -- CWE -> CAPEC attack patterns (MITRE RelatedAttackPatterns)
- STRIDE  -- CWE -> STRIDE threat class (documented heuristic mapping)

No new matching or scoring code: scope resolution reuses the shipping
`routers.cves._stack_match_clause`, the saved user stack, and the watchlist
table. Every count drills through to the exact CVE rows behind it, and CWEs
with no framework mapping are surfaced as their own bucket so the totals stay
honest (spec central principle: no invented arithmetic, no confident lies).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: BUSL-1.1
"""
