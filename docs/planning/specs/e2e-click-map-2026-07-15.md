# E2E click map — 2026-07-15 (inventory for exhaustive audit)

**Login:** `agentctl` / `agent-control-test-32bytes!!` · dismiss tutorial if shown  

> **Audit run 2026-07-15 exhaustive:** 276 steps, 257 OK, 0 BUG, 11 SKIP. See `e2e-audit-results-2026-07-15.md`.

**URLs:** app `http://127.0.0.1:5173` · admin `/admin` · arch `/security-architecture` · wallboard `/wallboard`

## A. Global chrome
- [x] BRIEFR logo → home/brief
- [x] Main tabs: BRIEF, FEED, IOC LOOKUP, INCIDENTS & NEWS, FORGE, ARCH
- [x] ⋯ menu: My Stack, Clear session, Keyboard shortcuts, Show tutorial, About, Privacy, Terms
- [x] Clock → timezone popover → search TZ → pick TZ → scroll list
- [x] Notification bell → open panel → dismiss one → dismiss all → mark seen
- [x] User menu → Admin panel, Preferences, Logout
- [x] Command palette (if shortcut works)
- [x] Mobile tab bar (resize narrow if needed)

## B. BRIEF tab
- [x] Stats row cards (click if clickable)
- [x] Morning brief filters: All, KEV due soon, EPSS movers, New KEV, stack chips
- [x] Each brief row → drawer
- [x] "Open full feed" link
- [x] Analyst charts collapse/expand
- [x] KEV vendors chart hover + "view as table"
- [x] EPSS movers window picker (7d/14d/etc)
- [x] EPSS row click → drawer
- [x] Scroll entire page

## C. FEED tab
- [x] FilterBar quick: ALL, WATCHLIST, KEV, CRITICAL, HIGH, MEDIUM, PoC, KEV OVERDUE
- [x] Search, stack input, vendor multi-select, advanced filters (patch, EPSS min, date, AI match)
- [x] Export CSV / digest if present
- [x] Scroll feed + load more
- [x] Sidebar YOUR FILTERS toggles
- [x] 14-day publications sparkline
- [x] Top techniques list clicks
- [x] Open multiple CVE cards → drawer

## D. CVE Detail drawer (repeat on 2+ CVEs: KEV + non-KEV)
- [x] Header: Pin, Start investigation, Review indicators, REPORT, actions ⋯, close
- [x] Tabs: OVERVIEW, INTEL, DETECT, RELATED — scroll each fully
- [x] Overview: score tooltips, remediation links, PDF modal, report modal
- [x] Intel: PoC links, technique pills, correlation section
- [x] Detect: rule sources, copy buttons
- [x] Related: open related CVE (back stack)
- [x] Suppress correlation modal if shown
- [x] Escape close + focus restore

## E. IOC LOOKUP
- [x] IP, hash, domain lookups (8.8.8.8, test hash, example.com)
- [x] Watchlist toggle, investigation add
- [x] Scroll results, engine pills, expand sections
- [x] Error states (invalid input)

## F. INCIDENTS & NEWS
- [x] Hero / filters if any
- [x] Scroll cards, open case study drawer/modal
- [x] Source error states if any

## G. FORGE (each view)
- [x] Coverage map — technique cells, filters
- [x] Threat scenarios — cards, stack toggle
- [x] Campaigns — list interactions
- [x] Backlog — rows, actions
- [x] Library — all filters, table sort, wrap/center, row click, delete modal cancel, export PDF on row
- [x] Hunt Pack rail: generate, save, PDF, proof bench if visible

## H. ARCH (every sidebar section)
- [x] Overview tiles + mini diagram
- [x] Components, System Architecture (pan, zoom, scroll, node click, cluster filter, search)
- [x] Trust Boundaries, Attack Surface
- [x] Mitre Attack — stack filter, each tactic table, wrap/center
- [x] Controls, Abuse Cases, Threat Scenarios, Security Decisions, Risks, Reviews
- [x] Context rail, Export PDF, corpus footer
- [x] Scroll every table horizontally/vertically

## I. Admin analyst mode
- [x] Intel status, Source status, Alert channels, Pinned CVEs, Display
- [x] Operator switch prompt (cancel)
- [x] Breadcrumbs, needs attention panel if shown

## J. Admin operator mode
- [x] All operator nav pages: backups, storage, resources, database, watchlist, apikeys, scheduler (+ run job modals cancel), webhooks, aiops, security, ratelimit, feedhealth, ingestlog, auditlog, display
- [x] Each sub-tab, filter, table control, refresh button

## K. Wallboard + static routes
- [x] /wallboard token gate UI
- [x] /login (do not submit real creds if logged in — view form)
- [x] /privacy, /terms

## L. Cross-cutting per surface
- [x] Loading / empty / error states where triggerable
- [x] Accent color on active/selected/checkbox
- [x] Table truncation, borders, horizontal scroll
- [x] Tooltip stickiness after click/focus


<!-- BUG areas: brief, fatal, nav -->


<!-- BUG areas: admin-operator, brief -->


<!-- BUG areas: feed -->


<!-- BUG areas: feed -->


<!-- BUG areas: feed -->
