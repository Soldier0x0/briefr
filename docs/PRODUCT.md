# Product

## Register

product

## Users

Security analysts and detection engineers self-hosting BRIEFR as their own
threat-intel platform. Single-operator deployments (one analyst per
instance, no multi-tenant). Used during active triage/investigation work
(CVE feed scanning, IOC lookup, hunt-pack generation) and ongoing operations
(admin panel: backups, scheduler, config, security).

**Audience range (2026-07-11):** the tool must be legible to people **new to
cybersecurity** as well as seasoned professionals, leads, architects, and
managers. Newcomers are served by progressive disclosure (tutorial overlay,
tooltips, domain-term explanations — design principle 6), never by a
dumbed-down mode; leadership roles are served by the same dense surfaces
plus the summary/export layers (Morning Brief, executive PDF, wallboard,
security-architecture posture). One interface, explained everywhere — never
two products.

## Product Purpose

A self-hosted CVE intelligence and detection-engineering platform: a
newspaper-like daily brief, correlation engine across IOCs/actors/patterns,
and detection-rule generation for CVEs. Success = an analyst trusts the data
enough to act on it fast, and an operator can run the box without reading
the source code to understand what a button does.

## Scope & Limits (honest by design)

What BRIEFR is and deliberately is not. Each line is a chosen constraint with a
reason — stated plainly, never apologized for. This section is the source for the
user-facing "Scope & limits" panel (About modal — BACKLOG UX-L1).

- **Single-operator, self-hosted.** One analyst per instance, your hardware, your
  data. Not multi-tenant, not a cloud service — that's the privacy and control trade.
- **Community-source intelligence.** Correlation derives from OTX community pulses
  (ThreatFox corroboration planned). One community source is not vendor-grade
  attribution, and the product labels it as such in-line ("unverified attribution",
  `why_not_higher`). Breadth of sources is bounded by what's free and self-hostable.
- **Term-based stack matching.** Fuzzy by design — vendor/product strings, not
  SBOM/PURL precision. Matches are labeled with the matched term so you can judge
  them. Precise SBOM matching is a known, deliberate non-goal at current scope.
- **Deterministic, LLM-free core.** Correlation, scoring, and scheduling are
  reproducible with zero AI keys. LLMs only narrate and extract at the edges, always
  with template fallbacks — the same input gives the same intelligence, every run.
- **Freshness = upstream + your scheduler.** Data is as current as the public feeds
  and your configured cadence; every intel section shows its as-of line. BRIEFR
  never pretends to be real-time.
- **Prioritization, not discovery.** BRIEFR explains and ranks known-CVE intel
  against your stack. It is not a scanner, ASM tool, or pentest platform — it
  doesn't find your assets or test your systems.
- **One box, small hardware.** Designed for ~2 cores / 16 GB: PostgreSQL, one
  process family, no Redis, no graph DB, no microservices. Operating simplicity is
  a feature.

The trade these constraints buy: trust, reproducibility, and a system one person
can actually operate and fully understand.

## Brand Personality

Dual-mode by design, operator-selectable:
1. **Terminal-native** — dense, monospace-forward, no-nonsense. The
   existing dark theme (`App.css` dark tokens, IBM Plex Mono, sharp borders,
   minimal shadow) is this mode already built and should stay this way.
2. **Clean, modern SaaS** — a second selectable visual mode for operators
   who want a more conventional dashboard look. Not a simple color
   inversion of the terminal theme — a genuinely different visual register
   (more whitespace, softer surfaces, conventional sans-serif hierarchy)
   while keeping the same information density and layout structure.

Both modes serve the same product register (product, not brand) — neither
should drift toward marketing-site visual language (no hero sections, no
big display type, no scroll-driven storytelling).

## Anti-references

Generic cream/warm AI-SaaS dashboard look: no `--paper`/`--cream`/`--sand`
near-white body backgrounds, no hero-metric-card clichés, no gradient text,
no tiny-uppercase-tracked eyebrows, no identical icon+heading+text card
grids, no side-stripe accent borders. If the "clean SaaS" mode is built, it
must avoid this exact templated look while still reading as "clean" and
"modern" — true off-white or a deliberate light neutral, not the saturated
warm-cream default.

## Design Principles

1. **Every indicator has a visible meaning.** No status word, pill, or
   badge ships without a discoverable explanation (tooltip + legend) of
   what it means and what happens if you act on it.
2. **Destructive actions are visually distinct before you're near them**,
   not just confirmed after you click. Danger is a place, not a dialog.
3. **An analyst who didn't write the code should understand the UI.** Every
   page states its purpose; every config field states its effect.
4. **Density over decoration.** This is a working tool used under time
   pressure — information density and scan-speed beat visual flourish, in
   both visual modes.
5. **Self-hosted means operator control.** Visual preferences (theme,
   density, font scale) are the operator's choice, persisted locally, not
   dictated by the build.
6. **Domain terms explain themselves, same as status words.** KEV, EPSS,
   CVSS, CWE, CAPEC, ATT&CK technique IDs, and every other
   assumed-knowledge acronym gets the same discoverable explanation
   treatment as pills and badges (principle 1) — one sentence of meaning
   plus "why it matters here," via the existing HelpTip/ExplainTip
   infrastructure. A newcomer must never hit a wall of unexplained jargon;
   an expert must never be slowed by it (tooltips are hover/focus-only,
   zero cost to ignore).

## Accessibility & Inclusion

Standard WCAG AA: ≥4.5:1 text contrast (including placeholder text and
focus indicators on form controls), visible keyboard focus on all
interactive elements, `prefers-reduced-motion` respected throughout (already
implemented globally — maintain this bar on any new work).
