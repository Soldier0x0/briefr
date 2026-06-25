# IOC lookup

Enrich IPs, hashes, and domains from multiple threat feeds.

---

![IOC lookup UI — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ui-ioc-lookup.png`](../assets/ui-ioc-lookup.png)  
> **Miro prompt:** [IMAGE_BRIEFS §14](../IMAGE_BRIEFS.md#14-ui-ioc-lookup)

![IOC lookup flow — pending](../assets/placeholder-diagram.svg)

> **Asset:** [`assets/ioc-lookup-flow.png`](../assets/ioc-lookup-flow.png)  
> **Miro prompt:** [IMAGE_BRIEFS §16](../IMAGE_BRIEFS.md#16-ioc-lookup-flow)

## Sources

VirusTotal, AbuseIPDB, GreyNoise (opt-in), OTX, MalwareBazaar, URLhaus — depending on keys.

## Caching

| Data | TTL |
|------|-----|
| IOC results | 6 hours (`ioc_cache`) |
| GreyNoise | 1 hour |

## Quotas

UI shows live quota where APIs expose limits. GreyNoise free tier: weekly cap — opt-in per lookup.

## Keys

See [api-keys-and-quotas.md](../troubleshoot/api-keys-and-quotas.md).

## Rate limits

`POST /api/ioc/lookup` is rate-limited — [rate-limits-and-429.md](../troubleshoot/rate-limits-and-429.md).
