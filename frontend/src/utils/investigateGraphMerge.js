/** Merge frozen GraphPage payloads by node_id / edge_id (P1 canvas). */

export function emptyGraphState() {
  return {
    nodes: [],
    edges: [],
    truncated: false,
    knowledge_state: 'unknown',
    source_status: 'ok',
    root_id: null,
  }
}

export function mergeGraphPage(existing, page) {
  const prior = existing || emptyGraphState()
  if (!page) return prior

  const nodes = new Map(prior.nodes.map((node) => [node.node_id, node]))
  const edges = new Map(prior.edges.map((edge) => [edge.edge_id, edge]))

  if (page.root?.node_id) {
    nodes.set(page.root.node_id, page.root)
  }
  for (const node of page.nodes || []) {
    if (node?.node_id) nodes.set(node.node_id, node)
  }
  for (const edge of page.edges || []) {
    if (edge?.edge_id) edges.set(edge.edge_id, edge)
  }

  const degraded = page.source_status === 'degraded' || prior.source_status === 'degraded'
  return {
    nodes: [...nodes.values()],
    edges: [...edges.values()],
    truncated: Boolean(prior.truncated || page.truncated),
    knowledge_state: page.knowledge_state || prior.knowledge_state,
    source_status: degraded ? 'degraded' : (page.source_status || prior.source_status || 'ok'),
    root_id: page.root?.node_id || prior.root_id,
  }
}

export function investigationEntityPath(entityType, entityId) {
  const type = encodeURIComponent(String(entityType || '').trim())
  const id = encodeURI(String(entityId || '')).replace(/\?/g, '%3F').replace(/#/g, '%23')
  return `/investigations/entities/${type}/${id}`
}
