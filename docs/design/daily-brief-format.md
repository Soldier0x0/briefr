# Daily brief — channel format standard

**Status:** Draft for implementation (pairs with `docs/superpowers/specs/2026-08-26-daily-brief-webhook-design.md`).  
**Analogy:** CVE PDF reports (`frontend/src/utils/pdfReport.js` + `pdfReportSections.js`) are a **section grammar** plus overflow rules. Daily briefs are the same idea for Discord / Telegram / generic HTTPS — not a second PDF.

When this file and a webhook payload disagree, **this file wins** for layout. When this file and `PRODUCT_STATUS.md` disagree after ship, **PRODUCT_STATUS wins**.

---

## 1. Why a standard

Webhook channels are not the BRIEFR UI. **Discord `daily_brief` uses one classic embed** (`embeds: […]`, color `0xE85533` / 15230259). The 2000-character `content` cap does **not** apply to that embed (Discord embed limits: 6000 combined characters, 25 fields, 1024 per field). Telegram uses HTML (`parse_mode=HTML`, 4096 cap; assembly target 3500). Generic HTTPS POSTs the HTML body as `text` plus `webhook_json_payload()` (`event_type`, `source`, optional `dedupe_key`, `brief`, `discord_embeds`). Machine consumers should read `brief`.

## 2. Canonical sections (order is fixed)

**Masthead** and **footer** always render. **Summary** and **At a glance** always render. Coverage / severity mix / products render when at least one CVE was published. Headlines (RSS snapshot, max 3) and Advisories (publications, max 2) render only when rows exist. Other lists render only when they have rows. Quiet windows still send At a glance zeros plus Summary `Quiet window.`

Morning vs end of day: same sections; title is **Morning briefing** or **End of day**. Author/product word remains **BRIEFR**. Discord does not use `//` PDF titles.

| Order | Section id | Title | Body |
|-------|------------|-------|------|
| 0 | `masthead` | `BRIEFR` + slot title | Window start → end, IANA tz |
| 1 | `headline` | **Summary** | 1–3 short sentences. Template or optional LLM. Never invent CVEs. |
| 2 | `counts` | **At a glance** | Fixed keys, one per line, integer values |
| 3 | `coverage` | **Coverage** | Named vs Unmapped counts + CPE snapshot copy (when published > 0) |
| 4 | `products` | **Published by product** | Top 8 primary-product clusters |
| 5 | `headlines` | **Headlines** | RSS snapshot cards in the window (max 3; `kind != atlas`) |
| 6 | `advisories` | **Advisories** | Publications in the window (max 2; prefer `cisa-news`) |
| 7 | `kev` | **CISA KEV** | New KEV in window (max 8 lines) |
| 8 | `stack` | **My Stack** | KEV or Critical/High matching admin My Stack CPE (max 8) |
| 9 | `watchlist` | **Pinned CVEs** | Pinned-CVE monitor reasons in window (max 8) |
| 10 | `ioc` | **IOC watch** | IOC watchlist hits in window (max 5) |
| 11 | `ops` | **Instance problems** | Job errors, unhealthy API keys, webhook delivery failures (max 5) |
| 12 | `footer` | (no title) | Generator line |

### At a glance keys (always all six, in this order)

```text
New on CISA KEV: {n}
Matches My Stack: {n}
Pinned-CVE alerts: {n}
IOC watch hits: {n}
New Critical or High: {n}
Instance problems: {n}
```

`n` is the **untruncated** total for the window, even when the list below is capped.

### Products / Unmapped

Internal cluster key remains `unanalyzed`. Display label is **Unmapped**. Empty CPE and empty `affected_products` land in that bucket. Unmapped must not be the Summary “led volume” product. If Unmapped ≥ 50% of published, Summary includes `{unmapped} of {published} published CVEs have no product mapped yet (Unmapped).`

Severity mix is spelled out (Critical / High / Medium / Low), not `C · H · M · L`.

### List line grammar

```text
• {CVE-YYYY-N} — {one-line reason} · {severity-or-blank}
```

IOC lines:

```text
• {type} {value} — {source}
```

Ops lines:

```text
Scheduler job failed: {catalog name}
CISA KEV list may be stale until this job succeeds.   # kev_metadata_sync only
Detail: {short error}
```

No nested bullets. No tables. No JSON inside Discord/Telegram text. Telegram HTML must escape `&`, `<`, `>` in interpolated titles.

## 3. Overflow

**Discord embeds:** if over 6000 characters or 25 fields, drop fields in order `ioc` → `watchlist` → `stack` → `kev` → `advisories` → `headlines`, then trim product lines to 5. Never drop coverage, severity mix, at a glance, or footer. Do not apply the 2000 `content` budget to Discord `daily_brief` embeds. If Discord rejects the embed (HTTP 400), retry once with plain `content` truncated to 2000.

**Telegram / generic / fallback text:** assemble against 2000 (plain) or ~3500 (HTML) then engine-truncate. Drop list sections `ops` → `ioc` → `watchlist` → `stack` → `kev` → `advisories` → `headlines`. Never drop masthead, summary, at a glance, products, or footer.

Machine consumers should read the structured `brief` object for the bounded item lists and untruncated window totals.

## 4. Worked examples

### Quiet standup

```text
BRIEFR Morning briefing
2026-08-25 18:00 → 2026-08-26 07:00 (Asia/Kolkata)

Summary
Quiet window.

At a glance
New on CISA KEV: 0
Matches My Stack: 0
Pinned-CVE alerts: 0
IOC watch hits: 0
New Critical or High: 0
Instance problems: 0

BRIEFR — generated 2026-08-26 07:00 Asia/Kolkata | slot=standup | facts=local | lede=template
```

### Busy end-of-day (abridged)

```text
BRIEFR End of day
2026-08-25 18:00 → 2026-08-26 18:00 (Asia/Kolkata)

Summary
6 published. nginx led volume. 2 new KEV. 1 stack match. Watchlist: 1.

At a glance
New on CISA KEV: 2
Matches My Stack: 1
Pinned-CVE alerts: 1
IOC watch hits: 0
New Critical or High: 4
Instance problems: 0

Products
Published: 6  ·  Critical: 2 · High: 2 · Medium: 2 · Low: 0
• nginx  3  (Critical 1 · High 1 · Medium 1 · Low 0)
• openssl  2  (Critical 1 · High 1 · Medium 0 · Low 0)
• Unmapped  1  (Critical 0 · High 0 · Medium 1 · Low 0)

CISA KEV
• CVE-2026-1111 — added to KEV · CRITICAL
• CVE-2026-2222 — added to KEV · HIGH

My Stack
• CVE-2026-1111 — CPE match · CRITICAL

Pinned CVEs
• CVE-2026-1234 — EPSS jump

BRIEFR — generated 2026-08-26 18:00 Asia/Kolkata | slot=eod | facts=local | lede=groq
```

## 5. What this is not

- Not a PDF, email, or in-app notification dump.
- Not a substitute for `watchlist_alert` / `kev_alert` (those stay real-time).
- Not per-user prose (“since *you* logged off”) on a shared webhook — window copy is clock + timezone (see spec).
