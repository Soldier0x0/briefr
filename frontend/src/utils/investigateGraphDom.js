export function applyGraphDom(rootEl, positions, edges) {
  if (!rootEl || !positions?.length) return
  const byId = new Map((positions || []).map((n) => [n.node_id, n]))
  for (const g of rootEl.querySelectorAll('[data-node-id]')) {
    const node = byId.get(g.getAttribute('data-node-id'))
    if (!node) {
      g.setAttribute('visibility', 'hidden')
      continue
    }
    g.removeAttribute('visibility')
    g.setAttribute('transform', `translate(${node.x} ${node.y})`)
  }
  for (const line of rootEl.querySelectorAll('[data-edge-id]')) {
    const edgeId = line.getAttribute('data-edge-id')
    const edge = (edges || []).find((item) => item.edge_id === edgeId)
    if (!edge) {
      line.setAttribute('visibility', 'hidden')
      continue
    }
    const source = byId.get(edge.source_node_id)
    const target = byId.get(edge.target_node_id)
    if (!source || !target) {
      line.setAttribute('visibility', 'hidden')
      continue
    }
    line.removeAttribute('visibility')
    line.setAttribute('x1', String(source.x))
    line.setAttribute('y1', String(source.y))
    line.setAttribute('x2', String(target.x))
    line.setAttribute('y2', String(target.y))
  }
}

export function applyWorldTransform(el, view) {
  if (!el || !view) return
  console.log('[DEBUG] applyWorldTransform:', view)
  el.setAttribute('transform', `translate(${view.x} ${view.y}) scale(${view.scale})`)
}

export function screenToWorld(view, screenX, screenY) {
  return {
    x: (screenX - view.x) / view.scale,
    y: (screenY - view.y) / view.scale,
  }
}
