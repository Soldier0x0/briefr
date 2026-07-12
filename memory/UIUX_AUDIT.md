# BRIEFR — End-to-end UI/UX audit
_Preview URL: https://ecdd065e-42da-4027-96ae-08d06601ce55.preview.emergentagent.com/  
Session: admin / harsha111 · Seed: 15 CVEs + 110 incident-news cards · SQLite dev  
Viewport: 1920 × 900 · Dark terminal theme_

Findings are ordered by severity (P0 = broken/blocking · P1 = clear bug or noticeable UX regression · P2 = polish/opinion).

---

## A. Global / cross-cutting

**A1 · P0 — Persistent "Not authenticated" toasts never dismiss after login.**  
Two red error toasts (bottom-right) stick to the screen on every route after login — including `/`, `/admin`, and even the `/login` screen itself. They regenerate with fresh `ref` IDs (e.g. `ec7eb4acac1b4e9a`, `77e346bab1bd4c13`, `9dc7976f...`, `88438973...`) about every 15–30 seconds. Something is polling an authed endpoint before/around the cookie set-lifecycle and surfacing every 401 as a persistent error toast. **Should be a soft banner that self-clears within one auth-refresh cycle, or suppressed entirely if a valid session is present within 2s of the failure.**

**A2 · P0 — Inline "Not authenticated (ref: …) Retry" banner in the middle of BRIEF.**  
Same root cause as A1 but rendered as a full-width inline error block **above** the Morning Brief section. It survives page reloads. Users see this before they see any product data. It's the first paragraph a newcomer reads. Devastating first impression. **This banner should not render at all when `auth/me` succeeds.**

**A3 · P1 — First-run signup screen shows the same persistent toasts.**  
When I created the admin account, two "Not authenticated" toasts were already visible on the signup screen before the account existed (screenshot 01). Even semantically, an account-creation screen showing "Not authenticated" is a category error — of course you're not authenticated, you're signing up.

**A4 · P1 — Uvicorn `--reload` watches the SQLite DB file, causing hot restarts every write.**  
Not a UI bug per se, but it was the actual cause of the "Request timed out" the user hit on signup: every write to `briefr_preview.db` triggered watchfiles → uvicorn restart → in-flight requests killed. Fixed for the preview by moving DB to `/tmp/`. Real product recommendation: `.graphifyignore`-style approach — set `--reload-exclude '*.db*'` (or move the SQLite dev fallback path outside the backend/ tree).

**A5 · P2 — All persistent error toasts have identical severity styling.**  
Every toast is red + error-icon + `ref` + "View application log", even trivial 401s from background polling. Users can't tell "your DB is on fire" from "auth cookie was 15ms late." Introduce at least two tiers (warning vs error) with different colour + no `ref` display for background/polled failures.

**A6 · P2 — Bottom-right toasts overlap important content.**  
On the FEED tab they cover the last two CVE cards. On IOC LOOKUP they cover the API quota panel. Move to a location that doesn't overlap analyst content (top-right below header would follow the pattern of the notification bell), or add a bottom-page footer offset.

---

## B. Header (global chrome)

**B1 · P1 — The "BRIEFR" wordmark is a `<button>` with no visible affordance.**  
Clicking it does nothing observable (no navigation, no menu). Either turn it into a link that goes to `/` (default), or remove the interactive role.

**B2 · P1 — "···" kebab is unlabelled.**  
No `aria-label`, no tooltip, no visible cue what's inside. Contents (once opened) are "Show tutorial again / About / Privacy Policy / Terms of Use" — a useful menu that a user will never find. Label it as "More" with an aria-label, or use an icon that reads (`?` for help, `⋯` with a tooltip "More").

**B3 · P1 — Header timezone "00:52:28 UTC" is a `<button>` but doesn't open a picker.**  
Clicking it should open a timezone selector (per PRODUCT.md/spec), but nothing happens. Either wire the click, or remove the button role.

**B4 · P2 — Notification bell has no visible unread indicator.**  
The bell button in the header shows no dot/count. Opening it reveals "No notifications." fine, but there's no way to tell at a glance whether there's anything worth clicking. Add a small red dot when unread > 0, hidden otherwise (per PRODUCT.md design principle 1: every indicator has a visible meaning).

