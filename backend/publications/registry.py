"""Publication source registry — configured connectors for durable advisories."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True)
class PublicationSourceDescriptor:
    source_key: str
    display_name: str
    source_kind: str
    connector: str
    endpoint_url: str
    pacing_key: str
    document_kind_default: str
    enabled_env: str | None = None
    sync_interval_hours_env: str | None = None
    fallback_url: str | None = None


PUBLICATION_SOURCES: tuple[PublicationSourceDescriptor, ...] = (
    PublicationSourceDescriptor(
        source_key="cisa-news",
        display_name="CISA Advisories",
        source_kind="cert",
        connector="rss",
        endpoint_url="https://www.cisa.gov/cybersecurity-advisories/all.xml",
        pacing_key="rss",
        document_kind_default="advisory",
        enabled_env="PUBLICATION_SYNC_ENABLED",
        sync_interval_hours_env="PUBLICATION_SYNC_INTERVAL_HOURS",
    ),
)

SOURCES_BY_KEY: Mapping[str, PublicationSourceDescriptor] = MappingProxyType(
    {s.source_key: s for s in PUBLICATION_SOURCES}
)
