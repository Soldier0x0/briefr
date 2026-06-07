"""CPE-based asset ↔ CVE version matching."""

from __future__ import annotations

import re
from typing import Any

_VERSION_PART = re.compile(r"(\d+|\D+)")


def _version_tuple(version: str) -> tuple:
    if not version or version in ("*", "-", ""):
        return ()
    parts: list = []
    for chunk in _VERSION_PART.findall(version.strip().lower()):
        if chunk.isdigit():
            parts.append(int(chunk))
        else:
            parts.append(chunk)
    return tuple(parts)


def _compare_versions(left: str, right: str) -> int:
    a, b = _version_tuple(left), _version_tuple(right)
    for i in range(max(len(a), len(b))):
        av = a[i] if i < len(a) else 0
        bv = b[i] if i < len(b) else 0
        if av == bv:
            continue
        if isinstance(av, int) and isinstance(bv, int):
            return -1 if av < bv else 1
        return -1 if str(av) < str(bv) else 1
    return 0


def _is_version_bound(value: str | None) -> bool:
    if not value:
        return False
    return str(value).strip() not in ("", "*", "-")


def version_in_range(
    version: str,
    *,
    start_including: str | None = None,
    start_excluding: str | None = None,
    end_including: str | None = None,
    end_excluding: str | None = None,
) -> bool:
    if not version or not str(version).strip():
        return True
    v = str(version).strip()
    if _is_version_bound(start_including) and _compare_versions(v, start_including) < 0:
        return False
    if _is_version_bound(start_excluding) and _compare_versions(v, start_excluding) <= 0:
        return False
    if _is_version_bound(end_including) and _compare_versions(v, end_including) > 0:
        return False
    if _is_version_bound(end_excluding) and _compare_versions(v, end_excluding) >= 0:
        return False
    return True


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def product_keys_match(asset_product: str, asset_vendor: str | None, cpe_vendor: str, cpe_product: str) -> bool:
    asset_p = _normalize_key(asset_product)
    asset_v = _normalize_key(asset_vendor or "")
    cpe_p = _normalize_key(cpe_product)
    cpe_v = _normalize_key(cpe_vendor)
    if asset_v and asset_v == cpe_v and asset_p == cpe_p:
        return True
    if asset_p and asset_p == cpe_p:
        return True
    if asset_p and (asset_p in cpe_p or cpe_p in asset_p):
        return True
    combined = _normalize_key(f"{asset_vendor or ''}{asset_product}")
    cpe_combined = _normalize_key(f"{cpe_vendor}{cpe_product}")
    return bool(combined and cpe_combined and (combined in cpe_combined or cpe_combined in combined))


def score_asset_against_cpe(
    asset: dict[str, Any],
    cpe_match: dict[str, Any],
) -> int | None:
    vendor = cpe_match.get("vendor") or ""
    product = cpe_match.get("product") or ""
    if not product_keys_match(
        asset.get("product") or "",
        asset.get("vendor"),
        vendor,
        product,
    ):
        return None

    version = (asset.get("version") or "").strip()
    in_range = version_in_range(
        version,
        start_including=cpe_match.get("version_start_including"),
        start_excluding=cpe_match.get("version_start_excluding"),
        end_including=cpe_match.get("version_end_including"),
        end_excluding=cpe_match.get("version_end_excluding"),
    )
    if not version:
        return 55
    if in_range:
        return 100
    return None


def score_cve_for_assets(
    cpe_matches: list[dict[str, Any]],
    assets: list[dict[str, Any]],
) -> int:
    best = 0
    for asset in assets:
        for cpe in cpe_matches:
            score = score_asset_against_cpe(asset, cpe)
            if score is not None and score > best:
                best = score
    return best
