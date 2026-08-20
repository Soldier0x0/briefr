const RELATED_SOURCE = 'related_cve_heuristic'

function emptyLayer() {
  return { nodes: [], edges: [] }
}

function nodeMap(nodes) {
  return new Map((nodes || []).map((n) => [n.node_id, n]))
}

export function heuristicOnlyNodeIds(graph) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const rootId = graph.root_id
  const byId = new Map()
  for (const node of nodes) {
    byId.set(node.node_id, { heuristic: false, other: false })
  }
  for (const edge of edges) {
    for (const nid of [edge.source_node_id, edge.target_node_id]) {
      const row = byId.get(nid)
      if (!row) continue
      if (edge.source_key === RELATED_SOURCE) row.heuristic = true
      else row.other = true
    }
  }
  const out = new Set()
  for (const [id, row] of byId) {
    if (id === rootId) continue
    if (row.heuristic && !row.other) out.add(id)
  }
  return out
}

export function splitGraphLayers(graph) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const rootId = graph.root_id
  const byId = nodeMap(nodes)

  const coreEdges = edges.filter((e) => e.source_key !== RELATED_SOURCE)
  const relatedEdges = edges.filter((e) => e.source_key === RELATED_SOURCE)
  const semanticEdges = edges.filter((e) => e.edge_class === 'semantic')

  const coreIds = new Set()
  if (rootId) coreIds.add(rootId)
  for (const edge of coreEdges) {
    coreIds.add(edge.source_node_id)
    coreIds.add(edge.target_node_id)
  }

  const heuristicIds = heuristicOnlyNodeIds(graph)
  const relatedIds = new Set(heuristicIds)
  for (const edge of relatedEdges) {
    const a = edge.source_node_id
    const b = edge.target_node_id
    if (heuristicIds.has(a) || heuristicIds.has(b)) {
      if (heuristicIds.has(a)) relatedIds.add(a)
      if (heuristicIds.has(b)) relatedIds.add(b)
    }
  }

  const pick = (ids) => nodes.filter((n) => ids.has(n.node_id))
  const core = { nodes: pick(coreIds), edges: coreEdges }
  const related = {
    nodes: pick(relatedIds),
    edges: relatedEdges.filter(
      (e) => relatedIds.has(e.source_node_id) || relatedIds.has(e.target_node_id),
    ),
  }
  const semantic = {
    nodes: nodes.filter((n) => semanticEdges.some(
      (e) => e.source_node_id === n.node_id || e.target_node_id === n.node_id,
    )),
    edges: semanticEdges,
  }

  return {
    core,
    related,
    semantic,
    counts: {
      relatedCves: related.nodes.length,
      semanticEdges: semantic.edges.length,
      coreNodes: core.nodes.length,
    },
    byId,
  }
}

export function applyGraphLayers(graph, {
  showRelatedCves = false,
  showSemantic = false,
} = {}) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const rootId = graph.root_id
  const hiddenHeuristic = showRelatedCves ? new Set() : heuristicOnlyNodeIds(graph)

  let visibleEdges = edges.filter((e) => {
    if (!showRelatedCves && e.source_key === RELATED_SOURCE) return false
    if (!showSemantic && e.edge_class === 'semantic') return false
    return true
  })

  const ids = new Set()
  if (rootId) ids.add(rootId)
  for (const edge of visibleEdges) {
    ids.add(edge.source_node_id)
    ids.add(edge.target_node_id)
  }
  for (const hid of hiddenHeuristic) ids.delete(hid)
  if (rootId) ids.add(rootId)

  const visibleNodes = nodes.filter((n) => ids.has(n.node_id))
  const visibleIds = new Set(visibleNodes.map((n) => n.node_id))
  visibleEdges = visibleEdges.filter(
    (e) => visibleIds.has(e.source_node_id) && visibleIds.has(e.target_node_id),
  )
  return { nodes: visibleNodes, edges: visibleEdges }
}
