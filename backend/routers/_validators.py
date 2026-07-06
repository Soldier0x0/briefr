from fastapi import HTTPException


def require_cve_id(cve_id: str) -> str:
    """Normalize and validate CVE ID, raise 400 if invalid."""
    cve_id = cve_id.strip().upper()
    if not cve_id.startswith("CVE-"):
        raise HTTPException(status_code=400, detail="Invalid CVE ID format")
    return cve_id
