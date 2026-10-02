/** Viewport culling helpers for INVESTIGATE graph draw/sim paths. */

const DEFAULT_MARGIN = 100

export function visibleInViewport(node, view, viewport, margin = DEFAULT_MARGIN) {
  if (!node || !view || !viewport) return true
  const scale = view.scale || 1
  const screenX = (node.x + view.x) * scale
  const screenY = (node.y + view.y) * scale
  const left = -margin
  const top = -margin
  const right = viewport.width + margin
  const bottom = viewport.height + margin
  return screenX >= left && screenX <= right && screenY >= top && screenY <= bottom
}

export function cullNodesForViewport(nodes, view, viewport, margin = DEFAULT_MARGIN) {
  if (!nodes?.length) return []
  return nodes.filter((node) => visibleInViewport(node, view, viewport, margin))
}

export function cullEdgesForNodes(edges, visibleNodeIds) {
  if (!edges?.length || !visibleNodeIds?.size) return []
  return edges.filter(
    (edge) => visibleNodeIds.has(edge.source_node_id) && visibleNodeIds.has(edge.target_node_id),
  )
}
