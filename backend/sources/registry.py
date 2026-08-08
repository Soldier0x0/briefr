"""Catalog source registry — data-driven descriptors for the TI corroboration layer.

The corroboration and sync paths iterate CATALOG_SOURCES instead of branching
per source. Add a new mirror source by appending a frozen descriptor here.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Callable, Mapping

from correlation.ioc_normalize import normalize_ioc_type
from feeds.threatfox import fetch_threatfox_iocs
from feeds.urlhaus import fetch_urlhaus_iocs

FetchFn = Callable[..., Any]


@dataclass(frozen=True)
class SourceDescriptor:
    """Immutable descriptor for one bulk catalog mirror source."""

    source_key: str
    key_env: str
    pacing_key: str
    receipt_prefix: str
    mirror_type_map: Mapping[str, str]
    retention_hours: int
    enabled_env: str | None = None
    sync_interval_hours_env: str | None = None
    sync_window_days_env: str | None = None
    fetch: FetchFn | None = None

    def canonical_type(self, ioc_type: str) -> str | None:
        """OTX-style canonical type (uppercase) -> mirror's stored ioc_type."""
        return self.mirror_type_map.get(normalize_ioc_type(ioc_type))


CATALOG_SOURCES: tuple[SourceDescriptor, ...] = (
    SourceDescriptor(
        source_key="threatfox",
        enabled_env="THREATFOX_SYNC_ENABLED",
        key_env="ABUSECH_AUTH_KEY",
        pacing_key="threatfox",
        sync_interval_hours_env="THREATFOX_SYNC_INTERVAL_HOURS",
        sync_window_days_env="THREATFOX_SYNC_DAYS",
        fetch=fetch_threatfox_iocs,
        mirror_type_map=MappingProxyType(
            {
                "IP": "ip",
                "DOMAIN": "domain",
                "HASH": "hash",
                "URL": "domain",
            }
        ),
        receipt_prefix="threatfox",
        retention_hours=24 * 7,
    ),
    SourceDescriptor(
        source_key="urlhaus",
        enabled_env="URLHAUS_SYNC_ENABLED",
        key_env="ABUSECH_AUTH_KEY",
        pacing_key="urlhaus",
        sync_interval_hours_env="URLHAUS_SYNC_INTERVAL_HOURS",
        sync_window_days_env="URLHAUS_SYNC_DAYS",
        fetch=fetch_urlhaus_iocs,
        mirror_type_map=MappingProxyType(
            {
                "URL": "url",
                "DOMAIN": "url",
            }
        ),
        receipt_prefix="urlhaus",
        retention_hours=24 * 7,
    ),
)

SOURCES_BY_KEY: Mapping[str, SourceDescriptor] = MappingProxyType(
    {s.source_key: s for s in CATALOG_SOURCES}
)
