# API keys and quotas

## Symptoms

- OTX pulses / correlation empty
- IOC providers return "not configured"
- PDF AI summary empty
- Embeddings / Hub warnings in logs

## Key matrix

| Key | Affects |
|-----|---------|
| `NVD_API_KEY` | NVD rate limits (recommended) |
| `OTX_API_KEY` | Pulses, correlation spine |
| `VIRUSTOTAL_API_KEY`, `ABUSEIPDB_API_KEY` | IOC lookup |
| `GREYNOISE_API_KEY` | Optional IOC (weekly free cap) |
| `GROQ_API_KEY` / `ANTHROPIC_API_KEY` | PDF AI summary |
| `GITHUB_TOKEN` | Detection rule search |
| `HF_TOKEN` | Optional — HuggingFace Hub for embeddings |
| `EMBEDDINGS_CACHE_DIR` | Writable model cache (systemd: `/var/lib/briefr/models`) |

Full list: `backend/.env.example`

## Fixes

1. Add keys to `backend/.env` (env vars beat `.env` — restart backend after Secrets change).
2. Check `/api/usage` and `/api/usage/ioc` in UI or API.

## Related

[ioc-lookup.md](../use/ioc-lookup.md), [correlation.md](../concepts/correlation.md)
