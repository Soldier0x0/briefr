# Empty feed and slow ingest

## Symptoms

- FEED shows no CVEs or very few
- `/api/health` shows low count or ingest in progress
- Logs mention NVD fetch / bootstrap

## Causes & fixes

| Cause | Fix |
|-------|-----|
| First boot (&lt;10 CVEs) | Wait for bootstrap chain (NVD→KEV→EPSS) or run `seed_screenshot_data.py` |
| NVD 503 / circuit open | Wait; check network; API queue will retry |
| Wrong `DATABASE_URL` | Fix `.env`, restart backend |
| `MAX_CVES_PER_FETCH` too low | Raise only if you understand runtime impact |

## Verify

```bash
curl -s http://127.0.0.1:8000/api/health | jq .
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM cves;"
```

## Related

[ingest-pipeline.md](../concepts/ingest-pipeline.md)
