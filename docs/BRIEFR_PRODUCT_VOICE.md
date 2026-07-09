# BRIEFR product voice

**Purpose:** compact guide for coding agents and maintainers. Defines how BRIEFR
speaks to analysts — not visual design, scoring math, or correlation logic.

**Last updated:** 2026-07-09

---

## Personality

BRIEFR is a calm, experienced security analyst beside the user: precise,
restrained, evidence-driven, technically competent, direct, skeptical of weak
evidence, confident when evidence is strong, explicit when incomplete,
operationally focused.

**Not:** alarmist, dramatic, cute, motivational, sarcastic, patronizing,
verbose, academically dense, generic enterprise dashboard, AI chatbot, beginner
tutorial.

**Assume:** domain knowledge (CVE, CVSS, EPSS, KEV, IOC, ATT&CK, Sigma, etc.).

**Do not assume:** BRIEFR-specific concepts (Operational Priority, Environment
Relevance, Correlation Priority, Momentum, stack match tiers, investigation
session). Explain those on hover/focus or in short inline copy.

---

## Layered communication

| Layer | Role | Example |
|-------|------|---------|
| **1 — Signal** | State at a glance | `ACTIVE EXPLOITATION CONFIRMED` |
| **2 — Why** | One sentence, not a restatement of layer 1 | `CISA lists this vulnerability in the KEV catalog.` |
| **3 — Evidence** | Source, indicator, relationship, dates | `Source: CISA KEV · Due: 2026-07-23` |
| **4 — Deep detail** | Formulas, raw scores, provider metadata | `Why this score?`, expandable evidence |

Primary workflow surfaces use layers 1–3 only. Layer 4 stays behind
expandables.

---

## Confidence language

| Evidence strength | Voice |
|-------------------|-------|
| **Strong** | Direct: `CONFIRMED AFFECTED VERSION`, `ACTIVE EXPLOITATION CONFIRMED` |
| **Weak** | Qualified: `POSSIBLE PRODUCT RELEVANCE`, `WEAK TEXTUAL OVERLAP` |
| **Unknown** | Explicit: `ENVIRONMENT RELEVANCE UNKNOWN`, `ENRICHMENT PENDING` |

**Never imply safety without evidence.** Prefer `NO MATCH FOUND`, `NO EXPLOIT
FOUND IN CURRENT SOURCES`, `ENVIRONMENT RELEVANCE UNKNOWN` over `SAFE`, `NOT
AFFECTED`, `NO EXPLOIT EXISTS`.

**Separate semantics:** technical severity (CVSS) ≠ observed exploitation (KEV)
≠ environment relevance (stack/CPE) ≠ operational priority (P1–P4 rule table).

---

## Uncertainty and skepticism

- Admit gaps: `No asset profile loaded — environment relevance cannot be determined.`
- Do not hide uncertainty behind bare `N/A`, `?`, or `--` when a short line helps.
- Weak correlations stay qualified — one CDN IP is not a campaign; fuzzy product
  overlap is not confirmed exposure; PoC is not in-the-wild exploitation.

---

## Action labels

Describe the outcome, not the verb alone.

| Avoid | Prefer |
|-------|--------|
| View, Open, More | Review evidence, Investigate relationship, Open detection context |
| Extract observables | Review indicators |
| Suppress relationship | Hide this link |
| Clear (investigation) | End investigation |

---

## Errors and provider pacing

Answer: what failed, what still works, what happens next, can the user retry.

```
GITHUB RATE LIMITED
Exploit-reference lookup is paused for 42s. BRIEFR will retry automatically.
```

Rate limits and queue waits are **not** errors. Failures keep existing
intelligence visible when possible.

---

## Terminology consistency

| Concept | Preferred label |
|---------|-----------------|
| User asset profile | **My Stack** (not "asset profile" in UI) |
| Feed text filter | **stack filter** |
| CISA catalogue | **KEV** with expansion on first hover where needed |
| Stat tile | **KEV (EXPLOITED)** aligned with filter chips |
| Threat signal section | **KEY EXPLOITATION SIGNALS** (not "critical threat") |
| OP band P1 | **P1 — Address first** (not "ACT NOW") |
| Correlation infra block | **SHARED INDICATOR LINKS** |
| Backend env var names | Never in analyst-facing errors |

---

## BRIEFR-specific tooltips (examples)

- **Operational Priority:** `BRIEFR's rule-based P1–P4 band from threat signals and environment relevance. Separate from CVSS.`
- **Correlation Priority:** `How strongly BRIEFR weights relationship evidence for this CVE — not vulnerability severity.`
- **Momentum:** `Recent movement in exploitation signals (KEV timing, EPSS change, OTX activity).`
- **Environment Relevance:** `Whether affected products match your My Stack — independent of Threat Score.`

---

## Anti-patterns (bad → good)

| Bad | Good |
|-----|------|
| `Great news! Related vulnerabilities found!` | `3 related CVEs share infrastructure evidence.` |
| `Oops! VirusTotal couldn't be reached.` | `VirusTotal enrichment failed. Existing intelligence remains available.` |
| `This CVE is extremely dangerous!` | `Active exploitation confirmed. Public exploit code is available.` |
| `You should patch immediately!` | `CISA requires remediation by 23 July 2026.` |
| `No IOC found.` | `No observables were extracted from current CVE intelligence.` |
| `CONF.IP 0.84` | `STRONG INFRASTRUCTURE RELATIONSHIP` + evidence line |

---

## Implementation rules

- Change copy only where it violates this guide — no blanket string rewrites.
- No i18n framework, no giant constants file, no LLM copy generation.
- Backend sentence templates (`templates/intelligence.py`) must match frontend tone.
- Update tests when user-facing strings are contractual.
- Runtime behavior unchanged unless a backend string is semantically wrong.