**B5 · P2 — Top nav uses ALL CAPS but user menu uses lowercase "admin".**  
"BRIEF / FEED / IOC LOOKUP / INCIDENTS & NEWS / FORGE" (uppercase, mono) sit next to "A · admin" (mixed case). Either uppercase the username display or lowercase the tabs — pick one register per row.

**B6 · P2 — Header "BRIEFR // CVE intelligence" has a tiny orange dot next to it (screenshot).**  
Purpose unclear — status indicator? unsaved changes? build-mode? Not documented on hover. Add a tooltip or drop it.

---

## C. Login / Signup screen

**C1 · P1 — No app-side password-strength meter on signup.**  
The setup form accepts any password ≥ some server-side minimum with no visual guidance. First-run experience should show a strength meter (weak/medium/strong) and enforce the same rules the backend does (`auth/passwords.py validate_password_strength`).

**C2 · P1 — "Sign in" screen and "Create account" screen are visually identical except for the button label.**  
No headline distinction ("Welcome back" vs "First-run setup") beyond the tiny "Create your admin account" subtitle. On first run, if a user hits the URL after setup was already done via API (as I did), the flip from "Create account" to "Sign in" is silent. Add a stronger visual differentiator so users know which mode they're in.

**C3 · P2 — Password field's eye toggle is `👁‍🗨` (crossed-out) by default.**  
The default state shows a "hidden" icon suggesting the password *is* being hidden. Correct behaviour but the icon glyph itself is confusing — most apps show an open eye to mean "click to reveal." Consider standard eye/eye-off pattern.

**C4 · P2 — Login card has no "Forgot password" link.**  
Single-operator self-hosted context, but the maintainer's playbook `#468` mentions "SQLite scheduler-lock login landmine" and manually resetting the admin password via DB. A "Forgot password (advanced)" link opening the recovery instructions (`briefr-doctor.sh` etc.) would prevent lock-outs.

---

## D. BRIEF tab

**D1 · P1 — KPI stat row shows "8₀ CRITICAL / 6₀ HIGH / 10₀ KEV (EXPLOITED) / 15₀ PATCHES AVAILABLE".**  
The subscript "₀" (or similar tiny character) next to each number is confusing — is it a delta indicator? a footnote reference? Nothing explains it. If it's meant to be the 24h delta and the delta happens to be 0, either hide the delta when 0, or show explicit `Δ 0` inline. Currently reads like a broken number.

**D2 · P1 — Morning brief filter chips ("All / KEV due soon / EPSS movers / New KEV") lack an active-state distinction sufficient in dark mode.**  
"All" is selected but the only signal is a very subtle border. Users tab-switching within a page can miss which chip is active.

**D3 · P1 — CVE-2024-3400 row shows "Due in 10 days" in orange but a red left-side stripe as if it's overdue.**  
The row severity strip on the left doesn't align with the individual badge state (10 days is not urgent, but the row-level treatment implies it is). Reserve red for "Due in ≤3 days" or "Overdue"; use amber for 4–14 days.

**D4 · P2 — "Analyst charts" section: the "TOP KEV VENDORS" bars are unlabelled counts.**  
Each row is a solid tan bar of equal length (1 KEV each), but the numeric value is only shown as "0 … 1" on the x-axis. Add `count` labels at the end of each bar so they're readable without squinting at the axis.

**D5 · P2 — "TOP EPSS MOVERS" table shows only 1 row (CVE-2024-6387).**  
When the panel has 1 row, it feels broken next to the 4-row KEV panel. Add a small empty-state line ("Only 1 mover in the last 7 days — expand the window") or make the widget shrink.

**D6 · P2 — 90-day publications heatmap and "What changed" panel are side-by-side but the heatmap y-axis labels ("S/M/T/W/T/F/S") are almost invisible on the dark background.**  
Contrast check needed. Also the "Less / More" legend below is a tiny nub with no title.

**D7 · P2 — "Open full feed →" link (top-right of morning brief) uses `→` while other similar links use `↗`.**  
Pick one arrow convention across the app.

---

## E. FEED tab

