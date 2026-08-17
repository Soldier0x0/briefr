"""RSS connector for durable security publications (separate from incident headline cache)."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

from db.publications import replace_publication_entity_links, upsert_publication
from db.timeutil import utcnow_str
from db.types import DbConnection
from feeds.file_identity import sha256_bytes
from feeds.incident_news import (
    _fetch_rss_source_bytes,
    _item_description,
    _item_link,
    _node_text,
    _parse_date,
    _strip_html,
)
from publications.extract import extract_cve_ids
from publications.actors import link_publication_actor, upsert_publication_actor
from publications.registry import PublicationSourceDescriptor

logger = logging.getLogger(__name__)

CONTENT_NS = {"content": "http://purl.org/rss/1.0/modules/content/"}
DC_NS = {"dc": "http://purl.org/dc/elements/1.1/"}


def _item_author(node: ET.Element) -> str:
    for tag, ns in (("author", {}), ("dc:creator", DC_NS), ("creator", {})):
        field = node.find(tag, ns)
        if field is not None and _node_text(field):
            return _strip_html(_node_text(field))
    return ""


def _source_feed_dict(desc: PublicationSourceDescriptor) -> dict[str, str]:
    payload: dict[str, str] = {
        "id": desc.source_key,
        "label": desc.display_name,
        "url": desc.endpoint_url,
    }
    if desc.fallback_url:
        payload["fallback_url"] = desc.fallback_url
    return payload


def parse_publication_rss_items(xml_text: str, desc: PublicationSourceDescriptor) -> list[dict]:
    """Parse RSS/Atom into publication records (no TAG_HINTS or headline filters)."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        preview = (xml_text or "").lstrip()[:80].replace("\n", " ")
        raise ValueError(
            f"Publication RSS parse failed for {desc.source_key}: "
            f"{exc} (response starts with: {preview!r})"
        ) from exc

    nodes = root.findall(".//item") or root.findall(".//entry")
    items: list[dict] = []

    for node in nodes:
        title = _strip_html(_node_text(node.find("title")))
        url = _item_link(node)
        if not title or not url:
            continue
        description = _item_description(node) or title
        pub_raw = None
        for tag in ("pubDate", "published", "updated", "dc:date"):
            field = node.find(tag)
            if field is not None and _node_text(field):
                pub_raw = _node_text(field)
                break
        published_at = _parse_date(pub_raw)
        updated_node = node.find("updated")
        updated_at = _parse_date(_node_text(updated_node) if updated_node is not None else pub_raw)

        items.append(
            {
                "canonical_url": url.strip(),
                "title": title,
                "body": description,
                "published_at": published_at,
                "updated_at": updated_at,
                "document_kind": desc.document_kind_default,
                "author": _item_author(node),
            }
        )
    return items


async def sync_publication_rss_source(db: DbConnection, desc: PublicationSourceDescriptor) -> dict:
    """Fetch RSS, upsert publications, and refresh deterministic entity links."""
    source = _source_feed_dict(desc)
    raw = await _fetch_rss_source_bytes(source)
    retrieved_at = utcnow_str()
    xml_text = raw.decode("utf-8", errors="replace")

    items = parse_publication_rss_items(xml_text, desc)
    inserted = 0
    updated = 0
    links_written = 0

    for item in items:
        item_bytes = f"{item['canonical_url']}\n{item['title']}\n{item['body']}".encode(
            "utf-8"
        )
        item_sha = sha256_bytes(item_bytes)
        pub_id, is_new = await upsert_publication(
            db,
            source_key=desc.source_key,
            canonical_url=item["canonical_url"],
            content_sha256=item_sha,
            title=item["title"],
            document_kind=item["document_kind"],
            published_at=item["published_at"],
            updated_at=item["updated_at"],
            retrieved_at=retrieved_at,
            extraction_status="complete",
        )
        if is_new:
            inserted += 1
        else:
            updated += 1
        links_written += await replace_publication_entity_links(
            db,
            pub_id,
            title=item["title"],
            body=item["body"],
            retrieved_at=retrieved_at,
        )
        author = (item.get("author") or "").strip()
        if author:
            actor_id = await upsert_publication_actor(
                db,
                source_key=desc.source_key,
                display_name=author,
            )
            if actor_id:
                await link_publication_actor(
                    db, pub_id, actor_id, observed_at=retrieved_at
                )

    logger.info(
        "Publication RSS sync %s: %d items (%d new, %d updated), %d links",
        desc.source_key,
        len(items),
        inserted,
        updated,
        links_written,
    )
    return {
        "source_key": desc.source_key,
        "items": len(items),
        "inserted": inserted,
        "updated": updated,
        "links_written": links_written,
        "cve_ids_sample": extract_cve_ids(*(i["title"] for i in items[:3])),
    }
