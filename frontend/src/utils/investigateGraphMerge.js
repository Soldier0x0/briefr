/** Merge frozen GraphPage payloads by node_id / edge_id (P1 canvas). */

export const INVESTIGATE_GRAPH_MAX_NODES = 200
export const INVESTIGATE_GRAPH_MAX_EDGES = 300

export function emptyGraphState() {
  return {
    nodes: [],
    edges: [],
    truncated: false,
    capped: false,
    knowledge_state: 'unknown',
    source_status: 'ok',
    root_id: null,
  }
}

function trimGraph(nodesMap, edgesMap, rootId) {
  let capped = false
  let nodes = [...nodesMap.values()]
  let edges = [...edgesMap.values()]

  if (nodes.length > INVESTIGATE_GRAPH_MAX_NODES) {
    capped = true
    const keep = new Set()
    if (rootId) keep.add(rootId)
    for (const node of nodes) {
      if (keep.size >= INVESTIGATE_GRAPH_MAX_NODES) break
      keep.add(node.node_id)
    }
    nodes = nodes.filter((node) => keep.has(node.node_id))
  }

  const nodeIds = new Set(nodes.map((node) => node.node_id))
  edges = edges.filter(
    (edge) => nodeIds.has(edge.source_node_id) && nodeIds.has(edge.target_node_id),
  )

  if (edges.length > INVESTIGATE_GRAPH_MAX_EDGES) {
    capped = true
    edges = edges.slice(0, INVESTIGATE_GRAPH_MAX_EDGES)
  }

  return { nodes, edges, capped }
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

  const rootId = page.root?.node_id || prior.root_id
  const trimmed = trimGraph(nodes, edges, rootId)
  const degraded = page.source_status === 'degraded' || prior.source_status === 'degraded'
  return {
    nodes: trimmed.nodes,
    edges: trimmed.edges,
    truncated: Boolean(prior.truncated || page.truncated || trimmed.capped),
    capped: Boolean(prior.capped || trimmed.capped),
    knowledge_state: page.knowledge_state || prior.knowledge_state,
    source_status: degraded ? 'degraded' : (page.source_status || prior.source_status || 'ok'),
    root_id: rootId,
  }
}

export function investigationEntityPath(entityType, entityId) {
  const type = encodeURIComponent(String(entityType || '').trim())
  const id = encodeURIComponent(String(entityId || ''))
  return `/investigations/entities/${type}/${id}`
}

export function buildInvestigationRelationshipQuery(params = {}) {
  const qs = new URLSearchParams()
  if (params.limit != null) qs.set('limit', String(params.limit))
  if (params.depth != null) qs.set('depth', String(params.depth))
  if (params.cursor) qs.set('cursor', params.cursor)
  return qs.toString() ? `?${qs.toString()}` : ''
}
