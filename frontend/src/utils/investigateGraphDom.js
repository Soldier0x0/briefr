/** Screen-space hit target radius for a node at the given camera scale. */
export function hitRadius(scale) {
  return Math.min(24, Math.max(8, 12 / scale))
}

/** Whether a node label should be visible at the current camera scale and focus state. */
export function shouldShowLabel(node, { selectedId, hoveredId, findLower, scale, rootId }) {
  if (node.node_id === rootId || node.node_id === selectedId || node.node_id === hoveredId) return true
  if (findLower && (node.label || node.entity_id || '').toLowerCase().includes(findLower)) return true
  if (node.entity_type !== 'cve' && scale >= 1.25) return true
  return scale >= 2
}

/**
 * Imperatively sync node positions and edge endpoints in the SVG DOM.
 * @param {object} [options]
 * @param {boolean} [options.hideWhenEmpty=false] When true, an empty positions array
 *   is an authoritative empty topology and stale nodes/edges are hidden. When false,
 *   an empty array is treated as a transient snapshot and the DOM is left unchanged.
 */
export function applyGraphDom(rootEl, positions, edges, { hideWhenEmpty = false } = {}) {
  if (!rootEl) return
  if (!positions?.length) {
    if (!hideWhenEmpty) return
    for (const g of rootEl.querySelectorAll('[data-node-id]')) {
      g.setAttribute('visibility', 'hidden')
    }
    for (const line of rootEl.querySelectorAll('[data-edge-id]')) {
      line.setAttribute('visibility', 'hidden')
    }
    return
  }
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

/** Update scale-dependent hit radii and label visibility without a React render. */
export function applyNodeScaleDom(rootEl, scale, {
  selectedId = null,
  hoveredId = null,
  findLower = '',
  rootId = null,
} = {}) {
  if (!rootEl || !Number.isFinite(scale)) return
  const hitR = hitRadius(scale)
  const find = String(findLower || '').trim().toLowerCase()
  for (const g of rootEl.querySelectorAll('[data-node-id]')) {
    const nodeId = g.getAttribute('data-node-id')
    const entityType = g.getAttribute('data-entity-type') || 'other'
    const labelText = g.getAttribute('data-label') || nodeId || ''
    const hit = g.querySelector('.investigate-node-hit')
    if (hit) hit.setAttribute('r', String(hitR))
    const labelEl = g.querySelector('.investigate-node-label')
    if (!labelEl) continue
    const show = shouldShowLabel(
      { node_id: nodeId, entity_type: entityType, label: labelText, entity_id: labelText },
      { selectedId, hoveredId, findLower: find, scale, rootId },
    )
    labelEl.setAttribute('visibility', show ? 'visible' : 'hidden')
  }
}

/** Apply the camera world transform to the SVG scene group. */
export function applyWorldTransform(el, view) {
  if (!el || !view) return
  el.setAttribute('transform', `translate(${view.x} ${view.y}) scale(${view.scale})`)
}

export function screenToWorld(view, screenX, screenY) {
  return {
    x: (screenX - view.x) / view.scale,
    y: (screenY - view.y) / view.scale,
  }
}
