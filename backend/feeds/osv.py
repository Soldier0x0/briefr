import logging

import httpx

from resilient_client import CircuitOpenError, resilient_get
from tracking import record_api_call

logger = logging.getLogger(__name__)

# /v1/query does not accept alias lookups (HTTP 400 "Invalid query");
# /v1/vulns/{id} resolves CVE IDs and OSV/GHSA IDs directly.
OSV_VULN_URL = "https://api.osv.dev/v1/vulns"

# CVE records often carry only GIT ranges without package info — the
# ecosystem/package data lives in alias records (e.g. GHSA). Follow at most
# this many aliases to find it.
MAX_ALIAS_FOLLOWS = 3


async def _fetch_osv_record(vuln_id: str) -> dict | None:
    try:
        response = await resilient_get(
            "osv",
            f"{OSV_VULN_URL}/{vuln_id}",
            timeout=30.0,
        )
        data = response.json()
    except CircuitOpenError:
        logger.warning("OSV circuit open — skipping lookup for %s", vuln_id)
        return None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        logger.error("OSV HTTP error %s for %s", exc.response.status_code, vuln_id)
        return None
    except httpx.HTTPError as exc:
        logger.error("OSV request error for %s: %s", vuln_id, exc)
        return None
    except Exception as exc:
        logger.error("OSV unexpected error for %s: %s", vuln_id, exc)
        return None

    await record_api_call("osv", 1)
    if isinstance(data, dict) and data.get("id"):
        return data
    return None


def _parse_osv_record(vuln: dict) -> dict | None:
    osv_id = vuln.get("id", "")
    affected = vuln.get("affected", [])

    ecosystems = {}
    for affected_entry in affected:
        pkg = affected_entry.get("package") or {}
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

    if not ecosystems:
        return None
    return {
        "osv_id": osv_id,
        "ecosystems": list(ecosystems.values()),
        "summary": vuln.get("summary", ""),
        "modified": vuln.get("modified", ""),
    }


async def fetch_osv_by_cve(cve_id: str) -> list[dict]:
    record = await _fetch_osv_record(cve_id.upper())
    if record is None:
        return []

    results: list[dict] = []
    parsed = _parse_osv_record(record)
    if parsed:
        results.append(parsed)
        return results

    for alias in (record.get("aliases") or [])[:MAX_ALIAS_FOLLOWS]:
        alias_record = await _fetch_osv_record(str(alias))
        if not alias_record:
            continue
        parsed = _parse_osv_record(alias_record)
        if parsed:
            results.append(parsed)
            break

    return results
