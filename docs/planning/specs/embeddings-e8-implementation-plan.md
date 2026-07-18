# Embeddings E8 — Campaign entity embeddings

**Design:** multi-entity growth after techniques (retrieval only, no RAG).  
**Depends on:** E6 technique pattern (`entity_type` on `embeddings`).

## Acceptance

- [x] `ENTITY_TYPE_CAMPAIGN = "campaign"` + `build_campaign_embed_text`
- [x] Pending/upsert for non-retracted `correlation_campaigns` (preserve `camp_*` case)
- [x] Scheduler `run_campaign_embeddings_backfill` after techniques
- [x] Hybrid search keyword + ANN typed campaign hits (`meta.includes_campaigns`)
- [x] Tests + docs

## Embed text

`label` + `adversary` + joined `malware_families` + `tags` (cap 2000). Skip empty /
retracted rows.
