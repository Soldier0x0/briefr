"""Intel snapshot format versioning (Wave 4 / open-core).

Copyright © 2026 Sai Harsha Vardhan
SPDX-License-Identifier: AGPL-3.0-or-later
"""

from __future__ import annotations

SNAPSHOT_FORMAT_VERSION = 1
SUPPORTED_FORMAT_VERSIONS = frozenset({1})
BUNDLE_KIND = "briefr-intel"


def validate_format_version(manifest: dict) -> None:
    version = manifest.get("format_version")
    if version not in SUPPORTED_FORMAT_VERSIONS:
        raise ValueError(
            f"unsupported snapshot format_version {version!r} "
            f"(supported: {sorted(SUPPORTED_FORMAT_VERSIONS)})"
        )
    kind = manifest.get("bundle_kind")
    if kind and kind != BUNDLE_KIND:
        raise ValueError(f"unexpected bundle_kind {kind!r} (expected {BUNDLE_KIND!r})")
