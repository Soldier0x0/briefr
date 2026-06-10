import logging

import httpx

from resilient_client import CircuitOpenError, resilient_request
from tracking import record_api_call

logger = logging.getLogger(__name__)

OSV_QUERY_URL = "https://api.osv.dev/v1/query"


async def fetch_osv_by_cve(cve_id: str) -> list[dict]:
    payload = {"aliases": [cve_id]}

    try:
        response = await resilient_request(
            "osv",
            "POST",
            OSV_QUERY_URL,
            json=payload,
            timeout=30.0,
        )
        data = response.json()
    except CircuitOpenError:
        logger.warning("OSV circuit open — skipping lookup for %s", cve_id)
        return []
    except httpx.HTTPStatusError as exc:
        logger.error("OSV HTTP error %s for %s", exc.response.status_code, cve_id)
        return []
    except httpx.HTTPError as exc:
        logger.error("OSV request error for %s: %s", cve_id, exc)
        return []
    except Exception as exc:
        logger.error("OSV unexpected error for %s: %s", cve_id, exc)
        return []

    await record_api_call("osv", 1)

    vulns = data.get("vulns", [])
    results = []

    for vuln in vulns:
        osv_id = vuln.get("id", "")
        affected = vuln.get("affected", [])

        ecosystems = {}
        for affected_entry in affected:
            pkg = affected_entry.get("package", {})
            ecosystem = pkg.get("ecosystem", "")
            name = pkg.get("name", "")

            versions = []
            for version_range in affected_entry.get("ranges", []):
                for event in version_range.get("events", []):
                    introduced = event.get("introduced")
                    fixed = event.get("fixed")
                    if introduced:
                        versions.append({"introduced": introduced})
                    if fixed:
                        versions.append({"fixed": fixed})

            if ecosystem:
                if ecosystem not in ecosystems:
                    ecosystems[ecosystem] = {"ecosystem": ecosystem, "packages": []}
                ecosystems[ecosystem]["packages"].append(
                    {
                        "name": name,
                        "versions": versions,
                    }
                )

        if ecosystems:
            results.append(
                {
                    "osv_id": osv_id,
                    "ecosystems": list(ecosystems.values()),
                    "summary": vuln.get("summary", ""),
                    "modified": vuln.get("modified", ""),
                }
            )

    return results
