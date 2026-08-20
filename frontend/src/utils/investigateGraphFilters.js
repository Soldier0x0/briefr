export const EXPANDABLE_ENTITY_TYPES = new Set([
  'cve', 'ioc', 'technique', 'campaign', 'publication',
])
export const IOC_KINDS = new Set(['ip', 'hash', 'domain', 'url'])
export const EDGE_CLASS_CHIPS = [
  'direct_fact', 'reported', 'derived', 'analyst_assertion', 'semantic',
]
export const DEFAULT_EDGE_CLASSES = new Set([
  'direct_fact', 'reported', 'derived', 'analyst_assertion',
])

export function canExpandEntityType(entityType) {
  return EXPANDABLE_ENTITY_TYPES.has(entityType)
}

export function parseIocEntityId(entityId, label) {
  const raw = String(entityId || '')
  const idx = raw.indexOf(':')
  if (idx <= 0) return { type: 'ip', value: label || raw }
  const type = raw.slice(0, idx).toLowerCase()
  const value = raw.slice(idx + 1) || label || ''
  return { type: IOC_KINDS.has(type) ? type : 'ip', value }
}

export function relatedCveCount(graph) {
  return (graph.edges || []).filter((e) => e.source_key === 'related_cve_heuristic').length
}

export function incidentEdges(graph, nodeId) {
  if (!nodeId) return []
  return (graph.edges || []).filter(
    (e) => e.source_node_id === nodeId || e.target_node_id === nodeId,
  )
}

export function otherNodeId(edge, nodeId) {
  return edge.source_node_id === nodeId ? edge.target_node_id : edge.source_node_id
}

export function neighborIds(graph, nodeId) {
  const ids = new Set()
  for (const e of incidentEdges(graph, nodeId)) {
    ids.add(otherNodeId(e, nodeId))
  }
  return ids
}

export function heuristicCveIds(graph) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const byCve = new Map()
  for (const node of nodes) {
    if (node.entity_type === 'cve') byCve.set(node.node_id, { heuristic: false, other: false })
  }
  for (const edge of edges) {
    for (const nid of [edge.source_node_id, edge.target_node_id]) {
      const row = byCve.get(nid)
      if (!row) continue
      if (edge.source_key === 'related_cve_heuristic') row.heuristic = true
      else row.other = true
    }
  }
  const out = new Set()
  for (const [id, row] of byCve) {
    if (row.heuristic && !row.other && id !== graph.root_id) out.add(id)
  }
  return out
}

export function visibleGraph(graph, {
  showRelatedCves = true,
  entityType = 'all',
  edgeClasses = null,
  isolateNodeId = null,
} = {}) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const rootId = graph.root_id
  const hiddenHeuristic = showRelatedCves ? new Set() : heuristicCveIds(graph)
  const allowedClass = edgeClasses || null

  let visibleEdges = edges.filter((e) => {
    if (allowedClass && !allowedClass.has(e.edge_class)) return false
    if (!showRelatedCves && e.source_key === 'related_cve_heuristic') return false
    return true
  })

  let ids = new Set()
  if (rootId) ids.add(rootId)
  for (const edge of visibleEdges) {
    ids.add(edge.source_node_id)
    ids.add(edge.target_node_id)
  }
  for (const hid of hiddenHeuristic) ids.delete(hid)
  if (rootId) ids.add(rootId)

  if (isolateNodeId) {
    const keep = new Set([isolateNodeId])
    for (const edge of visibleEdges) {
      if (edge.source_node_id === isolateNodeId) keep.add(edge.target_node_id)
      if (edge.target_node_id === isolateNodeId) keep.add(edge.source_node_id)
    }
    ids = keep
  }

  let visibleNodes = nodes.filter((n) => ids.has(n.node_id))
  if (entityType && entityType !== 'all') {
    visibleNodes = visibleNodes.filter(
      (n) => n.node_id === rootId || n.entity_type === entityType,
    )
  }
  const visibleIds = new Set(visibleNodes.map((n) => n.node_id))
  visibleEdges = visibleEdges.filter(
    (e) => visibleIds.has(e.source_node_id) && visibleIds.has(e.target_node_id),
  )
  return { nodes: visibleNodes, edges: visibleEdges }
}

export function formatNeighborhoodMarkdown(node, edges, nodesById) {
  if (!node) return ''
  const lines = [
    `# ${node.entity_type} ${node.entity_id}`,
    `knowledge: ${node.knowledge_state || 'known'}`,
    '',
    '## Incident edges',
  ]
  for (const edge of edges || []) {
    const other = nodesById.get(otherNodeId(edge, node.node_id))
    const otherLabel = other
      ? `${other.entity_type} ${other.entity_id}`
      : otherNodeId(edge, node.node_id)
    lines.push(
      `- ${edge.edge_class} via ${edge.source_key} → ${otherLabel}`
      + (edge.confidence ? ` confidence=${edge.confidence}` : '')
      + (edge.observed_at ? ` observed=${edge.observed_at}` : '')
      + (edge.fetched_at ? ` fetched=${edge.fetched_at}` : ''),
    )
  }
  return lines.join('\n')
}
