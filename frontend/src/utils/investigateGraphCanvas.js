/** Canvas edge layer for INVESTIGATE (optional; gated by investigateGraphGate). */

const EDGE_COLORS = {
  direct_fact: 'rgba(230, 230, 230, 0.85)',
  reported: 'rgba(232, 85, 51, 0.85)',
  derived: 'rgba(160, 160, 160, 0.75)',
  analyst_assertion: 'rgba(230, 180, 80, 0.85)',
  semantic: 'rgba(120, 120, 120, 0.65)',
}

export function createInvestigateGraphCanvas(canvasEl) {
  const ctx = canvasEl?.getContext?.('2d') || null

  function resize(width, height) {
    if (!canvasEl || !ctx) return
    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1
    canvasEl.width = Math.max(1, Math.floor(width * dpr))
    canvasEl.height = Math.max(1, Math.floor(height * dpr))
    canvasEl.style.width = `${width}px`
    canvasEl.style.height = `${height}px`
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  function clear() {
    if (!ctx || !canvasEl) return
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height)
  }

  function drawEdges(edges, positionsById, view) {
    if (!ctx || !edges?.length) return
    const scale = view?.scale || 1
    const tx = view?.x || 0
    const ty = view?.y || 0
    ctx.save()
    ctx.lineWidth = 1.25
    for (const edge of edges) {
      const source = positionsById.get(edge.source_node_id)
      const target = positionsById.get(edge.target_node_id)
      if (!source || !target) continue
      const x1 = (source.x + tx) * scale
      const y1 = (source.y + ty) * scale
      const x2 = (target.x + tx) * scale
      const y2 = (target.y + ty) * scale
      ctx.strokeStyle = EDGE_COLORS[edge.edge_class] || EDGE_COLORS.derived
      if (edge.edge_class === 'semantic') {
        ctx.setLineDash([4, 3])
      } else {
        ctx.setLineDash([])
      }
      ctx.beginPath()
      ctx.moveTo(x1, y1)
      ctx.lineTo(x2, y2)
      ctx.stroke()
    }
    ctx.restore()
  }

  return { resize, clear, drawEdges }
}