**E1 · P0 — Clicking anywhere on a CVE card opens the detail drawer, but there's no visual affordance that the card is clickable.**  
The whole card is a click target; the cursor probably changes to a pointer, but nothing on the card says "click to open." Users click the CVE-ID (which looks like a heading) expecting a link — it isn't. Solutions: (a) make the CVE-ID an actual link with underline-on-hover, and/or (b) add a "View details" affordance on hover. The `.card-share-btn ↗` icon in the top-right is *especially* misleading — it looks like the "open detail" icon but is actually "copy share link". Add an aria-label the user can see (tooltip) and change its visual to a clear share/link icon.

**E2 · P0 — "Start investigation" button opens an investigation session panel from the bottom, with a full-screen overlay that intercepts all pointer events except within the panel.**  
Two problems:
  1. **No indication** that clicking this locks the whole rest of the UI behind a modal until you "End investigation." The user tries to switch tabs, tries to search — nothing responds.
  2. **The panel doesn't visually communicate that it's modal** — the bottom sheet looks like a supplementary widget, not a lock-out.
Fix: (a) darken the background more emphatically when the investigation sheet is open, (b) label the panel `INVESTIGATION SESSION · locking rest of app — click "End investigation" to exit`, (c) let users close it via `Esc` or a big × in the top-right corner of the sheet (currently there's only a small ×), (d) allow read-only navigation across tabs while an investigation is active — the whole point is to pivot between CVE/IOC/related.

**E3 · P1 — Card-level checkbox appears only on the last visible card ("CVE-2024-21410") but not the others.**  
The `.card-checkbox-box` element exists on every card in DOM, but visually it only rendered on one. Multi-select intent unclear.

**E4 · P1 — CVE badges use inconsistent colour semantics.**  
- Red for KEV (correct)
- Red for "Due in 5 days" *and* "Overdue" (should be different — imminent vs breached)
- Orange for "Due in 10 days"
- Green for "Patch"
- Red for CVSS 9.8 (aligns severity to due-date colour, so they blend visually)

CVSS chip should stay red for critical, but the KEV-due chip should have its own family (amber → red gradient), otherwise the row looks like a wall of red.

**E5 · P1 — Vendor chip row ("Common vendors: Adobe / Amazon / Apache / …") has no active state and no plural-select cue.**  
Clicking "Apache" filters the feed, but the chip doesn't stay visibly toggled. Users can't tell which chip they clicked. Also 30+ chips shown in one long row — needs a "Show more / less" toggle or grouping.

**E6 · P1 — "MY STACK FILTER" instructional banner is visually the same weight as an alert.**  
The orange border-left + long paragraph + × close button reads like a warning banner, but it's an onboarding hint. Downgrade to a light-grey info style + smaller type.

**E7 · P2 — Right sidebar has "YOUR FILTERS" toggles (KEV only, PoC public, EPSS > 50 %, My stack only) but they're checkboxes styled like toggles.**  
Small styled boxes on the right — hard to see if they're on/off. Use larger toggles with explicit "on/off" states.

**E8 · P2 — "GENERATE DIGEST / EXPORT CSV / EXPORT XLSX" buttons in the top-right are all styled identically as ghost buttons.**  
"Generate digest" is a higher-intent action (opens a modal, potentially calls LLM); the two exports are simple downloads. Give Generate Digest a filled/primary treatment.

**E9 · P2 — Search input placeholder says "search CVE-ID or keyword…" but keyword search isn't documented.**  
Does it search description? Title? Product? Add a tooltip.

**E10 · P2 — Pagination: "Showing 1-4" implies pagination but no page controls visible on the visible area.**  
Bottom of the feed says "15 of 15 shown" once you scroll, so it's infinite scroll — but "1-4" at the top is a lie until you scroll. Update the count live as user scrolls.

---

## F. CVE detail drawer

**F1 · P1 — "Computing priority…" / "Loading intelligence summary…" / "Loading EPSS trend…" placeholder text stays visible indefinitely if the endpoint returns nothing (preview has no LLM keys, no OTX, no EPSS history).**  
There's no timeout → the loading text just stays there forever. Replace with an empty-state message like "OTX not configured — priority band unavailable" after 5 s of no response.

**F2 · P1 — Only 4 sub-tabs (OVERVIEW / INTEL / DETECT / RELATED) but the app's own PRODUCT_STATUS mentions "OP hero → environment relevance → threat signals → remediation → exploitation" as if these are separate tabs.**  
They're actually all sections stacked inside Overview. That's fine for scanning, but the section headings ("KEY EXPLOITATION SIGNALS", "WHY THIS MATTERS", "REMEDIATION", "SEVERITY CONTEXT", "EXPLOITATION") aren't in a right-hand table-of-contents; long CVE overviews become a wall of scroll. Add a sticky ToC or collapse each section.

**F3 · P1 — Drawer close (×) is a small hit target in the top-right corner.**  
`Esc` works and is documented in the shortcuts panel, but the visible close button is ~14px. Increase to 28px minimum for a modal-scale UI.

**F4 · P1 — "REPORT" button (top-right of drawer, next to Pin/Start investigation/Review indicators) is unlabelled beyond one word.**  
What does it do? Export a PDF report for this single CVE? File a bug? Report to CISA? Ambiguous verb. Change to "Export PDF report" or add a tooltip.

**F5 · P2 — The 4 header action buttons on the drawer (`Pin` / `Start investigation` / `Review indicators` / `REPORT`) are visually inconsistent.**  
Pin/Start/Review look identical (ghost, mono). REPORT is uppercase and slightly different padding. Standardize with the newly-added `.ui-btn` class (per UX-C1/UX-C2 sweep — the drawer was migrated but the REPORT button appears to still be bespoke).

**F6 · P2 — In INTEL tab, "// ACTIVE SCANNING" shows "GreyNoise is not configured on this server — on-demand IP context is unavailable." — good empty state. But "// MITRE ATT&CK" says just "No ATT&CK mapping available" — inconsistent voice.**  
Match the tone: `// MITRE ATT&CK not available — populate via Admin → Feeds → refresh MITRE.` Every empty state should tell the user *what to do next.*

**F7 · P2 — Detect tab shows a generated Sigma rule (great!) but the YAML has no syntax highlighting.**  
Long YAML in a mono block is dense. `highlight.js` or Prism (already in a JSX app) would make the rule readable. Also add a "Copy YAML" button *at the top* not just below.

**F8 · P2 — "PATCH AVAILABLE" green pill is the only differentiated colour in the remediation section.**  
Otherwise the section is grey text on dark. Add a subtle green side-stripe (per existing accent border pattern) to mark the remediation block visually.

---

## G. IOC LOOKUP tab

**G1 · P1 — Empty state before lookup shows "Enter an IP, file hash, or domain above and press LOOKUP" — but the input's placeholder shows three example values separated by `/`.**  
Users copy the placeholder (`8.8.8.8 / d41d8cd… / example.com or …`) and submit the raw string. Show one example at a time, cycling, or use a proper multi-line hint block below the input.

**G2 · P1 — API QUOTA row shows 6 provider columns (VirusTotal / AbuseIPDB / GreyNoise / AlienVault OTX / MalwareBazaar / URLhaus).**  
All 6 show "0 calls" or "0/500 today" even though the preview has *no* API keys configured. Empty state should say "Not configured" for the ones without keys, not "0 calls" (which reads like "configured but unused").

**G3 · P1 — Clicking LOOKUP with `8.8.8.8` in the preview stalled the page.**  
Playwright timed out; the request likely hung on an unconfigured provider without a proper reject-path. Should surface a friendly "No enrichment providers configured — configure keys in Admin → API keys" instead of just spinning.

**G4 · P2 — The visual "pipeline" at the bottom (`INDICATOR --> VT + ABUSEIPDB + GREYNOISE + MALWAREBAZAAR + URLHAUS --> VERDICT`) is a nice diagram, but takes prime real estate below the input.**  
On mobile it would swallow the whole screen. Consider collapsing behind a "How this works" toggle.

**G5 · P2 — "WATCHLIST (0)" section reads "Saved IOCs retro-match nightly against OTX + ThreatFox mirrors on this server." — but the OTX/ThreatFox sync is disabled in the preview.**  
Ideally the empty-state should reflect actual configuration: "Retro-match disabled (OTX not configured)".

---

## H. INCIDENTS & NEWS tab

**H1 · P0 — "// No feed items loaded — check source errors above" is shown even though the seed script warmed 110 incident-news cards.**  
Backend has the data, the frontend didn't fetch it (or fetched empty because the `case_study_feed` endpoint has a different code path than the seed populated). Verify:
- `GET /api/case-studies/feed` returns cards
- If yes, frontend query is broken
- If no, `INCIDENT_FEED_REFRESH_MINUTES` snapshot is being built on-demand and empty

Whichever it is, this tab is currently the biggest visual "the app is broken" moment in the flow.

**H2 · P1 — Three empty-state blocks side-by-side ("INCIDENTS & NEWS / LATEST FROM ATLAS / ACTIVE CAMPAIGNS") all say "No … loaded/populated/headlines."**  
Three identical empty states creates the strongest possible impression of a broken product. Consolidate into a single "Incident intelligence not yet loaded — first fetch happens after the MITRE + RSS scheduler jobs run (Admin → Refresh all sources)." with a "Refresh now" button.

---

## I. FORGE tab

**I1 · P1 — "COVERAGE MAP" and "HUNT PACK" are two side-by-side empty-state panels.**  
Same problem as H2 — two empty boxes make the whole tab look broken. Explain: "MITRE ATT&CK feed not yet ingested. Run `Refresh MITRE` from Admin to populate techniques."

**I2 · P2 — Sub-tabs "Coverage map / Threat scenarios / Campaigns / Backlog" have inconsistent capitalization vs Overview/Intel/Detect/Related in the drawer.**  
Sentence case vs Title Case — pick one.

**I3 · P2 — "GAP 0 / COMMUNITY 0 / YOURS 0" chips (top-right) explain themselves poorly.**  
0 what? Techniques? Rules? Tooltip should say "0 technique gaps in coverage · 0 community rules loaded · 0 rules you've saved."

---

## J. Admin panel

**J1 · P1 — Admin nav lives in a left sidebar that isn't discoverable from the main app.**  
There is no visible "Admin" link in the top nav — you have to know to type `/admin` or find "Admin panel" buried in the user dropdown. For a self-hosted operator app, this is a significant navigation gap.

**J2 · P1 — "Analyst / Operator" view toggle in the admin header isn't labelled as a role switch.**  
"VIEW · Analyst · Operator" pill (top-left of admin) looks like a filter chip. It's actually the mode switcher (Analyst = safe read-only intel view, Operator = backups/config/security). Label it: "Admin view: [Analyst] [Operator]" and add a tooltip on each.

**J3 · P1 — Admin left sidebar has section headers "INTEL / YOUR DATA / PREFERENCES" in tiny uppercase mono but no visual grouping (no divider).**  
Items list runs together — the header looks like an unclickable item.

**J4 · P2 — "Backups, config, logs → switch to Operator view" bottom sidebar link is a text hint dressed like a button.**  
The affordance is unclear — is it a button? a link? Style consistently with other sidebar items.

**J5 · P2 — Admin URL is `/admin` but going to `/admin` and reloading may 401 (redirect back to /login) because the session cookie hasn't been rehydrated yet.**  
Same class of bug as A1/A2.

**J6 · P2 — "DATABASE HEALTH: Healthy · checked on startup" — startup was minutes ago; not a live check.**  
Add "Run check now" button or "last checked X min ago" instead of "on startup."

**J7 · P2 — "NIST CVE FEED: —" (em-dash) instead of a status.**  
Empty state should read "No syncs yet" or similar, not an ambiguous dash that reads as an error.

---

## K. Interactions / accessibility

**K1 · P1 — ⌘K / Ctrl+K command palette shortcut does not appear to open a palette in the preview.**  
Firing `Meta+K` produced no visible modal. Either the shortcut binding is broken in the current build, or the palette relies on a data source (Kbar-style) that failed to load. Verify `CommandPalette.jsx` mounts.

**K2 · P1 — `?` global help shortcut also produced nothing.**  
PRODUCT_STATUS.md documents keyboard shortcuts (`/`, `F`, `Esc`, `g d`, arrow keys). None of them appear to have a discoverable in-app cheatsheet unless the user finds the "···" kebab → About/Show tutorial.

**K3 · P1 — Focus rings are inconsistent across button variants.**  
The UX-C1/C2 sweep landed a `.ui-btn` standard, but bespoke buttons (share-link ↗, checkbox-box, kebab, timezone clock) still have their own or no focus-visible outline.

**K4 · P2 — Tab-panel-keeps-mounted behaviour is nice, but scroll position is preserved even when data has updated in the background.**  
Users switching BRIEF → FEED → BRIEF find themselves at their old scroll position while data may have refreshed. Consider indicating "new data — scroll to top" if the underlying set changed.

**K5 · P2 — Colour palette contrast: on the dark theme, the ambient orange accent (`#e85533` per favicon) is used for both errors ("Not authenticated") and actions ("Sign in" button, active tab underline).**  
Errors should use a distinct hue (a redder red, or red + icon), otherwise every orange element reads as "something's wrong."

**K6 · P2 — "prefers-reduced-motion" not verified.**  
Product doc says it's respected globally — worth a runtime sanity check with `media (prefers-reduced-motion: reduce)`.

---

## L. Copy / voice

**L1 · P2 — "// COMMENTED-STYLE" headers (`// MORNING BRIEF`, `// ANALYST CHARTS`, `// COMMON VENDORS`, `// INDICATOR`, `// API QUOTA`, `// WATCHLIST (0)`, `// EXISTING COMMUNITY RULES`, `// BRIEFR HUNT STARTER`, `// SIEM QUICK SEARCH`, `// LOG PATTERNS`, `// PUBLIC EXPLOITS`, `// ACTIVE SCANNING`, `// ACTIVE CAMPAIGNS`, `// CORRELATION FINDINGS`, `// INVESTIGATION`) — this is the strongest voice-cue in the product, and it's *good.*** But the `//` prefix is applied inconsistently: some headings have it, some don't ("REMEDIATION", "WHY THIS MATTERS", "SEVERITY CONTEXT", "EXPLOITATION" don't; "MITRE ATT&CK" doesn't). Pick a rule and apply it — e.g. "primary section headers get `//`, sub-sections don't."

**L2 · P2 — "SUSPICIOUS ACTIVITY" tag next to "// SIEM QUICK SEARCH" is orange — reads like a threat level, but it's actually a query class.**  
Change colour or add a tooltip.

**L3 · P2 — "As of 2026-07-12T00:59:13 · SigmaHQ + Elastic + BRIEFR · Checked" provenance line at the top of the drawer detect tab is small and easy to miss.**  
This is a really valuable trust-signal line ("here's where the data came from and when"); make it more prominent or repeat it on each section that has data provenance.

---

## M. Positive notes (what to keep)

- Terminal aesthetic is genuinely distinctive and appropriate for the audience.
- IBM Plex Mono + dark palette + tight information density = zero AI-slop feel.
- Empty states for missing API keys ("GreyNoise is not configured on this server — on-demand IP context is unavailable.") are refreshingly honest — apply this voice to every empty state (H1/H2/I1).
- Investigation session concept is genuinely novel (a persistent tray you build across tabs, exports a PDF). Just needs (E2) discoverability.
- `briefr_basis: attack_technique | cwe | generic` provenance on Sigma rules — a great honesty gesture that most detection tools skip.
- Sub-tabs on the CVE drawer (OVERVIEW/INTEL/DETECT/RELATED) load fast and preserve state.

---

## Ranked top-10 fixes if you touch only 10 things

1. **A1 / A2 / A3** — Kill the persistent "Not authenticated" toast + inline banner storm.
2. **H1 / H2** — Fix Incidents & News tab (or its empty state).
3. **E2** — Investigation session: modal clarity + Esc + darker overlay + read-only tab switching.
4. **E1** — Make CVE cards visibly clickable and fix the misleading `↗` share-icon.
5. **I1** — Forge tab empty state should tell the user how to populate MITRE.
6. **F1** — Timeout "Computing priority…" / "Loading …" states with actionable fallbacks.
7. **D1** — Explain or hide the mystery `₀` subscript on KPI numbers.
8. **B2 / B3 / B4** — Label the kebab, wire the timezone clock, add unread indicator to bell.
9. **K1 / K2** — Fix ⌘K command palette and `?` shortcut.
10. **A4** — In-repo: `--reload-exclude '*.db*'` so watchfiles doesn't kill in-flight requests on any SQLite dev deploy.
